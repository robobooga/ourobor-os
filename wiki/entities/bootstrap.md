@entity bootstrap
@brief Initializes the Ourobor OS wiki structure in a target project and wires the LLM maintenance protocol into instruction files.

## Overview

`ouro/scripts/bootstrap.py` is a one-time setup script run from a target project's root. It creates the `ouro/wiki/` directory tree, copies the template skeleton from the installed skill, and appends the maintenance protocol to any LLM instruction files it finds.

## Functions

### `detect_llm_environment()`

Inspects the current working directory for known LLM config directories and returns a list of detected environments plus the primary instruction filename.

@snippet detect-llm-env
```python
if (cwd / '.claude').exists():
    detected.append('Claude Code')
    primary_instruction_file = 'CLAUDE.md'
if (cwd / '.cursor').exists():
    detected.append('Cursor')
    ...
```

**Detected environments**: Claude Code (`.claude/`), Cursor (`.cursor/`), Aider (`.aider/`), Continue (`.continue/`)

### `bootstrap()`

Orchestrates the full initialization sequence:

1. Calls `detect_llm_environment()` and reports findings.
2. Creates `ouro/wiki/` and subdirectories (`entities/`, `decisions/`, `patterns/`, `maps/`) if they don't already exist.
3. Copies template files (`index.md`, `schema.md`, `capture-queue.md`) from the skill's own `wiki/` directory.
4. Iterates over known instruction filenames and appends the maintenance protocol to each one found.
5. If no instruction file is found, creates one using the detected primary filename (fallback: `AI_INSTRUCTIONS.md`).
6. If `hook_options` is set (`--install-hooks`), calls `hooks.install(hook_options)`. Remaining CLI flags (`--capture-on`, `--docs-check`, `--commit-gate`) are parsed by `hooks.install_parser()` **before** any files are touched, so a typo fails fast. Otherwise the next-steps output suggests `hooks.py install`. See [hooks](hooks.md).

The protocol's **Session Start** step distinguishes hook-enabled projects (check `capture.py --status`) from those without hooks (run `--crawl --git`). It also tells the agent how to handle pointer captures (read the file at `Source`; `Change: deleted` retires the entity) and to stage wiki updates in the same commit as code, including how to respond when the docs check or commit gate blocks a commit. A **Code Comments & TODOs** section tells the agent that comments apply only to their own scope, that code wins when a comment disagrees with it (fix the comment in the same change), and that a `TODO` is not permission to defer requested work. Deferrals go in the wiki, not in new code `TODO`s ([ADR-011](../decisions/ADR-011-sidecar-pivot.md)). Projects bootstrapped earlier keep their old protocol text, because the append is skipped when the protocol header is already present.

**Instruction files checked**: `CLAUDE.md`, `GEMINI.md`, `CURSOR.md`, `CLINE.md`, `AIDER.md`, `CONTINUE.md`, `AI_INSTRUCTIONS.md`

The script is idempotent: it skips wiki creation if `ouro/wiki/` already exists, and skips protocol append if `"Ourobor OS Maintenance Protocol"` is already present in the file.

## CLI Usage

```bash
# Run from the target project root after installing the skill
python <path-to-skill>/scripts/bootstrap.py

# Also install the git post-commit and Claude Code SessionStart hooks (opt-in)
python <path-to-skill>/scripts/bootstrap.py --install-hooks

# Any hooks.py install flags can be passed through
python <path-to-skill>/scripts/bootstrap.py --install-hooks --docs-check strict --commit-gate
```

@note The maintenance protocol text is defined as an inline string inside `bootstrap()`. If the protocol changes, it must be updated in both `bootstrap.py` and `ouro/AGENT_PROTOCOL.md` to stay in sync.

## Post-Bootstrap Next Steps

1. Read `ouro/wiki/index.md` to verify initialization.
2. Run `python ouro/scripts/capture.py --crawl` to stage the existing codebase.
3. Ask the LLM to synthesize the capture queue into structured wiki entries.
