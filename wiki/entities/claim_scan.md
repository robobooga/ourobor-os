@entity claim_scan
@brief Read-only, stdlib-only scan of a git repo's code comments. It counts TODO deferrals by age, stale comments, and (as a review heuristic) comments with directive wording. It is shipped in the skill as step 3 of agent onboarding, and it is the seed of the Phase 1 claim ledger.

## Overview

`ouro/scripts/claim_scan.py` measures the problem [ADR-011](../decisions/ADR-011-sidecar-pivot.md) is meant to solve (comments and TODOs poisoning agent context) before any ledger or vault code is written. It never calls an LLM. The only thing it writes is the opt-in `--wiki` page. It can be pointed at any repo, which makes it the first working piece of the sidecar model.

@note It started as a root-level experiment and moved into the skill so that other projects can run it during onboarding. `scripts/package.py` lists it as a required file.

## Usage

```bash
python <path-to-skill>/scripts/claim_scan.py [repo_path] [--json] [--limit N] [--wiki] [--include-skill]
```

- `--wiki`: also writes `ouro/wiki/maps/comment-baseline.md` in the scanned project. The page has an `@entity CommentBaseline` header, a summary table, and the top rows of each section. It exits with an error if `ouro/wiki/` doesn't exist. **Never pass it in this repo**, because `ouro/wiki/` here is the empty distributable skeleton ([ADR-001](../decisions/ADR-001-ouro-as-distributable-skeleton.md)).
- `--include-skill`: by default, files under the skill's own directory are skipped, so a project that commits the skill doesn't scan it. Use this flag when developing Ourobor OS itself.

```bash
# this repo
python ouro/scripts/claim_scan.py --include-skill
```

## How it works

1. **Files**: `git ls-files`, restricted to extensions with `#` or `//` line comments. `dist/`, `node_modules/`, `vendor/`, virtualenvs, `build/` and (by default) the skill's own directory are skipped.
2. **Comments**: Python files use `tokenize`, so comment-like text inside strings is ignored. Other languages use a line-comment regex (approximate). Shebangs and encoding lines are dropped.
3. **Scope**: For Python, `ast` resolves the innermost enclosing function or class (for example `bootstrap` or `Cls.method`). Other languages have no scope yet.
4. **Blame**: `git blame --line-porcelain -w` gives each line's last-modified time. Uncommitted lines count as "now".
5. **Classification** per comment:
   - `todo`: matches `TODO|FIXME|HACK|XXX`. `age_days` comes from blame.
   - `stale`: a full-line comment whose annotated span was last changed by a different, later commit than the comment itself (compared by blame SHA and author time; there is no time-grace constant). The span is the first code statement after the comment (skipping blank lines and further comment lines), capped at `MAX_SPAN_LINES` (6). For Python, `ast` gives the statement's line range; a compound statement (`if`, `def`, ...) covers only its header, and a multi-line string ends the span at its first line. Other languages use the single next code line. Trailing comments are never marked stale, because they share a line with their code.
   - `global_wording`: a review heuristic, not a finding. It matches comments that start with `always`, `never`, `must`, `do not`, `don't` or `only`, or contain `must`. Descriptive uses such as "reused every frame" are not matched. The text report keeps it out of the headline summary and shows it in its own "Directive-worded comments" section; the JSON summary keeps the count under `global_wording_comments`.

@snippet stale-check
```python
any(blame[n][0] != comment_sha and blame[n][1] > comment_time for n in span if n in blame)
```

@warning Directive wording still over-reports: a comment like "Game logic must stay pure" is a scoped rule that happens to sound global. Treat the list as something to review.

## Precision fix (2026-09-30)

A real onboarding of a 4-day-old, agent-written repo (dabao-dasher, 123 commits) flagged 3 stale comments and 35 of 347 comments as global-sounding. A human review found all 3 stale hits accurate (for example `eslint.config.js` "Game logic must stay pure": other lines in the same config object changed later, not the rule). Two causes:
- The annotated block was every contiguous non-blank line up to 20, so edits to unrelated neighbouring lines counted. It is now one statement.
- The one-day grace period says nothing in a fast-moving repo. It was replaced by a commit comparison.

After the change, that repo shows 0 stale comments and 10 directive-worded comments (was 35). The demo repo's `src/money.py` comment ("amounts are always positive; never handle signs", above a line a later commit changed to handle signs) is still flagged stale.

## Baseline: ourobor-os (2026-09-30)

Measured with the pre-fix rules (block up to 20 lines, one-day grace):

| Metric | Before | After fixing |
|--------|--------|--------------|
| Files scanned | 6 | 6 |
| Comments | 57 | 57 |
| TODOs | 0 | 0 |
| Stale comments (no grace period) | 6 | — |
| Stale comments (1-day grace) | 2 | 0 |
| Global-wording | 1 (false positive) | 1 |

Without the grace period, 4 of the 6 hits were same-day edits (noise). The remaining 2 were real:
- `capture.py`: "Path to the capture queue" sat above a block that had grown to cover project and wiki paths.
- `bootstrap.py`: the "next steps" comment promised tips that live in a later block.

Both were rewritten.

After the move into the skill and the onboarding work, `--include-skill` scanned 7 files and 59 comments: 0 TODOs, 0 stale comments, 1 global-wording hit (the same `hooks.py` false positive). A new `bootstrap.py` comment that said "never" was reworded before commit.

Current baseline with the statement-span rules (`--include-skill`, 2026-09-30): 8 files, 70 comments, 0 TODOs, 0 stale, 0 directive-worded. (The count of 70 includes this change's own comments.)

## Verified end-to-end

In a throwaway repo with a backdated commit, a stale comment and a TODO, the skill installed at `.claude/skills/ouro` produced these results:
- `bootstrap.py` wrote `.claude/skills/ouro/scripts/...` paths into `CLAUDE.md`.
- `claim_scan.py --wiki` reported the TODO (638d, scope `fee`), the stale comment (scope `parse_amount`) and the global-wording hit, and saved the baseline page. This matches the worked example in the spec.

## Next

Onboard agent-heavy external repos and record their baselines (the Phase 0 exit check in ADR-011). The numbers decide how much Phase 1 ledger machinery is worth building.

@note Run as a script, its `main()` goes through `runlog.run()`, which logs argv, exit code and output locally to `~/.ouro/runs/` ([runlog](runlog.md), [ADR-012](../decisions/ADR-012-local-run-log.md)). Set `OURO_RUNLOG=off` to disable.
