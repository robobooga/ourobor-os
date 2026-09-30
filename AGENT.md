# AGENT.md

Project overview and rules for Ourobor OS.

## Overview
Ourobor OS is a portable, compounding knowledge system ("External Brain"). It maps project documentation to a machine-readable wiki contained in the `ouro/` directory.

> **CRITICAL**: The `ouro/` directory is a **portable skill package** (the "system"). Keep it distinct from your **target project codebase**. When running commands, be aware of whether you are operating on the Ourobor OS system or your project files.

## Project Brain

The project's living documentation lives in `wiki/` (root level). This directory is both the internal docs for Ourobor OS and a reference example for users of the skill.

> **Do not write project documentation into `ouro/wiki/`.** That directory is the clean distributable skeleton shipped to users. See `wiki/decisions/ADR-001-ouro-as-distributable-skeleton.md`.

- **Wiki Index**: `wiki/index.md` — start here.
- **Schema**: `wiki/schema.md` — Doxygen protocol and maintenance rules.
- **Capture Queue**: `wiki/capture-queue.md` — active staging area.

## Wiki Protocol
- **Persistence**: If it's not in the wiki, it doesn't exist.
- **Compounding**: Every session grows the collective intelligence.
- **1:1 Parity**: Maintain direct mapping between source modules and documentation.

> **RULE**: Any code change made during a session **must** be accompanied by wiki updates in the same response — not as a follow-up. Specifically:
> - Update the relevant `wiki/entities/*.md` file to reflect changed behaviour, new functions, or removed features.
> - Create a new `wiki/decisions/ADR-NNN-*.md` if the change involved a non-trivial design decision (new pattern, added constraint, rejected alternative).
> - Add new ADRs to `wiki/index.md`.
> Failing to do this is a protocol violation — the wiki is the source of truth, not the code.

### Code Comments & TODOs
Our own code follows the rule the skill ships (see [ADR-011](wiki/decisions/ADR-011-sidecar-pivot.md)):
- **Scope**: A comment applies only to the line, block, or function it sits in. Do not generalize a comment about one corner case into a rule for the whole codebase; check the code and the wiki first.
- **Staleness**: Comments drift. When a comment and the code disagree, trust the code, and fix or delete the comment in the same change.
- **Deferral**: A `TODO`/`FIXME` is not permission to defer work you were asked to do. Finish the task, or record the deferral and its reason in the wiki (capture queue or an ADR) instead of adding a new `TODO` to the code.
- **Measure**: Run `python ouro/scripts/claim_scan.py --include-skill` before and after larger changes; don't let the stale or `TODO` counts grow. Record the baseline in [claim_scan](wiki/entities/claim_scan.md). Never pass `--wiki` in this repo: it writes into `ouro/wiki/`, which must stay an empty skeleton ([ADR-001](wiki/decisions/ADR-001-ouro-as-distributable-skeleton.md)).

### Doxygen Standards
- `@entity <name>`: Module/entity defined.
- `@brief <text>`: One-sentence summary.
- `@snippet <id>`: Critical code block.
- `@note`/`@warning`: Dev context/alerts.
- `@param`/`@return`: Function documentation.

## Workflow For This Project
1. **Monitor**: Check `wiki/capture-queue.md`.
2. **Synthesize**: Use `python ouro/scripts/capture.py --pop` to process captures.
3. **Document**: Transform entries into `wiki/entities/`, `wiki/patterns/`, or `wiki/decisions/`.
4. **Index**: Update `wiki/index.md`.
5. **Clean**: Remove synthesized entries from queue.

## Workflow For Skill Package
1. **Monitor**: Check `ouro/wiki/capture-queue.md` (in the target project after install).
2. **Synthesize**: Use `python ouro/scripts/capture.py --pop` to process captures.
3. **Document**: Transform entries into `ouro/wiki/entities/` or `patterns/`.
4. **Index**: Update `ouro/wiki/index.md`.
5. **Clean**: Remove synthesized entries from queue.

## Development Commands
```bash
# Package distribution
python scripts/package.py
```

## Skill Distribution
The `ouro/` directory is a universal, platform-agnostic skill meant to be dropped into target projects.
- **Install Paths**: `~/.agents/skills/ouro/` or project-local `.llm/skills/ouro/`.
- **Initialization**: Run `python ouro/scripts/bootstrap.py` in the **project root**.
- **Source of Truth**: All Ourobor OS system development happens in `ouro/`.

## Key Directories
- `ouro/`: Core portable system (the "Skill").
- `ouro/scripts/`: `bootstrap.py` (init), `capture.py` (tag extraction).
- `ouro/wiki/`: The "Brain" (entities, decisions, patterns, maps).
- `docs/`: Ourobor OS project-specific planning.
- `dist/`: Generated archives.
