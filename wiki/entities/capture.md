@entity capture
@brief Manages the capture queue — staging, crawling, and popping knowledge entries for LLM synthesis.

## Overview

`ouro/scripts/capture.py` is the primary knowledge ingestion tool. It reads code and notes into `ouro/wiki/capture-queue.md` for later synthesis by an LLM agent. It is the entry point to the [Capture-Synthesize Loop](../patterns/capture-synthesize-loop.md).

## Functions

### `stage(input_str)`
@param input_str A file path or raw text string.

Stages a timestamped entry to the capture queue. If a valid file path is given, reads its content (via `file_capture()`); otherwise treats the input as a raw snippet with source `Manual Capture`. Handles binary file detection and encoding errors gracefully.

@snippet stage-entry-format
```
### Capture [2026-05-03T10:00:00]
- **Source**: `ouro/scripts/capture.py`
- **Content**:
```<content>```
---
```

### `enqueue(captures)`
@param captures List of `(source, entry_text)` tuples.
@return `False` if the queue could not be written.

The single write path for the queue. Reads the queue once, drops any existing entries whose `Source` matches an incoming file source (**deduplication**; raw `Manual Capture` notes are never deduplicated), appends the new entries, and writes once. `crawl()` and `crawl_git()` collect all captures first and call `enqueue()` a single time, avoiding a rewrite per file. The `*(Empty)*` marker is removed when entries exist and restored when none remain.

### `split_entries(content)` / `render_queue(preamble, entries)` / `entry_source(entry_lines)`

Queue parsing helpers shared by `enqueue()`, `pop()`, and `count_pending()`. An entry starts at a line beginning with `### Capture [` and runs until the next one (including its trailing `---`). Everything before the first entry is the preamble.

### `skip_reason(file_path, must_exist=True)`
@return `'ignored'`, `'sensitive'`, `'binary'`, or `None` if the file may be captured.

The filter chain shared by `crawl()`, `crawl_git()`, and `capture_commit()`: `ouro/wiki/` and `IGNORED_DIRS`, non-files, `is_sensitive()`, then `is_binary()`. `IGNORED_DIRS` is matched against the **project-relative** path, so a project that lives under e.g. `/tmp/` is not skipped wholesale. `must_exist=False` lets deleted files through (used for `Change: deleted` pointers).

### `crawl(directory)`
@param directory Root directory to walk recursively. Defaults to `.` via CLI.

Walks all files under `directory`, keeps those for which `skip_reason()` returns `None`, and enqueues their full content in one write. Reports a count of staged files and separately a count of skipped sensitive files.

### `get_git_changed_files(depth=1)`
@param depth Number of commits to look back for changed files. Defaults to `1`.

Runs four git commands to collect the full set of recently touched files: unstaged tracked changes (`git diff --name-only`), staged changes (`git diff --name-only --cached`), untracked new files (`git ls-files --others --exclude-standard`), and files changed in the last `depth` commits (`git diff --name-only HEAD~{depth} HEAD`). Returns a set of resolved absolute `Path` objects. Silently skips any command that fails (e.g. git not installed, not a repo).

### `crawl_git(directory, depth=1)`
@param directory Root directory to restrict results to. Defaults to `.` via CLI.
@param depth Passed through to `get_git_changed_files()`.

Git-aware alternative to `crawl()`. Calls `get_git_changed_files()` to determine which files to stage, then applies the same `skip_reason()` filters as `crawl()`. Only files within `directory` are staged. Recommended for ongoing sessions without hooks — avoids re-queuing unchanged files.

### `get_commit_files(rev='HEAD')`
@param rev Commit to inspect.
@return List of `(change, project_relative_path)`, where change is `added`, `modified`, or `deleted`.

Runs `git diff-tree --no-commit-id --name-status -r --root --no-renames -z <rev>`. `--root` handles the initial commit, `--no-renames` reports a rename as delete + add, and `-z` avoids path quoting. Returns `[]` if git fails.

### `parse_name_status(output)` / `get_index_files(include_unstaged=False, include_untracked=False)` / `capturable(files)`

`parse_name_status()` is shared by `get_commit_files()` and `get_index_files()`. `get_index_files()` lists staged files (`git diff --cached --name-status --no-renames -z`), plus unstaged tracked changes when `include_unstaged` is set, plus untracked, non-gitignored files (`git ls-files --others --exclude-standard -z`, reported as `added`) when `include_untracked` is set. Inside a git hook, the inherited `GIT_INDEX_FILE` makes this reflect the commit being made, including `commit -a`. `capturable()` keeps the `(change, path)` pairs that pass `skip_reason()` (deleted files allowed).

### `capture_commit(rev='HEAD')`

Invoked by the post-commit hook (`--from-commit`). For each file in the commit that passes `skip_reason()` (deleted files allowed), enqueues a **pointer entry** that carries no file content:

@snippet pointer-entry-format
```
### Capture [2026-09-13T10:00:00]
- **Source**: `src/foo.py`
- **Commit**: `abc1234`
- **Change**: modified
- **Content**: *(pointer — read the current file at `src/foo.py` during synthesis)*

---
```

Because `enqueue()` deduplicates by `Source`, repeated commits to the same file leave a single, latest entry. See [ADR-008](../decisions/ADR-008-automatic-capture-hooks.md).

### `capture_index()`

