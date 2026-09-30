import sys
import shutil
import os
from pathlib import Path

def detect_llm_environment():
    """Detect which LLM environment(s) are present and return prioritized instruction file."""
    cwd = Path.cwd()
    detected = []
    primary_instruction_file = None

    # Check for various LLM-specific directories and set primary instruction file
    if (cwd / '.claude').exists():
        detected.append('Claude Code')
        primary_instruction_file = 'CLAUDE.md'
    if (cwd / '.cursor').exists():
        detected.append('Cursor')
        if not primary_instruction_file:
            primary_instruction_file = 'CURSOR.md'
    if (cwd / '.aider').exists():
        detected.append('Aider')
        if not primary_instruction_file:
            primary_instruction_file = 'AIDER.md'
    if (cwd / '.continue').exists():
        detected.append('Continue')
        if not primary_instruction_file:
            primary_instruction_file = 'CONTINUE.md'

    return detected, primary_instruction_file

def skill_path_for_docs(script_dir):
    """How instruction files should refer to the skill: project-relative, ~-relative, or absolute."""
    skill_dir = script_dir.parent
    for base, prefix in ((Path.cwd(), ''), (Path.home(), '~/')):
        try:
            rel = skill_dir.relative_to(base)
        except ValueError:
            continue
        return f"{prefix}{rel.as_posix()}" if str(rel) != '.' else (prefix.rstrip('/') or '.')
    return skill_dir.as_posix()

