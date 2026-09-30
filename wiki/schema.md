# Wiki Schema: Doxygen Protocol

This document defines the operating manual for this wiki. It mirrors the schema distributed in `ouro/wiki/schema.md` and is the authoritative reference for the Ourobor OS project's own documentation.

## 1. Philosophy
- **Persistent Knowledge**: The wiki is the project's brain. If it's not in the wiki, it doesn't exist for the LLM.
- **Compounding**: Every session should add value to the wiki.
- **Dual-Readability**: Documentation must be equally readable by humans in any Markdown viewer and by LLMs crawling files for structure.
- **Doxygen**: Use structured tags within Markdown to allow for machine-readability and rich UI rendering.

## 2. Doxygen Tags
| Tag | Description |
| --- | --- |
| `@entity <name>` | Defines the module or entity this file documents. Required in every entity/pattern file. An optional single `#` title heading may precede it; it must appear within the first few lines. |
| `@brief <text>` | A one-sentence summary of the entity. Required. |
| `@snippet <id>` | Identifies a code block that is critical for understanding. |
| `@note <text>` | Important information for developers. |
| `@warning <text>` | Critical alerts regarding side effects or risks. |
| `@param <name> <desc>` | Documents a parameter (for function-level entities). |
| `@return <desc>` | Documents the return value. |

## 3. Maintenance Protocols
- **Capture**: New code snippets are staged in `wiki/capture-queue.md`.
- **Synthesis**: The LLM must periodically process the queue and update `wiki/entities/`, `wiki/patterns/`, or `wiki/maps/` as appropriate.
- **ADR**: Major architectural decisions must be recorded in `wiki/decisions/` capturing context, alternatives, trade-offs, and rationale.
- **Parity**: Keep one entity per meaningful module (here, one per `ouro/scripts/` module). A directory or package page is fine for large repos; split it when a page grows.

## 4. Directory Structure
- `index.md`: The central hub and catalog. Always kept up to date.
- `schema.md`: This file. The operating manual.
- `capture-queue.md`: Staging area for new knowledge.
- `entities/`: Documentation for code modules (one per meaningful module).
- `decisions/`: Architecture Decision Records (ADRs).
- `patterns/`: Abstracted, reusable workflow patterns.
- `maps/`: High-level data flows and mental models.

## 5. ADR Format
Every ADR must contain:
- **Context**: Why the decision is being made.
- **Decision**: What was decided.
- **Alternatives Considered**: Other options and why they were rejected.
- **Trade-offs**: What was gained and what was lost.
- **Rationale**: The reasoning behind the final choice.
