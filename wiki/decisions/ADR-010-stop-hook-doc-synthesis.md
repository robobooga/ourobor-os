@entity ADR-010
@brief `--stop-hook` installs a Claude Code Stop hook: when the agent ends a turn with code changes but no wiki updates, the hook blocks once so the agent already running writes the docs in the same session. No separate LLM call is made.

## Context

[ADR-008](ADR-008-automatic-capture-hooks.md) and [ADR-009](ADR-009-pre-commit-docs-hooks.md) automate *capture* and *checking*, but no hook causes documentation to be written. Synthesis still needed someone to ask the agent, or a blocked commit to prompt it. The goal is to have the LLM write the docs automatically.

The agent that just changed the code is the best author of its documentation: it knows *why* the change was made, and it is already running. Claude Code's `Stop` event fires when the agent is about to end its turn. A Stop hook that exits with code 2 prevents stopping, and Claude continues with the hook's stderr as its instruction.

## Decision

`hooks.py install --stop-hook` adds a `Stop` entry running `hooks.py claude-stop-hook`, which:

1. **Allows** the stop (exit 0) when `stop_hook_active` is true, meaning Claude is already continuing because of a Stop hook. This prevents loops.
2. Evaluates `capture.undocumented_changes(include_unstaged=True, include_untracked=True)`: capturable files changed anywhere in the working tree, returned only when no `ouro/wiki/` page (other than the queue) changed.
3. **Blocks** (exit 2) with a message listing the files and asking the agent to update the relevant entity, pattern, or decision pages, `index.md`, and pop related captures. The message also allows the agent to reply briefly that the work is unfinished, exploratory, not its own, or needs no docs.
4. **Asks at most once per session for the same contents.** `.git/ouro-stop-hook.json` stores `{session_id, fingerprint}`, where the fingerprint comes from `capture.changes_fingerprint()` over the listed files' contents. The hook blocks again only when the session or the file contents change.
5. **Fails open.** `OURO_SKIP_DOCS_CHECK` in the environment, a non-git directory, malformed input, or any error all allow the stop. The settings command is guarded with `[ -f <script> ]`, because Python's "can't open file" error exits with code 2, which Claude Code would treat as a block if the skill were moved or deleted. The same guard was applied to the SessionStart and commit-gate commands.

## Alternatives Considered

- **Headless synthesizer** (`claude -p` or another LLM CLI run by a script): Works outside agent sessions, but each run is a separate paid LLM call, and scripted `--bare` runs need an API key. The docs are written without the reasoning behind the change, the working tree is edited while the developer works, and the docs land in a later commit. Deferred; it may be added later for commits made outside agent sessions.
- **Run the headless synthesizer from post-commit**: All of the above on every commit, plus background locking and overlapping runs.
- **PreCompact hook**: Blocking it cancels compaction, which can make `/compact` unusable. It also fires based on context size, not when work is finished.
- **`prompt` / `agent` hook types**: Not available on the Stop event, and a fresh subagent lacks the change context anyway.
- **Block on every Stop with undocumented changes**: Simple, but it nags on every turn of an exploratory or work-in-progress session. The fingerprint limits it to once per distinct set of changes.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Cost / credentials | None beyond the session already running |
| Doc quality | Written with full context of the change |
| Timing | Before commit, so the ADR-009 docs check and commit gate pass naturally |
| Interruptions | At most one extra continuation per session per distinct set of changes |
| Precision | Coarse "any wiki change counts" rule, shared with ADR-009; later code changes in a turn with existing wiki edits are not flagged |
| Scope of changes | Includes the user's own uncommitted edits; the agent may decline in one sentence |
| Coverage | Claude Code only; also fires in `claude -p` runs that load the project's settings |

## Rationale

Reusing the active agent turns "remember to synthesize" into the natural end of every task, at no extra cost. The docs are written by the only party that understands the change, and they're written before the commit. `stop_hook_active`, the per-session content fingerprint, and fail-open behavior keep the hook from trapping, nagging, or breaking a session.
