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
4. Iterates over known instruction filenames and appends the maintenance protocol to each one found. Before appending, every `<path-to-skill>` placeholder in the protocol is replaced with the actual skill location from `skill_path_for_docs()`: project-relative if the skill is inside the project (for example `.claude/skills/ouro`), `~/`-relative if it is under the home directory, and absolute otherwise. Agents in later sessions can then run commands without having to find the skill.
5. If no instruction file is found, creates one using the detected primary filename (fallback: `AI_INSTRUCTIONS.md`).
6. If `hook_options` is set (`--install-hooks`), calls `hooks.install(hook_options)`. Remaining CLI flags (`--capture-on`, `--docs-check`, `--commit-gate`) are parsed by `hooks.install_parser()` **before** any files are touched, so a typo fails fast. Otherwise the next-steps output suggests `hooks.py install`. See [hooks](hooks.md).

The protocol's **Session Start** step distinguishes hook-enabled projects (check `capture.py --status`) from those without hooks (run `--crawl --git`). It also tells the agent how to handle pointer captures (read the file at `Source`; `Change: deleted` retires the entity) and to stage wiki updates in the same commit as code, including how to respond when the docs check or commit gate blocks a commit. A **Code Comments & TODOs** section tells the agent that comments apply only to their own scope, that code wins when a comment disagrees with it (fix the comment in the same change), and that a `TODO` is not permission to defer requested work. Deferrals go in the wiki, not in new code `TODO`s ([ADR-011](../decisions/ADR-011-sidecar-pivot.md)). The protocol allows one optional `# Title` heading before `@entity`/`@brief` (which must be in the first few lines) and asks for one entity per meaningful module, where a directory or package page is fine for large repos. Projects bootstrapped earlier keep their old protocol text, because the append is skipped when the protocol header is already present.

**Interpreter**: `python_command()` derives the command from `sys.executable`: its basename when `shutil.which` resolves that name to the same interpreter, else `python3` if on PATH, else the absolute path. It replaces the `<python>` placeholder in the protocol and prefixes the printed next steps, so projects without a `python` on PATH get commands that run.

**Existing docs**: `find_project_docs()` looks for `docs/` or `doc/` and an ADR dir (`docs/adr`, `docs/adrs`, `docs/decisions`, `adr/`, and similar). When found, bootstrap prints the detection and appends an "Existing project docs" subsection to the protocol: existing docs stay the source of truth, wiki pages link to them, ADRs go in the detected dir, and code/doc contradictions are recorded in `ouro/wiki/maps/doc-drift.md` and fixed.

**Instruction files checked**: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CURSOR.md`, `CLINE.md`, `AIDER.md`, `CONTINUE.md`, `AI_INSTRUCTIONS.md`. Files are deduplicated by resolved path, so a `CLAUDE.md -> AGENTS.md` symlink gets the protocol once.

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

@note After bootstrapping, the next steps printed are: run `claim_scan.py --wiki` (comment/TODO baseline), run `capture.py --crawl`, have the LLM synthesize, and optionally install hooks. These are the same steps as the Agent Onboarding checklist in `SKILL.md`.

@note The maintenance protocol text is defined as an inline string inside `bootstrap()`. If the protocol changes, it must be updated in both `bootstrap.py` and `ouro/AGENT_PROTOCOL.md` to stay in sync.

## Post-Bootstrap Next Steps

1. Read `ouro/wiki/index.md` to verify initialization.
2. Run `python ouro/scripts/capture.py --crawl` to stage the existing codebase.
3. Ask the LLM to synthesize the capture queue into structured wiki entries.

@note Run as a script, its `main()` goes through `runlog.run()`, which logs argv, exit code and output locally to `~/.ouro/runs/` ([runlog](runlog.md), [ADR-012](../decisions/ADR-012-local-run-log.md)). Set `OURO_RUNLOG=off` to disable.
