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

An observability, interpretability and documentation app for vibecoders and professionals: explain code, and test values or debug more easily. See [ADR-011](../decisions/ADR-011-sidecar-pivot.md) and `docs/spec-v0.3-sidecar.md` (v0.3.3).

0. ✅ **Measure and onboard**:
   - `ouro/scripts/claim_scan.py` shipped in the skill ([claim_scan](../entities/claim_scan.md)), with `--wiki` baseline pages.
   - Agent Onboarding checklist added to `SKILL.md`.
   - `bootstrap.py` fills in the real skill path.
   - Code Comments & TODOs rule in the protocol and in AGENT.md.
   - Local run log (`runlog.py`, [ADR-012](../decisions/ADR-012-local-run-log.md)) so external test runs can be reviewed.
0. ✅ **Exit check (first run, dabao-dasher)**: comment debt was negligible, while docs drift was real (2/2). Nine onboarding defects were found and fixed in `feat/onboarding-fixes`.
0. ⬜ More field tests, including a non-TypeScript repo and a vibecoder-owned repo.
1. 🔄 **Docs-vs-code drift** (on `feat/doc-scan`: ✅ `doc_scan.py` ([doc_scan](../entities/doc_scan.md), [ADR-013](../decisions/ADR-013-doc-scan-heuristics.md)) and the `drift_page.py` page module ([drift_page](../entities/drift_page.md)) are built and wired into onboarding step 5; on dabao-dasher both known drifts rank in the top 5. ⬜ Comment claims on the same page, the agent feed, and `--vault` follow): `doc_scan.py` shortlists outdated doc statements (broken references, docs older than the code they reference); the agent confirms them into `maps/doc-drift.md`; comment claims feed the same page; agent feed through the hooks; `--vault` / `OURO_VAULT`.
2. ⬜ **Ask & Verify**: explanations, suggested tests, value probes, and one-click local verify with the project's own runner in a throwaway worktree (*inferred* → *verified*).
3. ⬜ **Trace view and vibecoder flows**: `sys.settrace` trace view from real runs, guided "what happens if…?" flows, vault mode as the default.
- Deferred: isolated sandbox (for untrusted repos), LSP/SCIP, local UI app, LLM "contradicted" judge, advisory Pass Gate, vault sync.

## Next Steps (as of 2026-10-25)

Pick up here. Work in this order. Step 5 was built first, on 2026-10-25, so the re-run in steps 2–3 can measure it.

1. **Merge [PR #2](https://github.com/robobooga/ourobor-os/pull/2)** (`feat/onboarding-fixes`): the nine onboarding fixes plus the Phase 1 retarget. Then `git checkout main && git pull`.
2. **Re-run the dabao-dasher onboarding** with the fixed skill:
   - Reinstall or update the skill (`npx skills add robobooga/ourobor-os`).
   - In `~/base/dabao-dasher`, remove the previous run's `ouro/` directory and the appended protocol section in `AGENTS.md`, or start on a fresh branch from `master`.
   - Ask the agent: "Set up Ourobor OS in this project."
3. **Review the run**:
   - Run `python3 ouro/scripts/runlog.py show ~/base/dabao-dasher --last 200` and compare it with the previous run (the first report, from 2026-09-30, is in the same log).
   - Check that the agent:
     - clears captures with `--done` rather than editing the queue by hand
     - runs `doc_scan.py --wiki` and marks every raised entry on `maps/doc-drift.md` confirmed or dismissed. `docs/AUDIO.md` is already fixed at HEAD; the ENGINE.md kerb stopgap and the MAPGEN.md stage table should come out confirmed, and GRAPHICS.md dismissed.
     - Count the confirmed entries in the top 10 (the ≥50% precision criterion), and record the count in [doc_scan](../entities/doc_scan.md).
     - uses the `python3` commands bootstrap wrote
     - needs no workarounds
   - Record any new deviations in the capture queue or as an ADR-011 amendment.
4. **Field-test two more repos** (Phase 0 item above): one non-TypeScript repo, ideally Python, and one owned by a vibecoder. Log both, and compare doc drift with comment drift again before committing to the Phase 1 design.
5. ✅ **Build `doc_scan.py`** (Phase 1), built 2026-10-25 on `feat/doc-scan` ([doc_scan](../entities/doc_scan.md), [ADR-013](../decisions/ADR-013-doc-scan-heuristics.md)):
   - Known-positive test passed: at the commit before the AUDIO fix, the two drifts rank #1 and #5. It also found an unknown drift at #2 (the MAPGEN.md stage table).
   - Still open: the success criterion (at least 50% of the top 10 confirmed) needs the full labelling in step 3, and a second repo from step 4.
   - Next for Phase 1: comment claims on the same page, the agent feed through hooks, and `--vault`.
6. **Open decisions**, with the defaults chosen in PR #2 (change them if the field tests disagree):
   - Crawl pointer `Commit` label is HEAD even for dirty files.
   - `claim_scan` span cap is 6 lines.
   - Non-Python comments annotate only the next line.
   - Spec §9 open questions: runner detection for local verify, the "trusted repo" rule, prose-claim patterns for `doc_scan`.
7. **Known rough edge:**
   - The crawl on dabao-dasher still queues 291 entries (about 68 KB), including 91 test files.
   - Consider letting onboarding crawl only source directories (`--crawl src tools`), or skipping tests by default.
   - Decide after the re-run in step 2.

## Verification Criteria

These define what "done" looks like for the current phase:

| Criterion | Status |
|-----------|--------|
| LLM can look up a decision or entity in the wiki | ✅ Met — `wiki/` is now populated |
| `python ouro-webui/builder.py` generates a functional, linked dashboard | ✅ Met |
| Wiki structure is portable and drop-in ready | ✅ Met — `ouro/` skeleton is clean |

## Source

Synthesized from `docs/PLAN.md`. That file can be considered superseded by this entry and the broader `wiki/` documentation. It is retained in `docs/` as a historical artifact.
