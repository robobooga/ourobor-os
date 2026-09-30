"""Installs or removes Ourobor OS automation hooks in the current project.

Git hooks (deterministic; never call an LLM):
- post-commit (default capture mode): stages pointer captures for every committed file.
- pre-commit, `--capture-on pre-commit`: stages pointer captures and adds the queue to the same commit.
- pre-commit, `--docs-check warn|strict`: flags commits that change code without touching ouro/wiki/.

Claude Code hooks (only when .claude/ exists):
- SessionStart: tells the agent how many captures are pending.
- PreToolUse, `--commit-gate`: blocks an agent `git commit` that has no wiki updates.
- Stop, `--stop-hook`: when the agent ends a turn with code changes but no wiki updates, asks it (once per set
  of changes) to write the docs before finishing. The running agent does the writing; no extra LLM call is made.

Usage (from the project root):
    python <path-to-skill>/scripts/hooks.py install [--capture-on post-commit|pre-commit|none]
                                                    [--docs-check warn|strict] [--commit-gate] [--stop-hook]
    python <path-to-skill>/scripts/hooks.py uninstall

`install` is declarative: it applies exactly the given options and removes Ourobor OS hooks no longer selected.
"""
import argparse
import copy
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CAPTURE_SCRIPT = SCRIPTS_DIR / 'capture.py'

BLOCK_START = '# >>> ourobor-os >>>'
BLOCK_END = '# <<< ourobor-os <<<'
BLOCK_PATTERN = re.compile(r'\n*' + re.escape(BLOCK_START) + r'.*?' + re.escape(BLOCK_END) + r'\n?', re.DOTALL)
GIT_HOOK_NAMES = ('pre-commit', 'post-commit')

CLAUDE_SETTINGS_FILES = ('settings.json', 'settings.local.json')
CLAUDE_HOOK_MARKERS = ('capture.py" --status', 'hooks.py" claude-commit-gate', 'hooks.py" claude-stop-hook')
STOP_STATE_FILE = 'ouro-stop-hook.json'  # lives in the git directory, so it is never committed
PYTHON = '"$(command -v python3 || command -v python)"'

# `git commit` as a command (not commit-tree etc.), optionally after global `-C <dir>` / `-c <k=v>` options
GIT_COMMIT = re.compile(r'\bgit(?:\s+-[cC]\s+\S+)*\s+commit(?![\w-])')
# -a / -am / --all after `commit`: tracked changes get staged by the commit itself, after PreToolUse runs
COMMIT_ALL = re.compile(r'\s(?:-[a-zA-Z]*a[a-zA-Z]*|--all)(?=\s|$)')


def run_git(args):
    """Runs a git command; returns stripped stdout, or None on failure."""
    try:
        result = subprocess.run(['git'] + args, capture_output=True, text=True)
    except Exception:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


# ---------------------------------------------------------------------------- git hooks

def git_hooks_dir():
    """Resolves the active hooks directory (honours core.hooksPath, e.g. husky); None outside a repo."""
    top_level = run_git(['rev-parse', '--show-toplevel'])
    if top_level is None:
        return None
    custom = run_git(['config', 'core.hooksPath'])
    hooks = Path(custom).expanduser() if custom else Path(run_git(['rev-parse', '--git-path', 'hooks']))
    return hooks if hooks.is_absolute() else Path(top_level) / hooks


def git_hook_commands(capture_on, docs_check):
    """Maps install options to the commands each git hook runs (capture always runs before the docs check)."""
    commands = {name: [] for name in GIT_HOOK_NAMES}
    if capture_on == 'post-commit':
        commands['post-commit'].append('"$OURO_PY" "$OURO_CAPTURE" --from-commit HEAD >/dev/null 2>&1 || true')
    elif capture_on == 'pre-commit':
        commands['pre-commit'].append('"$OURO_PY" "$OURO_CAPTURE" --from-index >/dev/null 2>&1 || true')
    if docs_check:
        strict = ' --strict' if docs_check == 'strict' else ''
        commands['pre-commit'].append(f'"$OURO_PY" "$OURO_CAPTURE" --check-docs{strict} || exit 1')
    return commands


