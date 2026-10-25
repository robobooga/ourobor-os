@entity ADR-013
@brief `doc_scan.py` shortlists doc drift with deterministic git signals: broken references, plus cited files changed after the citing paragraph. Provisional wording only ranks candidates. Directories never date code, and the agent confirms every entry on `maps/doc-drift.md`, a page whose reviewed entries survive re-runs.

## Context

The first field test (dabao-dasher, [ADR-011](ADR-011-sidecar-pivot.md) amendment) showed that prose docs drift more than code comments. Phase 1 therefore needs a scanner that finds the doc statements most likely to be outdated, with no LLM, so the agent can check a short list rather than every doc. Both known drifts were known positives:
- `docs/AUDIO.md`: "nothing currently imports" `src/audio`.
- `docs/ENGINE.md`: "the proper fix belongs in mapgen ... this is a runtime stopgap".

## Decision

1. **Unit of dating is the paragraph; unit of reporting is the section.** Each prose block, list item or table row is dated by its newest `git blame` line (committer time). A section is reported once with its strongest evidence, and keyed `<doc>#<slug>` so reviews have a stable identity.
2. **Two signals decide candidacy:**
   - A broken reference: a rooted path or link to nothing tracked, or a code-like symbol `git grep -w` can't find.
   - Moved code: a cited **file** with commits after its paragraph.
   Cited directories are checked for existence only.
3. **Provisional wording is a ranking signal, not a finding.** Phrases like "stopgap", "for now" and "nothing imports" add to the score only in a paragraph that already has a broken or moved reference.
4. **Ranking favours depth over breadth.** The score uses the commit count of the most-changed file (capped at 10) plus the number of moved files (capped at 5). The moved score is halved for ADR directories. A broken path or link scores 5, and a broken symbol 2, because docs also name other tools' APIs.
5. **Agent confirmation through the page.** `drift_page.py` owns `maps/doc-drift.md`:
   - Entries are `###` blocks with `Key`, `Status` and `Code state` lines.
   - Confirmed, dismissed and fixed entries are kept verbatim.
   - A dismissed or fixed entry comes back only when the newest commit among its cited files differs from the one recorded on it.
   - Only unconfirmed entries are regenerated.

## Alternatives Considered

- **Section-level dating** (as written in spec v0.3.3): one late typo fix hides every older statement in the section, and one long table gets dated as a block. On dabao-dasher a 40-row module table scored 55 and buried both known positives. Rejected in favour of per-paragraph dating.
- **Dating directories by their files' commits:** in an active repo, `src/` changes after every doc edit, so instruction-file rules (`src/game` must stay pure) filled the top 10. **Dating them by files added or removed** was also tried, and was still noisy. Rejected; directories are checked for existence only.
- **Summing commits across cited files:** this rewards long sections rather than likely-wrong statements. Rejected.
- **Bare file names as broken references:** `credentials.json` and `AGENTS.md` are usually generic examples. Only rooted paths and links can break.
- **Function-level history (`git log -L`) for symbols:** more precise, but language-dependent and slow. Deferred; a symbol is dated by the file it appears in, restricted to a file the section also cites.
- **An LLM judge in the script:** out of scope for Phase 1 (spec §3, Deferred). The agent running onboarding is the judge.
- **Regenerating the whole page:** it would discard the agent's evidence and reasons. Rejected in favour of keeping reviewed entries verbatim.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Recall | Drift caused by code in a file the doc doesn't cite is caught only through other cited files or wording (the kerb case was caught because `poiAccess.ts` also changed) |
| Precision | Planned files in roadmaps read as broken references; the agent dismisses them once |
| Cost | One `git blame` per doc with references, one `git log` per cited file, one `git grep` per symbol (cached); about 3 s on a 326-file repo |
| Page edits | Free-form text outside `###` entries is regenerated |

## Rationale

The two known drifts rank #1 and #5 on dabao-dasher at the commit before the AUDIO fix, and the scan found a third, unknown drift (the MAPGEN stage table) at #2. Deterministic signals keep Phase 1 free of LLM calls. Keeping reviews on the page makes the confirm/dismiss loop cheap to re-run, and gives the ≥50% top-10 precision criterion something to measure.
