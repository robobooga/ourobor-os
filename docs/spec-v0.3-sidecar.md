# Ourobor OS Sidecar: Observability & Explainability Vault

**Version:** 0.3.2-Draft
**Date:** 2026-09-30
**Supersedes:** 0.3.1 (re-phased to put explaining code and testing values first), 0.3.0, and 0.2.0-Draft ("Sidecar Control Plane & Visual Debugger")
**Decision record:** [ADR-011](../wiki/decisions/ADR-011-sidecar-pivot.md)

---

## 1. Vision

Ourobor OS is an **observability, interpretability and documentation app for code, for vibecoders and professional engineers alike**. It does two things for its users:

- **Explain your code easily.** It says what the code does, why it does it, and which of its comments can still be trusted.
- **Test values and debug more easily.** You ask "does `abc()` work with numbers, not just letters?" and get an answer, a test that checks it, and a real run that confirms it.

It is heading toward being a **sidecar that sits above a codebase rather than inside it**. You point it at a directory, the way you open a folder as an Obsidian vault, and it keeps a living, honest account of the code outside the repo.

Two problems motivate it:

1. **Comprehension.** Agent-written code is dense and high-volume. Vibecoders can't read it easily, and professionals reviewing it don't have time to.
2. **Context poisoning.** In agent-maintained repos, agents over-trust in-code comments and `TODO`s. A `TODO` gives an agent permission to put off work. A comment about one corner case gets read as a rule for the whole codebase. Stale comments mislead human readers in the same way.

The core idea behind the explanations: **comments are claims, not truth.** Every comment applies to a scope and was written at some point in time. The code may since have moved on without it. Every answer Ourobor OS gives says how it knows: inferred from reading the code, or verified by running it.

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

Ask (Phase 2) can then check the claim itself. "Does `parse_amount` handle negative amounts?" produces an inferred answer citing the code, a suggested test for `parse_amount("(5.00)")`, and, with one click, a verified result from running that test.

## 2. Personas

Both personas are served from Phase 1 onward. They share one engine and differ only in presentation.

| Persona | Core questions | Presentation |
|---------|----------------|--------------|
| Vibecoder (non-technical builder) | "What does this do? Does it work if I give it X? Why did it break?" | Plain-English explanations, one-click checks, no jargon by default |
| Professional engineer / maintainer | "Which comments and TODOs can I trust? What are the edge cases? Is agent output degrading the code?" | `file:line` citations, scopes, ages, raw test code |
| Coding agents (served on the user's behalf) | Which comments are in scope and current | Ledger feed injected by hooks |

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
- **Exit check:** run the onboarding on agent-heavy external repos. The baseline numbers decide how much Phase 1 ledger machinery is worth building. Phase 2 (explain and test values) goes ahead either way, because it is the core product.

### Phase 1: Claim ledger (deterministic, no LLM)
- **Claim ledger.** Python `ast`/`tokenize` plus `git blame` plus span hashes, growing out of `claim_scan.py`:
  - Every comment becomes a record with `scope` (its enclosing AST node), `kind` (rationale, invariant, warning, workaround, deferral), a `status` of **stale** or **current** only, `age`, and provenance (commit SHA plus a hash of the code span it annotates).
  - There is no "contradicted" status until an LLM judge has been measured.
- **TODO ledger.** Deferrals are listed with location, age, and optional owner and expiry.
- **Outputs:**
  - A CLI report (`ouro claims [path]`).
  - Static HTML via `builder.py`, with a plain-English mode ("this note about signs is older than the code below it") and a technical mode.
  - A read-only **agent feed** through the existing hooks (SessionStart, and a hook on file reads such as Claude Code PostToolUse where the agent supports it).
- Python first. Other languages use line-comment regexes with file-level scope.

### Phase 2: Ask & Verify (the core experience)
- **Ask.** Natural-language questions are routed by intent. The response is one of three kinds:
  - **Explanation**: what the code does, in plain English or technical detail depending on the user, with `file:line` citations and relevant ledger claims. A stale claim is shown as stale, never used as evidence on its own.
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
- **Advisory Pass Gate.** This extends the existing docs check ([ADR-009](../wiki/decisions/ADR-009-pre-commit-docs-hooks.md)) to flag new TODOs missing from the ledger, and newly stale claims.
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
- **Agent behaviour (Phase 1 feed):** on a fixed set of tasks in a repo with seeded stale comments and TODOs, how often does an agent (a) defer via a new `TODO`, or (b) act on an out-of-scope comment, with the feed vs. without it?
- **Repo health:**
  - TODO count and median age over time.
  - Stale-comment count.
  - Both come from `claim_scan` / the ledger. The ourobor-os baseline is in [claim_scan](../wiki/entities/claim_scan.md).
- **Ledger precision:** the share of flagged stale comments a maintainer agrees are stale, from a labelled sample of at least 50.
- **Onboarding:** share of agent-run onboardings (Phase 0 checklist) that finish without user intervention beyond the hooks question.

## 9. Open Questions

1. What false-positive rate is acceptable before the "contradicted" status (LLM judge) is added? What labelled sample establishes it?
2. Which PreToolUse or read-time hook points exist in agents other than Claude Code for the agent feed?
3. How should suggested tests and value probes fit a project's existing test framework and conventions? How is the runner detected, and when is the user asked instead?
4. What marks a repo as "trusted" for local verify: an explicit per-repo opt-in, git remote ownership, or something else?
5. How should conflicting claims be surfaced (two comments that disagree, or a comment that disagrees with a test)?
6. Should the ledger's summary counts be exposed as a shareable "repo health" badge?
