@entity ADR-011
@brief Ourobor OS is heading toward a sidecar vault outside the target repo. Work is ordered measure → deterministic claim ledger plus agent feed → Ask. Comments are treated as scoped, time-stamped claims, not truth. The skill already ships the comment/TODO rule, and this repo follows it itself. Full spec: [docs/spec-v0.3-sidecar.md](../../docs/spec-v0.3-sidecar.md).

## Context

In agent-maintained codebases, agents over-trust in-code comments and `TODO`s. A `TODO` gives an agent permission to put off work. A comment about one corner case gets read as a rule for the whole codebase, especially when tech debt isn't pruned.

People reviewing agent-written code also need to understand it and be able to question it.

A draft spec (v0.2) proposed an external "control plane" with four parts:
- an Obsidian-style vault
- an LLM "dry-run" debugger
- a regex Pass Gate that banned every TODO and inline comment
- a concierge bot

The first rewrite (v0.3.0) fixed its framing. A six-advisor council review (2026-09-30) then found that v0.3.0's Phase 1 was about four products for one developer:
- a vault
- Tree-sitter plus LSP/SCIP
- an LLM claim judge
- Ask with a sandbox and a local app

It also found that v0.3.0 sequenced the agent context channel last, even though it is the only piece that changes what agents read. Reviewers added three points:
- The problem had not been measured.
- Moving docs out of the repo does not touch the comments in the source.
- The vault's own LLM-written pages could become new over-trusted context.

## Decision

1. **Destination: a sidecar vault.** `~/.ouro/vaults/<id>/`, identified by remote URL plus first-commit SHA. It reuses the existing wiki layout, Doxygen tags and capture loop. The skill gains a `--vault` / `OURO_VAULT` path override, and in-repo mode stays the default until the spec's parity criteria are met.
2. **Phase 0: measure first.**
   - `scripts/claim_scan.py` ([entity](../entities/claim_scan.md)) is a stdlib, read-only scan that reports TODOs by age, stale comments, and comments worded as global rules.
   - It must be run on an agent-heavy external repo before any ledger code is written. If the counts there are low, stop at the protocol rule.
3. **Ship the cheap rule now.** The maintenance protocol (`ouro/AGENT_PROTOCOL.md` and the protocol string in `bootstrap.py`) gains a **Code Comments & TODOs** section:
   - comments apply only to their own scope
   - code wins when it disagrees with a comment
   - a `TODO` is not permission to defer requested work; deferrals are recorded in the wiki
4. **Phase 1: a deterministic claim ledger plus an agent feed.**
   - The ledger uses `ast`/`tokenize`, git blame and span hashes, with no LLM. Status is only *stale* or *current*.
   - Outputs are a CLI report, static HTML via `builder.py`, and a read-only feed injected by the existing hooks. The feed goes to agents first because it's the part that fixes the problem.
5. **Phase 2: Ask.**
   - Responses are direct answers, suggested tests or extension points, labelled *inferred* only.
   - Suggested tests stay in the vault until the user exports them. LLM-written pages carry a visible marker.
6. **Deferred:** the sandbox and *verified* tier, LSP/SCIP, a local UI app, the LLM "contradicted" judge, the advisory Pass Gate, vibecoder surfaces, and vault sync.
7. **This repo follows the same rule.**
   - AGENT.md applies the same comment/TODO rule to this repository's own code.
   - The Phase 0 baseline for ourobor-os is recorded in the claim_scan entity.
   - The two stale comments the scan found (`capture.py`, `bootstrap.py`) were fixed.

## Alternatives Considered

- **v0.3.0 as written (Ask-first Phase 1):** Too large for one developer, and it leaves agents' context unchanged until the last phase.
- **Protocol rule plus TODO lint only (no ledger):** The cheapest option, and it is adopted as Phase 0. A lint can't tell which scope a comment belongs to or whether it is stale, so the ledger stays planned, but only if measurement shows it's needed.
- **Hard-ban comments and TODOs through the Pass Gate:** This throws away real rationale, and pushes agents to hide deferrals rather than record them.
- **LLM-simulated dry-run debugger:** A trace an LLM imagines is the hallucination the tool is meant to counter.
- **LLM "contradicted" judge in Phase 1:** An unmeasured false-positive rate would make the ledger itself untrustworthy context.
- **Treat it as a commercial product first (find paying teams):** The project is open source and distributed as a skill. Distribution stays through `npx skills`, and the sidecar is a mode of the skill.

## Trade-offs

| Factor | Impact |
|--------|--------|
| Scope | Phase 1 is deterministic Python plus hooks; Ask and the sandbox wait for evidence |
| Repo cleanliness | Vault mode leaves the target repo untouched; in-repo mode remains until parity |
| Versioning | Vault mode loses git history for docs; replaced by SHA and span-hash provenance |
| Cost / privacy | Phases 0 and 1 make no LLM calls; Phase 2 needs path filters, a local-model option and a provider notice |
| Existing projects | Projects bootstrapped before this change don't get the new protocol section automatically (the append is skipped when the header exists) |
| Heuristics | Stale detection depends on git blame and a one-day grace period; the global-wording flag is noisy and is shown for review, not treated as findings |

## Rationale

The agent feed of scoped, time-stamped claims is the narrow piece that is both new and aimed at the stated problem, and it can be built cheaply and deterministically. Measuring first keeps the project from building a vault for a problem that turns out to be small. Applying the same rule to this repo keeps the claims honest: the rule, the scan and the baseline are all used here first.
