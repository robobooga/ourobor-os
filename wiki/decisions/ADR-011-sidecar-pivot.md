@entity ADR-011
@brief Ourobor OS is an observability, interpretability and documentation app for vibecoders and professionals alike, heading toward a sidecar vault outside the target repo. Work is ordered measure and onboard → deterministic claim ledger → Ask & Verify (explanations, suggested tests, value probes, one-click local runs) → trace view. Comments are treated as scoped, time-stamped claims. The skill already ships the scan, agent onboarding, and the comment/TODO rule, and this repo follows the rule itself. Full spec: [docs/spec-v0.3-sidecar.md](../../docs/spec-v0.3-sidecar.md).

## Context

Two problems motivate this.

**Comprehension.** Agent-written code is dense and high-volume. Vibecoders can't easily read it, and professionals reviewing it lack time. Both want to know what the code does, and to check behaviour directly, for example "does `abc()` work with numbers?".

**Context poisoning.** Agents over-trust in-code comments and `TODO`s. A `TODO` gives an agent permission to put off work, and a comment about one corner case gets read as a rule for the whole codebase. Stale comments mislead human readers in the same way.

The decision went through several rounds on 2026-09-30:
- **v0.2 draft:** proposed an external "control plane" with an LLM-simulated dry-run debugger and a regex Pass Gate that banned every comment and TODO.
- **v0.3.0 rewrite:** fixed that framing.
- **Six-advisor council review:** found v0.3.0's Phase 1 was about four products for one developer, and that the problem hadn't been measured. It recommended starting with a measurement, then a deterministic claim ledger. That produced v0.3.1.
- **Product owner's clarification:** the product is an observability, interpretability and documentation app for vibecoders and professionals alike, centred on explaining code and testing values or debugging. v0.3.1 had pushed vibecoders to "later" and left real runs unscheduled. That produced v0.3.2, which this ADR records.

## Decision

1. **Identity.** Ourobor OS is an app for observability, interpretability and documentation, serving vibecoders and professionals through one engine with two presentations (plain English, or technical with citations). Agents are served on the user's behalf.
2. **Destination: a sidecar vault.**
   - It lives in `~/.ouro/vaults/<id>/`, identified by remote URL plus first-commit SHA.
   - It reuses the existing wiki layout, Doxygen tags and capture loop.
   - The skill gains a `--vault` / `OURO_VAULT` path override, and in-repo mode stays the default until the parity criteria in the spec are met.
3. **Phase 0: measure and onboard (shipped).**
   - `ouro/scripts/claim_scan.py` ([entity](../entities/claim_scan.md)) is read-only and stdlib-only. It reports TODO age, stale comments and global-sounding wording, and `--wiki` saves a baseline page.
   - `SKILL.md` gains an **Agent Onboarding** checklist that an agent runs on the user's behalf: bootstrap, measure, document key modules, offer hooks, report.
   - `bootstrap.py` fills in the real skill path in the protocol it appends.
   - The protocol gains the **Code Comments & TODOs** rule: comments apply only to their own scope, code wins over a stale comment, and a `TODO` is not permission to defer requested work.
4. **Phase 1: deterministic claim ledger.**
   - It uses `ast`/`tokenize`, git blame and span hashes, with no LLM. Status is only *stale* or *current*.
   - Outputs are a CLI report, static HTML in plain-English and technical modes, and a read-only agent feed through the existing hooks.
5. **Phase 2: Ask & Verify, the core experience.**
   - **Ask** returns one of three kinds of response: an explanation, suggested tests, or extension points.
   - **Value probes** call a function with given values and tabulate the results.
   - **Local verify** runs a test or probe in one click with the project's own runner, in a throwaway `git worktree`, with consent and a time limit. It upgrades the answer from *inferred* to *verified*.
   - Suggested tests stay in the vault until the user exports them. LLM-written pages carry a visible marker.
6. **Phase 3:**
   - a `sys.settrace` trace view built only from real verified runs
   - vibecoder guided flows
   - vault mode becoming the default
7. **Deferred:**
   - an isolated cross-platform sandbox (needed only for untrusted repos)
   - LSP/SCIP and a local UI app
   - the LLM "contradicted" judge and the advisory Pass Gate
   - vault sync between people
8. **This repo follows the same rule.**
   - AGENT.md applies the comment/TODO rule to this repository.
   - `claim_scan.py --include-skill` measures our own code, and the baseline is kept in the claim_scan entity.
   - The stale comments the scan found were fixed.

## Alternatives Considered

- **v0.3.0 (Ask-first Phase 1 with sandbox, LSP/SCIP and a local app):** Too large for one developer, and nothing it produced would have been verified.
- **v0.3.1 (ledger and agent feed first; vibecoders and real runs "later"/deferred):** It underweighted the product's core promise, which is explaining code and testing values for both audiences.
- **Isolated sandbox as the only way to run code:** Cross-platform containers or microVMs are an infrastructure project. Running the project's own runner in a throwaway worktree covers users' own repos now. The sandbox stays deferred for untrusted code.
- **LLM-simulated dry-run traces:** A trace an LLM imagines is the hallucination the tool is meant to counter. Traces come only from real runs.
- **Protocol rule plus TODO lint only (no ledger):** Adopted as Phase 0. A lint can't tell a comment's scope or whether it is stale, and the explanations need trustworthy claims.
- **Hard-ban comments and TODOs:** This throws away real rationale and pushes agents to hide deferrals.
- **LLM "contradicted" judge in Phase 1:** An unmeasured false-positive rate would make the ledger untrustworthy.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Scope | Phase 1 is deterministic Python plus hooks; Phase 2 adds LLM interpretation plus local runs, not new infrastructure |
| Trust | Answers are labelled inferred or verified; traces are never simulated |
| Safety | Local verify executes the user's code in their environment: consent, worktree isolation, time limit, and only trusted repos; untrusted repos wait for the sandbox |
| Repo cleanliness | Vault mode leaves the target repo untouched; in-repo mode remains until parity; tests are exported only on request |
| Cost / privacy | Phases 0 and 1 make no LLM calls; Phase 2 needs path filters, a local-model option and a provider notice |
| Existing projects | Projects bootstrapped earlier don't get the new protocol section automatically (the append is skipped when the header exists) |
| Heuristics | Staleness depends on git blame and a one-day grace period; global-wording flags are for review, not treated as findings |

## Rationale

Users come to understand their code and to check what it does. Deterministic claims make explanations trustworthy. Real local runs make "does it handle X?" answerable with evidence rather than a guess. Plain-English presentation opens the same engine to vibecoders. Ordering the work as facts, then real runs, then LLM interpretation, then infrastructure keeps each phase useful on its own and within one developer's reach. Applying the rule to this repo keeps the claims honest.
