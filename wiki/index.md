# Ourobor OS: Project Wiki

This is the internal documentation for the Ourobor OS project. It also serves as a reference example for users of the skill — this is what a populated `ouro/wiki/` looks like in practice.

> The distributable skill package lives in `ouro/`. This `wiki/` directory documents the Ourobor OS project itself and mirrors the structure users receive when they run `bootstrap.py`. See [ADR-002](decisions/ADR-002-wiki-as-dual-purpose.md).

## Core Documentation
- [Wiki Schema](schema.md) — Doxygen tag reference (`@entity`, `@brief`, `@snippet`, etc.) and maintenance protocols (capture → synthesize → pop → index).

## Entities
- [capture.py](entities/capture.md) — Stages files/text into the capture queue (deduplicated by source); `--from-commit` / `--from-index` stage pointer entries (post-/pre-commit hooks); `--check-docs` flags staged code without wiki updates; `--status` reports pending captures; `--crawl --git` stages git-changed files; `--crawl` walks a directory (initial setup); `--pop` removes the first entry for LLM synthesis.
- [bootstrap.py](entities/bootstrap.md) — One-time init: detects the LLM environment (Claude, Cursor, Aider, Continue), creates the `ouro/wiki/` tree, and appends the maintenance protocol (with the real skill path filled in, plus the Code Comments & TODOs rule) to instruction files; `--install-hooks` opts in to automatic capture. Idempotent.
- [hooks.py](entities/hooks.md) — Opt-in, declarative installer for git capture hooks (post- or pre-commit), the pre-commit docs check (warn/strict), the Claude Code SessionStart status hook, the Claude Code commit gate, and the Claude Code Stop hook that has the agent write docs before finishing. Honours `core.hooksPath`.
- [builder.py](entities/builder.md) — Converts `wiki/*.md` → `ouro-webui/dist/*.html`; processes Doxygen tags via regex, renders Markdown with `mistune`, generates grouped sidebar. Not part of the distributed skill.
- [package.py](entities/package.md) — Validates `ouro/` structure then zips it to `dist/ouro-skill.zip`. Aborts if required files/dirs are missing. Root-level only, not in the distributed skill.
- [claim_scan.py](entities/claim_scan.md) — Shipped in the skill (ADR-011 Phase 0): read-only, stdlib scan of a repo's comments for TODO age, stale comments (code changed more than a day after the comment) and global-sounding wording. `--wiki` saves `ouro/wiki/maps/comment-baseline.md`; skips the skill's own files unless `--include-skill`. Includes this repo's baseline.

## Architecture Decisions
- [ADR-001](decisions/ADR-001-ouro-as-distributable-skeleton.md) — `ouro/wiki/` subdirs stay empty (`.gitkeep` only); project docs must not ship to users at install time.
- [ADR-002](decisions/ADR-002-wiki-as-dual-purpose.md) — Root `wiki/` doubles as internal docs and a populated reference example; one directory, two jobs.
- [ADR-003](decisions/ADR-003-doxygen-tags-in-markdown.md) — Inline Doxygen-style tags in plain Markdown (not real Doxygen); readable in any viewer, provides a rendering hook for `builder.py`.
- [ADR-004](decisions/ADR-004-webui-as-separate-concern.md) — Web UI excluded from the skill package; core skill stays pure stdlib + Markdown, web UI evolves independently.
- [ADR-005](decisions/ADR-005-crawl-sensitive-file-guard.md) — `--crawl` is secure-by-default: skips ~50 credential dirs, exact sensitive filenames, and dangerous extensions. Edit constants in `capture.py` to tune.
- [ADR-006](decisions/ADR-006-collapsible-sidebar-sections.md) — Sidebar sections with >20 links use `<details>/<summary>`; active section auto-opens via inline script.
- [ADR-007](decisions/ADR-007-git-aware-crawl.md) — `--crawl --git` limits staging to git-changed files; full `--crawl` reserved for initial wiki population.
- [ADR-008](decisions/ADR-008-automatic-capture-hooks.md) — Opt-in git post-commit hook stages deduplicated pointer captures; Claude Code SessionStart hook prompts synthesis. LLMs are never called from git.
- [ADR-009](decisions/ADR-009-pre-commit-docs-hooks.md) — Docs ship with the feature: opt-in pre-commit docs check (warn/strict), Claude Code commit gate, and pre-commit capture mode; one capture mode at a time; declarative install.
- [ADR-010](decisions/ADR-010-stop-hook-doc-synthesis.md) — Opt-in Claude Code Stop hook blocks once when a turn ends with undocumented changes, so the running agent writes the docs; loop-safe via `stop_hook_active`, once per session per content fingerprint; no separate LLM call.
- [ADR-011](decisions/ADR-011-sidecar-pivot.md) — Ourobor OS is an observability, interpretability and documentation app for vibecoders and professionals, heading toward a sidecar vault. Phases: measure and onboard (shipped) → deterministic claim ledger → Ask & Verify (explanations, suggested tests, value probes, one-click local runs) → trace view. Comments are scoped claims; code wins over stale comments; a TODO is not permission to defer. Spec: `docs/spec-v0.3-sidecar.md`.

## Patterns
- [Capture-Synthesize Loop](patterns/capture-synthesize-loop.md) — The core workflow: raw code/notes → capture queue → LLM synthesizes into entities/patterns/decisions → `--pop` clears entry → `index.md` updated.

## Maps
- [System Architecture](maps/system-architecture.md) — Full directory tree, data flow diagram, and separation-of-concerns table (what ships vs. what doesn't).
- [Project Roadmap](maps/project-roadmap.md) — Phase 1 (core) and Phase 2 (web UI) complete; Phase 3 (observability app and sidecar vault, ADR-011) in progress: Phase 0 (measure and onboard) shipped.

## Capture Queue
- [Capture Queue](capture-queue.md)
