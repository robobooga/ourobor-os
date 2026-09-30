@entity SystemArchitecture
@brief High-level component map of the Ourobor OS project — what exists, where it lives, and what is included in the distributed package.

## Component Map

```
ourobor-os/
│
├── ouro/                          [Distributable Skill Package]  ← shipped to users
│   ├── SKILL.md                   npx skills entry point & description
│   ├── AGENT_PROTOCOL.md          LLM maintenance protocol (appended by bootstrap.py)
│   ├── README.md                  Skill-level quick start
│   ├── scripts/
│   │   ├── capture.py             Knowledge ingestion tooling
│   │   ├── bootstrap.py           One-time project initialization
│   │   └── hooks.py               Opt-in git pre/post-commit + Claude Code hooks
│   └── wiki/                      Clean skeleton — empty subdirs only
│       ├── index.md               Template hub
│       ├── schema.md              Template schema
│       ├── capture-queue.md       Template queue (empty)
│       ├── entities/              .gitkeep
│       ├── decisions/             .gitkeep
│       ├── patterns/              .gitkeep
│       └── maps/                  .gitkeep
│
├── wiki/                          [Project Brain + Reference Example]  ← this directory
│   ├── index.md                   Project wiki hub
│   ├── schema.md                  Doxygen protocol reference
│   ├── capture-queue.md           Active staging area
│   ├── entities/                  Module docs (capture, bootstrap, builder, package)
│   ├── decisions/                 ADRs (001–004)
│   ├── patterns/                  Capture-synthesize loop
│   └── maps/                      This file
│
├── ouro-webui/                    [Web UI — Separate Concern]  ← not in package
│   ├── builder.py                 Markdown → HTML static site generator
│   ├── requirements.txt           mistune, jinja2
│   ├── templates/
│   │   ├── base.html              Base layout (has known template inheritance bug)
│   │   └── page.html              Per-page template
│   └── dist/                      Generated HTML output (gitignored)
│
├── scripts/
│   ├── package.py                 Packages ouro/ → dist/ouro-skill.zip
│   └── claim_scan.py              Phase 0 comment/TODO baseline scan (ADR-011)
│
├── docs/
│   └── spec-v0.3-sidecar.md       Sidecar vault spec (ADR-011)
│
└── dist/
    └── ouro-skill.zip             Distribution artifact
```

## Data Flow

```
Developer's codebase
        |
        | python ouro/scripts/capture.py --crawl
        v
ouro/wiki/capture-queue.md
        |
        | LLM synthesizes during active session
        v
ouro/wiki/entities/ | patterns/ | decisions/
        |
        | (optional) python ouro-webui/builder.py
        v
ouro-webui/dist/*.html             browsable dashboard

        | python scripts/package.py
        v
dist/ouro-skill.zip                → npx skills / direct download → user projects
```

## Separation of Concerns

| Directory | Purpose | In Package |
|-----------|---------|------------|
| `ouro/` | Distributable skill skeleton | Yes |
| `wiki/` | Project documentation + example | No |
| `ouro-webui/` | Optional web rendering layer | No |
| `scripts/` | Release tooling and experiments | No |
| `docs/` | Forward-looking specs | No |
| `dist/` | Build artifacts | No |

See [ADR-001](../decisions/ADR-001-ouro-as-distributable-skeleton.md) and [ADR-002](../decisions/ADR-002-wiki-as-dual-purpose.md) for the reasoning behind the `ouro/` vs `wiki/` separation.
