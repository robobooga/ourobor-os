"""The ouro/wiki/maps/doc-drift.md page: parse the reviewed entries, merge fresh candidates, render.

Scanners (doc_scan.py today; claim_scan.py comment claims later) produce candidates. The agent reviews
them by editing each entry's Status line. Reviewed entries are kept verbatim across re-runs, so the
agent's evidence and reasons are never overwritten; only unconfirmed candidates are regenerated.

Entry format (one `###` block per entry):

    ### docs/ENGINE.md § Why pickups move to the kerb
    - Key: `docs/ENGINE.md#why-pickups-move-to-the-kerb`
    - Status: unconfirmed | confirmed | dismissed | fixed
    - Code state: `1a2b3c4`
    - ...free-form lines (Claim, Signals, Evidence, Reason)...

A dismissed or fixed entry is raised again when its candidate's code state (the newest commit among
the referenced files) differs from the one recorded on the entry. See wiki/entities/drift_page.md.
"""
import re
from datetime import date
from pathlib import Path

PAGE_REL = Path('ouro/wiki/maps/doc-drift.md')
REVIEWED = ('confirmed', 'dismissed', 'fixed')

ENTRY_RE = re.compile(r'^### ', re.M)
KEY_RE = re.compile(r'^- Key: `([^`]+)`', re.M)
STATUS_RE = re.compile(r'^- Status: \**(\w+)', re.M)
STATE_RE = re.compile(r'^- Code state: `([^`]*)`', re.M)

HEADER = [
    '@entity DocDrift',
    '@brief Doc statements that may no longer match the code: shortlisted by doc_scan.py, then confirmed '
    'or dismissed by the agent against the code.',
    '',
    'Updated {today} by `doc_scan.py --wiki`. Re-running keeps every reviewed entry as written and '
    'regenerates the unconfirmed ones.',
    '',
    '**To review an entry**, check the claim against the code, then change its `Status`:',
    '- `confirmed`: add `- Evidence:` with the contradicting code as `file:line`, and the proposed doc fix.',
    '- `dismissed`: add `- Reason:`. It is raised again only if its code changes.',
    '- `fixed`: the doc was corrected.',
    '',
    'Write only inside `###` entries; text elsewhere is regenerated. An entry you add by hand needs a '
    '`- Status:` line, and a `- Key:` line if a scanner may raise the same section.',
]


def parse_entries(text):
    """List of {key, status, state, block} for each `###` entry in an existing page."""
    starts = [m.start() for m in ENTRY_RE.finditer(text)]
    entries = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end]
        block = re.split(r'^## ', block, maxsplit=1, flags=re.M)[0].rstrip()  # stop at the next section heading
        key, status, state = KEY_RE.search(block), STATUS_RE.search(block), STATE_RE.search(block)
        entries.append({
            'key': key.group(1) if key else None,
            'status': status.group(1).lower() if status else 'unconfirmed',
            'state': state.group(1) if state else None,
            'block': block,
        })
    return entries


def render_candidate(c):
    """Markdown block for one candidate dict (title, key, state, lines)."""
    return '\n'.join([
        f"### {c['title']}",
        f"- Key: `{c['key']}`",
        '- Status: unconfirmed',
        f"- Code state: `{c['state']}`",
        *c['lines'],
    ])


def merge(existing, candidates):
    """(reviewed blocks, candidates still to raise).

    A confirmed key is held until someone marks it fixed. A dismissed or fixed key is raised again only
    when its code state has moved since it was reviewed.
    """
    reviewed = [e for e in existing if e['status'] in REVIEWED]
    held = {e['key']: e for e in reviewed if e['key']}
    fresh = []
    for c in candidates:
        prior = held.get(c['key'])
        if prior is None:
            fresh.append(c)
        elif prior['status'] != 'confirmed' and prior['state'] and prior['state'] != c['state']:
            note = f"- Previously {prior['status']} at `{prior['state']}`; the code has changed since."
            fresh.append({**c, 'lines': [*c['lines'], note]})
            reviewed.remove(prior)
    return [e['block'] for e in reviewed], fresh


def write_page(root, candidates, limit):
    """Merge candidates into the page under root and save it; returns (path, reviewed count, raised count)."""
    wiki_dir = root / 'ouro' / 'wiki'
    if not wiki_dir.is_dir():
        raise FileNotFoundError(f"No ouro/wiki/ in {root}. Run bootstrap.py first, or omit --wiki.")
    path = root / PAGE_REL
    existing = parse_entries(path.read_text(encoding='utf-8')) if path.exists() else []
    reviewed, fresh = merge(existing, candidates)
    lines = [line.format(today=date.today().isoformat()) for line in HEADER]
    lines += ['', f'## Reviewed: {len(reviewed)}', '']
    lines += ['\n\n'.join(reviewed)] if reviewed else ['None yet.']
    lines += ['', f'## Unconfirmed candidates: {len(fresh)}', '']
    lines += ['\n\n'.join(render_candidate(c) for c in fresh[:limit])] if fresh else ['None.']
    if len(fresh) > limit:
        lines += ['', f'...and {len(fresh) - limit} more (`--limit` to raise more).']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path, len(reviewed), min(len(fresh), limit)
