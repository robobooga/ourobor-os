"""Local run log for Ourobor OS scripts. Nothing leaves the machine.

Each skill script invocation appends one JSON line to
    ~/.ouro/runs/<project>-<hash>/events.jsonl
with its arguments, exit code, duration and (capped) stdout/stderr. Agents append their own summary
with `report`, which also snapshots the wiki, so a maintainer can compare what the agent did with
what they would have done.

Disable with OURO_RUNLOG=off. Relocate with OURO_HOME=<dir> (default ~/.ouro).

Usage:
    python <path-to-skill>/scripts/runlog.py report [--step NAME] < summary.txt
    python <path-to-skill>/scripts/runlog.py report --step onboarding --message "..."
    python <path-to-skill>/scripts/runlog.py show [project_path] [--last N]
    python <path-to-skill>/scripts/runlog.py list

See wiki/entities/runlog.md and ADR-012.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_CAP = 8000
DISABLED_VALUES = {'off', '0', 'false', 'no'}
SKILL_DIR = Path(__file__).resolve().parent.parent


def enabled():
    return os.environ.get('OURO_RUNLOG', 'on').strip().lower() not in DISABLED_VALUES


def ouro_home():
    return Path(os.environ.get('OURO_HOME') or Path.home() / '.ouro').expanduser()


def project_root(start=None):
    """Git top-level of start (default cwd), falling back to the directory itself."""
    start = Path(start or Path.cwd()).resolve()
    result = subprocess.run(['git', '-C', str(start), 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True)
    return Path(result.stdout.strip()) if result.returncode == 0 else start


def run_dir(root):
    digest = hashlib.sha1(str(root).encode('utf-8')).hexdigest()[:8]
    return ouro_home() / 'runs' / f"{root.name}-{digest}"


def append(event, root=None):
    """Append one event; logging failures are swallowed so they can't break a script."""
    try:
        root = root or project_root()
        path = run_dir(root) / 'events.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'project': str(root),
                  'skill_dir': str(SKILL_DIR), **event}
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception:
        pass


class _Tee:
    """Forwards writes to the real stream and keeps the first OUTPUT_CAP characters."""

    def __init__(self, stream):
        self.stream = stream
        self.parts, self.size, self.truncated = [], 0, False

    def write(self, text):
        if self.size < OUTPUT_CAP:
            keep = text[:OUTPUT_CAP - self.size]
            self.parts.append(keep)
            self.size += len(keep)
            self.truncated = self.truncated or len(keep) < len(text)
        elif text:
            self.truncated = True
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def run(script, main):
    """Run a script's main(), logging argv, exit code, duration and printed output."""
    if not enabled():
        return main()
    tee, err_tee, started, code, error = _Tee(sys.stdout), _Tee(sys.stderr), time.time(), 0, None
    sys.stdout, sys.stderr = tee, err_tee
    try:
        return main()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        error = exc.code if isinstance(exc.code, str) else None  # sys.exit("msg") prints to stderr
        raise
    except BaseException as exc:
        code, error = 1, f"{type(exc).__name__}: {exc}"
        raise
    finally:
        sys.stdout, sys.stderr = tee.stream, err_tee.stream
        append({'kind': 'script', 'script': script, 'argv': sys.argv[1:], 'exit': code,
                'seconds': round(time.time() - started, 2), 'error': error,
                'output': ''.join(tee.parts), 'stderr': ''.join(err_tee.parts),
                'output_truncated': tee.truncated or err_tee.truncated})


def wiki_snapshot(root):
    """What the agent produced: wiki pages (path, size, has @entity), queue size, protocol presence."""
    wiki = root / 'ouro' / 'wiki'
    pages = []
    if wiki.is_dir():
        for path in sorted(wiki.rglob('*.md')):
            text = path.read_text(encoding='utf-8', errors='replace')
            head = [ln for ln in text.splitlines() if ln.strip()][:5]  # pages often open with a '# Title' line
            pages.append({'path': path.relative_to(root).as_posix(), 'bytes': len(text.encode('utf-8')),
                          'entity': any(ln.lstrip().startswith('@entity') for ln in head)})
    queue = wiki / 'capture-queue.md'
    pending = None
    if queue.exists():
        from capture import split_entries  # sibling module; same parser the queue tools use
        pending = len(split_entries(queue.read_text(encoding='utf-8', errors='replace'))[1])
    protocol_files = [p.name for p in sorted(root.glob('*.md'))
                      if 'Ourobor OS Maintenance Protocol' in p.read_text(encoding='utf-8', errors='replace')]
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True)
    return {'git_head': head.stdout.strip() or None, 'wiki_pages': pages, 'pending_captures': pending,
            'protocol_in': protocol_files}


def cmd_report(args):
    message = args.message if args.message is not None else sys.stdin.read()
    root = project_root()
    append({'kind': 'report', 'step': args.step, 'message': message.strip(), 'snapshot': wiki_snapshot(root)}, root)
    print(f"[OK] Report logged to {run_dir(root) / 'events.jsonl'}")


def cmd_show(args):
    path = run_dir(project_root(args.project)) / 'events.jsonl'
    if not path.exists():
        sys.exit(f"[!] No run log at {path}")
    events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    for event in events[-args.last:]:
        if event['kind'] == 'script':
            print(f"--- {event['ts']} {event['script']} {' '.join(event['argv'])} "
                  f"(exit {event['exit']}, {event['seconds']}s)")
            if event.get('error'):
                print(f"error: {event['error']}")
            print(event['output'].rstrip() + (' [truncated]' if event['output_truncated'] else ''))
            if event.get('stderr', '').strip():
                print(f"stderr: {event['stderr'].rstrip()}")
        else:
            snap = event['snapshot']
            print(f"=== {event['ts']} REPORT [{event['step']}] head={snap['git_head']} "
                  f"pages={len(snap['wiki_pages'])} pending={snap['pending_captures']}")
            print(event['message'])


def cmd_list(_args):
    runs = ouro_home() / 'runs'
    for events in sorted(runs.glob('*/events.jsonl')) if runs.is_dir() else []:
        lines = events.read_text(encoding='utf-8').splitlines()
        last = json.loads(lines[-1]) if lines else {}
        print(f"{events.parent.name}: {len(lines)} event(s), last {last.get('ts')} — {last.get('project')}")


def main():
    parser = argparse.ArgumentParser(description='Local Ourobor OS run log (never sent anywhere).')
    sub = parser.add_subparsers(dest='command', required=True)
    report = sub.add_parser('report', help="Log the agent's summary plus a wiki snapshot (message from stdin)")
    report.add_argument('--step', default='onboarding', help='Label for this report (default: onboarding)')
    report.add_argument('--message', help='Summary text instead of stdin')
    report.set_defaults(func=cmd_report)
    show = sub.add_parser('show', help="Print a project's run log")
    show.add_argument('project', nargs='?', help='Project path (default: cwd)')
    show.add_argument('--last', type=int, default=50, help='Number of most recent events (default 50)')
    show.set_defaults(func=cmd_show)
    sub.add_parser('list', help='List all logged projects').set_defaults(func=cmd_list)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