Pre-commit capture (`--from-index`). Enqueues pointer entries with `Commit: staged` for every capturable staged file, then `git add`s `ouro/wiki/capture-queue.md` so the entries ship in the commit being made. If the queue's staged copy differs from `HEAD`, it is re-added even when nothing new was captured: `git commit <paths>` restores the real index afterwards, leaving a stale staged queue that would otherwise be committed next. See [ADR-009](../decisions/ADR-009-pre-commit-docs-hooks.md).

### `undocumented_changes(include_unstaged=False, include_untracked=False)`
@return Sorted capturable paths in the pending commit, or `[]` if the commit includes any `ouro/wiki/` page other than `capture-queue.md` (or has no capturable changes).

The single rule behind the git docs check and the Claude Code commit gate (staged files, plus unstaged for `-a` commits) and the Claude Code Stop hook (the whole working tree: staged, unstaged, and untracked).

### `changes_fingerprint(paths)`

SHA-256 over the sorted paths and each file's content hash (`deleted` for missing files). The Stop hook stores it with the session ID so it asks only once per distinct set of changes.

### `check_docs(strict=False)`
@return Exit code — `1` only when `strict` and `undocumented_changes()` is non-empty.

Pre-commit docs check (`--check-docs [--strict]`). Prints the offending files to stderr (via `describe_undocumented()`, max 10 listed) as a warning or a block. Returns `0` when `OURO_SKIP_DOCS_CHECK` is set or on any unexpected error, so it never fails a commit for the wrong reason.

### `status()` / `count_pending()`

`status()` prints `Ourobor OS: N pending capture(s) in ouro/wiki/capture-queue.md. …` when the queue is non-empty and **prints nothing** when it is empty, so the Claude Code SessionStart hook adds no noise to sessions with nothing to do.

**Module-level constants** (edit in `capture.py` to customise for your project):

- **`IGNORED_DIRS`** — directory names that cause an entire subtree to be skipped. Covers version control, Python/JS/Go/Rust/JVM build and cache directories, infrastructure state (`.terraform`), and credential directories (`.aws`, `.ssh`, `secrets`, `certs`, `vault`, etc.).
- **`SENSITIVE_NAMES`** — exact filenames always skipped (`.env`, `id_rsa`, `credentials.json`, etc.).
- **`SENSITIVE_SUFFIXES`** — extensions always skipped (`.pem`, `.key`, `.p12`, `.pfx`, `.crt`, `.secret`, `.token`, etc.).

See [ADR-005](../decisions/ADR-005-crawl-sensitive-file-guard.md) for the rationale.

### `is_sensitive(file_path)`

Combines `SENSITIVE_NAMES`, `SENSITIVE_SUFFIXES`, and heuristic keyword matching (`secret`, `credential`, `password`, `passwd`, `apikey`, `api_key`, `token`, `private_key` in the filename) to decide whether a file should be skipped during crawl.

@warning `IGNORED_DIRS`, `SENSITIVE_NAMES`, `SENSITIVE_SUFFIXES`, and the keyword list in `is_sensitive()` are project-agnostic defaults. Projects with non-standard secret naming conventions should update these constants directly in `capture.py`.

### `pop()`

Reads and prints the first `### Capture [...]` entry from the queue (content or pointer), removes it, and rewrites the file. If no entries remain, restores the `*(Empty)*` marker. Used by the LLM agent to process one entry at a time during synthesis.

### `is_binary(file_path)`

Heuristic check — reads the first 1024 bytes of a file and returns `True` if a null byte is found.

## CLI Usage

```bash
# Stage a specific file
python ouro/scripts/capture.py path/to/file.py

# Stage a raw architectural note
python ouro/scripts/capture.py "Decision: use composition over inheritance in the plugin loader."

# Crawl only git-changed files (recommended after initial setup)
python ouro/scripts/capture.py --crawl --git

# Include last N commits' worth of changes
python ouro/scripts/capture.py --crawl --git 3

# Crawl the whole project (use for initial wiki population)
python ouro/scripts/capture.py --crawl

# Crawl a specific directory
python ouro/scripts/capture.py --crawl src/

# Stage pointer captures for a commit (run by the post-commit hook)
python ouro/scripts/capture.py --from-commit HEAD

# Print pending capture count (silent when empty; run by the SessionStart hook)
python ouro/scripts/capture.py --status

# Pre-commit capture: pointer entries for staged files + stage the queue (run by the pre-commit hook)
python ouro/scripts/capture.py --from-index

# Pre-commit docs check: warn (exit 0) or, with --strict, exit 1 when staged code has no wiki updates
python ouro/scripts/capture.py --check-docs --strict

# Pop the first entry from the queue (used during synthesis)
python ouro/scripts/capture.py --pop
```

@note `QUEUE_PATH` is resolved relative to `Path.cwd()`, so the script must be run from the project root. Git hooks run from the repository top level, and the SessionStart hook `cd`s to `$CLAUDE_PROJECT_DIR`.

## Known Gaps

- `--status` reports the count only, not the last capture timestamp.
- `IGNORED_DIRS` and `SENSITIVE_*` constants are not user-configurable via CLI flags — editing the source file is required.
- A captured file whose content contains a line starting with `### Capture [` will be mis-split by the queue parser.
- `undocumented_changes()` accepts *any* staged wiki page as documentation; it cannot tell whether the right entity was updated.
- Git paths are relative to the repository root while `QUEUE_PATH` is relative to the cwd, so projects whose `ouro/` sits in a subdirectory of the repo (monorepos) are not supported by the git-based commands.
- `--git` depth uses `HEAD~{depth}` which fails gracefully (silent skip) when the repo has fewer commits than `depth`; the working-tree commands still run.
