@entity ADR-008
@brief Capture is automated with an opt-in git post-commit hook that stages lightweight, deduplicated pointer entries; a Claude Code SessionStart hook prompts the agent to synthesize. Synthesis is never run from git.

## Context

Even with `--crawl --git` ([ADR-007](ADR-007-git-aware-crawl.md)), users or their agent had to remember to run capture at session start and guess how many commits back to look (`--git N`). Commits made between agent sessions were easily missed, which is exactly the staleness the project exists to prevent.

The capture-synthesize loop has two halves with very different properties:
- **Capture** is deterministic, fast, offline, and stdlib-only.
- **Synthesis** needs an LLM: slow, costs money, needs credentials, and gives non-deterministic output.

## Decision

1. **git `post-commit` hook** runs `capture.py --from-commit HEAD`. It uses `git diff-tree --no-commit-id --name-status -r --root --no-renames -z` to get the exact files in the commit and stages one **pointer entry** per file (`Source`, short `Commit`, `Change: added|modified|deleted`, no content). The same ignore/sensitive/binary filters as `--crawl` apply; deleted files are still staged so the agent can retire their entities.
2. **Deduplication**: staging any file replaces older queue entries with the same `Source` (raw notes are never deduplicated). The queue holds at most one entry per file.
3. **Claude Code `SessionStart` hook** runs `capture.py --status`, whose output is injected into the agent's context. The status command prints nothing when the queue is empty.
4. **Opt-in installation** via `bootstrap.py --install-hooks` or `hooks.py install`. It appends a marked block rather than overwriting, honours `core.hooksPath`, and ships a matching `uninstall`.

## Alternatives Considered

- **pre-commit hook**: Could add the queue to the same commit, but it slows every commit, can block it, and stages captures for commits that end up aborted. Not the default, but later added as the opt-in `--capture-on pre-commit` mode alongside a pre-commit docs check; see [ADR-009](ADR-009-pre-commit-docs-hooks.md).
- **Calling an LLM from the hook**: Fully automatic docs, but commits become slow, costly, networked, and non-deterministic; it also requires API keys in every developer environment.
- **Full-content entries from the hook**: Keeps the existing format but copies whole files into a git-tracked queue on every commit, bloating diffs and history. The content is also stale by synthesis time.
- **File-watch daemon**: Rejected in ADR-007 (persistent process, OS-specific APIs).
- **Automatic installation during bootstrap**: Less friction, but silently changing `.git/hooks` and agent settings is too intrusive for a drop-in skill.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Manual steps | None after install; capture happens on commit |
| Queue size | Small: pointer entries, one per file |
| Synthesis fidelity | Agent reads the *current* file, which may be newer than the recorded commit |
| Working tree | `capture-queue.md` shows as modified after each commit |
| Agent coverage | SessionStart hook is Claude Code–only; other tools follow the protocol's `--status` step |
| Portability | Hook bakes in the absolute path to `capture.py`; reinstall if the skill moves |
| Uncommitted work | Not captured until committed; `--crawl --git` remains available |

## Rationale

The commit is the natural unit of change and git reports its file list exactly, which removes the `--git N` guesswork. Keeping the hook deterministic and non-blocking means it can be safely left on. Pointer entries with dedup keep the queue proportional to the number of *distinct files* awaiting synthesis, not the number of commits. Recursion is avoided because `ouro` is in `IGNORED_DIRS`, so committing wiki updates stages nothing.

Implementing dedup also fixed an existing gap noted in the `capture` entity. While extracting the shared `skip_reason()` filter, the `IGNORED_DIRS` check was changed to use project-relative paths; previously a project located under a directory such as `/tmp/` or `~/build/` was skipped entirely.

## Follow-ups

- The queue path is hard-coded to `ouro/wiki/`. In this repository that is the distributable skeleton, so hooks must not be installed here until the wiki directory is configurable.
