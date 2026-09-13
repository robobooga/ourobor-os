---
name: ouro
description: Portable, compounding LLM wiki foundation (Ourobor OS). Initialize a structured documentation system that evolves with your codebase using Doxygen tags. Works with Claude Code, Gemini CLI, Cursor, and other LLM tools.
---

# Ourobor OS: The Compounding Wiki for LLM Agents

Ourobor OS is a portable knowledge system designed to be the "External Brain" for LLM agents. It uses Doxygen tags to create machine-readable documentation that mirrors your codebase, creating a compounding knowledge base that grows with every development session.

**Platform-agnostic**: Works with Claude Code, Gemini CLI, Cursor, Cline, Aider, Continue, and any LLM tool that can read files and execute commands.

## 🚀 Getting Started (Bootstrap)

To initialize Ourobor OS in your project:

### Bootstrap Workflow
1. **Locate the skill path** - Find where this ouro skill is installed
2. **Run the bootstrap script**:
   ```bash
   python <path-to-skill>/scripts/bootstrap.py
   ```
3. **Verify initialization**:
   - Check that `ouro/wiki/` directory was created
   - Verify that your LLM instruction file was updated with maintenance protocols

The bootstrap script will:
- Create the `ouro/wiki/` directory structure
- Set up subdirectories: `entities/`, `decisions/`, `patterns/`, `maps/`
- Copy template files (`index.md`, `schema.md`, `capture-queue.md`)
- Append maintenance protocols to your instruction file (CLAUDE.md, GEMINI.md, etc.)
- Detect your LLM environment and provide relevant tips

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

Staging a file that is already in the queue replaces its older entry. Pointer entries carry no content — read the current file at `Source` when synthesizing (`Change: deleted` means retire or update its entity).

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
```

## 💡 Best Practices

### Universal Principles
- **1:1 Parity**: Aim for a 1:1 mapping between complex code modules and wiki entities
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

1. **Start of session**: "Read the capture queue and show me what needs synthesis"
2. **Synthesis**: "Create an entity file for the AuthService module based on the captures"
3. **Track work**: "Create a task to document the new payment patterns" (if supported)
4. **Schedule**: "Set up a weekly reminder to review the wiki capture queue" (if supported)
5. **Verify**: "Check if all modules in src/ have corresponding wiki entities"

## 📚 Additional Resources

- Read `ouro/wiki/schema.md` for detailed Doxygen protocol
- Read `ouro/wiki/index.md` to see what's already documented
- Check `ouro/wiki/capture-queue.md` regularly for new captures

---

**Ready to start?** Run the bootstrap script and let your LLM help you build your External Brain!
