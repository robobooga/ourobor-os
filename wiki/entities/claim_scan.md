@entity claim_scan
@brief Phase 0 experiment: a read-only, stdlib-only scan of a git repo's code comments that counts TODO deferrals by age, stale comments, and comments worded as global rules. It gives a baseline before the claim ledger is built.

## Overview

`scripts/claim_scan.py` measures the problem [ADR-011](../decisions/ADR-011-sidecar-pivot.md) is meant to solve (comments and TODOs poisoning agent context) before any ledger or vault code is written. It never calls an LLM and never writes to the repo it scans. It can be pointed at any repo, which makes it the first working piece of the sidecar model.

@note It lives in root-level `scripts/`, not `ouro/scripts/`. It is an experiment and is not shipped in the skill package until the ledger design settles.

## Usage

```bash
python scripts/claim_scan.py [repo_path] [--json] [--limit N]
```

## How it works

1. **Files**: `git ls-files`, restricted to extensions with `#` or `//` line comments. `dist/`, `node_modules/`, `vendor/`, virtualenvs and `build/` are skipped.
2. **Comments**: Python files use `tokenize`, so comment-like text inside strings is ignored. Other languages use a line-comment regex (approximate). Shebangs and encoding lines are dropped.
3. **Scope**: For Python, `ast` resolves the innermost enclosing function or class (for example `bootstrap` or `Cls.method`). Other languages have no scope yet.
4. **Blame**: `git blame --line-porcelain -w` gives each line's last-modified time. Uncommitted lines count as "now".
5. **Classification** per comment:
   - `todo`: matches `TODO|FIXME|HACK|XXX`. `age_days` comes from blame.
   - `stale`: a full-line comment whose annotated block (the contiguous non-blank code lines below it, up to 20) was modified more than `STALE_GRACE_SECONDS` (one day) after the comment. Trailing comments are never marked stale, because they share a line with their code.
   - `global_wording`: absolute words (`always`, `never`, `must`, `do not`, ...) in a comment that isn't a TODO.

@snippet stale-check
```python
stale = written and latest_code and not is_trailing and latest_code - written > STALE_GRACE_SECONDS
```

@warning `global_wording` is a noisy heuristic. On this repo its one hit (`hooks.py`: "...so it is never committed") is accurate and properly scoped. Treat it as a list to review, not as findings.

## Baseline: ourobor-os (2026-09-30)

| Metric | Before | After fixing |
|--------|--------|--------------|
| Files scanned | 6 | 6 |
| Comments | 57 | 57 |
| TODOs | 0 | 0 |
| Stale comments (no grace period) | 6 | — |
| Stale comments (1-day grace) | 2 | 0 |
| Global-wording | 1 (false positive) | 1 |

Without the grace period, 4 of the 6 hits were same-day edits (noise), which is why the grace period was added. The remaining 2 were real:
- `capture.py`: "Path to the capture queue" sat above a block that had grown to cover project and wiki paths.
- `bootstrap.py`: the "next steps" comment promised tips that live in a later block.

Both were rewritten.

## Next

Run it on at least one agent-heavy external repo. If TODO and stale counts are low there too, the simple rule in the maintenance protocol may be enough, and the ledger isn't needed. That is the exit condition in ADR-011.