def git_hook_block(commands):
    body = '\n'.join(f'  {command}' for command in commands)
    return f"""{BLOCK_START}
# Managed by Ourobor OS hooks.py. Skipped silently if Python or the skill is missing.
OURO_PY=$(command -v python3 || command -v python)
OURO_CAPTURE="{CAPTURE_SCRIPT.as_posix()}"
if [ -n "$OURO_PY" ] && [ -f "$OURO_CAPTURE" ]; then
{body}
fi
{BLOCK_END}"""


def set_git_hook_block(hooks_dir, name, commands):
    """Installs, replaces, or (with no commands) removes the Ourobor OS block in one git hook.

    Content outside the block is preserved. Returns True if the hook file changed.
    """
    hook = hooks_dir / name
    existing = hook.read_text(encoding='utf-8') if hook.exists() else ''
    stripped = BLOCK_PATTERN.sub('\n', existing) if BLOCK_START in existing else existing

    if not commands:
        if stripped == existing:
            return False
        if stripped.strip() in ('', '#!/bin/sh'):
            hook.unlink()
            print(f"[OK] Removed {hook}.")
        else:
            hook.write_text(stripped.rstrip('\n') + '\n', encoding='utf-8')
            print(f"[OK] Removed Ourobor OS block from {hook}.")
        return True

    block = git_hook_block(commands)
    shebang = stripped.splitlines()[0] if stripped.strip() else ''
    if shebang.startswith('#!') and 'sh' not in shebang:
        print(f"[!] {hook} is not a shell script. Add this block to it manually:\n{block}")
        return False
    if re.search(r'^\s*(exit|exec)\b', stripped, re.MULTILINE):
        print(f"[!] {hook} contains an `exit`/`exec` statement; the Ourobor OS block appended after it may never run.")

    prefix = stripped.rstrip('\n') + '\n\n' if stripped.strip() else '#!/bin/sh\n\n'
    content = prefix + block + '\n'
    if content == existing:
        print(f"[OK] Git {name} hook already up to date at {hook}.")
        return False

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook.write_text(content, encoding='utf-8')
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"[OK] {'Updated' if BLOCK_START in existing else 'Installed'} git {name} hook at {hook}.")
    return True


def install_git_hooks(capture_on='post-commit', docs_check=None):
    hooks_dir = git_hooks_dir()
    if hooks_dir is None:
        print("[!] Not a git repository. Skipping git hooks.")
        return
    for name, commands in git_hook_commands(capture_on, docs_check).items():
        set_git_hook_block(hooks_dir, name, commands)


def uninstall_git_hooks():
    hooks_dir = git_hooks_dir()
    changed = [set_git_hook_block(hooks_dir, name, []) for name in GIT_HOOK_NAMES] if hooks_dir else []
    if not any(changed):
        print("[OK] No Ourobor OS git hooks installed.")


# ---------------------------------------------------------------------------- Claude Code hooks

def claude_settings_target(project_root):
    """Shared settings with a portable path when the skill lives inside the project; local settings otherwise."""
    try:
        relative = SCRIPTS_DIR.relative_to(project_root)
        return project_root / '.claude' / 'settings.json', f'$CLAUDE_PROJECT_DIR/{relative.as_posix()}'
    except ValueError:
        return project_root / '.claude' / 'settings.local.json', SCRIPTS_DIR.as_posix()


