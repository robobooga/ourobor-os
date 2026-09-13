# Ourobor OS: The Living Project Documentation Ecosystem

Ourobor OS is an AI-native "operating system" for project documentation — a self-renewing knowledge base that embeds capture directly into your development workflow so docs stay synchronized with your code.

> Inspired by the *Ouroboros*, the ancient symbol of a snake eating its own tail: as you develop, the system captures knowledge, which informs future development, which in turn updates the documentation. A cycle that continuously feeds on its own evolution.

## ⚠️ The Documentation Problem

Documentation often falls into a "trap of obsolescence":
- **Context Friction**: Stopping the flow of coding to write documentation is mentally expensive and interrupts the development cycle.
- **The Staleness Cycle**: Documentation is frequently the first thing to become outdated as code changes, eventually leading to mistrust and abandonment of the wiki.

Ourobor OS solves these by embedding documentation into the development flow and using automation to keep the "Brain" synchronized with the evolving codebase.

## 🧠 Core Philosophy

- **Single Source of Truth**: The wiki is the canonical knowledge store — if it isn't there, it doesn't inform future work.
- **Compounding**: Every development session adds to the collective intelligence of the project.
- **Portability**: The entire Ouro Core system is lightweight, modular, and portable across any codebase.
- **Dual-Readability**: Documentation must be equally elegant for humans to read and structured for LLMs to crawl and synthesize.

## 🛠 Features

- **Doxygen Protocol**: Structured tags (`@entity`, `@brief`, `@snippet`) make Markdown machine-readable and UI-ready.
- **Automated Capture**: Scripts to crawl your codebase and stage new knowledge for synthesis.
- **Architecture Mapping**: Dedicated tracks for ADRs (Decisions), Patterns, and Mental Models (Maps).
- **1:1 Parity**: Maintains a direct mapping between source modules and documentation entities.
- **Web UI**: A static site generator that turns your wiki into a navigable, browser-ready knowledge base.

## 📂 Structure

Once installed, your project's Brain lives in `ouro/wiki/` (the distributable skeleton shipped with the package):
- **`index.md`**: The central hub and catalog.
- **`schema.md`**: The operating manual and Doxygen standards.
- **`entities/`**: 1:1 mirrored documentation of your codebase.
- **`decisions/`**: Architecture Decision Records (ADRs).
- **`patterns/`**: Abstracted, reusable architectural logic.
- **`capture-queue.md`**: The active capture staging area.

## 🌐 Web UI

The `ouro-webui/` module ships a static site generator that compiles your wiki into a clean, browser-ready documentation site.

**Features:**
- **Doxygen rendering**: `@entity`, `@brief`, `@note`, and `@warning` tags are rendered as styled HTML components.
- **Auto-generated navigation**: A sidebar tree is built from your wiki's directory structure, grouped by section (Entities, Decisions, Patterns, Maps).
- **Responsive layout**: Collapses to a mobile-friendly stacked view on small screens.
- **Zero JS**: Pure HTML/CSS output — no framework, no build pipeline, no dependencies at runtime.
- **Configurable source**: Point it at any compatible wiki directory via `--wiki-dir`.

**Build your wiki site:**
```bash
python ouro-webui/builder.py --wiki-dir ./wiki
# Output lands in ouro-webui/dist/
```

**Live demo:** See this project's own wiki rendered at **[nick-tan.com/ourobor-os](https://nick-tan.com/ourobor-os/)** — a real-world example of an Ourobor OS brain served as a static site.

## 🔁 Dogfooding: See It In Action

The [`/wiki`](./wiki) directory at the root of this repository is Ourobor OS documenting itself — a live example of what a project Brain looks like in practice. It is the canonical knowledge store for this codebase, maintained using the same agent workflow and Doxygen protocol that ships to users. Browse the [live site](https://nick-tan.com/ourobor-os/) or the raw Markdown to get a concrete sense of how the system works before installing it in your own project.

> **Note:** Because the wiki is generated and maintained by an LLM, the structure, depth, and formatting of your own wiki will naturally differ from the live demo. Every project's brain grows organically — shaped by the codebase, the agent's synthesis decisions, and the information fed into the capture queue. The live demo is a reference point, not a template to match exactly.

## 🚀 Quick Start

### 1. Installation

Recommended: Using [npx skills](https://github.com/vercel-labs/skills)
```bash
# Run the command at your project root to install the skill
npx skills add robobooga/ourobor-os
```

Alternative: clone this repository and copy the `ouro/` directory into your project's root:
```bash
git clone https://github.com/robobooga/ourobor-os.git
cp -r ourobor-os/ouro ./
```

### 2. Integration
Enable the agent by appending the maintenance protocols to your project's instructions (e.g., `GEMINI.md` or `CLAUDE.md`). See `ouro/AGENT_PROTOCOL.md` for the full protocol.

### 3. Usage
Run the capture script to scan your project for Doxygen tags:
```
python ./ouro/scripts/capture.py --crawl
```

Or, initialize the system in a new project:
```
python ./ouro/scripts/bootstrap.py
```

To stop running capture by hand, opt in to hooks. A git post-commit hook stages every committed file, and a Claude Code SessionStart hook tells your agent what's pending:
```
python ./ouro/scripts/bootstrap.py --install-hooks
```

To make docs ship in the same commit as the feature, add a pre-commit docs check and, for Claude Code, a commit gate that makes the agent document before it commits:
```
python ./ouro/scripts/hooks.py install --docs-check strict --commit-gate
```

With Claude Code, the agent can also write the docs for you: `--stop-hook` asks the running agent to document its code changes before it finishes a turn, with no extra LLM call:
```
python ./ouro/scripts/hooks.py install --docs-check strict --commit-gate --stop-hook
```

## 🌟 Roadmap

Ourobor OS currently ships as an **Agent Skill** for seamless IDE integration, with a **Web UI** for publishing your wiki as a static site. Planned extensions include:
- **Auxiliary Tooling**: Specialized utilities for documentation maintenance, validation, and analytics.
- **Holistic Integration**: A unified standard for AI-assisted project management where documentation is the primary interface for both developers and agents.

## 📖 Learn More
- Navigate to the [Wiki Index](./ouro/wiki/index.md) to explore the system's full capabilities.
- Inspired by [Andrej Karpathy's "LLM Wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) concept.
