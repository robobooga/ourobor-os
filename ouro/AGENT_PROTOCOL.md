# Ourobor OS Maintenance Protocol

You are responsible for maintaining the project's **LLM Wiki** in `ouro/wiki/`.

### 0. Session Start

Before doing any work, check whether the wiki has already been populated:

- **Initial setup** (no entity files in `ouro/wiki/entities/`): run a full crawl to bootstrap the wiki.
  ```bash
  python <path-to-skill>/scripts/capture.py --crawl
  ```
- **Ongoing sessions, hooks installed** (`bootstrap.py --install-hooks`): every commit already stages pointer captures automatically. Check for pending work (Claude Code shows this notice at session start):
  ```bash
  python <path-to-skill>/scripts/capture.py --status
  ```
- **Ongoing sessions, no hooks** (drift correction): run a git-aware crawl to stage only recently changed files. This is cheaper and avoids bloating the queue with unchanged code.
  ```bash
  python <path-to-skill>/scripts/capture.py --crawl --git
  ```
  To include files from the last N commits (e.g. if you want to catch changes from earlier in the week):
  ```bash
  python <path-to-skill>/scripts/capture.py --crawl --git 3
  ```

### 1. Monitor & Synthesize
- **Monitor**: Regularly check `ouro/wiki/capture-queue.md` for new snippets.
- **Synthesize**: Move snippets into appropriate `ouro/wiki/entities/`, `ouro/wiki/patterns/`, or `ouro/wiki/maps/` files using **Doxygen** tags (`@entity`, `@brief`, `@snippet`).
- **Pointer captures**: Entries with `Commit` and `Change` fields instead of content come from the git hooks (`Commit: staged` when captured at pre-commit). Read the current file at `Source` before synthesizing; `Change: deleted` means the file is gone — update or remove its entity.
- **Ship docs with the change**: When you commit code, update and `git add` the relevant wiki pages in the same commit. If the Ourobor OS docs check or commit gate blocks a commit, document the listed files, stage the wiki pages, and retry. Prefix the commit with `OURO_SKIP_DOCS_CHECK=1` only when the change needs no documentation. If an Ourobor OS Stop hook reports undocumented changes when you finish a task, document them before stopping, or reply briefly why they need no documentation yet.
- **Finalize**: After synthesis, remove processed entries from the queue:
  ```bash
  python <path-to-skill>/scripts/capture.py --pop
  ```

### 2. Doxygen Standards
- Every entity/pattern file must start with `@entity` and `@brief`.
- Use `@snippet` to mirror critical code logic.
- Use `@note` or `@warning` for architectural context.

### 3. Architecture Decision Records (ADR)
- Whenever a significant architectural decision is made, create or update an ADR in `ouro/wiki/decisions/`.
- ADRs must document:
  - **Context**: Why the decision is being made.
  - **Alternatives**: Other options considered.
  - **Trade-offs**: What was gained and what was lost.
  - **Rationale**: The reasoning behind the final choice.
- Always link new ADRs in the `ouro/wiki/index.md` file.

### 4. Code Comments & TODOs
- **Scope**: A comment applies only to the line, block, or function it sits in. Do not generalize a comment about one corner case into a rule for the whole codebase; check the code and the wiki first.
- **Staleness**: Comments drift. When a comment and the code disagree, trust the code, and fix or delete the comment in the same change.
- **Deferral**: A `TODO`/`FIXME` is not permission to defer work you were asked to do. Finish the task, or record the deferral and its reason in the wiki (capture queue or an ADR) instead of adding a new `TODO` to the code.

### 5. Maintenance Best Practices
- **Fragment**: Split files that become too large or cover too many distinct concepts.
- **Combine**: Merge highly interdependent or undersized files.
- **Parity**: Maintain 1:1 mapping between code modules and documentation.
- **Verification**: Ensure `ouro/wiki/index.md` is always up to date with new entries.
- **Consistency**: Maintain structural adherence to `ouro/wiki/schema.md`.
