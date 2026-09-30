# Ourobor OS Sidecar: Observability & Explainability Vault

**Version:** 0.3.1-Draft
**Date:** 2026-09-30
**Supersedes:** 0.3.0-Draft (same day; re-phased after council review) and 0.2.0-Draft ("Sidecar Control Plane & Visual Debugger")
**Decision record:** [ADR-011](../wiki/decisions/ADR-011-sidecar-pivot.md)

---

## 1. Vision

Ourobor OS becomes a **sidecar that sits above a codebase, not inside it**. You point it at a directory, the way you open a folder as an Obsidian vault. It reads the code and keeps an honest, living account of it outside the repo. People can see what the code does and which of its comments can still be trusted. Later they can also question it.

It serves two problems:

1. **Context poisoning.** In agent-maintained repos, agents over-trust in-code comments and `TODO`s. A `TODO` gives an agent permission to put off work. A comment about one corner case gets read as a rule for the whole codebase. Unpruned tech debt makes this worse over time.
2. **Comprehension.** Agent-written code is dense and high-volume. Maintainers reviewing it need to understand it.

The core idea: **comments are claims, not truth.** Every comment applies to a scope and was written at some point in time. The code may since have moved on without it.

### A concrete failure

```python
def parse_amount(s):
    # amounts are always positive; never handle signs
    return Decimal(s.strip())
```

Two years later, `parse_amount` also handles refunds. An agent editing `format_ledger()` reads this comment, generalizes "amounts are always positive", and removes a sign check elsewhere. The comment was scoped to one function, and it had also gone stale.

The Phase 1 ledger reports it like this:

```
src/money.py:2 [parse_amount] STALE (code changed 412d after comment) GLOBAL-WORDING
  "amounts are always positive; never handle signs"
```

An agent reading that file through the adapter sees the same annotation.

## 2. Personas (phased)

| Phase | Persona | Core question |
|-------|---------|---------------|
| 1 | Maintainer overseeing agent output, and the agents themselves | "Which comments and TODOs here can I trust?" |
| 2 | Maintainer | "What does this code do? Does `abc()` handle numbers?" |
| Later | Non-technical builder ("vibecoder") | "Does this work, and what happens if I give it X?" |

## 3. Phasing

The order is set by one rule: **ship the cheap, deterministic piece that changes what agents read first. Build the expensive, crowded pieces only once that piece has proved useful.**

### Phase 0: Measure (done for this repo)
- `scripts/claim_scan.py` is a read-only, stdlib-only scan. It reports TODOs by age, stale comments, and comments worded as global rules. See [claim_scan](../wiki/entities/claim_scan.md).
- The maintenance protocol shipped with the skill gains a **Code Comments & TODOs** rule:
  - comments apply only to their own scope
  - code wins when it disagrees with a comment
  - a `TODO` is not permission to defer requested work
- **Exit condition:** run the scan on at least one agent-heavy external repo. If the TODO and stale counts are low, the protocol rule alone may be enough, and the ledger is not built.

### Phase 1: Claim ledger + agent feed (deterministic, no LLM)
- **Claim ledger.** Python `ast`/`tokenize` plus `git blame` plus span hashes:
  - Every comment becomes a record with `scope` (its enclosing AST node), `kind` (rationale, invariant, warning, workaround, deferral), a `status` of **stale** or **current** only, `age`, and provenance (commit SHA plus a hash of the code span it annotates).
  - There is no "contradicted" status until an LLM judge has been measured (see open questions).
- **TODO ledger.** Deferrals are listed with location, age, and optional owner and expiry.
- **Outputs:**
  - A CLI report (`ouro claims [path]`).
  - A static HTML page generated with `builder.py`. This is the human observability surface.
  - A read-only **agent feed**. The existing `ouro/` hooks (SessionStart, and a hook on file reads such as Claude Code PostToolUse where the agent supports it) inject each comment's scope and status for the files the agent touches. This is the only piece that changes what agents read, so it ships first.
- Python first. Other languages use line-comment regexes with file-level scope.
- **Storage:** `~/.ouro/vaults/<vault-id>/` (see §4). The in-repo skill keeps working unchanged.

### Phase 2: Ask the codebase (inferred answers only)
- Natural-language questions are routed by intent. The response is one of three kinds:
  - **Direct answer**, with `file:line` citations.
  - **Suggested tests** that exercise the behaviour in question.
  - **Extension points** showing where and how to extend the code.
- Every answer is labelled **inferred** and cites ledger claims. A claim marked stale is shown as stale, never used as evidence on its own.
- Suggested tests live in the vault. **Export** writes them into the repo as a patch or file, and only when the user asks.
- Saved answers get the same provenance and staleness tracking as pages. Vault pages that an LLM wrote carry a visible "LLM-distilled" marker, so the vault doesn't become new over-trusted context.

### Deferred (not scheduled)
- **Sandbox verification** (the *verified* evidence tier, and real-instrumentation traces such as `sys.settrace` or DAP). Cross-platform sandboxing is too large for now.
- **LSP/SCIP cross-file semantics.**
- **Local UI app.** Static HTML covers Phases 1 and 2.
- **LLM claim judge** ("contradicted" status). Only after a false-positive rate has been measured against a labelled sample.
- **Advisory Pass Gate.** This extends the existing docs check ([ADR-009](../wiki/decisions/ADR-009-pre-commit-docs-hooks.md)) to flag new TODOs missing from the ledger, and newly stale claims.
- Vibecoder surfaces, more languages, vault sync between people, and engine adapters.

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
- The vault holds summaries derived from code. It inherits the sensitivity of the repo, stays under `~/.ouro/` with user-only permissions, and is never synced by default.

## 6. Positioning

Swimm (docs tied to code, with drift detection) is the closest comparison. DeepWiki and Greptile answer questions over repos. CodeRabbit reviews PRs.

What sets Ourobor OS apart is narrow and deliberate:
- comments treated as scoped, time-stamped claims
- served to the agent at read time
- deterministically, locally, and without cost

Ask (Phase 2) is table stakes rather than the differentiator, so it is built on top of the ledger and not first.

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

- **Phase 0/1 (agent behaviour):**
  - On a fixed set of tasks in a repo with seeded stale comments and TODOs, how often does an agent (a) defer via a new `TODO`, or (b) act on an out-of-scope comment, with the feed vs. without it?
  - This is the metric the project exists to move.
- **Repo health:**
  - TODO count and median age over time.
  - Stale-comment count.
  - Both come from `claim_scan` / the ledger. The ourobor-os baseline is in [claim_scan](../wiki/entities/claim_scan.md).
- **Ledger precision:** the share of flagged stale comments a maintainer agrees are stale, from a labelled sample of at least 50.
- **Phase 2:** the share of Ask answers a maintainer judges correct, and the share of answers that cite at least one current claim.

## 9. Open Questions

1. What false-positive rate is acceptable before the "contradicted" status (LLM judge) is added? What labelled sample establishes it?
2. Which PreToolUse or read-time hook points exist in agents other than Claude Code for the agent feed?
3. How should suggested tests fit a project's existing test framework and conventions?
4. How should conflicting claims be surfaced (two comments that disagree, or a comment that disagrees with a test)?
5. Should the ledger's summary counts be exposed as a shareable "repo health" badge?
