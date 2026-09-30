@entity ProjectRoadmap
@brief Phased development plan for Ourobor OS, synthesized from docs/PLAN.md.

## Objective

Establish a compounding, product-agnostic LLM Wiki system (`ouro/wiki/`) supported by an offline-first dashboard (`ouro-webui/`). The wiki serves as the persistent knowledge base maintained by the LLM and curated by the developer.

## Phase 1: Ouro Core — COMPLETED

1. Created `ouro/wiki/schema.md` — philosophy, taxonomy, and maintenance protocols.
2. Created `ouro/wiki/index.md` — initialized the hub with links to categories.
3. Updated `CLAUDE.md` / `GEMINI.md` — LLM agent maintenance protocol appended.
4. Initialized logging and cleanup of project documentation.

@note PLAN.md references populating `ouro/wiki/entities/Parser.md` and foundational ADRs as part of Phase 1. These were not kept — the `ouro/` wiki directories must stay empty (skeleton only). See [ADR-001](../decisions/ADR-001-ouro-as-distributable-skeleton.md). The project's own documentation now lives in `wiki/` instead. See [ADR-002](../decisions/ADR-002-wiki-as-dual-purpose.md).

## Phase 2: Ouro-WebUI — COMPLETED

1. ✅ Scaffold `ouro-webui/` directory and basic structure.
2. ✅ Develop `builder.py` using `mistune` (Markdown + Doxygen tag processing) and `jinja2` (templating).
3. ✅ Create responsive, portable dashboard templates (two-column sidebar layout, mobile-responsive).
4. ✅ Integrate Doxygen tag renderer via regex preprocessing (`@entity`, `@brief`, `@note`, `@warning`).
5. ✅ Verify generation and portability of the dashboard.

## Phase 3: Observability App & Sidecar Vault — IN PROGRESS

An observability, interpretability and documentation app for vibecoders and professionals: explain code, and test values or debug more easily. See [ADR-011](../decisions/ADR-011-sidecar-pivot.md) and `docs/spec-v0.3-sidecar.md` (v0.3.2).

0. ✅ **Measure and onboard**:
   - `ouro/scripts/claim_scan.py` shipped in the skill ([claim_scan](../entities/claim_scan.md)), with `--wiki` baseline pages.
   - Agent Onboarding checklist added to `SKILL.md`.
   - `bootstrap.py` fills in the real skill path.
   - Code Comments & TODOs rule in the protocol and in AGENT.md.
0. ⬜ **Exit check**: onboard agent-heavy external repos and record their baselines.
1. ⬜ **Claim ledger** (no LLM): `ouro claims`, static HTML in plain-English and technical modes, agent feed through the hooks, `--vault` / `OURO_VAULT`.
2. ⬜ **Ask & Verify**: explanations, suggested tests, value probes, and one-click local verify with the project's own runner in a throwaway worktree (*inferred* → *verified*).
3. ⬜ **Trace view and vibecoder flows**: `sys.settrace` trace view from real runs, guided "what happens if…?" flows, vault mode as the default.
- Deferred: isolated sandbox (for untrusted repos), LSP/SCIP, local UI app, LLM "contradicted" judge, advisory Pass Gate, vault sync.

## Verification Criteria

These define what "done" looks like for the current phase:

| Criterion | Status |
|-----------|--------|
| LLM can look up a decision or entity in the wiki | ✅ Met — `wiki/` is now populated |
| `python ouro-webui/builder.py` generates a functional, linked dashboard | ✅ Met |
| Wiki structure is portable and drop-in ready | ✅ Met — `ouro/` skeleton is clean |

## Source

Synthesized from `docs/PLAN.md`. That file can be considered superseded by this entry and the broader `wiki/` documentation. It is retained in `docs/` as a historical artifact.
