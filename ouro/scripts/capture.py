import sys
import os
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

# Path to the capture queue
PROJECT_ROOT = Path.cwd()
WIKI_REL = 'ouro/wiki/'
QUEUE_REL = 'ouro/wiki/capture-queue.md'
QUEUE_PATH = PROJECT_ROOT / QUEUE_REL
WIKI_PATH = PROJECT_ROOT.resolve() / WIKI_REL

ENTRY_HEADER = '### Capture ['
SOURCE_PREFIX = '- **Source**: `'
MANUAL_SOURCE = 'Manual Capture'

# Set (to any value) to bypass the pre-commit docs check and the agent commit gate for one commit
SKIP_DOCS_ENV = 'OURO_SKIP_DOCS_CHECK'

# git diff-tree status letters -> human-readable change type (anything else is 'modified')
GIT_CHANGES = {'A': 'added', 'D': 'deleted'}

def is_binary(file_path):
    """Heuristic to check if a file is binary."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' in chunk
    except Exception:
        return True

def source_for(path_obj):
    """Queue source label for a file: project-relative POSIX path when possible."""
    try:
        return path_obj.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path_obj)

def content_entry(source, content):
    """Full capture: the file (or raw note) content is embedded in the queue."""
    return f"""### Capture [{datetime.now().isoformat()}]
- **Source**: `{source}`
- **Content**:
```
{content}
```

---"""

def pointer_entry(source, commit, change):
    """Lightweight capture written by the git hooks: the agent reads the file at synthesis time.

    `commit` is a short SHA (post-commit) or `staged` (pre-commit, where the entry ships in that commit).
    """
    return f"""### Capture [{datetime.now().isoformat()}]
- **Source**: `{source}`
- **Commit**: `{commit}`
- **Change**: {change}
- **Content**: *(pointer — read the current file at `{source}` during synthesis)*

---"""

def split_entries(content):
    """Splits queue text into (preamble_lines, [entry_lines, ...])."""
    lines = content.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(ENTRY_HEADER)]
    if not starts:
        return lines, []
    bounds = starts + [len(lines)]
    entries = [lines[bounds[i]:bounds[i + 1]] for i in range(len(starts))]
    return lines[:starts[0]], entries

def entry_source(entry_lines):
    """Returns the `Source` of a queue entry, or None."""
    for line in entry_lines:
        if line.startswith(SOURCE_PREFIX):
            return line[len(SOURCE_PREFIX):].rstrip('`')
    return None

def render_queue(preamble, entries):
    """Joins preamble and entries back into queue text, keeping the *(Empty)* marker in sync."""
    head = '\n'.join(preamble).strip()
    if not entries:
        if '## Pending Captures' in head and '*(Empty)*' not in head:
            head = head.replace('## Pending Captures', '## Pending Captures\n*(Empty)*')
        return head + '\n'
    head = head.replace('*(Empty)*', '').strip()
    body = '\n\n'.join('\n'.join(entry).strip() for entry in entries)
    return f'{head}\n\n{body}\n'

def enqueue(captures):
    """Appends (source, entry_text) captures in one write, replacing older entries for the same file.

    Raw notes (MANUAL_SOURCE) are never deduplicated. Returns False if the queue could not be written.
    """
    if not captures:
        return True
    try:
        content = QUEUE_PATH.read_text(encoding='utf-8') if QUEUE_PATH.exists() else ''
        preamble, entries = split_entries(content)
        new_sources = {source for source, _ in captures if source != MANUAL_SOURCE}
        entries = [entry for entry in entries if entry_source(entry) not in new_sources]
        entries += [text.splitlines() for _, text in captures]
        QUEUE_PATH.write_text(render_queue(preamble, entries), encoding='utf-8')
        return True
    except Exception as e:
        print(f'Failed to write to capture queue: {e}')
        return False

def file_capture(path_obj):
    """Builds a full-content (source, entry) capture for a file, or None if it can't be read."""
    if is_binary(path_obj):
        print(f"Skipping binary file: {path_obj}")
        return None
    try:
        content = path_obj.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading file {path_obj}: {e}")
        return None
    source = source_for(path_obj)
    return source, content_entry(source, content)

def stage(input_str):
    """Stages a file or raw snippet to the capture queue."""
    path_obj = Path(input_str)
    if path_obj.is_file():
        capture = file_capture(path_obj)
        if capture is None:
            return
    else:
        capture = (MANUAL_SOURCE, content_entry(MANUAL_SOURCE, input_str))

    if enqueue([capture]):
        print(f'Successfully staged capture from "{capture[0]}" to {QUEUE_PATH}')

