@entity drift_page
@brief Shared module for `ouro/wiki/maps/doc-drift.md`. It parses the page's `###` entries, keeps every reviewed entry verbatim, re-raises a dismissed or fixed entry only when its code state moved, and renders the fresh unconfirmed candidates.

## Overview

`ouro/scripts/drift_page.py` has no CLI. [doc_scan](doc_scan.md) calls `write_page(root, candidates, limit)`, and comment claims from [claim_scan](claim_scan.md) are meant to use the same entry point later. It is kept separate so the page format has one owner ([ADR-013](../decisions/ADR-013-doc-scan-heuristics.md)).

## Page format

The header (`@entity DocDrift`, review instructions) and the two section headings are regenerated on every run. Everything the agent writes goes inside `###` entries:

```markdown
### docs/ENGINE.md § Why pickups move to the kerb
- Key: `docs/ENGINE.md#why-pickups-move-to-the-kerb`
- Status: confirmed
- Code state: `eae956e`
- Evidence: tools/mapgen/poiDoors.ts:12 places pickup doors outside the footprint
- ...signal lines written by the scanner...
```

- **Key**: `<doc>#<GitHub-style heading slug>`. A repeated heading gets a `-N` suffix.
- **Status**: `unconfirmed`, `confirmed`, `dismissed` or `fixed`. Parsing ignores case and a leading `**`. An entry with no Status line counts as unconfirmed.
- **Code state**: the scanner's state for the candidate when the entry was written.

## Merge rules (`merge`)

| Existing entry | Candidate this run | Result |
|----------------|--------------------|--------|
| none | yes | raised as unconfirmed |
| unconfirmed | any | dropped and regenerated from this run's candidates |
| confirmed | any | kept verbatim; not raised again |
| dismissed / fixed | same code state | kept verbatim |
| dismissed / fixed | different code state | removed and raised again as unconfirmed, with a "Previously dismissed at ..." line |
| reviewed, no Key | — | kept verbatim (hand-written entries) |

Only `limit` unconfirmed candidates are written. The section heading shows the full count, with an "...and N more" line.

@warning Text outside `###` entries is regenerated. The page header says so, but an agent that adds free-form notes between entries will lose them.

## Verified

A scratchpad test covered parsing (a `**Confirmed**` hand-written entry, section headings not leaking into the last block) and the merge cases above. A dabao-dasher run with one confirmed and one dismissed entry kept both entries verbatim across a re-run.
