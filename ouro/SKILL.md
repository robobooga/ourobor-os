---
name: ouro
description: Ourobor OS — observability and documentation for your codebase. Onboard a project (bootstrap a living LLM wiki, measure stale comments and old TODOs), explain what code does, and keep docs in sync with code via Doxygen-tagged Markdown. Use when the user asks to set up / onboard Ourobor OS, document or explain a codebase, find stale comments or TODO debt, or maintain the ouro/wiki. Works with Claude Code, Gemini CLI, Cursor, and other LLM tools.
---

# Ourobor OS: Observability & Documentation for Your Codebase

Ourobor OS helps both vibecoders and professional engineers understand their code. It maintains a living wiki that explains what the code does and why, and it flags comments and `TODO`s that can no longer be trusted. The wiki compounds with every session: capture → synthesize → index.

**Platform-agnostic**: Works with Claude Code, Gemini CLI, Cursor, Cline, Aider, Continue, and any LLM tool that can read files and run commands. Needs Python 3.9+ (standard library only) and git.

## 🚀 Agent Onboarding (do this on the user's behalf)

When a user asks you to set up or onboard Ourobor OS, run these steps from the **project root** in order. Every step is safe to re-run. Only step 6 needs the user's input. If `python` isn't on the PATH, use `python3`. After step 2, use the exact commands bootstrap prints and writes into the protocol.

1. **Locate the skill.** Use the directory containing this `SKILL.md`, referred to below as `<path-to-skill>`. Typical locations are `.claude/skills/ouro`, `.agents/skills/ouro`, `~/.claude/skills/ouro`, `~/.agents/skills/ouro`, or `./ouro`.
2. **Bootstrap.**
   ```bash
   python <path-to-skill>/scripts/bootstrap.py
   ```
   - This creates `ouro/wiki/` and appends the maintenance protocol to the instruction files it finds (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, ...), with the skill path and a working Python command filled in.
   - Symlinked aliases, such as `CLAUDE.md -> AGENTS.md`, get the protocol only once.
   - If the project already has `docs/` or an ADR folder, bootstrap says so and tells you to keep those as the source of truth, and to put ADRs there.
   - It is idempotent.
3. **Measure comment and TODO debt** (git repos only; read-only apart from the saved page):
   ```bash
   python <path-to-skill>/scripts/claim_scan.py --wiki
   ```
   This saves `ouro/wiki/maps/comment-baseline.md`, which lists:
   - `TODO`s by age
   - stale comments, where the first statement under the comment changed in a later commit
   - directive-worded comments ("must", "never ..."). This list is for review only, not findings.
   No LLM is called. Before reporting a stale comment, check it against the code.
4. **Populate the wiki.**
   ```bash
   python <path-to-skill>/scripts/capture.py --crawl
   ```
   - The crawl respects `.gitignore` and stages lightweight pointer entries. Read the file at each `Source`.
   - Write entity pages for the most important modules first. One page per directory or package is fine for large repos.
   - Add the pages to `ouro/wiki/index.md`.
   - After each module, clear its captures with `capture.py --done '<dir>/*'`. Don't edit the queue by hand.
   - On a large repo, do the top 5–10 modules now and tell the user how many captures remain.
5. **Check the docs against the code.** While documenting, compare what the project's existing docs (`docs/`, READMEs, ADRs) say with what the code does.
   - Record each contradiction in `ouro/wiki/maps/doc-drift.md` as **confirmed**, with the doc location, the claim, and the contradicting code as `file:line`.
   - Record a claim you checked and found accurate as **dismissed**.
   - Don't edit the docs yet; list the proposed fixes for the user.
6. **Ask the user about hooks** (optional). Offer:
   ```bash
   python <path-to-skill>/scripts/hooks.py install --docs-check warn --stop-hook
   ```
   This captures on every commit, warns when code ships without docs, and (in Claude Code) has the agent write docs before it finishes a turn. Install only if the user agrees.
7. **Report back** to the user in a few lines:
   - what was created
   - the baseline numbers: TODO count and oldest age, and stale comments (say how many you confirmed)
   - confirmed doc drift, as `doc → code file:line`
   - which modules are documented so far and how many captures are pending
   - whether hooks were installed

   **Log the same report** so the onboarding can be reviewed later. Also include anything that was confusing or that you skipped, and why:
   ```bash
   python <path-to-skill>/scripts/runlog.py report --step onboarding --message "<your report>"
   ```

**Run log (local only).** Every skill script appends its arguments, exit code and output to `~/.ouro/runs/<project>-<hash>/events.jsonl`, and `runlog.py report` adds your summary plus a snapshot of the wiki. Nothing is sent anywhere. The log lets the user (or a maintainer reviewing with them) compare what happened with what they expected. Use `runlog.py show` to read it, `OURO_RUNLOG=off` to disable it, and `OURO_HOME=<dir>` to relocate it.