IGNORED_DIRS = {
    # Version control
    '.git', '.svn', '.hg',
    # Python
    '__pycache__', '.venv', 'venv', 'env', '.tox', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    # JavaScript / Node
    'node_modules', 'bower_components', '.yarn', '.pnp', '.npm',
    # Build outputs
    'dist', 'build', 'out', 'target', '_build', 'dist-skill', '.next', '.nuxt', '.svelte-kit', '.expo',
    # Caches
    '.cache', 'cache', '.parcel-cache',
    # Java / Kotlin / Scala
    '.gradle', '.m2',
    # Ruby
    '.bundle',
    # Haskell / Elm
    '.stack-work', 'elm-stuff',
    # Elixir / Erlang
    '_build', 'deps',
    # iOS / macOS
    'Pods', 'DerivedData',
    # Misc build / temp
    'tmp', 'temp', 'logs', 'coverage', '.coverage',
    # Infrastructure-as-code state (may contain secrets)
    '.terraform', '.vagrant',
    # Credential / secret directories
    '.aws', '.ssh', '.gnupg', '.gpg',
    'secrets', '.secrets', 'credentials', '.credentials',
    'certs', 'certificates', '.certs', 'keystore', 'keystores',
    'keys', '.keys', 'private', '.private', 'vault',
    # Project-specific
    'ouro',
}

# Individual filenames that are likely to contain secrets
SENSITIVE_NAMES = {
    '.env', '.env.local', '.env.development', '.env.production',
    '.env.staging', '.env.test', '.env.example',
    'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519',
    'id_rsa.pub', 'id_dsa.pub', 'id_ecdsa.pub', 'id_ed25519.pub',
    'known_hosts', 'authorized_keys',
    '.netrc', '.pgpass',
    'secrets.json', 'credentials.json', 'service-account.json',
}

# File extensions that are likely to contain secrets or are binary-adjacent
SENSITIVE_SUFFIXES = {
    '.pem', '.key', '.p12', '.pfx', '.cer', '.crt', '.der', '.ca-bundle',
    '.keystore', '.jks', '.p8',
    '.secret', '.secrets',
    '.token', '.tokens',
    '.asc',  # GPG armored
}

def is_sensitive(file_path: Path) -> bool:
    name = file_path.name.lower()
    if name in SENSITIVE_NAMES:
        return True
    if file_path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    # Catch patterns like .env.local, *credentials*.json, *secret*.yml
    if name.startswith('.env'):
        return True
    if any(kw in name for kw in ('secret', 'credential', 'password', 'passwd', 'apikey', 'api_key', 'token', 'private_key')):
        return True
    return False

def skip_reason(file_path, must_exist=True):
    """Returns why a file must not be captured ('ignored', 'sensitive', 'binary'), or None if it may be.

    IGNORED_DIRS is matched against the project-relative path, so a project that itself lives under
    e.g. `/tmp/` or `~/build/` is not skipped wholesale. `must_exist=False` allows deleted files.
    """
    file_path = Path(file_path).resolve()
    try:
        parts = file_path.relative_to(PROJECT_ROOT.resolve()).parts
    except ValueError:
        parts = file_path.parts
    if WIKI_PATH in file_path.parents or any(part in IGNORED_DIRS for part in parts):
        return 'ignored'
    exists = file_path.exists()
    if (exists and not file_path.is_file()) or (not exists and must_exist):
        return 'ignored'
    if is_sensitive(file_path):
        return 'sensitive'
    if exists and is_binary(file_path):
        return 'binary'
    return None

def run_git(args):
    """Runs a git command from the project root; returns stdout, or None on failure."""
    try:
        result = subprocess.run(['git'] + args, capture_output=True, text=True, cwd=PROJECT_ROOT)
    except Exception:
        return None
    return result.stdout if result.returncode == 0 else None


def get_git_changed_files(depth=1):
    """Returns a set of absolute Paths for files touched by git (working tree + recent commits)."""
    cwd = Path.cwd()
    files = set()
    commands = [
        ['diff', '--name-only'],
        ['diff', '--name-only', '--cached'],
        ['ls-files', '--others', '--exclude-standard'],
        ['diff', '--name-only', f'HEAD~{depth}', 'HEAD'],
    ]
    for cmd in commands:
        output = run_git(cmd)
        if output is not None:
            files.update(f.strip() for f in output.splitlines() if f.strip())
    return {(cwd / f).resolve() for f in files}


