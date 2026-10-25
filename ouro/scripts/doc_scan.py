"""Phase 1 doc scan: shortlist Markdown doc statements that may no longer match the code.

Read-only by default. Stdlib only. Never calls an LLM. The only write is the opt-in `--wiki` flag,
which merges the shortlist into ouro/wiki/maps/doc-drift.md in the scanned project (see drift_page.py).

For every tracked Markdown doc (outside ouro/wiki/ and vendored dirs) it extracts code references:
backticked paths (`src/audio/`, `poiAccess.ts`), backticked symbols (`AudioWiring`, `relocate_pickups()`)
and relative links to files. Then, per doc section, it reports:
- Broken references: a link or repo-rooted path that matches nothing tracked, or a symbol `git grep -w`
  can't find in code.
- Moved code: a referenced file changed in commits after the paragraph citing it was last edited.
- Provisional wording (ranking signal only): "stopgap", "for now", "nothing imports"... in a paragraph
  whose references broke or moved.

Usage:
    python <path-to-skill>/scripts/doc_scan.py [repo_path] [--json] [--limit N] [--wiki] [--include-skill]

See wiki/entities/doc_scan.md and ADR-013.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import drift_page

SKIP_DIRS = {'dist', 'node_modules', 'vendor', '.venv', 'venv', 'build', '__pycache__'}
WIKI_PREFIX = 'ouro/wiki/'  # generated pages: their references are the scanners' own output
DOC_EXTS = {'.md', '.markdown'}

FENCE_RE = re.compile(r'^\s*(```|~~~)')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
CODE_SPAN_RE = re.compile(r'`([^`\n]+)`')
LINK_RE = re.compile(r'\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
SYMBOL_RE = re.compile(r'^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*(?:\([^()]*\))?$')
CALL_ARGS_RE = re.compile(r'\([^()]*\)$')
LOCATION_SUFFIX_RE = re.compile(r'(:\d+(-\d+)?|#L\d+(-L?\d+)?)$')
NOT_A_PATH = set('<>{}*$ ~=,;|')
# Provisional or absolute claims that go stale when the code moves on. Only ranks candidates that
# already have a broken or moved reference; on its own it is not evidence of drift.
WORDING_RE = re.compile(
    r'\b(stopgap|workaround|temporary|temporarily|for now|for the time being|not yet|no longer|deprecated|'
    r'nothing (\w+ )?(imports|uses|calls)|(is|are) (unused|not used)|proper fix|will (be|add|move|replace)|'
    r'(another|a later|a future|follow-up) (change|pr))\b', re.I)
LIST_ITEM_RE = re.compile(r'^\s*([-*+|]|\d+[.)])\s')
MAX_MATCHES = 3  # a reference matching more files than this is too ambiguous to date or call broken
MAX_COMMITS_SCORED = 10
MAX_FILES_SCORED = 5
BROKEN_PATH_WEIGHT = 5
BROKEN_SYMBOL_WEIGHT = 2  # docs also name other tools' APIs, so a missing symbol is weaker evidence
HISTORICAL_DIRS = {'decisions', 'adr', 'adrs'}
WORDING_WEIGHT = 4  # tuned on dabao-dasher: both known drifts carry provisional wording
MAX_WORDING_SCORED = 2


def git(repo, *args):
    """Run a git command in repo and return stdout, or None on failure."""
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


class Repo:
    """Tracked files plus cached git lookups for one repository."""

    def __init__(self, root, include_skill=False):
        self.root = root
        self.files = [f for f in (git(root, 'ls-files') or '').splitlines() if not SKIP_DIRS.intersection(Path(f).parts)]
        self.file_set = set(self.files)
        self.dirs = {str(p) for f in self.files for p in Path(f).parents if str(p) != '.'}
        self.top_level = {Path(f).parts[0] for f in self.files}
        self.suffixes = {Path(f).suffix for f in self.files if Path(f).suffix}
        skill_dir = Path(__file__).resolve().parent.parent
        self.skill_rel = None if include_skill or not skill_dir.is_relative_to(root) else str(skill_dir.relative_to(root))
        self._log, self._grep = {}, {}

    def docs(self):
        """Tracked Markdown docs, minus symlinked aliases (CLAUDE.md -> AGENTS.md), generated wiki pages and
        (by default) this skill's own docs."""
        return [f for f in self.files if Path(f).suffix.lower() in DOC_EXTS and not f.startswith(WIKI_PREFIX)
                and not (self.root / f).is_symlink()
                and not (self.skill_rel and (f + '/').startswith(self.skill_rel + '/'))]

    def is_dated(self, rel):
        """True for a non-doc file. A cited directory is only checked for existence: in an active repo
        something inside it changes after almost every doc edit, so its history says little about the doc."""
        return rel in self.file_set and Path(rel).suffix.lower() not in DOC_EXTS

    def commits(self, rel):
        """[(sha, committer time)] newest first for commits touching a tracked file."""
        if rel not in self._log:
            out = git(self.root, 'log', '--no-merges', '--format=%H %ct', '--', rel) or ''
            self._log[rel] = [(sha, int(ts)) for sha, ts in (row.split() for row in out.splitlines())]
        return self._log[rel]

    def grep(self, term):
        """Tracked non-doc files containing term as a whole word."""
        if term not in self._grep:
            out = git(self.root, 'grep', '-lwF', '-e', term, '--', '.', ':(exclude)*.md', f':(exclude){WIKI_PREFIX}')
            self._grep[term] = [f for f in (out or '').splitlines() if f in self.file_set]
        return self._grep[term]

    def resolve_path(self, ref, doc):
        """Tracked files or dirs ref names: relative to the doc, the root, or as a unique path suffix."""
        ref = ref.rstrip('/')
        for base in (Path(doc).parent, Path('.')):
            try:
                candidate = (self.root / base / ref).resolve().relative_to(self.root.resolve()).as_posix()
            except ValueError:  # points outside the repo
                continue
            if candidate in self.file_set or candidate in self.dirs:
                return [candidate]
        return [f for f in sorted(self.file_set | self.dirs) if f.endswith('/' + ref)]

    def is_ignored(self, ref):
        """True when .gitignore covers ref as a file or, for a pattern like `public/tiles/`, as a directory."""
        ref = ref.rstrip('/')
        return any(subprocess.run(['git', '-C', str(self.root), 'check-ignore', '-q', path]).returncode == 0
                   for path in (ref, ref + '/'))