def load_settings(path):
    """Loads a Claude settings file; {} if missing, None if it isn't valid JSON."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f"[!] Could not parse {path} ({e}). Leaving it untouched.")
        return None


def write_settings(path, settings):
    path.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')


def is_ouro_hook(hook):
    return any(marker in hook.get('command', '') for marker in CLAUDE_HOOK_MARKERS)


def remove_ouro_hooks(settings):
    """Removes Ourobor OS entries from every hook event, pruning empty groups, events, and `hooks`."""
    events = settings.get('hooks', {})
    for event in list(events):
        kept_groups = []
        for group in events[event]:
            kept = [hook for hook in group.get('hooks', []) if not is_ouro_hook(hook)]
            if kept:
                kept_groups.append(dict(group, hooks=kept))
        if kept_groups:
            events[event] = kept_groups
        else:
            del events[event]
    if 'hooks' in settings and not settings['hooks']:
        del settings['hooks']


def install_claude_hooks(commit_gate=False, stop_hook=False, project_root=None):
    """Writes the SessionStart status hook, plus the optional PreToolUse commit gate and Stop hook, into Claude Code settings."""
    project_root = (project_root or Path.cwd()).resolve()
    if not (project_root / '.claude').is_dir():
        print("[*] No .claude/ directory. Skipping Claude Code hooks.")
        return

    settings_path, scripts_ref = claude_settings_target(project_root)
    settings = load_settings(settings_path)
    if settings is None:
        return

    before = copy.deepcopy(settings)
    remove_ouro_hooks(settings)
    def entry(script, args):
        path = f'{scripts_ref}/{script}'
        # Guarded: if the skill is moved or deleted, Python's "can't open file" exits 2, which Claude Code treats as a block
        command = f'cd "$CLAUDE_PROJECT_DIR" && if [ -f "{path}" ]; then {PYTHON} "{path}" {args}; fi'
        return {'type': 'command', 'command': command}

    hooks = settings.setdefault('hooks', {})
    hooks.setdefault('SessionStart', []).append({'hooks': [entry('capture.py', '--status')]})
    if commit_gate:
        hooks.setdefault('PreToolUse', []).append({'matcher': 'Bash', 'hooks': [entry('hooks.py', 'claude-commit-gate')]})
    if stop_hook:
        hooks.setdefault('Stop', []).append({'hooks': [entry('hooks.py', 'claude-stop-hook')]})

    extras = [label for label, enabled in (('PreToolUse commit gate', commit_gate), ('Stop hook', stop_hook)) if enabled]
    names = ' + '.join(['SessionStart'] + extras)
    if settings == before:
        print(f"[OK] Claude Code hooks ({names}) already up to date in {settings_path}.")
        return
    write_settings(settings_path, settings)
    print(f"[OK] Installed Claude Code hooks ({names}) in {settings_path}.")


def uninstall_claude_hooks(project_root=None):
    """Removes Ourobor OS hooks from shared and local Claude Code settings."""
    project_root = (project_root or Path.cwd()).resolve()
    for name in CLAUDE_SETTINGS_FILES:
        settings_path = project_root / '.claude' / name
        settings = load_settings(settings_path)
        if not settings or 'hooks' not in settings:
            continue
        before = copy.deepcopy(settings)
        remove_ouro_hooks(settings)
        if settings != before:
            write_settings(settings_path, settings)
            print(f"[OK] Removed Claude Code hooks from {settings_path}.")


def claude_commit_gate(stream=None):
    """Claude Code PreToolUse hook for Bash.

    Exits 2 (blocks the tool call; stderr is shown to the agent) when a `git commit` changes code without
    wiki updates. Exits 0 for anything else, including unexpected errors.
    """
    try:
        command = json.load(stream or sys.stdin).get('tool_input', {}).get('command', '')
    except Exception:
        return 0
    match = GIT_COMMIT.search(command)
    if not match:
        return 0

    import capture  # sibling module; imported late so its PROJECT_ROOT is the hook's cwd
    if capture.SKIP_DOCS_ENV + '=' in command:
        return 0
    try:
        missing = capture.undocumented_changes(include_unstaged=bool(COMMIT_ALL.search(command[match.end():])))
        pending = capture.count_pending()
    except Exception:
        return 0
    if not missing:
        return 0

    queue_note = (f' Synthesize the {pending} pending capture(s) in {capture.QUEUE_REL} that relate to these files.'
                  if pending else '')
    print(f'Ourobor OS: this commit changes {len(missing)} file(s) without updating {capture.WIKI_REL}:\n'
          f'{capture.describe_undocumented(missing)}\n'
          f'Update the relevant wiki pages and `git add` them so the docs ship in this same commit, then retry.'
          f'{queue_note} If the change genuinely needs no documentation, rerun as '
          f'`{capture.SKIP_DOCS_ENV}=1 git commit ...`.', file=sys.stderr)
    return 2


def stop_state_path():
    """Per-repository Stop hook state inside the git directory; None outside a repository."""
    path = run_git(['rev-parse', '--git-path', STOP_STATE_FILE])
    return Path(path) if path else None


def claude_stop_hook(stream=None):
    """Claude Code Stop hook: has the running agent document its changes before it finishes.

    Exits 2 (Claude keeps working with stderr as its instruction) when the working tree has capturable changes but
    no wiki updates, at most once per session for the same file contents. Exits 0 otherwise: when Claude is already
    continuing because of a Stop hook (`stop_hook_active`), when skipped via OURO_SKIP_DOCS_CHECK, and on any error.
    """
    try:
        payload = json.load(stream or sys.stdin)
        if payload.get('stop_hook_active'):
            return 0

        import capture  # sibling module; imported late so its PROJECT_ROOT is the hook's cwd
        if os.environ.get(capture.SKIP_DOCS_ENV):
            return 0
        missing = capture.undocumented_changes(include_unstaged=True, include_untracked=True)
        state_path = stop_state_path()
        if not missing or state_path is None:
            return 0

        state = {'session_id': payload.get('session_id'), 'fingerprint': capture.changes_fingerprint(missing)}
        try:
            previous = json.loads(state_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            previous = None
        if previous == state:
            return 0
        state_path.write_text(json.dumps(state), encoding='utf-8')
    except Exception:
        return 0

    print(f'Ourobor OS: before finishing, document these changes in {capture.WIKI_REL}; they have no wiki updates yet:\n'
          f'{capture.describe_undocumented(missing)}\n'
          'Update or create the relevant entity, pattern, or decision pages following the Ourobor OS maintenance '
          f'protocol, update {capture.WIKI_REL}index.md, and `--pop` any queue captures you synthesize. '
          'If this work is unfinished, exploratory, not yours, or needs no documentation, reply with one short sentence '
          'saying so and stop; you will not be asked again about these same changes in this session.', file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------- CLI

def install_parser():
    parser = argparse.ArgumentParser(prog='hooks.py install',
                                     description='Install Ourobor OS automation hooks (declarative).')
    parser.add_argument('--capture-on', choices=['post-commit', 'pre-commit', 'none'], default='post-commit',
                        help='git hook that stages pointer captures (default: post-commit)')
    parser.add_argument('--docs-check', choices=['warn', 'strict'],
                        help='pre-commit check for code changes without ouro/wiki/ updates')
    parser.add_argument('--commit-gate', action='store_true',
                        help='Claude Code PreToolUse hook that blocks agent commits without wiki updates')
    parser.add_argument('--stop-hook', action='store_true',
                        help='Claude Code Stop hook that has the agent document code changes before finishing a turn')
    return parser


def install(options):
    install_git_hooks(options.capture_on, options.docs_check)
    install_claude_hooks(options.commit_gate, options.stop_hook)


def uninstall():
    uninstall_git_hooks()
    uninstall_claude_hooks()


def main():
    action, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ('', [])
    if action == 'install':
        install(install_parser().parse_args(rest))
    elif action == 'uninstall':
        uninstall()
    elif action == 'claude-commit-gate':
        sys.exit(claude_commit_gate())
    elif action == 'claude-stop-hook':
        sys.exit(claude_stop_hook())
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    import runlog  # sibling module; the script's directory is on sys.path
    runlog.run('hooks', main)