def crawl_git(directory, depth=1):
    """Crawls only git-changed files within directory."""
    dir_path = Path(directory).resolve()
    changed = get_git_changed_files(depth=depth)

    if not changed:
        print('No git-changed files found. Is this a git repo with recent changes?')
        return

    print(f'Git-aware crawl ({len(changed)} changed file(s) detected)...')
    captures = []
    skipped_sensitive = 0

    for file_path in sorted(changed):
        try:
            file_path.relative_to(dir_path)
        except ValueError:
            continue

        reason = skip_reason(file_path)
        if reason == 'sensitive':
            skipped_sensitive += 1
        if reason:
            continue

        capture = file_capture(file_path)
        if capture:
            captures.append(capture)

    if enqueue(captures):
        print(f'Git-aware crawl complete. Staged {len(captures)} files. Skipped {skipped_sensitive} sensitive file(s).')


def crawl(directory):
    """Crawls a directory for files containing Doxygen tags."""
    dir_path = Path(directory).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        print(f'Error: Directory "{directory}" does not exist.')
        sys.exit(1)

    print(f'Crawling directory: {dir_path}...')
    captures = []
    skipped_sensitive = 0

    for file_path in sorted(dir_path.rglob('*')):
        reason = skip_reason(file_path)
        if reason == 'sensitive':
            print(f'Skipping sensitive file: {file_path}')
            skipped_sensitive += 1
        if reason:
            continue

        capture = file_capture(file_path)
        if capture:
            captures.append(capture)

    if enqueue(captures):
        print(f'Crawl complete. Staged {len(captures)} files. Skipped {skipped_sensitive} sensitive file(s).')


def parse_name_status(output):
    """Parses `git ... --name-status -z` output into [(change, project_relative_path)]."""
    if not output:
        return []
    tokens = output.split('\0')
    return [(GIT_CHANGES.get(status[:1], 'modified'), path)
            for status, path in zip(tokens[0::2], tokens[1::2]) if path]


def get_commit_files(rev='HEAD'):
    """Returns [(change, project_relative_path)] for files touched by commit `rev`; [] if git fails."""
    return parse_name_status(run_git(['diff-tree', '--no-commit-id', '--name-status', '-r', '--root', '--no-renames', '-z', rev]))


def get_index_files(include_unstaged=False, include_untracked=False):
    """Returns [(change, project_relative_path)] for staged files, optionally plus unstaged tracked changes
    and untracked (not gitignored) files."""
    files = parse_name_status(run_git(['diff', '--cached', '--name-status', '--no-renames', '-z']))
    if include_unstaged:
        files += parse_name_status(run_git(['diff', '--name-status', '--no-renames', '-z']))
    if include_untracked:
        output = run_git(['ls-files', '--others', '--exclude-standard', '-z']) or ''
        files += [('added', path) for path in output.split('\0') if path]
    return files


def capturable(files):
    """Filters [(change, path)] down to files that may be captured (deleted files are allowed)."""
    return [(change, path) for change, path in files
            if not skip_reason(PROJECT_ROOT / path, must_exist=(change != 'deleted'))]


def capture_commit(rev='HEAD'):
    """Stages pointer captures for every capturable file touched by commit `rev` (used by the post-commit hook)."""
    sha = (run_git(['rev-parse', '--short', rev]) or '').strip()
    if not sha:
        print(f'Could not resolve commit "{rev}". Is this a git repository?')
        return

    captures = [(path, pointer_entry(path, sha, change)) for change, path in capturable(get_commit_files(rev))]
    if enqueue(captures):
        print(f'Staged {len(captures)} pointer capture(s) from commit {sha}.')


def capture_index():
    """Pre-commit capture: stages pointer captures for staged files and adds the queue to the same commit.

    Also re-stages the queue when its staged copy differs from HEAD even if nothing new was captured:
    `git commit <paths>` restores the real index afterwards, leaving a stale queue staged that would
    otherwise be committed next.
    """
    captures = [(path, pointer_entry(path, 'staged', change)) for change, path in capturable(get_index_files())]
    if captures and not enqueue(captures):
        return
    queue_staged = run_git(['diff', '--cached', '--quiet', '--', QUEUE_REL]) is None
    if captures or queue_staged:
        run_git(['add', '--', QUEUE_REL])
    if captures:
        print(f'Staged {len(captures)} pointer capture(s) into this commit.')


