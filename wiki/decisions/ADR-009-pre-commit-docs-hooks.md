@entity ADR-009
@brief Adds opt-in pre-commit hooks so documentation can ship in the same commit as the feature: a pre-commit docs check (warn/strict), a Claude Code commit gate, and a pre-commit capture mode. Capture modes are mutually exclusive and `hooks.py install` is declarative.

## Context

[ADR-008](ADR-008-automatic-capture-hooks.md) automated capture in a post-commit hook. The docs for a change still land in a *later* commit (or never), because the queue is only synthesized afterwards. The goal is for a feature commit to carry its documentation.

Hooks cannot write documentation — synthesis needs an LLM. So "docs in the same commit" can only be achieved by making sure synthesis happens **before** committing, and by checking that it did.

## Decision

Three independent, opt-in `hooks.py install` flags:

1. **`--docs-check warn|strict`** — git `pre-commit` runs `capture.py --check-docs [--strict]`. `undocumented_changes()` lists staged files that pass `skip_reason()` (code, not secrets/binaries/ignored dirs) **when no staged path under `ouro/wiki/` other than `capture-queue.md` exists**. `warn` prints the list; `strict` exits 1. Bypass once with `OURO_SKIP_DOCS_CHECK=1` (or `--no-verify`). The hook block skips itself when Python or `capture.py` is missing, and internal errors never fail the commit.
2. **`--commit-gate`** — Claude Code `PreToolUse` hook (matcher `Bash`) running `hooks.py claude-commit-gate`. It applies the same rule to `git commit` commands the agent runs and exits 2 with a message listing the files, which Claude Code feeds back to the agent. `-a`/`--all` commits also include unstaged tracked changes. `OURO_SKIP_DOCS_CHECK=1` in the command allows it.
3. **`--capture-on pre-commit`** — git `pre-commit` runs `capture.py --from-index`: pointer entries for staged files with `Commit: staged`, then `git add ouro/wiki/capture-queue.md` so the entries ship in the same commit.

Supporting decisions:
- **One capture mode** (`post-commit` default, `pre-commit`, or `none`). With both, post-commit would replace the `staged` entry the commit just included with a SHA entry, leaving the queue dirty after every commit.
- **Declarative install**: each run applies exactly the flags given, adding, updating, or removing marked blocks and Claude hook entries accordingly.
- **Protocol**: agents are told to stage wiki updates with the code they commit and how to respond when blocked.

## Alternatives Considered

- **Run synthesis (an LLM) in pre-commit**: The only way for a hook to *produce* docs. Rejected for the same reasons as ADR-008: slow, costly, networked, non-deterministic, credentials everywhere.
- **Gate on pending queue entries** ("block if the queue isn't empty"): Rejected. With post-commit capture, every commit, even a documented one, re-queues its files, so the next commit would always be blocked.
- **Per-file entity mapping check** (require `entities/<module>.md` for each changed module): More precise, but there is no reliable file→entity mapping; entities are named and split by the agent. "Any wiki page changed" is coarse but predictable.
- **Only `--no-verify` as a bypass**: Also skips linters and other hooks; a scoped env var is friendlier for docs-irrelevant commits.
- **Pre-commit capture only** (the first idea raised): Ships a to-do list, not docs, so it doesn't achieve the goal alone. Kept as an option for teams who want queue entries versioned with the change.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Docs in the same commit | Enforced (strict / gate) or nudged (warn); still authored by the agent or developer |
| Check precision | Coarse: a one-line wiki edit satisfies it for any number of files |
| Commit friction | `strict` blocks human commits; mitigated by `OURO_SKIP_DOCS_CHECK=1` |
| Agent coverage | Commit gate is Claude Code–only and regex-based (aliases/scripts not gated); the git docs check covers everyone |
| Pre-commit capture | Queue entries versioned with the change; an aborted commit (e.g. a failing later hook) leaves captures staged |
| `git commit <paths>` | Git restores the real index afterwards, leaving a stale staged queue (`MM`); the next pre-commit run re-stages the working-tree copy so the stale copy is never committed |
| Queue churn in history | Pre-commit capture commits `capture-queue.md` changes alongside code |

## Rationale

The only reliable way to get docs into a feature commit is to make the missing docs visible, or unmissable, at the moment of committing, and to put the agent in charge of writing them before it commits. A deterministic, index-based rule works identically for humans (git hook) and agents (PreToolUse gate), never needs an LLM in git, and composes with either capture mode without deadlocking.
