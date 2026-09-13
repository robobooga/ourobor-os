@entity CaptureLoop
@brief The core knowledge accumulation loop: raw material is captured into a queue, synthesized by an LLM into structured wiki entries, then the queue is cleared.

## Overview

The capture-synthesize loop is the central operational pattern of Ourobor OS. It defines how knowledge moves from the codebase into the persistent wiki without interrupting the development flow.

## The Loop

```
[Code / Architecture Notes]
          |
          | python ouro/scripts/capture.py --crawl
          | python ouro/scripts/capture.py path/to/file.py
          | python ouro/scripts/capture.py "raw note"
          | git commit → post-commit hook → capture.py --from-commit HEAD   (automatic, opt-in, default)
          | git commit → pre-commit hook  → capture.py --from-index         (alternative: queue ships in the commit)
          v
  ouro/wiki/capture-queue.md        (staging area, one entry per file)
          |
          | SessionStart hook → capture.py --status   (Claude Code, opt-in)
          | Stop hook → agent documents its own changes before finishing a turn   (Claude Code, opt-in)
          | LLM reads queue, synthesizes entries
          v
  ouro/wiki/entities/  (module docs)
  ouro/wiki/patterns/  (reusable patterns)
  ouro/wiki/decisions/ (ADRs)
          |
          | python ouro/scripts/capture.py --pop
          v
  Entry removed from queue
          |
          | Update ouro/wiki/index.md
          v
  Wiki catalog stays current
```

## Roles

| Actor | Responsibility |
|-------|----------------|
| Developer | Triggers captures (or commits, with hooks installed); curates what gets staged |
| `capture.py` | Moves raw content or commit pointers into the queue |
| `hooks.py` | Optionally wires capture into git commits, checks that docs ship with code, and prompts/gates the agent |
| LLM agent | Reads queue, synthesizes structured docs, pops processed entries |
| `index.md` | Maintained as the always-current catalog |

## When to Trigger a Capture

- After writing or significantly refactoring a module
- When making an architectural decision worth preserving
- When identifying a reusable pattern
- On every commit, automatically, when hooks are installed ([ADR-008](../decisions/ADR-008-automatic-capture-hooks.md))
- At the start of a session without hooks — use `--crawl --git` to catch drift on recently touched files; use bare `--crawl` only for initial wiki population
- Before a release (verify parity between code and wiki)

## Synthesis Guidelines

When the LLM processes a queue entry:

1. Read the full capture to understand context. For pointer entries, read the current file at `Source`; `Change: deleted` means update or remove the entity.
2. Check `index.md` and existing entities — don't create duplicates.
3. Determine the correct destination: `entities/`, `patterns/`, or `decisions/`.
4. Apply required tags: `@entity` and `@brief` are mandatory.
5. Extract critical code logic using `@snippet` blocks.
6. Run `capture.py --pop` to remove the processed entry.
7. Update `index.md` with a link to the new file.
8. When committing code, stage the wiki updates in the same commit. The `--docs-check` pre-commit hook and the `--commit-gate` agent hook enforce this when installed ([ADR-009](../decisions/ADR-009-pre-commit-docs-hooks.md)).

@note Synthesis requires an LLM agent in an active session; no hook calls an LLM itself. Hooks automate capture and the reminder at session start. With `--stop-hook`, the running Claude Code agent is asked to document its changes before it finishes a turn ([ADR-010](../decisions/ADR-010-stop-hook-doc-synthesis.md)). The queue is a buffer and staging area, not an autonomous pipeline.

@warning Avoid letting the queue grow stale. Long queues lose context fidelity and become expensive for the LLM to process in a single session. Process incrementally, not in bulk.
