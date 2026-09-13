@entity hooks
@brief Opt-in, declarative installer for Ourobor OS automation: git pre/post-commit capture, a pre-commit docs check, a Claude Code SessionStart status hook, a Claude Code commit gate, and a Claude Code Stop hook that has the agent write docs before finishing.

## Overview

`ouro/scripts/hooks.py` removes the need to run `capture.py` by hand and helps documentation ship in the same commit as the code. It wires the deterministic half of the [Capture-Synthesize Loop](../patterns/capture-synthesize-loop.md) (capture, checks) into git and nudges, gates, or (with the Stop hook) directly asks the running agent to perform the LLM half (synthesis). It never calls an LLM itself. See [ADR-008](../decisions/ADR-008-automatic-capture-hooks.md), [ADR-009](../decisions/ADR-009-pre-commit-docs-hooks.md), and [ADR-010](../decisions/ADR-010-stop-hook-doc-synthesis.md).

Installed via `bootstrap.py --install-hooks [flags]` or `hooks.py install [flags]`; always opt-in.

## Install Options

| Flag | Hook | Effect |
|------|------|--------|
| `--capture-on post-commit` (default) | git `post-commit` | `capture.py --from-commit HEAD` — pointer entries with the commit SHA |
| `--capture-on pre-commit` | git `pre-commit` | `capture.py --from-index` — pointer entries (`Commit: staged`) + `git add` of the queue, so they ship in the same commit |
| `--capture-on none` | — | No capture hook |
| `--docs-check warn\|strict` | git `pre-commit` | `capture.py --check-docs [--strict]` — flags / blocks commits that change code but no `ouro/wiki/` page |
| `--commit-gate` | Claude Code `PreToolUse` (matcher `Bash`) | `hooks.py claude-commit-gate` — blocks the agent's `git commit` under the same rule |
| `--stop-hook` | Claude Code `Stop` | `hooks.py claude-stop-hook` — when the turn ends with undocumented working-tree changes, the agent is asked to write the docs before stopping |
| *(always, if `.claude/` exists)* | Claude Code `SessionStart` | `capture.py --status` — pending capture notice |

@note `install` is **declarative**: it applies exactly the flags given. Re-running without `--docs-check` removes the docs check; switching `--capture-on` moves capture between hooks. Only one capture mode can be active, because post-commit would otherwise rewrite the `staged` entry the commit just shipped, leaving the queue dirty after every commit.

## Functions

### `git_hooks_dir()`

Returns the active hooks directory: `git config core.hooksPath` if set (husky and similar), otherwise `git rev-parse --git-path hooks` (worktree-aware). Relative paths are resolved against the repository top level. Returns `None` outside a git repository.

### `git_hook_commands(capture_on, docs_check)`

Maps install options to `{'pre-commit': [...], 'post-commit': [...]}`. In `pre-commit`, capture runs before the docs check so the check sees the staged queue (which it deliberately ignores).

### `set_git_hook_block(hooks_dir, name, commands)`

Installs, replaces, or — with no commands — removes the marked block in one hook file. Content outside the block is always preserved; a file left with only `#!/bin/sh` is deleted; new files get `#!/bin/sh` and the executable bit.

@snippet git-hook-block
```sh
# >>> ourobor-os >>>
# Managed by Ourobor OS hooks.py. Skipped silently if Python or the skill is missing.
OURO_PY=$(command -v python3 || command -v python)
OURO_CAPTURE="/abs/path/to/ouro/scripts/capture.py"
if [ -n "$OURO_PY" ] && [ -f "$OURO_CAPTURE" ]; then
  "$OURO_PY" "$OURO_CAPTURE" --from-index >/dev/null 2>&1 || true
  "$OURO_PY" "$OURO_CAPTURE" --check-docs --strict || exit 1
fi
# <<< ourobor-os <<<
```

