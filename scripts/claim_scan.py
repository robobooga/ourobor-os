"""Phase 0 claim scan: measure comment/TODO debt in a git repo before building the claim ledger.

Read-only. Stdlib only. Never calls an LLM and never writes to the scanned repo.

For every code comment in tracked files it reports:
- TODO-style deferrals (TODO/FIXME/HACK/XXX) with their age from git blame.
- Stale comments: the code block a comment annotates was modified more than a day after the comment
  was last touched.
- Global-sounding comments: absolute wording ("always", "never", "must", ...) that an agent may read
  as a codebase-wide rule even though it sits in one scope.

Usage:
    python scripts/claim_scan.py [repo_path] [--json] [--limit N]

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
from pathlib import Path

HASH_COMMENT_EXTS = {'.py', '.sh', '.bash', '.zsh', '.rb', '.pl', '.r', '.yaml', '.yml', '.toml'}
SLASH_COMMENT_EXTS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.go', '.rs', '.c', '.h', '.cc',
                      '.cpp', '.hpp', '.java', '.kt', '.swift', '.cs', '.scala', '.dart', '.php'}
SKIP_DIRS = {'dist', 'node_modules', 'vendor', '.venv', 'venv', 'build', '__pycache__'}

TODO_RE = re.compile(r'\b(TODO|FIXME|HACK|XXX)\b')
GLOBAL_RE = re.compile(r"\b(always|never|every|everywhere|must|do not|don't|all callers|only ever)\b", re.I)
HASH_LINE_RE = re.compile(r'(?:^|\s)#\s?(.*)$')
SLASH_LINE_RE = re.compile(r'(?:^|\s)//\s?(.*)$')
MAX_BLOCK_LINES = 20
SECONDS_PER_DAY = 86400
STALE_GRACE_SECONDS = SECONDS_PER_DAY  # same-day edits to comment and code are one change, not drift


def git(repo, *args):
    """Run a git command in repo and return stdout, or None on failure."""
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def tracked_files(repo):
    """Tracked code files with a supported comment syntax, excluding vendored/build dirs."""
    out = git(repo, 'ls-files') or ''
    files = []
    for rel in out.splitlines():
        path = Path(rel)
        if SKIP_DIRS.intersection(path.parts):
            continue
        if path.suffix in HASH_COMMENT_EXTS or path.suffix in SLASH_COMMENT_EXTS:
            files.append(path)
    return files


def blame_times(repo, rel):
    """Map 1-indexed line number -> last-modified unix time. Uncommitted lines get the current time."""
    out = git(repo, 'blame', '--line-porcelain', '-w', '--', str(rel))
    if out is None:
        return {}
    times, line_no, now = {}, None, int(time.time())
    for row in out.splitlines():
        parts = row.split()
        if len(parts) >= 3 and len(parts[0]) == 40 and parts[1].isdigit() and parts[2].isdigit():
            line_no = int(parts[2])
            times[line_no] = now if set(parts[0]) == {'0'} else None
        elif row.startswith('author-time ') and line_no is not None and times.get(line_no) is None:
            times[line_no] = int(row.split()[1])
    return times


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


def annotated_block(line_no, is_trailing, lines, comment_lines):
    """Line numbers of the code a comment describes: its own line if trailing, else the following block."""
    if is_trailing:
        return [line_no]
    block, i = [], line_no + 1
    while i <= len(lines) and len(block) < MAX_BLOCK_LINES:
        if not lines[i - 1].strip():
            break
        if i not in comment_lines:
            block.append(i)
        i += 1
    return block


def scan_file(repo, rel):
    """Return claim records for one file."""
    try:
        source = (repo / rel).read_text(encoding='utf-8')
    except (UnicodeDecodeError, OSError):
        return []
    lines = source.splitlines()
    if rel.suffix == '.py':
        comments, scopes = python_comments(source), python_scopes(source)
    else:
        pattern = SLASH_LINE_RE if rel.suffix in SLASH_COMMENT_EXTS else HASH_LINE_RE
        comments, scopes = regex_comments(lines, pattern), []
    comments = [c for c in comments if c[1] and not c[1].startswith('!') and 'coding' not in c[1][:20]]
    if not comments:
        return []

    times = blame_times(repo, rel)
    comment_lines = {c[0] for c in comments if not c[2]}
    now = time.time()
    records = []
    for line_no, text, is_trailing in comments:
        written = times.get(line_no)
        block = annotated_block(line_no, is_trailing, lines, comment_lines)
        code_times = [times[n] for n in block if times.get(n)]
        latest_code = max(code_times) if code_times else None
        records.append({
            'file': str(rel),
            'line': line_no,
            'scope': scope_for(line_no, scopes) if scopes else None,
            'text': text[:120],
            'todo': bool(TODO_RE.search(text)),
            'global_wording': bool(GLOBAL_RE.search(text)) and not TODO_RE.search(text),
            'stale': bool(written and latest_code and not is_trailing and latest_code - written > STALE_GRACE_SECONDS),
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


def print_report(summary, records, limit):
    print("Claim scan (Phase 0 baseline)")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    sections = [
        ('TODO / deferrals (oldest first)', [r for r in records if r['todo']], lambda r: -(r['age_days'] or 0)),
        ('Stale comments (code changed after comment)', [r for r in records if r['stale']], lambda r: -(r['age_days'] or 0)),
        ('Global-sounding comments', [r for r in records if r['global_wording']], lambda r: r['file']),
    ]
    for title, rows, key in sections:
        print(f"\n## {title}: {len(rows)}")
        for r in sorted(rows, key=key)[:limit]:
            scope = f" [{r['scope']}]" if r['scope'] else ''
            age = f"{r['age_days']}d" if r['age_days'] is not None else '?'
            print(f"  {r['file']}:{r['line']}{scope} ({age}) {r['text']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('repo', nargs='?', default='.', help='Path to a git repository (default: cwd)')
    parser.add_argument('--json', action='store_true', help='Emit summary and records as JSON')
    parser.add_argument('--limit', type=int, default=15, help='Rows per section in the text report')
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if git(repo, 'rev-parse', '--is-inside-work-tree') is None:
        sys.exit(f"[!] Not a git repository: {repo}")
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip())

    files = tracked_files(root)
    records = [rec for rel in files for rec in scan_file(root, rel)]
    summary = summarize(records, len(files))
    if args.json:
        print(json.dumps({'summary': summary, 'records': records}, indent=2))
    else:
        print_report(summary, records, args.limit)


if __name__ == '__main__':
    main()
