# Ourobor OS Sidecar: Observability & Explainability Vault

**Version:** 0.3.3-Draft
**Date:** 2026-09-30
**Supersedes:** 0.3.2 (Phase 1 retargeted from code comments to docs-vs-code drift after the first field test), 0.3.1, 0.3.0, and 0.2.0-Draft ("Sidecar Control Plane & Visual Debugger")
**Decision record:** [ADR-011](../wiki/decisions/ADR-011-sidecar-pivot.md)

---

## 1. Vision

Ourobor OS is an **observability, interpretability and documentation app for code, for vibecoders and professional engineers alike**. It does two things for its users:

- **Explain your code easily.** It says what the code does, why it does it, and which of its docs and comments can still be trusted.
- **Test values and debug more easily.** You ask "does `abc()` work with numbers, not just letters?" and get an answer, a test that checks it, and a real run that confirms it.

It is heading toward being a **sidecar that sits above a codebase rather than inside it**. You point it at a directory, the way you open a folder as an Obsidian vault, and it keeps a living, honest account of the code outside the repo.

Two problems motivate it:

1. **Comprehension.** Agent-written code is dense and high-volume. Vibecoders can't read it easily, and professionals reviewing it don't have time to.
2. **Context poisoning.** In agent-maintained repos, agents over-trust what they read: design docs, READMEs, in-code comments and `TODO`s. A doc that says "nothing imports `src/audio`" after something does, or a comment about one corner case read as a rule for the whole codebase, sends the agent and a human reader the wrong way.

The core idea behind the explanations: **documentation is claims, not truth.** Every statement in a doc or comment applies to some code and was written at some point in time. The code may since have moved on without it. The first field test showed this happens most in Markdown docs, not code comments (see "Field test" below). Every answer Ourobor OS gives says how it knows: inferred from reading the code, or verified by running it.

### A concrete failure

```python
def parse_amount(s):
    # amounts are always positive; never handle signs
    value = Decimal(s.strip())
    return -value if s.startswith('(') else value
```

`parse_amount` was changed to handle refunds, but its comment wasn't. An agent editing `format_ledger()` reads the comment, generalizes "amounts are always positive", and removes a sign check elsewhere. A vibecoder reading the file believes the same thing. The comment was scoped to one function, and it had also gone stale.

`claim_scan.py` (Phase 0, shipped) already reports it:

```
src/money.py:5 [parse_amount] (638d) amounts are always positive; never handle signs   ← stale, global wording
```

### Field test: dabao-dasher (2026-09-30)

An agent onboarded a 4-day-old, agent-written TypeScript game (251 files, 123 commits) with the Phase 0 checklist.
- **Code comments were clean.** It found 0 `TODO`s. All 3 comments flagged stale turned out, on review, to still be accurate: the code near them had changed, not the rule they state.
- **The docs had drifted.**
  - `docs/AUDIO.md` said nothing imports `src/audio`, but `AudioWiring` does.
  - `docs/ENGINE.md` called a runtime workaround a stopgap awaiting a mapgen fix, and `tools/mapgen/poiDoors.ts` now does that fix.
- **The agent found both drifts itself**, by reading `docs/` while documenting modules. It recorded them in a `maps/doc-drift.md` page.

In this repo's agent workflow, prose docs drift faster than comments, because agents update code and nearby comments together but seldom revisit design docs. Phase 1 therefore targets docs-vs-code drift first.

Ask (Phase 2) can then check the claim itself. "Does `parse_amount` handle negative amounts?" produces an inferred answer citing the code, a suggested test for `parse_amount("(5.00)")`, and, with one click, a verified result from running that test.

## 2. Personas

Both personas are served from Phase 1 onward. They share one engine and differ only in presentation.