def bootstrap(hook_options=None):
    # Source template directory is the skill's wiki directory
    script_dir = Path(__file__).resolve().parent
    template_src = script_dir.parent / 'wiki'

    # Destination is the 'ouro' folder in the current project
    dest_ouro = Path.cwd() / 'ouro'
    dest_wiki = dest_ouro / 'wiki'

    # Detect LLM environment
    detected_llms, primary_file = detect_llm_environment()
    if detected_llms:
        print(f"[OK] Detected LLM environment(s): {', '.join(detected_llms)}")
        if primary_file:
            print(f"[OK] Primary instruction file: {primary_file}")

    # Initialize wiki structure
    if dest_wiki.exists():
        print(f"[!] Ouro wiki already exists at {dest_wiki}. Skipping copy.")
    else:
        print(f"[*] Initializing Ouro wiki at {dest_wiki}...")
        dest_wiki.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (dest_wiki / 'entities').mkdir(exist_ok=True)
        (dest_wiki / 'decisions').mkdir(exist_ok=True)
        (dest_wiki / 'patterns').mkdir(exist_ok=True)
        (dest_wiki / 'maps').mkdir(exist_ok=True)

        # Copy template files
        if template_src.exists():
            for item in template_src.iterdir():
                if item.is_file():
                    shutil.copy2(item, dest_wiki / item.name)
            print("[OK] Wiki structure initialized.")
        else:
            print(f"[!] Warning: Template source {template_src} not found. Only directories created.")

    # Platform-agnostic maintenance protocol
    protocol = """
## Ourobor OS Maintenance Protocol

You are responsible for maintaining the project's **LLM Wiki** in the `ouro/wiki/` directory.

### 0. Session Start

Before doing any work, check whether the wiki has already been populated:

- **Initial setup** (no entity files in `ouro/wiki/entities/`): run a full crawl.
  ```bash
  python <path-to-skill>/scripts/capture.py --crawl
  ```
- **Ongoing sessions, hooks installed** (`bootstrap.py --install-hooks`): every commit already stages captures automatically. Check for pending work (Claude Code shows this notice at session start):
  ```bash
  python <path-to-skill>/scripts/capture.py --status
  ```
- **Ongoing sessions, no hooks**: run a git-aware crawl to stage only recently changed files.
  ```bash
  python <path-to-skill>/scripts/capture.py --crawl --git
  ```
  To include files from the last N commits: `--crawl --git N` (e.g. `--crawl --git 3`).

### 1. Monitor the Capture Queue
- Regularly read `ouro/wiki/capture-queue.md` using your file reading tool.
- When new snippets are found, "Synthesize" them into the appropriate `ouro/wiki/entities/`, `ouro/wiki/patterns/`, or `ouro/wiki/maps/` files.
- **Pointer captures** (entries with `Commit` and `Change` fields instead of content) come from the git hooks (`Commit: staged` when captured at pre-commit): read the current file at `Source` before synthesizing. `Change: deleted` means the file is gone — update or remove its entity.
- **Ship docs with the change**: when you commit code, update and `git add` the relevant wiki pages in the same commit. If the Ourobor OS docs check or commit gate blocks a commit, document the listed files, stage the wiki pages, and retry. Prefix the commit with `OURO_SKIP_DOCS_CHECK=1` only when the change needs no documentation. If an Ourobor OS Stop hook reports undocumented changes when you finish a task, document them before stopping, or reply briefly why they need no documentation yet.
- Use **Doxygen** tags (`@entity`, `@brief`, `@snippet`, etc.) to structure the documentation.
- Once synthesized, finalize the capture by popping it from the queue:
  ```bash
  python <path-to-skill>/scripts/capture.py --pop
  ```

### 2. Doxygen Standards
- Always include an `@entity` and `@brief` tag at the top of entity/pattern files.
- Mirror critical code logic using `@snippet` blocks.
- Highlight architectural notes with `@note` or `@warning`.

### 3. Architecture Decision Records (ADR)
- Whenever a significant architectural decision is made, create or update an ADR in `ouro/wiki/decisions/`.
- ADRs must document:
  - **Context**: Why the decision is being made.
  - **Alternatives**: Other options considered.
  - **Trade-offs**: What was gained and what was lost.
  - **Rationale**: The reasoning behind the final choice.
- Always link new ADRs in the `ouro/wiki/index.md` file.

### 4. Wiki Maintenance Tools
- Use your LLM's **file reading** tool to review wiki files and the capture queue.
- Use your LLM's **file editing** tool to update existing entity files.
- Use your LLM's **file writing** tool to create new entities, patterns, or decisions.
- Use your LLM's **search/grep** tool to find existing documentation before creating duplicates.

### 5. LLM-Specific Features (if available)
- **Recurring tasks**: If your LLM supports scheduling (e.g., Claude's `/schedule`), set up weekly capture queue reviews.
- **Task tracking**: If your LLM has a task system, use it to track pending synthesis work.
- **Plan mode**: If your LLM has a planning mode, use it for complex wiki restructuring.

### 6. Code Comments & TODOs
- **Scope**: A comment applies only to the line, block, or function it sits in. Do not generalize a comment about one corner case into a rule for the whole codebase; check the code and the wiki first.
- **Staleness**: Comments drift. When a comment and the code disagree, trust the code, and fix or delete the comment in the same change.
- **Deferral**: A `TODO`/`FIXME` is not permission to defer work you were asked to do. Finish the task, or record the deferral and its reason in the wiki (capture queue or an ADR) instead of adding a new `TODO` to the code.

### 7. Verification
- Ensure `ouro/wiki/index.md` is updated with any new entities, ADRs, patterns, or maps.
- Maintain a 1:1 parity between code modules and wiki documentation.
"""

    # Point commands at this install so agents need not locate the skill
    skill_ref = skill_path_for_docs(script_dir)
    protocol = protocol.replace('<path-to-skill>', skill_ref)

    # Update all existing instruction files (projects may use multiple LLMs)
    instruction_files = [
        'CLAUDE.md', 'GEMINI.md', 'CURSOR.md', 'CLINE.md',
        'AIDER.md', 'CONTINUE.md', 'AI_INSTRUCTIONS.md'
    ]

    found_instruction_file = False
    for filename in instruction_files:
        file_path = Path.cwd() / filename
        if file_path.exists():
            found_instruction_file = True
            content = file_path.read_text(encoding='utf-8')
            if "Ourobor OS Maintenance Protocol" not in content:
                print(f"[*] Appending Ourobor OS protocol to {filename}...")
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write("\n" + protocol)
            else:
                print(f"[OK] Ourobor protocol already present in {filename}.")

    # If no instruction file exists at all, create one (use detection if available, else generic)
    if not found_instruction_file:
        target_file = primary_file or 'AI_INSTRUCTIONS.md'
        print(f"[*] Creating {target_file} with Ourobor OS protocol...")
        with open(Path.cwd() / target_file, 'w', encoding='utf-8') as f:
            f.write("# Project Instructions for LLM Agents\n" + protocol)

    if hook_options is not None:
        import hooks  # sibling module; the script's directory is on sys.path
        print("[*] Installing automation hooks...")
        hooks.install(hook_options)

    print("\n" + "="*60)
    print("[OK] Bootstrap complete. Ourobor OS is ready!")
    print("="*60)

    # Next steps; the hooks step only appears when hooks were not requested
    print("\n[*] Next steps:")
    print("1. Measure comment/TODO debt and save it as a wiki page:")
    print(f"   python {skill_ref}/scripts/claim_scan.py --wiki")
    print("2. Capture your codebase:")
    print(f"   python {skill_ref}/scripts/capture.py --crawl")
    print("3. Have your LLM synthesize ouro/wiki/capture-queue.md into ouro/wiki/ pages, then update ouro/wiki/index.md")
    if hook_options is None:
        print("4. (Optional) Capture on every commit and keep docs in the same commit:")
        print(f"   python {skill_ref}/scripts/hooks.py install [--capture-on pre-commit] [--docs-check warn|strict] [--commit-gate] [--stop-hook]")

    if 'Claude Code' in detected_llms:
        print("\n[TIP] Claude Code tips:")
        print("   - Use '!' prefix to run shell commands")
        print("   - Use /schedule for recurring wiki maintenance")
        print("   - Use tasks to track synthesis work")

    if detected_llms:
        print(f"\n[>] Detected environment: {', '.join(detected_llms)}")

    print("="*60 + "\n")

if __name__ == "__main__":
    args = sys.argv[1:]
    hook_options = None
    if '--install-hooks' in args:
        import hooks
        # Parse hook flags before touching the project so a typo fails fast
        hook_options = hooks.install_parser().parse_args([a for a in args if a != '--install-hooks'])
    bootstrap(hook_options)
