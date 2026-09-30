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

## Phase 3: Sidecar Vault — IN PROGRESS

Destination: a sidecar vault outside the target repo. Work is ordered measure → deterministic ledger → Ask. See [ADR-011](../decisions/ADR-011-sidecar-pivot.md) and `docs/spec-v0.3-sidecar.md`.

0. ✅ **Measure**: `scripts/claim_scan.py` written, and this repo's baseline recorded ([claim_scan](../entities/claim_scan.md)).
0. ✅ **Rule**: the Code Comments & TODOs section added to the skill protocol and to AGENT.md, and the two stale comments in this repo fixed.
0. ⬜ **Exit check**: run `claim_scan.py` on an agent-heavy external repo; if the counts are low, stop at the rule.
1. ⬜ **Claim ledger plus agent feed** (no LLM): `ouro claims`, static HTML, and claims injected by the hooks; `--vault` / `OURO_VAULT` path override.
2. ⬜ **Ask**: answers, suggested tests or extension points, labelled *inferred*; exported only when the user asks.
- Deferred: sandbox/*verified* tier, LSP/SCIP, local UI app, LLM "contradicted" judge, advisory Pass Gate, vibecoder surfaces.

## Verification Criteria

These define what "done" looks like for the current phase:

| Criterion | Status |
|-----------|--------|
| LLM can look up a decision or entity in the wiki | ✅ Met — `wiki/` is now populated |
| `python ouro-webui/builder.py` generates a functional, linked dashboard | ✅ Met |
| Wiki structure is portable and drop-in ready | ✅ Met — `ouro/` skeleton is clean |

## Source

Synthesized from `docs/PLAN.md`. That file can be considered superseded by this entry and the broader `wiki/` documentation. It is retained in `docs/` as a historical artifact.
