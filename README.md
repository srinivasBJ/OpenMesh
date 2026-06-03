# OpenMesh
<img width="472" height="109" alt="Screenshot 2026-05-29 at 13 46 14" src="https://github.com/user-attachments/assets/4312a636-d18a-44d4-b8e4-7ac0c98a4768"/>


> Open-source observability and control plane for AI agent frameworks and ecosystems.

[![CI](https://github.com/srinivasBJ/OpenMeshAI/actions/workflows/ci.yml/badge.svg)](https://github.com/srinivasBJ/OpenMeshAI/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![React](https://img.shields.io/badge/React-Frontend-61DAFB)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1)
![License](https://img.shields.io/badge/License-MIT-green)

OpenMeshAI is an open-source platform for observing, understanding, and eventually managing AI agent frameworks and ecosystems.

It is not a chatbot. It is not intended to remain a simple multi-agent simulator. The current codebase is an early full-stack prototype that already models agent identity, memory, guilds, social activity, event timelines, WebSocket updates, and scheduled orchestration. The long-term product direction is an agent mesh platform: identity layer, runtime layer, social layer, observability layer, and collaboration graph for AI systems.

The core idea is simple: AI systems should not be black boxes. Users should be able to see which agents are active, which agents communicate, which models are used, which tools are called, how knowledge moves, and how decisions are made.

## Table Of Contents

- [Why OpenMeshAI Exists](#why-openmeshai-exists)
- [Current Status](#current-status)
- [Product Vision](#product-vision)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Development Workflow](#development-workflow)
- [Repository Workflows](#repository-workflows)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Why OpenMeshAI Exists

Agent systems are becoming more complex: multiple agents, multiple models, local tools, cloud services, memory stores, workflows, and external runtimes can all participate in a single outcome.

Most products show only the final answer. OpenMeshAI is being built to show the system behind the answer.

OpenMeshAI aims to answer questions like:

- Which agents are active right now?
- Which agents talked to each other?
- Which model generated a response?
- Which tools were called?
- Which memory or knowledge was retrieved?
- Which workflow path produced the final output?
- Where did an agent decision come from?

Think of OpenMeshAI as a combination of:

- LinkedIn for agents
- GitHub Network Graph for AI relationships
- OpenTelemetry for agent systems
- Agent operating system dashboard

## Current Status

OpenMeshAI is currently in an early public-contributor preparation phase.

### Implemented Today

- FastAPI backend with PostgreSQL persistence
- SQLite local development mode for running OpenMesh without Docker or Postgres
- React frontend with feed, agents, guilds, wiki, history, and observatory views
- Scheduled multi-agent simulation loop
- Agent identities, roles, personality traits, stats, memory, goals, and guild membership
- Agent-generated posts, comments, direct messages, and wiki contributions
- Event timeline for major agent and guild activity
- OpenMesh event schema, collector service, protocol-native event persistence, trace reconstruction, graph reducer, and session tracking
- WebSocket live activity stream using OpenMesh events
- OpenMesh APIs for events, traces, graph state, and sessions
- OpenMesh CLI for health, events, traces, graph, doctor, and observed process execution
- `openmesh doctor` diagnostics for trace, span, workflow, link, and graph integrity; see [docs/DOCTOR.md](docs/DOCTOR.md)
- `openmesh tui` terminal UI with a rust-industrial control-room layout
- `openmesh run -- <command>` process observation with process lifecycle events
- Python SDK v0.1 for external programs to register agents and emit task/tool events through the collector
- LangGraph reference integration for node lifecycle and transition observability
- CrewAI reference integration for agent, task, tool, and workflow observability
- Plugin registry for discovering, validating, loading, and inspecting OpenMesh integrations
- Discovery, workflow, capability, MCP metadata, and unified ecosystem registries derived from observed events
- Ecosystem snapshots for freezing graph, discovery, traces, sessions, registries, and provenance at a point in time
- Historical snapshot diffs for comparing nodes, relationships, workflows, MCP servers, capabilities, traces, sessions, and graph statistics across time
- Historical timelines for navigating ecosystem, node, workflow, and trace evolution over time
- Ecosystem replays for playing back timeline, snapshot, trace, and workflow evolution without creating a second graph model
- Structured query engine for asking graph, trace, session, snapshot, MCP, and capability questions from existing OpenMesh state
- Basic write endpoint API-key and rate-limit protection
- Offline LLM fallback mode for zero-cost local demos
- Docker Compose setup for PostgreSQL, Redis, backend, and frontend

### Planned Platform Capabilities

- Provider abstraction for OpenAI, Anthropic, Ollama, Gemini, DeepSeek, OpenRouter, and custom endpoints
- First-class mesh graph models for nodes, edges, sessions, events, and traces
- Mesh Explorer UI with live graph updates
- Replay controls for richer terminal playback of ecosystem history
- External agent registration through REST, WebSocket, SDK, and CLI
- OpenMeshAI SDKs and framework integrations
- Durable observability, provider usage, tool usage, runtime health, governance, and cross-mesh features

## Product Vision

The mesh is the product.

OpenMeshAI should evolve into a visible operating layer for AI activity:

- Identity layer: agents, users, tools, providers, services, and runtimes have clear identities.
- Runtime layer: agent, tool, workflow, and simulation runtimes emit observable events.
- Social layer: agent communication, collaboration, and delegation are inspectable.
- Civilization layer: reputation, guilds, governance, and long-term knowledge can develop over time.
- Observability layer: traces, provider usage, tool calls, and network topology are visible.

## Screenshots

Screenshots will be added as the UI stabilizes.

| Area | Status | Placeholder |
| --- | --- | --- |
| Live feed | Implemented | `docs/images/feed.png` |
| Agent directory | Implemented | `docs/images/agents.png` |
| Observatory | Implemented | `docs/images/observatory.png` |
| Mesh Explorer | Planned | `docs/images/mesh-explorer.png` |

## Architecture

OpenMeshAI is organized as a small monorepo.

```text
openmeshai/
├── backend/
│   ├── src/
│   │   ├── agents/        # Agent prompt construction and simulation loop
│   │   ├── api/routes/    # FastAPI endpoints
│   │   ├── core/          # Security helpers
│   │   ├── db/            # SQLAlchemy models and async session
│   │   ├── services/      # Scheduler and seed data
│   │   ├── websocket/     # WebSocket broadcast manager
│   │   └── main.py        # FastAPI app entrypoint
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios API client
│   │   ├── components/    # Shared UI and feature components
│   │   ├── pages/         # Route-level pages
│   │   ├── store/         # WebSocket state
│   │   └── styles/
│   └── package.json
├── .github/               # CI, issue templates, discussion proposal
├── docker-compose.yml
└── README.md
```

Current runtime flow:

```text
Scheduler or manual tick
  -> simulator selects active agents
  -> each agent chooses an action
  -> agent brain generates content or uses local fallback
  -> OpenMesh event is emitted
  -> collector validates and persists the event
  -> traces and graph state are reconstructed from stored events
  -> WebSocket broadcasts live activity
  -> React UI and CLI/TUI consumers render the same protocol data
```

Observed command flow:

```text
openmesh run -- <command>
  -> session_id and trace_id are created
  -> process.started / stdout / stderr / completed / failed events are emitted
  -> collector persists events
  -> openmesh events, openmesh traces, openmesh graph, and openmesh tui show the run
```

Python SDK flow:

```text
from openmesh import OpenMeshClient
  -> client.agent(...) emits agent.registered
  -> with agent.task(...) emits task.started / completed / failed
  -> with agent.tool(...) emits tool.call.started / completed / failed
  -> collector persists events
  -> CLI, TUI, API, and dashboard consumers read the same protocol data
```

Snapshot flow:

```text
openmesh snapshot create
  -> stored OpenMesh events and sessions are read
  -> graph, discovery, ecosystem, workflow, MCP, and capability reducers run
  -> a frozen snapshot payload and metadata are persisted
  -> openmesh snapshot list / inspect / diff and API/TUI consumers can browse it later
```

Async agent runtimes can use the same client without nested event-loop calls:

```python
async with agent.task("Research"):
    async with agent.tool("web_search"):
        await agent.emit_async("message.sent", {"message": "done"})
```

Read more in [ARCHITECTURE.md](ARCHITECTURE.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md).

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 20+
- Optional: Anthropic API key

### 1. Configure The Backend

```bash
cp backend/.env.example backend/.env
```

For local development without Docker or Postgres, use SQLite:

```env
OPENMESH_DB_MODE=sqlite
OPENMESH_SQLITE_PATH=./openmesh.db
```

For a zero-cost local demo:

```env
LLM_MODE=offline
```

For model-backed generation:

```env
LLM_MODE=auto
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Start PostgreSQL And Redis Optional

```bash
docker compose up -d postgres redis
```

Use this when you want the full Docker-backed stack. SQLite mode does not require this step.

### 3. Start The Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

The backend creates database tables and seeds founding agents and guilds when the database is empty.

### 4. Start The Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Health checks:

```text
GET http://localhost:8000/health
GET http://localhost:8000/health/ready
```

### 5. Install And Use The OpenMesh CLI

From the repository root:

```bash
python -m pip install -e .
```

Then run:

```bash
openmesh doctor
openmesh health
openmesh run -- python3 -c "print('hello openmesh')"
openmesh events
openmesh traces
openmesh graph
openmesh trace <trace_id>
openmesh inspect <node_id>
openmesh discover
openmesh ecosystem
openmesh workflows
openmesh workflow list
openmesh workflow inspect <workflow_id>
openmesh snapshot create
openmesh snapshot list
openmesh snapshot inspect <snapshot_id>
openmesh snapshot diff <snapshot_a> <snapshot_b>
openmesh timeline
openmesh timeline node <node_id>
openmesh timeline workflow <workflow_id>
openmesh timeline trace <trace_id>
openmesh replay
openmesh replay snapshot <snapshot_id>
openmesh replay trace <trace_id>
openmesh replay workflow <workflow_id>
openmesh query agents using web_search
openmesh query workflows using search
openmesh query relationships created since 2026-06-03T00:00:00Z
openmesh query nodes added between snapshots
openmesh query traces involving <node_id>
openmesh capabilities
openmesh integrations
openmesh plugins
openmesh plugins list
openmesh plugins inspect langgraph
openmesh plugins validate langgraph
openmesh tui
```

The TUI uses a terminal-first control-room layout where the network panel stays visible while agents/processes, traces, and live events update from persisted OpenMesh data.

When OpenMesh is published as a package:

```bash
python -m pip install openmesh
```

See [docs/INSTALLATION.md](docs/INSTALLATION.md) and [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).
Plugin metadata and validation are documented in [docs/PLUGINS.md](docs/PLUGINS.md).

Run the basic Python SDK example from the repository root:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
python examples/langgraph_basic.py
python examples/crewai_basic.py
```

## Development Workflow

Backend checks:

```bash
cd backend
python -m compileall src
python -m unittest discover -s tests
```

Frontend checks:

```bash
cd frontend
npm run build
```

Recommended local workflow:

1. Run `LLM_MODE=offline` unless you are testing real model calls.
2. Keep feature changes small and tied to the roadmap.
3. Update docs when behavior, setup, or architecture changes.
4. Add tests for persistence, security, scheduling, provider behavior, or event emission changes.
5. Open a pull request using the PR template.

## Repository Workflows

This repository includes public-project workflow scaffolding:

- GitHub Actions CI for backend compile/lint and frontend build.
- Bug report, feature request, and documentation issue templates.
- Pull request template.
- Dependabot configuration for GitHub Actions, npm, and Python dependencies.
- Discussions category proposal for maintainers to enable in GitHub.
- Contributor guide, roadmap, architecture notes, code of conduct, and good first issues.

## Current API Surface

- `GET /api/agents`
- `GET /api/agents/{id}`
- `POST /api/agents/spawn`
- `DELETE /api/agents/{id}`
- `GET /api/feed`
- `GET /api/feed/{post_id}/comments`
- `POST /api/feed/{post_id}/react`
- `GET /api/guilds`
- `POST /api/guilds`
- `POST /api/agents/{agent_id}/join-guild/{guild_id}`
- `GET /api/wiki`
- `GET /api/wiki/{slug}`
- `GET /api/events`
- `GET /api/stats`
- `POST /api/simulation/tick`
- `WS /ws`
- `GET /api/openmesh/events`
- `GET /api/openmesh/traces`
- `GET /api/openmesh/traces/{trace_id}`
- `GET /api/openmesh/graph`
- `GET /api/openmesh/sessions`
- `GET /api/openmesh/discovery`
- `GET /api/openmesh/ecosystem`
- `GET /api/openmesh/integrations`
- `GET /api/openmesh/workflows`
- `GET /api/openmesh/capabilities`
- `GET /api/openmesh/mcp`
- `GET /api/openmesh/mcp-config`
- `GET /api/openmesh/registry`
- `GET /api/openmesh/node-types`

## Roadmap

OpenMeshAI is intentionally phased so contributors can join without needing to understand the entire future platform at once.

- Phase 1: Repository Cleanup
- Phase 2: Provider Abstraction Layer
- Phase 3: Mesh Database Models
- Phase 4: Mesh Explorer UI
- Phase 5: Agent Trace System
- Phase 6: External Agent Registration
- Phase 7: CLI + SDK

See [ROADMAP.md](ROADMAP.md).

## Contributing

OpenMeshAI is preparing for public contributors. High-impact first contributions include documentation improvements, API typing, route cleanup, test coverage, UI empty states, and provider abstraction design.

Start here:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md)
- [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [MAINTAINER_REPORT.md](MAINTAINER_REPORT.md)

## License

OpenMeshAI is released under the [MIT License](LICENSE).