def blame_times(repo, rel):
    """Map 1-indexed line -> (sha, committer time). Uncommitted lines get the current time."""
    out = git(repo, 'blame', '--line-porcelain', '-w', '--', rel)
    if out is None:
        return {}
    info, line_no, sha, now = {}, None, None, int(time.time())
    for row in out.splitlines():
        parts = row.split()
        if len(parts) >= 3 and len(parts[0]) == 40 and parts[1].isdigit() and parts[2].isdigit():
            line_no, sha = int(parts[2]), parts[0]
            info[line_no] = (sha, now if set(sha) == {'0'} else None)
        elif row.startswith('committer-time ') and line_no is not None and info[line_no][1] is None:
            info[line_no] = (sha, int(row.split()[1]))
    return info


def slugify(heading, seen):
    """GitHub-style anchor, de-duplicated within one doc."""
    slug = re.sub(r'[^\w\s-]', '', heading.lower()).strip().replace(' ', '-')
    count = seen.get(slug, 0)
    seen[slug] = count + 1
    return f'{slug}-{count}' if count else slug


def sections(lines):
    """[(heading line, heading, slug, [paragraph line lists])], skipping fenced code; text before any heading is '(top)'.

    A paragraph is the unit a doc statement is dated by: a block of prose, or one list item or table row.
    """
    result, seen, in_fence = [[1, '(top)', 'top', [[]]]], {}, False
    for i, line in enumerate(lines, start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        heading = None if in_fence else HEADING_RE.match(line)
        if heading:
            result.append([i, heading.group(2), slugify(heading.group(2), seen), [[]]])
        elif in_fence or not line.strip():
            if result[-1][3][-1]:
                result[-1][3].append([])
        else:
            if LIST_ITEM_RE.match(line) and result[-1][3][-1]:
                result[-1][3].append([])  # each list item or table row is dated on its own
            result[-1][3][-1].append(i)
    return [(s[0], s[1], s[2], [p for p in s[3] if p]) for s in result if any(s[3])]


def references(line):
    """(kind, text) for each code reference on a Markdown line: 'path', 'symbol' or 'link'."""
    refs = []
    for span in CODE_SPAN_RE.findall(line):
        span = LOCATION_SUFFIX_RE.sub('', span.strip())
        if not span or NOT_A_PATH.intersection(span) or '://' in span:
            continue
        refs.append(('path' if '/' in span or ('.' in span and not SYMBOL_RE.match(span)) else 'symbol', span.removeprefix('./')))
    for target in LINK_RE.findall(line):
        target = target.split('#', 1)[0]
        if target and ':' not in target and not target.startswith('/'):
            refs.append(('link', target.removeprefix('./')))
    return refs


def code_like(name):
    """True for identifiers that look like code rather than English: snake_case, camelCase, PascalCase with 2+ capitals."""
    return len(name) >= 4 and ('_' in name.strip('_') or bool(re.search(r'[a-z][A-Z]', name)) or
                               sum(c.isupper() for c in name) >= 2 and any(c.islower() for c in name))


def check_ref(repo, kind, ref, doc):
    """(status, files): status is 'ok', 'broken' or None (not a checkable code reference)."""
    if kind == 'symbol' and Path(ref).suffix in repo.suffixes:
        kind = 'path'  # a bare file name such as `poiAccess.ts` also parses as a dotted symbol
    if kind == 'symbol':
        names = [part for part in CALL_ARGS_RE.sub('', ref).split('.') if code_like(part)]
        if not names:
            return None, []
        hits = repo.grep(names[-1])
        return ('ok', hits if len(hits) <= MAX_MATCHES else []) if hits else ('broken', [])
    matches = repo.resolve_path(ref, doc)
    if matches:
        return 'ok', matches if len(matches) <= MAX_MATCHES else []
    # A bare name (`credentials.json`) is usually a generic example, and a path outside the top-level
    # dirs (`feat/doc-scan`, `text/html`) usually isn't a path; only a link or a rooted path can break.
    rooted = '/' in ref and Path(ref).parts[0] in repo.top_level
    if kind == 'path' and not rooted or ref.startswith(WIKI_PREFIX) or repo.is_ignored(ref):
        return None, []
    return 'broken', []


def scan_doc(repo, doc):
    """Drift candidates (one per section) for one doc."""
    try:
        lines = (repo.root / doc).read_text(encoding='utf-8').splitlines()
    except (UnicodeDecodeError, OSError):
        return []
    blame = None
    candidates = []
    for heading_line, heading, slug, paragraphs in sections(lines):
        checks = {(kind, ref): check_ref(repo, kind, ref, doc)
                  for n in (n for para in paragraphs for n in para) for kind, ref in references(lines[n - 1])}
        cited = {f for (kind, _), (_, files) in checks.items() if kind != 'symbol' for f in files}
        broken, moved, wording, claim, newest, edited = [], {}, set(), None, None, 0
        for para in paragraphs:
            refs = [(kind, ref, n) for n in para for kind, ref in references(lines[n - 1])]
            if not refs:
                continue
            blame = blame if blame is not None else blame_times(repo.root, doc)
            para_time = max((blame.get(n, (None, 0))[1] for n in para), default=0)
            edited = max(edited, para_time)
            hit = False
            for kind, ref, n in refs:
                status, files = checks[(kind, ref)]
                if kind == 'symbol' and cited.intersection(files):
                    files = [f for f in files if f in cited]  # the symbol's home is the file the section names
                if status == 'broken' and (kind, ref) not in broken:
                    broken.append((kind, ref))
                    hit = True
                for rel in (f for f in files if repo.is_dated(f)):
                    history = repo.commits(rel)
                    if history and (newest is None or history[0][1] > newest[1]):
                        newest = history[0]
                    later = {sha for sha, ts in history if ts > para_time}
                    if later:
                        entry = moved.setdefault(rel, {'refs': [], 'shas': set()})
                        entry['shas'] |= later
                        entry['refs'] += [] if ref in entry['refs'] else [ref]
                        hit = True
                if hit and claim is None:
                    claim = n
            if hit:
                matches = {m.group(0).lower() for n in para for m in WORDING_RE.finditer(lines[n - 1])}
                if matches and not wording:  # the first provisional sentence is the likeliest outdated claim
                    claim = next((n for n in para if WORDING_RE.search(lines[n - 1])), claim)
                wording |= matches
        if not broken and not moved:
            continue
        commits = set().union(*(m['shas'] for m in moved.values()))
        # The most-changed file carries the score; breadth adds a little, so long tables don't dominate.
        moved_score = (min(max((len(m['shas']) for m in moved.values()), default=0), MAX_COMMITS_SCORED) +
                       min(len(moved), MAX_FILES_SCORED))
        if HISTORICAL_DIRS.intersection(Path(doc).parts[:-1]):
            moved_score //= 2  # an ADR records the code as it was when the decision was made
        broken_score = sum(BROKEN_SYMBOL_WEIGHT if kind == 'symbol' else BROKEN_PATH_WEIGHT for kind, _ in broken)
        score = broken_score + moved_score + WORDING_WEIGHT * min(len(wording), MAX_WORDING_SCORED)
        candidates.append({
            'doc': doc,
            'line': heading_line,
            'heading': heading,
            'key': f'{doc}#{slug}',
            'edited': date.fromtimestamp(edited).isoformat() if edited else None,
            'claim_line': claim,
            'claim': lines[claim - 1].strip()[:160] if claim else None,
            'broken': [ref for _, ref in broken],
            'moved': [{'file': rel, 'refs': m['refs'], 'commits': len(m['shas'])} for rel, m in
                      sorted(moved.items(), key=lambda item: -len(item[1]['shas']))],
            'commits_since': len(commits),
            'wording': sorted(wording),
            'state': newest[0][:7] if newest else '-',
            'score': score,
        })
    return candidates


def summarize(candidates, docs_scanned):
    return {
        'docs_scanned': docs_scanned,
        'candidates': len(candidates),
        'with_broken_refs': sum(bool(c['broken']) for c in candidates),
        'with_moved_code': sum(bool(c['moved']) for c in candidates),
    }


def signal_lines(c):
    """Human-readable evidence lines for one candidate, shared by the text report and the wiki page."""
    lines = []
    if c['claim']:
        lines.append(f"Claim ({c['doc']}:{c['claim_line']}): {c['claim']}")
    if c['broken']:
        lines.append('Broken references: ' + ', '.join(f'`{ref}`' for ref in c['broken']))
    if c['moved']:
        moved = ', '.join(f"{m['file']} ({m['commits']}, cited as {'/'.join(f'`{r}`' for r in m['refs'][:3])})"
                          for m in c['moved'][:5])
        more = f" and {len(c['moved']) - 5} more" if len(c['moved']) > 5 else ''
        lines.append(f"Code changed since the section was edited ({c['edited']}): {moved}{more}")
    if c['wording']:
        lines.append('Provisional wording: ' + ', '.join(f'"{w}"' for w in c['wording']))
    return lines


def page_candidate(c):
    return {
        'key': c['key'],
        'title': f"{c['doc']} § {c['heading']}",
        'state': c['state'],
        'lines': [f"- Doc: `{c['doc']}:{c['line']}` (score {c['score']})", *[f'- {line}' for line in signal_lines(c)]],
    }


def print_report(summary, candidates, limit):
    print("Doc scan (docs-vs-code drift shortlist)")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print(f"\n## Top candidates: {min(limit, len(candidates))} of {len(candidates)}")
    for c in candidates[:limit]:
        print(f"\n  [{c['score']}] {c['doc']}:{c['line']} § {c['heading']}")
        for line in signal_lines(c):
            print(f"      {line}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('repo', nargs='?', default='.', help='Path to a git repository (default: cwd)')
    parser.add_argument('--json', action='store_true', help='Emit summary and candidates as JSON')
    parser.add_argument('--limit', type=int, default=10, help='Candidates shown, and raised on the wiki page')
    parser.add_argument('--include-skill', action='store_true',
                        help="Also scan the Ourobor OS skill's own docs (for developing the skill itself)")
    parser.add_argument('--wiki', action='store_true',
                        help=f'Also merge the shortlist into {drift_page.PAGE_REL} in the scanned project')
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    if git(repo_path, 'rev-parse', '--is-inside-work-tree') is None:
        sys.exit(f"[!] Not a git repository: {repo_path}")
    root = Path(git(repo_path, 'rev-parse', '--show-toplevel').strip())

    repo = Repo(root, args.include_skill)
    docs = repo.docs()
    candidates = sorted((c for doc in docs for c in scan_doc(repo, doc)), key=lambda c: (-c['score'], c['key']))
    summary = summarize(candidates, len(docs))
    if args.json:
        print(json.dumps({'summary': summary, 'candidates': candidates}, indent=2))
    else:
        print_report(summary, candidates, args.limit)
    if args.wiki:
        try:
            path, reviewed, raised = drift_page.write_page(root, [page_candidate(c) for c in candidates], args.limit)
        except FileNotFoundError as err:
            sys.exit(f"[!] {err}")
        print(f"\n[OK] Updated {path.relative_to(root)}: {reviewed} reviewed kept, {raised} unconfirmed raised",
              file=sys.stderr if args.json else sys.stdout)


if __name__ == '__main__':
    import runlog  # sibling module; the script's directory is on sys.path
    runlog.run('doc_scan', main)