After onboarding, follow the protocol appended to the instruction file. In particular, **comments apply only to their own scope; code wins over a stale comment; a `TODO` is not permission to defer requested work.**

### Automatic Capture (optional)
Skip running capture by hand after every change by installing hooks:
```bash
python <path-to-skill>/scripts/bootstrap.py --install-hooks
# or, on an already-bootstrapped project:
python <path-to-skill>/scripts/hooks.py install
```
- **git post-commit** (default): after each commit, stages a lightweight *pointer* entry (path, commit, change type) for every committed file, replacing older entries for the same file. It never blocks a commit.
- **Claude Code SessionStart** (when `.claude/` exists): tells the agent how many captures are pending so it synthesizes them without being asked.

To keep documentation in the **same commit** as the code it describes, add any of:
```bash
python <path-to-skill>/scripts/hooks.py install --docs-check strict --commit-gate --stop-hook
python <path-to-skill>/scripts/hooks.py install --capture-on pre-commit
```
- `--docs-check warn|strict` (git pre-commit): warns about, or blocks, commits that change code but no `ouro/wiki/` page. Bypass once with `OURO_SKIP_DOCS_CHECK=1 git commit ...`.
- `--commit-gate` (Claude Code PreToolUse): stops the agent's `git commit` under the same rule and tells it which files to document first.
- `--stop-hook` (Claude Code Stop): when the agent finishes a turn with code changes but no wiki updates, it is asked — once per set of changes — to write the docs right then, in the same session. No extra LLM call; the agent that made the change documents it.
- `--capture-on pre-commit`: captures staged files at pre-commit and adds the queue to that commit, instead of post-commit.

`install` is declarative — re-running it applies exactly the flags given.

Synthesis itself stays with your LLM agent — hooks never call an LLM. Remove with `python <path-to-skill>/scripts/hooks.py uninstall`.

## 🧠 Maintenance Workflow

Once initialized, your LLM agent is responsible for maintaining the wiki.

### 1. Capture Snippets

Use the capture script to stage important code snippets or architectural notes to the wiki queue:

```bash
# Crawl only git-changed files (recommended after initial setup)
python <path-to-skill>/scripts/capture.py --crawl --git

# Include last N commits' worth of changes
python <path-to-skill>/scripts/capture.py --crawl --git 3

# Crawl the whole project (use for initial wiki population)
python <path-to-skill>/scripts/capture.py --crawl

# Crawl a specific directory
python <path-to-skill>/scripts/capture.py src/

# Capture a specific file
python <path-to-skill>/scripts/capture.py src/main.py

# Capture raw text or architectural notes
python <path-to-skill>/scripts/capture.py "Architectural Note: Use composition over inheritance here."

# Show how many captures are pending (prints nothing when empty)
python <path-to-skill>/scripts/capture.py --status

# Stage pointer captures for a commit (what the post-commit hook runs)
python <path-to-skill>/scripts/capture.py --from-commit HEAD

# Stage pointer captures for staged files and add the queue to the commit (pre-commit capture)
python <path-to-skill>/scripts/capture.py --from-index

# Check staged changes include wiki updates (pre-commit docs check; --strict exits 1)
python <path-to-skill>/scripts/capture.py --check-docs --strict
```

Staging a file that is already in the queue replaces its older entry. Crawls (`Change: crawl`) and hooks stage pointer entries with no content. Clear finished work with `--done <path-or-glob>`. Pointer entries carry no content — read the current file at `Source` when synthesizing (`Change: deleted` means retire or update its entity).

### 2. Monitor & Synthesize

This is where your LLM's file tools excel:

- **Read** the capture queue regularly:
  ```
  Use your LLM's file reading tool on ouro/wiki/capture-queue.md
  ```

- **Synthesize** captures into structured documentation:
  - Use file editing/writing tools to move content to `ouro/wiki/entities/` or `ouro/wiki/patterns/`
  - Structure with Doxygen tags (`@entity`, `@brief`, `@snippet`, etc.)
  - Remove synthesized entries from the capture queue

- **Track synthesis work** (if your LLM supports it):
  - Use task systems to track which captures need synthesis
  - Create tasks for complex wiki maintenance

- **Automate recurring maintenance** (if available):
  - Claude Code: Use `/schedule` to set up recurring wiki reviews
  - Other LLMs: Check if your tool supports scheduled tasks

### 3. Clean Up

Once captures are synthesized:
- **Delete** the processed entries from `capture-queue.md`
- **Update** `ouro/wiki/index.md` to reference new entities
- **Verify** that the wiki structure remains consistent with `schema.md`

## 🏷️ Doxygen Standards

Use these tags in your documentation for consistency:

| Tag | Description |
| --- | --- |
| `@entity <name>` | Defines the module or entity (Required for files in `entities/`). |
| `@brief <text>` | A one-sentence summary (Required). |
| `@snippet <id>` | Identifies a critical code block. |
| `@note <text>` | Important developer information. |
| `@warning <text>` | Critical alerts regarding side effects. |
| `@param <name> <desc>` | Documents a parameter (for function-level entities). |
| `@return <desc>` | Documents the return value. |

## 📂 Directory Structure

```
ouro/
└── wiki/
    ├── index.md              # Central hub and catalog
    ├── schema.md             # Operating manual and Doxygen standards
    ├── capture-queue.md      # Staging area for new knowledge
    ├── entities/             # Codebase-mirrored documentation
    ├── decisions/            # Architecture Decision Records (ADRs)
    ├── patterns/             # Reusable architectural patterns
    └── maps/                 # High-level mental models and data flows
        └── comment-baseline.md  # claim_scan.py --wiki output (regenerate, do not hand-edit)

~/.ouro/runs/<project>-<hash>/events.jsonl   # local run log (runlog.py), outside the repo
```

## 💡 Best Practices

### Universal Principles
- **Granularity**: One entity per meaningful module; a directory or package page is fine for large repos, split it when it grows
- **Compounding**: Every major feature or refactor should be captured and synthesized
- **ADRs**: Use the `decisions/` folder to document *why* something was done, not just *what*
- **Portability**: Keep all wiki links relative so the `ouro/` folder remains portable

### LLM Tool Usage
- **File reading**: Perfect for reviewing capture queue and existing wiki pages
- **File editing**: Best for updating existing entity files with new snippets
- **File writing**: Use for creating new entity/pattern/decision files
- **Search/grep**: Search for existing documentation before creating duplicates

### Synthesis Guidelines
When processing captures from the queue:

1. **Read the full capture** to understand context
2. **Check for existing entities** - don't duplicate
3. **Apply appropriate tags** - always include `@entity` and `@brief`
4. **Extract critical code** using `@snippet` blocks
5. **Link in index.md** so it's discoverable
6. **Remove from queue** once processed

## 🔄 Recurring Maintenance

Consider setting up these recurring workflows:

**Weekly Wiki Review** (if your LLM supports scheduling):
- Review `capture-queue.md`
- Synthesize pending captures
- Update index.md with new entities
- Check for wiki/code drift

**After Major Features**:
- Capture key architectural decisions in `decisions/`
- Document new patterns in `patterns/`
- Update mental models in `maps/`

**Before Releases**:
- Ensure all new modules have entity documentation
- Verify ADRs are up to date
- Clean up the capture queue

## 🎯 LLM-Specific Tips

### Claude Code
- Use the `!` prefix to run shell commands directly in conversation
- Leverage `/schedule` for recurring wiki maintenance
- Use the task system to track synthesis work
- Use plan mode for complex wiki restructuring
- Tools: Read, Edit, Write, Grep

### Gemini CLI
- Use `invoke_agent` for complex research or batch tasks to keep history lean.
- Use `update_topic` to maintain a clear narrative during multi-turn workflows.
- Leverage sub-agents (`codebase_investigator`, `generalist`) for deep codebase analysis.
- Maintain project context through `GEMINI.md` and `MEMORY.md`.
- Tools: `read_file`, `write_file`, `replace`, `grep_search`, `run_shell_command`, `invoke_agent`.

### Cursor / VS Code Extensions
- Run bootstrap from integrated terminal
- Use file navigation to browse wiki structure
- Leverage inline editing for quick wiki updates

### Aider / CLI-based LLMs
- Run capture scripts as part of your development workflow
- Use `/add` to include wiki files in context
- Synthesize captures during natural development pauses

## 🎓 Example Workflow

Here's a typical session with Ourobor OS:

1. **Onboard**: "Set up Ourobor OS in this project" (the agent follows Agent Onboarding above)
2. **Explain**: "Explain what src/billing does, and tell me which of its comments are stale"
3. **Start of session**: "Read the capture queue and show me what needs synthesis"
4. **Synthesis**: "Create an entity file for the AuthService module based on the captures"
5. **Track work**: "Create a task to document the new payment patterns" (if supported)
6. **Schedule**: "Set up a weekly reminder to review the wiki capture queue" (if supported)
7. **Verify**: "Check if all modules in src/ have corresponding wiki entities"

## 📚 Additional Resources

- Read `ouro/wiki/schema.md` for detailed Doxygen protocol
- Read `ouro/wiki/index.md` to see what's already documented
- Read `ouro/wiki/maps/comment-baseline.md` for stale comments and TODO debt (re-run `claim_scan.py --wiki` to refresh)
- Check `ouro/wiki/capture-queue.md` regularly for new captures

---

**Ready to start?** Ask your agent to "set up Ourobor OS in this project".
