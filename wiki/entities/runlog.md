@entity runlog
@brief Local, opt-out run log. Wraps every skill script's entry point to record its arguments, exit code, duration and capped stdout/stderr in `~/.ouro/runs/<project>-<hash>/events.jsonl`, and lets agents log reports with a wiki snapshot. Nothing is transmitted.

## Overview

`ouro/scripts/runlog.py` gives the maintainer ground truth about real-world runs, especially agent-driven onboarding in other projects. See [ADR-012](../decisions/ADR-012-local-run-log.md).

## Integration

Each script ends with:

@snippet runlog-main
```python
if __name__ == '__main__':
    import runlog  # sibling module; the script's directory is on sys.path
    runlog.run('capture', main)
```

This applies to `bootstrap.py` (whose inline `__main__` code became `main()`), `capture.py`, `claim_scan.py` and `hooks.py`. Importing these modules (for example `bootstrap.py` importing `hooks`) doesn't log; only direct script runs do.

## Functions

- `run(script, main)`: tees `sys.stdout` and `sys.stderr` through `_Tee`, which keeps the first `OUTPUT_CAP` (8000) characters of each, then calls `main()`. It records the exit code from `SystemExit` (the message if `sys.exit("...")`) or `1` plus the exception text, and always re-raises. If `enabled()` is false, it calls `main()` directly.
- `append(event, root=None)`: adds `ts`, `project` and `skill_dir`, then appends one JSON line. Every error is swallowed.
- `project_root(start)`: the git top-level, falling back to the directory itself. `run_dir(root)` is `OURO_HOME/runs/<name>-<sha1(path)[:8]>`.
- `wiki_snapshot(root)`: git HEAD; each `ouro/wiki/**/*.md` page's path, byte size and whether `@entity` appears in its first 5 non-blank lines (pages usually open with a `# Title` line first); pending captures, parsed with `capture.split_entries`; and the root `*.md` files that contain the maintenance protocol.

## CLI

```bash
python <path-to-skill>/scripts/runlog.py report [--step onboarding] [--message TEXT]   # else reads stdin
python <path-to-skill>/scripts/runlog.py show [project_path] [--last 50]
python <path-to-skill>/scripts/runlog.py list
```

## Event shapes

- Script events: `{"kind": "script", "script", "argv", "exit", "seconds", "error", "output", "stderr", "output_truncated", "ts", "project", "skill_dir"}`
- Report events: `{"kind": "report", "step", "message", "snapshot": {"git_head", "wiki_pages": [{"path", "bytes", "entity"}], "pending_captures", "protocol_in"}, ...}`

@note The first real finding from the log came from a throwaway demo. After onboarding, the first `capture.py --pop` hands the agent `CLAUDE.md`, which is mostly the appended protocol boilerplate, because `--crawl` stages instruction files. Left as is until external test runs confirm how much it matters.

@warning Logs contain repo-derived text (capture content, comment text, paths) in the user's home directory. `OURO_RUNLOG=off` disables logging; `OURO_HOME` relocates it.