| Persona | Core questions | Presentation |
|---------|----------------|--------------|
| Vibecoder (non-technical builder) | "What does this do? Does it work if I give it X? Why did it break?" | Plain-English explanations, one-click checks, no jargon by default |
| Professional engineer / maintainer | "Which docs, comments and TODOs can I trust? What are the edge cases? Is agent output degrading the code?" | `file:line` citations, scopes, ages, raw test code |
| Coding agents (served on the user's behalf) | Which docs and comments are current | Drift and claim feed injected by hooks |

## 3. Phasing

The order is set by one rule: **ship what users can rely on first. That means deterministic facts, then real test runs, then LLM interpretation, and the expensive infrastructure only once the rest has proved useful.**

### Phase 0: Measure and onboard (shipped)
- **`ouro/scripts/claim_scan.py`**, shipped in the skill. It is a read-only, stdlib-only scan that reports TODOs by age, stale comments, and comments worded as global rules. `--wiki` saves `ouro/wiki/maps/comment-baseline.md`. See [claim_scan](../wiki/entities/claim_scan.md).
- **Agent Onboarding** in `SKILL.md`. A user says "set up Ourobor OS in this project", and the agent then:
  - bootstraps
  - measures
  - documents the key modules
  - offers hooks
  - reports back
  Every step is safe to re-run.
- **Protocol rule** (Code Comments & TODOs):
  - comments apply only to their own scope
  - code wins when it disagrees with a comment
  - a `TODO` is not permission to defer requested work
- **Local run log** ([ADR-012](../wiki/decisions/ADR-012-local-run-log.md)): every script run and the agent's onboarding report are logged to `~/.ouro/runs/`, so real onboardings can be reviewed.
- **Exit check, first result (dabao-dasher):**
  - Comment and TODO debt was negligible, and the stale-comment heuristic scored 0 of 3.
  - Docs drift was real (2 of 2 confirmed).
  - This moves Phase 1 from the comment ledger to docs-vs-code drift.
  - It also surfaced nine onboarding fixes:
    - crawl ignoring `.gitignore`
    - full-content queue entries too large
    - no batch completion of captures
    - `python` vs `python3`
    - `AGENTS.md` and symlinks
    - existing `docs/` and ADR conventions
    - a heading before `@entity`
    - parity granularity
    - scan precision
  All nine are fixed in the same release.

### Phase 1: Docs-vs-code drift (deterministic shortlist, agent-confirmed)
Prose docs (`docs/**/*.md`, `README*`, ADRs, instruction files) make claims about code. Phase 1 finds the claims most likely to be out of date and has the agent confirm them.
- **`doc_scan.py` (deterministic, no LLM):**
  - Extracts code references from Markdown: backticked paths (`src/audio/`), symbols (`AudioWiring`), commands, and links to source files.
  - **Broken references**: a path that doesn't exist, or a symbol not found in tracked files (via `git grep -w`).
  - **Outdated sections**: each doc section (by heading) is dated with `git blame`, and each referenced file with `git log`. A section is a drift candidate when code it references changed in commits after the section was last edited. Candidates are ranked by how many commits and files have moved since.
  - Output: a text or JSON report, and `--wiki` writes `ouro/wiki/maps/doc-drift.md`, adopting the format the dabao-dasher agent invented. Confirmed entries are kept across re-runs, and new candidates are marked *unconfirmed*.
- **Agent confirmation (the protocol, not an LLM call from a script):**
  - Onboarding and session-start steps ask the agent to check the top candidates against the code.
  - For each one it marks the entry *confirmed* (with the code evidence as `file:line`) or *dismissed* (with the reason).
  - It then fixes the doc when the user agrees.
  - Dismissals are recorded so a candidate isn't raised again until its code changes.
- **Comment claims** (`claim_scan.py`) remain a secondary source feeding the same page and the same confirm/dismiss loop:
  - stale = the first statement under a comment changed in a later commit
  - `TODO` age
  - a review-only wording heuristic
- **Outputs:**
  - the CLI report
  - the `doc-drift.md` wiki page
  - static HTML via `builder.py`, with a plain-English mode ("this design doc describes audio as unused, but the game now plays sounds through `AudioWiring`")
  - an **agent feed** through the existing hooks, so an agent opening a doc with confirmed drift is told which statements are outdated
- **Precision target:** at least 50% of the top-10 candidates confirmed on a labelled sample, before the feed is enabled by default.

### Phase 2: Ask & Verify (the core experience)
- **Ask.** Natural-language questions are routed by intent. The response is one of three kinds:
  - **Explanation**: what the code does, in plain English or technical detail depending on the user, with `file:line` citations and the relevant doc statements and comments. A statement with confirmed drift is shown as outdated, never used as evidence on its own.
  - **Suggested tests**: tests written in the project's own framework that check the behaviour asked about.
  - **Extension points**: where and how to extend the code.
- **Value probes.** For "try `abc('123')`" style questions, generate a minimal harness that calls the function with the given values. It records the return values, exceptions and printed output, and shows them as a table. This is the "test values / debug easier" loop for people who don't write tests.
- **Local verify (opt-in, one click).** Run a suggested test or value probe with the **project's own runner** (`pytest`, `npm test`, `go test`, and so on, detected or confirmed once):
  - It runs in the user's own environment, in a throwaway `git worktree`, so the working tree is never touched.
  - It has a time limit and shows the output in full.
  - Answers are upgraded from **inferred** to **verified** with the run output attached.
  - This is not a sandbox. The user is running their own code on their own machine, so the first run asks for explicit consent.
- **Evidence tiers.** Every answer is labelled **inferred** (from reading the code) or **verified** (actually run). LLM-imagined runtime values are never presented as observed.
- **Output location.** Suggested tests and probes live in the vault. **Export** writes them into the repo as a patch or file, and only when the user asks. LLM-written vault pages carry a visible "LLM-distilled" marker.

### Phase 3: Trace view & friendlier surfaces
- **Trace / watch window** for verified Python runs, using `sys.settrace` in the probe harness. It shows a step-by-step view of variable values for the function under test. It is built only from real runs, never simulated.
- **Vibecoder surfaces.** Guided questions ("What happens if…?"), a plain-English overview of the repo, and a "why did this break?" flow that starts from a failing probe.
- **Sidecar vault mode by default**, once the parity criteria (§7) are met.

### Deferred (not scheduled)
- **Isolated sandbox** (containers or microVMs, cross-platform) for running untrusted code or code whose environment isn't set up. Local verify covers the common case.
- **LSP/SCIP cross-file semantics.**
- **Local UI app.** Static HTML covers Phases 1–3.
- **LLM claim judge** ("contradicted" status). Only after a false-positive rate has been measured against a labelled sample.
- **Advisory Pass Gate.** This extends the existing docs check ([ADR-009](../wiki/decisions/ADR-009-pre-commit-docs-hooks.md)) to flag commits that change code referenced by a doc without touching the doc.
- **Full comment ledger** (scope, kind, span hashes, TODO owners and expiry). It is revisited if field tests show comment drift matters more than dabao-dasher suggested.
- More languages for traces, vault sync between people, and engine adapters.

## 4. The Vault Model

- **Point at a directory.** `ouro open <path>` creates or opens a vault. Nothing is written to the target repo.
- **Location and identity.** `~/.ouro/vaults/<vault-id>/`. The vault id comes from the remote URL plus the first-commit SHA, not the checkout path, so worktrees and multiple clones share one vault. Per-branch state is keyed by branch name inside the vault.
- **The format carries over from the skill.** The vault uses the same wiki layout (`entities/`, `decisions/`, `patterns/`, `maps/`, `index.md`, `capture-queue.md`), the same Doxygen tags, and the same capture → synthesize → pop → index loop ([schema.md](../wiki/schema.md)). The ledger is added as `ledger/`. Only the location changes.
- **Path handling.** `capture.py` and `hooks.py` currently resolve `ouro/wiki/` relative to the working directory. Phase 1 adds a single `--vault` / `OURO_VAULT` override. All paths resolve through it, and the default stays in-repo.
- **Safety.** Ingestion reuses the sensitive-file guard in `capture.py` ([ADR-005](../wiki/decisions/ADR-005-crawl-sensitive-file-guard.md)).

## 5. Privacy & Cost

- Phases 0 and 1 make **no LLM calls**. The ledger is deterministic.
- Phase 2 sends code spans to an LLM. It needs:
  - a per-vault allow/deny path list
  - a local-model option
  - an explicit first-run notice naming the provider
  - budget caps
- **Local verify runs the user's own code.** The rules:
  - It needs explicit consent on first use per repo.
  - It runs in a throwaway `git worktree` with a time limit.
  - It is refused on repos the user hasn't marked as trusted, for example a freshly cloned third-party repo. Those wait for the deferred isolated sandbox.
- The vault holds summaries derived from code. It inherits the sensitivity of the repo, stays under `~/.ouro/` with user-only permissions, and is never synced by default.

## 6. Positioning

Swimm (docs tied to code, with drift detection) is the closest comparison. DeepWiki and Greptile answer questions over repos. CodeRabbit reviews PRs.

What sets Ourobor OS apart:
- **Answers that say how they know.** Each answer is either *inferred* from the code or *verified* by a real run of a test or value probe with the project's own runner. The run happens locally, in one click, and is usable by people who don't write tests.
- **Comments treated as scoped, time-stamped claims.** A stale comment never quietly shapes an explanation, whether a human or an agent is reading it.
- **One engine for both audiences.** Vibecoders get plain English and value tables; professionals get citations, scopes and test code.

Plain "ask the repo" Q&A is common. What makes Ask distinctive here is verification and trustworthy claims, which is why the ledger and the verify loop come before any UI.

**Distribution** stays with the `npx skills` skill package. The sidecar is a mode of the skill, not a separate install.

## 7. Migration from the In-Repo Skill

| Today (`ouro/` in repo) | Sidecar mode |
|-------------------------|--------------|
| `ouro/wiki/` in the target repo | `~/.ouro/vaults/<id>/`, same layout, selected by `--vault` / `OURO_VAULT` |
| `capture.py` crawl / git / commit pointers | Same, writing to the vault |
| `hooks.py` hooks | Same hooks, plus the agent feed of claims |
| `builder.py` | Also renders the ledger |

**Parity criteria** (the point at which vault mode can become the default):
1. Every `capture.py` and `hooks.py` command works with `--vault`.
2. The docs check and Stop hook detect vault updates as documentation.
3. An existing in-repo wiki imports into a vault losslessly.
4. The agent feed works in Claude Code, and in at least one other agent through its instruction file.

## 8. Success Metrics

- **Explain & verify (primary, Phase 2):**
  - Time from a behaviour question ("does `abc()` handle numbers?") to a *verified* answer.
  - Share of behaviour questions that end verified rather than inferred.
  - Share of answers a user judges correct, split by tier.
  - Task success for a non-technical user, for example explaining a module or finding why an input fails, compared with using a plain chat assistant.
- **Drift precision (Phase 1):** the share of `doc_scan.py` top-10 candidates the agent or maintainer confirms. The target is at least 50%. Comment staleness is measured the same way. Baseline: dabao-dasher, where comment staleness was 0/3 before the precision fix, and 2 of 2 docs drifts were found by the agent unaided.
- **Agent behaviour (Phase 1 feed):** on a fixed set of tasks in a repo with seeded outdated doc statements and comments, how often does an agent act on an outdated statement, with the feed vs. without it?
- **Repo health:**
  - Confirmed doc drifts open, and their age.
  - TODO count and median age.
  - These come from `doc_scan` and `claim_scan`. The ourobor-os baseline is in [claim_scan](../wiki/entities/claim_scan.md).
- **Onboarding:** share of agent-run onboardings (Phase 0 checklist) that finish without user intervention beyond the hooks question.

## 9. Open Questions

1. What false-positive rate is acceptable before the "contradicted" status (LLM judge) is added? What labelled sample establishes it?
2. Which PreToolUse or read-time hook points exist in agents other than Claude Code for the agent feed?
3. How should suggested tests and value probes fit a project's existing test framework and conventions? How is the runner detected, and when is the user asked instead?
4. What marks a repo as "trusted" for local verify: an explicit per-repo opt-in, git remote ownership, or something else?
5. How should conflicting claims be surfaced (two comments that disagree, or a comment that disagrees with a test)?
6. Should the drift and TODO counts be exposed as a shareable "repo health" badge?
7. Which doc statements carry claims worth checking beyond code references: prose like "nothing imports X" or "Y is a stopgap"? Can a cheap pattern list shortlist them, or do they need the agent?