def undocumented_changes(include_unstaged=False, include_untracked=False):
    """Capturable changed files when none of the considered changes touch a wiki page.

    Considers staged files (the pending commit), optionally plus unstaged and untracked files (the working tree).
    Returns [] if any `ouro/wiki/` page is included or no capturable file changed.
    The capture queue itself does not count as documentation.
    """
    files = get_index_files(include_unstaged, include_untracked)
    if any(path.startswith(WIKI_REL) and path != QUEUE_REL for _, path in files):
        return []
    return sorted({path for _, path in capturable(files)})


def describe_undocumented(paths, limit=10):
    """Bulleted file list for docs-check / commit-gate messages."""
    lines = [f'  - {path}' for path in paths[:limit]]
    if len(paths) > limit:
        lines.append(f'  ... and {len(paths) - limit} more')
    return '\n'.join(lines)


def changes_fingerprint(paths):
    """Stable hash of the given files' current contents (missing files hash as 'deleted')."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        file_path = PROJECT_ROOT / path
        content = hashlib.sha256(file_path.read_bytes()).hexdigest() if file_path.is_file() else 'deleted'
        digest.update(f'{path}\0{content}\n'.encode('utf-8'))
    return digest.hexdigest()


def check_docs(strict=False):
    """Pre-commit docs check. Returns the exit code: 1 only in strict mode when code changes lack wiki updates.

    Never fails the commit on unexpected errors.
    """
    if os.environ.get(SKIP_DOCS_ENV):
        return 0
    try:
        missing = undocumented_changes()
    except Exception as e:
        print(f'Ourobor OS: docs check skipped ({e}).', file=sys.stderr)
        return 0
    if not missing:
        return 0

    level = 'commit blocked' if strict else 'warning'
    print(f'Ourobor OS {level}: this commit changes {len(missing)} file(s) but no {WIKI_REL} pages:\n'
          f'{describe_undocumented(missing)}\n'
          f'Update and stage the relevant wiki pages so the docs ship with this change. '
          f'If none are needed, commit with {SKIP_DOCS_ENV}=1.', file=sys.stderr)
    return 1 if strict else 0


def count_pending():
    """Number of entries currently in the capture queue."""
    if not QUEUE_PATH.exists():
        return 0
    _, entries = split_entries(QUEUE_PATH.read_text(encoding='utf-8'))
    return len(entries)


def status():
    """Prints a one-line pending-capture notice for agents; prints nothing when the queue is empty."""
    pending = count_pending()
    if pending:
        print(f'Ourobor OS: {pending} pending capture(s) in ouro/wiki/capture-queue.md. '
              'Synthesize them into the wiki per the maintenance protocol, then `--pop` each one.')


def pop():
    """Pops the first capture from the queue and prints it."""
    if not QUEUE_PATH.exists():
        print("Queue file not found.")
        return

    try:
        content = QUEUE_PATH.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading queue: {e}")
        return

    preamble, entries = split_entries(content)
    if not entries:
        print("No captures found in the queue.")
        return

    try:
        QUEUE_PATH.write_text(render_queue(preamble, entries[1:]), encoding='utf-8')
        print('\n'.join(entries[0]).strip())
    except Exception as e:
        print(f"Failed to update queue: {e}")

def main():
    if len(sys.argv) < 2:
        print('Error: Please provide a file path, raw snippet, --crawl [--git [N]] [dir], --from-commit [rev], '
              '--from-index, --check-docs [--strict], --status, or --pop.')
        sys.exit(1)

    arg1 = sys.argv[1]

    if arg1 == '--crawl':
        rest = sys.argv[2:]
        use_git = '--git' in rest
        git_depth = 1
        if use_git:
            rest = [a for a in rest if a != '--git']
            if rest and rest[0].isdigit():
                git_depth = int(rest.pop(0))
        directory = rest[0] if rest else '.'
        if use_git:
            crawl_git(directory, depth=git_depth)
        else:
            crawl(directory)
    elif arg1 == '--from-commit':
        capture_commit(sys.argv[2] if len(sys.argv) > 2 else 'HEAD')
    elif arg1 == '--from-index':
        capture_index()
    elif arg1 == '--check-docs':
        sys.exit(check_docs(strict='--strict' in sys.argv[2:]))
    elif arg1 == '--status':
        status()
    elif arg1 == '--pop':
        pop()
    else:
        stage(arg1)

if __name__ == '__main__':
    main()
