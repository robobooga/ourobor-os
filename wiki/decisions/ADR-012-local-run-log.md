@entity ADR-012
@brief Every skill script logs its arguments, exit code, duration and capped stdout/stderr to a local JSONL file under `~/.ouro/runs/`. Agents add an onboarding report plus a wiki snapshot. Nothing is transmitted. Logging is on by default and disabled with `OURO_RUNLOG=off`.

## Context

The skill is now onboarded by agents on the user's behalf (the Agent Onboarding checklist in `SKILL.md`, [ADR-011](ADR-011-sidecar-pivot.md)). When the user tries it in another project, the maintainer only sees the agent's chat summary. That hides three things:
- which commands actually ran, and in what order
- what they printed, including hook messages on stderr
- what the agent wrote into the wiki

Tuning onboarding needs that ground truth, so the maintainer (or Claude working with them) can compare the run with what they would have done. The product's own principle applies here too: observability over trust.

## Decision

1. **`ouro/scripts/runlog.py`** holds the logging code. Each script's `__main__` calls `runlog.run('<script>', main)`. That records `argv`, the exit code (including `sys.exit(2)` from hooks), duration, the `sys.exit("message")` text, and stdout and stderr, each capped at 8000 characters. It appends one JSON line to `~/.ouro/runs/<project-name>-<sha1(path)[:8]>/events.jsonl`. The project is the git top-level of the working directory.
2. **Agent reports.** `runlog.py report --step <name> --message "..."` (or the message on stdin) logs the agent's summary with a wiki snapshot: the git HEAD, each `ouro/wiki/**/*.md` page's path, size and whether it has an `@entity` header, the pending capture count, and which instruction files contain the protocol. Onboarding step 6 asks the agent to log the same report it gives the user, plus anything it found confusing or skipped.
3. **Reading.** `runlog.py list` and `runlog.py show [project] [--last N]`.
4. **Local only, opt-out.** No network code exists in the module. `OURO_RUNLOG=off` (or `0`/`false`/`no`) disables it, and `OURO_HOME` relocates it. Every logging error is swallowed, so logging can't change a script's behaviour or exit code.
5. **Location outside the repo.** `~/.ouro/` is the same home the sidecar vault will use (ADR-011), so logs never pollute the target repo or show up in the docs check.

## Alternatives Considered

- **Remote telemetry:** It would show usage across users, but it sends repo-derived content (file paths, comment text, capture content) off the machine, needs consent flows and a server, and doesn't suit a local-first skill. Rejected.
- **Log file inside the project (`ouro/.runlog`):** It pollutes the target repo, needs `.gitignore` handling, and could trip the docs check. Rejected in favour of `~/.ouro/`.
- **Only the agent's report, no script logging:** It relies on the agent's own account. The point is to compare that account against what actually ran.
- **Per-function logging in each script:** More structured, but invasive. Wrapping `main()` captures everything with one line per script, and structured fields can be added later where needed.
- **Opt-in logging:** Test runs would often forget to enable it, which defeats the purpose. It is on by default, local only, and one environment variable turns it off.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Privacy | Logs contain repo-derived text (captured content, comment text) in the user's home directory; never transmitted; disable with `OURO_RUNLOG=off` |
| Size | Unbounded append-only JSONL; each event capped at ~16 KB of output; hook events (commit gate, Stop hook) add a line per agent turn or commit |
| Fidelity | Exact for scripts; agent actions between scripts are visible only through the report and the wiki snapshot |
| Robustness | Logging errors are swallowed; the wrapper re-raises `SystemExit`, so exit codes are unchanged |

## Rationale

Local, append-only logs give the ground truth needed to improve agent onboarding. They cost one line per script and send nothing anywhere. Keeping them in `~/.ouro/` matches the sidecar direction and keeps target repos clean.
