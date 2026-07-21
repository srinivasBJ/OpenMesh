# OpenMesh 
  ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ <img width="472" height="109" alt="a" src="https://github.com/user-attachments/assets/6acd38d6-bed6-48d1-8e2d-9065053be75f" />


<a href="https://github.com/srinivasBJ/OpenMesh/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/srinivasBJ/OpenMesh/actions/workflows/ci.yml/badge.svg"></a>
<a href="pyproject.toml"><img alt="Python 3.11-3.13" src="https://img.shields.io/badge/Python-3.11--3.13-3776AB?logo=python&logoColor=white"></a>
<a href="backend/src/main.py"><img alt="FastAPI 0.135" src="https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white"></a>
<a href="frontend/package.json"><img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111111"></a>
<a href="INSTALLATION.md"><img alt="PostgreSQL supported" src="https://img.shields.io/badge/PostgreSQL-supported-4169E1?logo=postgresql&logoColor=white"></a>
<a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg"></a>

**OpenMesh is open-source observability for AI agents — think OpenTelemetry, but for agent ecosystems.**

It watches the agents you already run — Claude Code, LangChain, CrewAI, MCP servers,
or your own SDK code — and turns their activity into a live graph of agents, tools,
models, workflows, traces, and relationships. Everything lands in one local event
store and is served four ways: a browser dashboard, a Control Room terminal UI,
a CLI, and an HTTP API.

