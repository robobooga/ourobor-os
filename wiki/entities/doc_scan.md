@entity doc_scan
@brief Read-only, stdlib-only Phase 1 scan that shortlists Markdown doc sections the code may have outgrown: broken references, and cited code that changed after the citing paragraph was last edited. `--wiki` merges the shortlist into `ouro/wiki/maps/doc-drift.md` for the agent to confirm or dismiss.

## Overview

`ouro/scripts/doc_scan.py` is the deterministic half of Phase 1 ([ADR-011](../decisions/ADR-011-sidecar-pivot.md), [ADR-013](../decisions/ADR-013-doc-scan-heuristics.md)). It never calls an LLM. It only produces a ranked shortlist. The agent decides what is real by reading the code, following onboarding step 5 in `SKILL.md`. The page format and the merge rules live in [drift_page](drift_page.md).

## Usage

```bash
python <path-to-skill>/scripts/doc_scan.py [repo_path] [--json] [--limit N] [--wiki] [--include-skill]
```

- `--limit` (default 10): how many candidates are printed, and how many unconfirmed entries are raised on the page.
- `--wiki`: merges into `ouro/wiki/maps/doc-drift.md` in the scanned project. It exits with an error if `ouro/wiki/` doesn't exist. **Never pass it in this repo** ([ADR-001](../decisions/ADR-001-ouro-as-distributable-skeleton.md)).
- `--include-skill`: also scans the skill's own docs (for developing Ourobor OS).

## How it works

1. **Docs**: tracked `*.md` / `*.markdown` files, minus vendored and build dirs, generated pages under `ouro/wiki/`, symlinked aliases (`CLAUDE.md -> AGENTS.md`), and (by default) the skill's own directory.
2. **Sections and paragraphs**: ATX headings split a doc into sections; fenced code is skipped. Within a section, each prose block, list item or table row is a *paragraph*, the unit a statement is dated by.
3. **References** per line: backticked spans and relative Markdown links. A span is a *path* if it contains `/` or a dotted name that isn't an identifier; otherwise a *symbol*. A bare file name like `poiAccess.ts` whose suffix appears among tracked files is treated as a path. Spans with spaces, globs, placeholders (`<name>`) or URLs are ignored.
4. **Resolution**:
   - Paths resolve relative to the doc, then to the repo root, then as a unique path suffix (`world/physics.ts` → `src/world/physics.ts`). More than 3 matches is too ambiguous to use.
   - Symbols are searched with `git grep -lwF` outside Markdown. Only identifiers that look like code count (snake_case, camelCase, or PascalCase with 2+ capitals), so `Surface` or `true` are ignored. Call arguments are stripped (`beginFrame(dt)` → `beginFrame`), and for dotted names the last code-like part is searched (`PICKUP_ACCESS.kerbHighways` → `kerbHighways`). When the section also cites a file the symbol appears in, only that file dates it.
5. **Broken**: a link or a rooted path (first segment is a tracked top-level entry) that resolves to nothing and isn't gitignored, or a symbol with no hits. Bare names (`credentials.json`) and non-paths (`feat/doc-scan`, `text/html`) are never broken.
6. **Moved**: for each cited *file* (directories are only checked for existence), the `git log --no-merges` commits with a committer time later than the paragraph's newest `git blame` line. Committer time is used on both sides so rebases don't reorder them.
7. **Wording**: in a paragraph that has a broken or moved reference, provisional phrases (`stopgap`, `workaround`, `for now`, `not yet`, `nothing [currently] imports`, `proper fix`, `will be`, `another change`, ...) are recorded, and the claim line moves to the first such sentence.
8. **Score** per section:
   - 5 per broken path or link, plus 2 per broken symbol.
   - The commit count of the most-changed cited file (capped at 10), plus the number of moved files (capped at 5). This moved score is halved for docs under `decisions/`, `adr/` or `adrs/`, because ADRs are historical records.
   - 4 per provisional phrase, up to 2.
9. **Code state**: the short SHA of the newest commit touching any cited file. [drift_page](drift_page.md) uses it to decide when a dismissed entry should come back.

@snippet moved-check
```python
later = {sha for sha, ts in history if ts > para_time}
```

## Field test: dabao-dasher (2026-10-25)

Run on a clone of dabao-dasher (17 docs, 326 tracked files, about 3 s):
- **Known positives** (the two drifts the agent found by hand on 2026-09-30), at `99d5c22^`, the commit before the AUDIO fix: `docs/ENGINE.md § Why pickups move to the kerb` ranks **#1** ("proper fix", "stopgap"; `poiAccess.ts` changed since) and `docs/AUDIO.md § Audio (AUD-1)` ranks **#5** ("nothing currently imports"; `src/app.ts` changed since).
- **At HEAD** the AUDIO entry is gone, because the doc was fixed. The kerb entry is still #1, because it is still unfixed.
- **New finding at #2**: `docs/MAPGEN.md § Stages` lists 15 of the 37 `tools/mapgen/*.ts` modules. The missing ones include `poiDoors.ts`, which does the kerb fix, and the hawker and void-deck modules.
- **Clear false positive at #3**: `docs/GRAPHICS.md § Plan` cites files that are planned in a parked roadmap.
- The rest of the top 10 has not been labelled yet. That review is part of the dabao-dasher re-run (roadmap Next Steps) and decides the ≥50% precision criterion.

Tuning that came out of this run (each change was checked against the two known positives):
- Directories don't date code. `src/` and `tests/` changed after every doc edit and filled the top 10 with rules from `AGENTS.md`.
- Each table row and list item is dated on its own. Before this, one 40-row module table scored 55.
- The moved score is driven by the most-changed file, not the commit total.
- Symlinked aliases are skipped, gitignored directories (`public/tiles/`) are never broken, and call arguments are stripped from symbols.
- Bare `until` was dropped from the wording list (descriptive use, "until the player has moved"), and the wording weight was raised from 3 to 4.

## Dogfood: ourobor-os (2026-10-25)

`--include-skill`: 36 docs, 70 candidates.
- #1, `wiki/entities/bootstrap.md § bootstrap()`, was partly real: its "Existing docs" paragraph didn't mention the `doc_scan` line this change added to the protocol, and it was fixed. Its broken references (`docs/adr`, `docs/adrs`) are example names, so they are false positives.
- #2–#4 are field-test notes that quote dabao-dasher paths (`docs/AUDIO.md`), which are broken here by design. This kind of false positive is expected in docs that describe other repos.

@note Run as a script, `main()` goes through `runlog.run()` ([runlog](runlog.md)).

## Next

- Label the full top 10 on dabao-dasher and on a Python repo.
- Possible signal suggested by the MAPGEN case: tracked files added to a directory a section enumerates, but not named in it.
- Comment claims from [claim_scan](claim_scan.md) feeding the same page.
- The agent feed through hooks, and `--vault`.
