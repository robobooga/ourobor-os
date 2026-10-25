"""Phase 0 claim scan: measure comment/TODO debt in a git repo before building the claim ledger.

Read-only by default. Stdlib only. Never calls an LLM. The only write is the opt-in `--wiki` flag,
which saves the report to ouro/wiki/maps/comment-baseline.md in the scanned project.

For every code comment in tracked files it reports:
- TODO-style deferrals (TODO/FIXME/HACK/XXX) with their age from git blame.
- Stale comments: the first statement a comment annotates was last changed in a different, later
  commit than the comment itself.
- Directive-worded comments (review heuristic, not a finding): phrasing like "always", "never",
  "must" that an agent may read as a codebase-wide rule even though it sits in one scope.

Usage:
    python <path-to-skill>/scripts/claim_scan.py [repo_path] [--json] [--limit N] [--wiki] [--include-skill]

See wiki/entities/claim_scan.md and ADR-011.
"""
import argparse
import ast
import io
import json
import re
import subprocess
import sys
import time
import tokenize
from datetime import date
from pathlib import Path

HASH_COMMENT_EXTS = {'.py', '.sh', '.bash', '.zsh', '.rb', '.pl', '.r', '.yaml', '.yml', '.toml'}
SLASH_COMMENT_EXTS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.go', '.rs', '.c', '.h', '.cc',
                      '.cpp', '.hpp', '.java', '.kt', '.swift', '.cs', '.scala', '.dart', '.php'}
SKIP_DIRS = {'dist', 'node_modules', 'vendor', '.venv', 'venv', 'build', '__pycache__'}

TODO_RE = re.compile(r'\b(TODO|FIXME|HACK|XXX)\b')
# Directive phrasing only: a comment opening with an imperative or absolute, or using the modal verb.
# Descriptive uses ("reused every frame") are deliberately not matched.
GLOBAL_RE = re.compile(r"^(always|never|must|do not|don't|only)\b|\bmust\b", re.I)
HASH_LINE_RE = re.compile(r'(?:^|\s)#\s?(.*)$')
SLASH_LINE_RE = re.compile(r'(?:^|\s)//\s?(.*)$')
MAX_SPAN_LINES = 6  # cap on the annotated statement; long statements are mostly unrelated to the comment
SECONDS_PER_DAY = 86400
BASELINE_REL = Path('ouro/wiki/maps/comment-baseline.md')


def git(repo, *args):
    """Run a git command in repo and return stdout, or None on failure."""
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def tracked_files(repo, include_skill=False):
    """Tracked code files with a supported comment syntax, excluding vendored/build dirs and (by default) this skill."""
    out = git(repo, 'ls-files') or ''
    skill_dir = Path(__file__).resolve().parent.parent
    files = []
    for rel in out.splitlines():
        path = Path(rel)
        in_skill = (repo / path).resolve().is_relative_to(skill_dir)
        if SKIP_DIRS.intersection(path.parts) or (in_skill and not include_skill):
            continue
        if path.suffix in HASH_COMMENT_EXTS or path.suffix in SLASH_COMMENT_EXTS:
            files.append(path)
    return files


def blame_info(repo, rel):
    """Map 1-indexed line number -> (commit sha, last-modified unix time). Uncommitted lines get the current time."""
    out = git(repo, 'blame', '--line-porcelain', '-w', '--', str(rel))
    if out is None:
        return {}
    info, line_no, sha, now = {}, None, None, int(time.time())
    for row in out.splitlines():
        parts = row.split()
        if len(parts) >= 3 and len(parts[0]) == 40 and parts[1].isdigit() and parts[2].isdigit():
            line_no, sha = int(parts[2]), parts[0]
            info[line_no] = (sha, now if set(sha) == {'0'} else None)
        elif row.startswith('author-time ') and line_no is not None and info[line_no][1] is None:
            info[line_no] = (sha, int(row.split()[1]))
    return info