- [Why OpenMesh](#why-openmesh)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Demo mode (temporary, fully erasable)](#demo-mode-temporary-fully-erasable)
- [Connecting real agents](#connecting-real-agents)
- [The web dashboard](#the-web-dashboard)
- [The Control Room TUI](#the-control-room-tui)
- [The CLI](#the-cli)
- [HTTP API](#http-api)
- [Architecture](#architecture)
- [Development](#development)
- [Documentation](#documentation)
- [Contributing & license](#contributing--license)

## Why OpenMesh

Modern AI systems are fleets of agents calling tools, editing files, running
commands, and talking to each other — and almost none of that is visible.
OpenMesh gives you the missing control room:

- **See the ecosystem** — a live network map of agents, processes, tools,
  MCP servers, workflows, and how they relate.
- **Trace the work** — every event carries a trace, session, workspace, and
  provenance, so you can replay exactly what happened and why.
- **Trust what you see** — OpenMesh never fabricates activity. A provider API
  key connects a *provider*; it does not create agents. Agents appear only when
  something real reports itself, or when you explicitly run the clearly-labeled
  demo simulation.
- **Own your data** — everything is local (SQLite by default, Postgres
  optional). No cloud services required.

## How it works

```text
your agents (Claude Code, SDK, MCP, collectors)
        │  OpenMesh events (spec 0.1)
        ▼
   collector ──► event store (SQLite / Postgres)
        │
        ▼
 graph · traces · timeline · discovery · replay · diagnostics
        │
        ▼
 dashboard (React) · Control Room TUI · CLI · HTTP API · OTel export
```

The identity model is strict about what is real:

| Source | Meaning | How it appears |
|---|---|---|
| `sdk`, `mcp`, `claude_code`, `openai_agent`, `custom` | **Real agents** | Register themselves via API/SDK and send heartbeats. Stale heartbeat → shown as `disconnected`. |
| `simulation` | **Demo agents** | Created only by "Run Demo Environment". Always labeled, isolated in the demo workspace, deleted on terminate. |

Agent lifecycle statuses: `starting → running → idle → completed / failed /
terminated / disconnected`.

Work is organized as **Provider → Workspace → Project → Agent Session →
Events & Traces**. The workspace selector scopes every page — a "Smart Glasses"
workspace shows only smart-glasses activity, the demo workspace shows only demo
activity, never mixed.

📸 **[See the dashboard in action → docs/SCREENSHOTS.md](docs/SCREENSHOTS.md)**

## Quick start

Prerequisites: Python 3.11–3.13, Node.js 20+ for the dashboard.
(Python 3.14 is not yet supported — pinned database wheels don't install there.)

```bash
git clone https://github.com/srinivasBJ/OpenMesh.git
cd OpenMesh

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

openmesh doctor          # verifies install + bootstraps local SQLite
```

Start the backend and the dashboard:

```bash
# terminal 1 — API on :8000
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
PYTHONPATH=backend python -m uvicorn src.main:app --reload --port 8000

# terminal 2 — dashboard on :5173
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173`. A fresh install shows **0 agents** and a
first-launch panel with four paths:

1. **Run Demo Environment** — explore with temporary simulated agents.
2. **Connect AI Provider** — Anthropic, OpenAI, or OpenRouter. Keys are
   validated against the provider's live API, stored encrypted on your machine
   (`~/.openmesh/`, Fernet, 0600), and hot-reloaded — no `.env`, no restart.
   Models are discovered from the provider (never hardcoded), with a curated
   top-25 view, categories, and search.
3. **Connect Existing Agent** — point Claude Code, LangChain, CrewAI, MCP, or
   your SDK code at the collector.
4. **Run SDK Example** — `python examples/python_basic_agent.py` and watch it
   appear in the graph.

## Demo mode (temporary, fully erasable)

Demo agents exist **only for exploring the product**. When you click
*Run Demo Environment*, OpenMesh creates a dedicated demo workspace
("OpenMesh Demo Network") with three simulated agents — Pioneer, Explorer,
and Scientist — clearly labeled `simulation` everywhere they appear.

While the demo runs, a **Simulation Mode** banner stays visible with two
controls:

- **Stop Demo** — pauses the simulation, keeps the data for inspection.
- **Terminate Demo** — asks for confirmation, then **deletes everything the
  demo produced**: agents, posts, events, traces, and the demo workspace
  itself. You are back to a clean install, exactly as before the demo.

Demo activity is confined to the demo workspace and can never leak into your
real workspaces. The simulator is structurally incapable of generating
activity for real agents.

## Connecting real agents

Real agents report themselves and stay alive with heartbeats:

```bash
# an agent announces itself (SDK, MCP bridge, or collector do this for you)
curl -X POST localhost:8000/api/agents/register \
  -H 'content-type: application/json' \
  -d '{"name": "Claude Code", "source": "claude_code", "model": "claude-opus"}'

# keep-alive + status reporting (stale for 90s → shown as disconnected)
curl -X POST localhost:8000/api/agents/<id>/heartbeat \
  -H 'content-type: application/json' -d '{"status": "running"}'
```

Or use the higher-level paths:

```bash
python examples/python_basic_agent.py       # OpenMesh Python SDK
python examples/python_async_agent.py
openmesh run -- <command>                   # observe any real process
openmesh mcp discover                       # discover MCP servers
```

Every event they emit is tagged with its workspace, project, session, agent,
and source, and flows into the graph in real time over WebSocket.

## The web dashboard

Same rust-industrial Control Room aesthetic across eight pages:

| Page | What it shows |
|---|---|
| **Graph** | Live network map: agents, processes, tools, workflows, MCP servers, relationships, provenance. |
| **Feed** | Activity stream (simulation content stays in the demo workspace). |
| **Agents** | Every agent with source chip, lifecycle status, and profile. |
| **Guilds / Agentpedia** | Simulation-world organization and knowledge base. |
| **History** | Event timeline, traces, and step-through replay. |
| **Observatory** | Ecosystem metrics and diagnostics. |

The top bar shows backend link, active provider · model, events/sec, agent
count, and session controls (Start / Pause / Resume / Terminate — terminate
always confirms and returns you to a clean workspace view). The Event Bus card
holds the workspace selector and project creation, including a built-in
repository folder picker.

## The Control Room TUI

Everything the dashboard shows, in your terminal — reading the same live
database. If OpenMesh is installed:

```bash
openmesh tui
```

Don't want to figure out paths or environments? The dashboard's first-launch
panel has a **copy button that produces the exact ready-to-run command for
your machine** — absolute paths included, generated by your own backend at
request time. Paste it into any terminal and the Control Room opens.

| Keys | Action |
|---|---|
| `Tab` / `Shift+Tab`, `1`–`4` | Cycle / jump between panels |
| Arrows, `PgUp/PgDn`, `Home/End`, `j/k` | Scroll tables, detail view, event stream |
| `Enter` / click | Inspect the selected row (trace, node, relationship) |
| `/` | Live global search across agents, traces, relationships, events |
| `z` / `Ctrl+L` | Pause / clear the event stream (auto-scroll holds when you scroll up) |
| `v` | Cycle sort column on the focused table |
| `E` | Export events / traces / graph to JSON + CSV |
| `5`–`0`, `w e s d l r y` | Integrations, discovery, registry, MCP, workflows, ecosystem, snapshots, diff, timeline, replay, queries |
| `?` | Full keyboard reference · `q` quit |

Tables re-render only when data changes and keep cursor and scroll position
across refreshes. `openmesh tui --once` prints a one-shot snapshot for scripts.

## The CLI

```bash
openmesh doctor                     # health + install diagnostics
openmesh run -- <command>           # observe a real process
openmesh graph --details            # the ecosystem graph, in text
openmesh discover                   # frameworks, agents, tools, capabilities
openmesh timeline                   # historical evolution
openmesh replay ecosystem --control step
openmesh snapshot create            # point-in-time snapshots + diffs
openmesh query --saved              # saved analytical queries
openmesh export otel --summary      # OpenTelemetry / Prometheus export
```

Demo data from the terminal is equally explicit — nothing is generated unless
you ask: `openmesh simulate`, `openmesh seed demo`, `openmesh demo start`,
`openmesh run-demo multi-agent`. Full inventory:
[docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md).

## HTTP API

```text
GET             /api/status/live            live snapshot (provider, agents, evt/s, tui command)
GET             /api/providers              provider + model status
POST            /api/providers/{id}/connect validate key, discover + curate models
POST            /api/providers/select       choose active (provider, model)
GET/POST/DELETE /api/workspaces             workspace CRUD
POST            /api/projects               project creation (can spawn a typed agent)
GET/POST/DELETE /api/demo/*                 demo lifecycle (terminate = full erase)
POST            /api/agents/register        real agent reports itself
POST            /api/agents/{id}/heartbeat  liveness; stale => disconnected
POST            /api/agents/session/*       start | pause | resume | terminate | delete
POST            /api/openmesh/events        ingest OpenMesh events (spec 0.1)
GET             /api/openmesh/graph|traces|timeline|replay|...   query surface
GET             /api/filesystem/browse      repo path picker (home-restricted, read-only)
```

Workspace filtering (`?workspace_id=`) is available on agents, feed, events,
and graph queries. WebSocket streaming lives at `/ws`.

## Architecture

One event path, many consumers:

```text
observe -> OpenMesh event -> collector -> persistence
        -> graph, discovery, timeline, replay, diagnostics
        -> dashboard, TUI, CLI, API, OTel export
```

Core tables: `openmesh_events` (with workspace/project/source provenance),
`openmesh_sessions`, `openmesh_snapshots`, `workspaces`, `projects`, plus the
simulation-world tables (agents, posts, guilds, wiki). Schema upgrades run
in place at startup — no manual migrations for local installs.

Security notes: provider keys are encrypted at rest and never echoed back
(masked only); write endpoints share a rate-limit/auth layer; the filesystem
browser is read-only and confined to your home directory; Postgres connection
strings are never exposed to the frontend.

Deep dives: [ARCHITECTURE.md](ARCHITECTURE.md) ·
[docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md)

## Development

```bash
# backend — 200+ tests (identity lifecycle, demo erasure, TUI regression,
# provider store, workspace isolation)
python -m unittest discover -s backend/tests

# frontend — vitest + testing-library (modal lifecycle, state refresh)
cd frontend && npm test && npm run build

# lint / release checks
ruff check .
python -m compileall backend/src
```

Reset local state completely:

```bash
rm -f ./openmesh.db
openmesh doctor
```

## Documentation

[INSTALLATION.md](INSTALLATION.md) · [QUICKSTART.md](QUICKSTART.md) ·
[STARTUP_GUIDE.md](STARTUP_GUIDE.md) · [FEATURES.md](FEATURES.md) ·
[FAQ.md](FAQ.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md) ·
[ROADMAP.md](ROADMAP.md) · [docs/](docs/)

## Contributing & license

OpenMesh welcomes focused contributions that make the platform easier to
install, validate, observe, and understand — start with
[CONTRIBUTING.md](CONTRIBUTING.md) and
[GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md).

MIT licensed. See [LICENSE](LICENSE).