- Idempotent: identical content is not rewritten.
- Refuses to append to a non-shell hook (shebang without `sh`) and prints the block for manual insertion.
- Warns if the existing hook contains `exit` or `exec` (e.g. the `pre-commit` framework's generated hook ends in `exec`), which would make the appended block unreachable.
- Variables are `OURO_`-prefixed to avoid clobbering the user's hook variables.

@note The absolute path to `capture.py` is baked in at install time. If the skill is moved, re-run `hooks.py install` with the same flags.

### `install_git_hooks(capture_on, docs_check)` / `uninstall_git_hooks()`

Apply `git_hook_commands()` to both hook files, or clear both blocks.

### `install_claude_hooks(commit_gate=False, stop_hook=False, project_root=None)`

Only runs when `.claude/` exists. Removes existing Ourobor OS entries, then adds the `SessionStart` status hook and, if requested, a `PreToolUse` entry with `"matcher": "Bash"` running the commit gate and a `Stop` entry running the Stop hook. Every command is guarded with `if [ -f <script> ]`, because Python's "can't open file" error exits with code 2, which Claude Code would treat as a block if the skill were moved or deleted. Unrelated settings and hooks are preserved; invalid JSON is reported and left untouched.

`claude_settings_target()` picks the file:
- skill inside the project → `.claude/settings.json` with `$CLAUDE_PROJECT_DIR`-relative paths (shareable with the team);
- skill outside the project (e.g. `~/.agents/skills/ouro`) → `.claude/settings.local.json` with absolute paths (machine-specific).

Ourobor OS entries are recognised by `is_ouro_hook()` (`capture.py" --status`, `hooks.py" claude-commit-gate`, or `hooks.py" claude-stop-hook` in the command).

### `uninstall_claude_hooks(project_root=None)`

Removes Ourobor OS entries from every event in both `settings.json` and `settings.local.json`, pruning empty groups, events, and the `hooks` object.

### `claude_commit_gate(stream=None)`
@return Exit code: `2` blocks the Bash tool call (stderr is shown to the agent); `0` allows it.

Reads the PreToolUse JSON payload from stdin. If `tool_input.command` contains `git commit` (regex `GIT_COMMIT`; excludes `commit-tree` and similar), calls `capture.undocumented_changes()`. When the command uses `-a`/`-am`/`--all` after `commit`, unstaged tracked changes are included, because the commit itself stages them after the hook runs. Blocks with a message listing up to 10 files, the pending-capture count, and the `OURO_SKIP_DOCS_CHECK=1` escape hatch (which, when present in the command, allows it). Any unexpected error allows the command.

### `claude_stop_hook(stream=None)`
@return Exit code: `2` makes Claude keep working with stderr as its instruction; `0` lets it stop.

Reads the Stop payload from stdin and decides, in order:
1. `stop_hook_active` is true (Claude is already continuing because of a Stop hook) → `0`, to prevent loops.
2. `OURO_SKIP_DOCS_CHECK` set in the environment → `0`.
3. `capture.undocumented_changes(include_unstaged=True, include_untracked=True)` is empty, or the cwd is not a git repository → `0`.
4. State in `.git/ouro-stop-hook.json` (`stop_state_path()`, via `git rev-parse --git-path`) equals `{session_id, fingerprint}`, where the fingerprint is `capture.changes_fingerprint()` → `0`. The agent was already asked about these exact contents this session.
5. Otherwise it writes the state and exits `2`, listing the files and asking the agent to update the relevant wiki pages and `index.md` and pop synthesized captures. The agent may instead reply in one sentence that the work is unfinished, exploratory, not its own, or needs no docs.

Any exception → `0`. See [ADR-010](../decisions/ADR-010-stop-hook-doc-synthesis.md).

## CLI Usage

```bash
# Run from the project root
python <path-to-skill>/scripts/hooks.py install                                   # post-commit capture + SessionStart
python <path-to-skill>/scripts/hooks.py install --docs-check strict --commit-gate  # docs must ship with code
python <path-to-skill>/scripts/hooks.py install --stop-hook                         # agent writes docs before finishing
python <path-to-skill>/scripts/hooks.py install --capture-on pre-commit --docs-check warn
python <path-to-skill>/scripts/hooks.py uninstall
```

@warning Do not install hooks in the Ourobor OS repository itself: `capture.py` writes to `ouro/wiki/capture-queue.md`, which in this repo is the distributable skeleton (see [ADR-001](../decisions/ADR-001-ouro-as-distributable-skeleton.md)).

## Known Gaps

- Only Claude Code gets agent-side hooks; other tools rely on the protocol's instructions and the git pre-commit docs check.
- The Stop hook considers the whole working tree, so it may ask about the user's own uncommitted edits (once per session per set of contents). Once any wiki page is modified, later code changes in the same working tree are not flagged.
- The Stop hook also runs in `claude -p` sessions that load the project's settings.
- The docs check and commit gate treat *any* staged `ouro/wiki/` page (other than the queue) as documentation; they don't verify that the right entity was updated.
- The commit gate detects commits by regex over the command string, so git aliases (`git ci`) or wrapper scripts are not gated; the git pre-commit docs check still applies to those.
- With post-commit capture, commits that already include docs still enqueue pointer entries, so the agent must pop them after confirming the docs are current.
- With post-commit capture, `capture-queue.md` shows as modified after each commit until the next commit or synthesis.
- With pre-commit capture, `git commit <paths>` leaves `capture-queue.md` shown as `MM` (the working tree matches `HEAD`, but the real index is stale) until the next commit re-stages it.