def python_comments(source):
    """(line, text, is_trailing) for each Python comment, via tokenize so strings are ignored."""
    comments = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                line_no, col = tok.start
                is_trailing = bool(tok.line[:col].strip())
                comments.append((line_no, tok.string.lstrip('#').strip(), is_trailing))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return comments


def regex_comments(lines, pattern):
    """(line, text, is_trailing) using a line-comment regex; approximate for non-Python languages."""
    comments = []
    for i, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if match:
            comments.append((i, match.group(1).strip(), bool(line[:match.start()].strip())))
    return comments


def python_scopes(source):
    """List of (start, end, qualified_name) for functions and classes, innermost resolvable by span."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    scopes = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                scopes.append((child.lineno, child.end_lineno, name))
                visit(child, name + '.')
            else:
                visit(child, prefix)

    visit(tree, '')
    return scopes


def scope_for(line_no, scopes):
    """Innermost enclosing scope name, or '<module>'."""
    best = None
    for start, end, name in scopes:
        if start <= line_no <= end and (best is None or start >= best[0]):
            best = (start, end, name)
    return best[2] if best else '<module>'


def python_statements(source):
    """Map first line -> last line of each statement header (compound statements stop before their body)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    spans = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            end = node.end_lineno
            body = getattr(node, 'body', None)
            if isinstance(body, list) and body:
                end = max(node.lineno, body[0].lineno - 1)
            for child in ast.walk(node):  # a triple-quoted string's body is data, not what the comment describes
                if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.end_lineno > child.lineno:
                    end = min(end, max(node.lineno, child.lineno))
            spans.setdefault(node.lineno, end)
    return spans


def annotated_span(line_no, is_trailing, lines, comment_lines, statements):
    """Line numbers of the code a comment describes: its own line if trailing, else the first statement below it."""
    if is_trailing:
        return [line_no]
    i = line_no + 1
    while i <= len(lines) and (not lines[i - 1].strip() or i in comment_lines):
        i += 1
    if i > len(lines):
        return []
    end = min(statements.get(i, i), i + MAX_SPAN_LINES - 1, len(lines))
    return list(range(i, end + 1))


def is_stale(comment_at, span, blame):
    """True when a span line was last changed by a different commit that is later than the comment's."""
    comment_sha, comment_time = comment_at
    return any(blame[n][0] != comment_sha and blame[n][1] > comment_time for n in span if n in blame)


def scan_file(repo, rel):
    """Return claim records for one file."""
    try:
        source = (repo / rel).read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        return []
    lines = source.splitlines()
    if rel.suffix == '.py':
        comments, scopes, statements = python_comments(source), python_scopes(source), python_statements(source)
    else:
        pattern = SLASH_LINE_RE if rel.suffix in SLASH_COMMENT_EXTS else HASH_LINE_RE
        comments, scopes, statements = regex_comments(lines, pattern), [], {}
    comments = [c for c in comments if c[1] and not c[1].startswith('!') and 'coding' not in c[1][:20]]
    if not comments:
        return []

    blame = blame_info(repo, rel)
    comment_lines = {c[0] for c in comments if not c[2]}
    now = time.time()
    records = []
    for line_no, text, is_trailing in comments:
        written_at = blame.get(line_no)
        written = written_at[1] if written_at else None
        span = annotated_span(line_no, is_trailing, lines, comment_lines, statements)
        records.append({
            'file': str(rel),
            'line': line_no,
            'scope': scope_for(line_no, scopes) if scopes else None,
            'text': text[:120],
            'todo': bool(TODO_RE.search(text)),
            'global_wording': bool(GLOBAL_RE.search(text)) and not TODO_RE.search(text),
            'stale': bool(written_at and not is_trailing and is_stale(written_at, span, blame)),
            'age_days': round((now - written) / SECONDS_PER_DAY) if written else None,
        })
    return records


def summarize(records, files_scanned):
    todos = [r for r in records if r['todo']]
    ages = sorted(r['age_days'] for r in todos if r['age_days'] is not None)
    return {
        'files_scanned': files_scanned,
        'comments': len(records),
        'todos': len(todos),
        'todo_median_age_days': ages[len(ages) // 2] if ages else None,
        'todo_max_age_days': ages[-1] if ages else None,
        'stale_comments': sum(r['stale'] for r in records),
        'global_wording_comments': sum(r['global_wording'] for r in records),
    }


def report_sections(records):
    """(title, rows) for each report section, each sorted for display."""
    todos = [r for r in records if r['todo']]
    stale = [r for r in records if r['stale']]
    wording = [r for r in records if r['global_wording']]
    return [
        ('TODO / deferrals (oldest first)', sorted(todos, key=lambda r: -(r['age_days'] or 0))),
        ('Stale comments (annotated statement changed in a later commit)', sorted(stale, key=lambda r: -(r['age_days'] or 0))),
        ('Directive-worded comments (review heuristic, not findings)', sorted(wording, key=lambda r: r['file'])),
    ]


def format_row(r):
    scope = f" [{r['scope']}]" if r['scope'] else ''
    age = f"{r['age_days']}d" if r['age_days'] is not None else '?'
    return f"{r['file']}:{r['line']}{scope} ({age}) {r['text']}"


def print_report(summary, records, limit):
    print("Claim scan (Phase 0 baseline)")
    for key, value in summary.items():
        if key != 'global_wording_comments':  # review heuristic: has its own section, stays in JSON
            print(f"  {key}: {value}")
    for title, rows in report_sections(records):
        print(f"\n## {title}: {len(rows)}")
        for r in rows[:limit]:
            print(f"  {format_row(r)}")


def write_wiki_page(root, summary, records, limit):
    """Save the report as a wiki map page in the scanned project; returns the path written."""
    wiki_dir = root / 'ouro' / 'wiki'
    if not wiki_dir.is_dir():
        sys.exit(f"[!] No ouro/wiki/ in {root}. Run bootstrap.py first, or omit --wiki.")
    lines = [
        '@entity CommentBaseline',
        '@brief Comment and TODO debt measured by claim_scan.py: TODO age, stale comments, and comments '
        'worded as global rules. Re-run to compare.',
        '',
        f'Generated {date.today().isoformat()} by `claim_scan.py --wiki`. Regenerate rather than hand-edit.',
        '',
        '## Summary',
        '',
        '| Metric | Value |',
        '|--------|-------|',
        *[f'| {key} | {value} |' for key, value in summary.items()],
    ]
    for title, rows in report_sections(records):
        lines += ['', f'## {title}: {len(rows)}', '']
        lines += [f'- `{format_row(r)}`' for r in rows[:limit]] or ['None.']
        if len(rows) > limit:
            lines.append(f'- ...and {len(rows) - limit} more (`--limit` to show more)')
    path = root / BASELINE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('repo', nargs='?', default='.', help='Path to a git repository (default: cwd)')
    parser.add_argument('--json', action='store_true', help='Emit summary and records as JSON')
    parser.add_argument('--limit', type=int, default=15, help='Rows per section in the text report')
    parser.add_argument('--include-skill', action='store_true',
                        help="Also scan the Ourobor OS skill's own files (for developing the skill itself)")
    parser.add_argument('--wiki', action='store_true',
                        help=f'Also save the report to {BASELINE_REL} in the scanned project')
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if git(repo, 'rev-parse', '--is-inside-work-tree') is None:
        sys.exit(f"[!] Not a git repository: {repo}")
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip())

    files = tracked_files(root, args.include_skill)
    records = [rec for rel in files for rec in scan_file(root, rel)]
    summary = summarize(records, len(files))
    if args.json:
        print(json.dumps({'summary': summary, 'records': records}, indent=2))
    else:
        print_report(summary, records, args.limit)
    if args.wiki:
        path = write_wiki_page(root, summary, records, args.limit)
        print(f"\n[OK] Saved baseline to {path.relative_to(root)}", file=sys.stderr if args.json else sys.stdout)


if __name__ == '__main__':
    import runlog  # sibling module; the script's directory is on sys.path
    runlog.run('claim_scan', main)
