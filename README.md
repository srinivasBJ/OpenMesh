# OpenMesh
  ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ <img width="472" height="109" alt="a" src="https://github.com/user-attachments/assets/6acd38d6-bed6-48d1-8e2d-9065053be75f" />

OpenMesh is a terminal-first observability layer for AI agent ecosystems.

It observes agents, tools, models, runtimes, MCP servers, workflows, traces,
relationships, failures, reputation, genome profiles, snapshots, replay, and
OpenTelemetry export from one local event store.

The fastest first run uses SQLite. No API keys, Docker, Postgres, cloud LLMs, or
external services are required for the local graph demo.

Default backend startup is intentionally empty. Starting the API creates the
database schema and waits for events; it does not create agents, posts, traces,
workflows, warmup ticks, or demo ecosystems. Demo data appears only after an
explicit command such as `openmesh simulate`, `openmesh seed demo`,
`openmesh demo start`, `openmesh run-demo research`, or
`openmesh run-demo multi-agent`.

## Status

OpenMesh v1.0 alpha is release-candidate software. The core architecture works,
the CLI/TUI/API/frontend can read the same SQLite event store, and the project is
being hardened for public launch and contributor onboarding.

Known alpha limits:

- Optional framework packages such as LangGraph, CrewAI, AutoGen, and OpenHands
  are not installed by default.
- Real LLM demos require configured provider keys or local model servers.
- Large graph, timeline, replay, and genome payloads are not paginated yet.
- The browser dashboard is a visualization layer; the CLI and TUI are the
  primary OpenMesh consumers.

## Quick Start

Prerequisites:

- Python 3.11, 3.12, or 3.13
- Node.js 20+ only if you want the browser dashboard
- Docker only if you want Postgres instead of SQLite

Python 3.14 is not supported in this alpha because pinned database wheels do not
install reliably there yet.

```bash
git clone https://github.com/srinivasBJ/OpenMesh.git
cd OpenMesh

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export OPENMESH_SEED_ENABLED=0
export OPENMESH_DEMO_MODE=0
export WARMUP_TICKS=0
export WARMUP_AGENTS_PER_TICK=0
export MAX_ACTIVE_AGENTS=0

openmesh doctor
openmesh simulate --agents 12 --events 180 --nodes 4
openmesh graph --details
openmesh discover
openmesh ecosystem
openmesh timeline
openmesh replay ecosystem --control step
openmesh tui --once
```

That path should take less than five minutes on a fresh clone.

## First Workflow

Start from an empty platform:

```bash
openmesh doctor
openmesh graph --details
```

Generate local ecosystem data only when you want demo data:

```bash
openmesh simulate --agents 20 --events 500 --nodes 4
```

Alternative demo entry points:

```bash
openmesh seed demo
openmesh demo start --agents 20 --events 500 --nodes 4
openmesh run-demo multi-agent
openmesh run-demo research --provider openai
```

Observe a real process:

```bash
openmesh run -- python -c "print('hello openmesh')"
```

Inspect the resulting ecosystem:

```bash
openmesh events
openmesh traces
openmesh graph --details
openmesh nodes
openmesh inspect "Research Agent"
openmesh workflows
openmesh workflow inspect workflow:openmesh:multi-agent-handoff-demo
openmesh snapshot create
openmesh timeline
openmesh query --limit 1000 agents using web_search
```

## Browser Dashboard

The dashboard uses the same API and event store. Start the backend first:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0
export WARMUP_AGENTS_PER_TICK=0
export MAX_ACTIVE_AGENTS=0
PYTHONPATH=backend python -m uvicorn src.main:app --reload --port 8000
```

Then start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Routes currently expected to render:

- `/`
- `/graph`
- `/feed`
- `/agents`
- `/guilds`
- `/wiki`
- `/history`
- `/observatory`

## SDK Examples

Core SDK examples run without optional framework packages:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
```

Optional integration examples require their framework package or local runtime:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

## Major Commands

```bash
openmesh doctor
openmesh health
openmesh simulate --agents 20 --events 500 --nodes 4
openmesh seed demo
openmesh demo start --agents 20 --events 500 --nodes 4
openmesh run -- <command>
openmesh run-demo multi-agent
openmesh providers verify
openmesh providers discover
openmesh models list
openmesh runtimes discover
openmesh mcp discover
openmesh discover
openmesh ecosystem
openmesh graph --details
openmesh inspect <node>
openmesh workflows
openmesh workflow inspect <workflow_id>
openmesh timeline
openmesh replay ecosystem --control step
openmesh snapshot create
openmesh snapshot list
openmesh query --saved
openmesh failures
openmesh rankings
openmesh genome <agent>
openmesh export otel --summary
openmesh export prometheus --summary
openmesh tui
```

Full command inventory: [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md).

## Architecture

OpenMesh follows one event path:

```text
observe
  -> OpenMesh event
  -> collector
  -> persistence
  -> graph, discovery, timeline, replay, diagnostics
  -> CLI, TUI, API, frontend, export
```

Core persisted tables:

- `openmesh_events`
- `openmesh_sessions`
- `openmesh_snapshots`
- legacy dashboard tables for feed, agents, guilds, wiki, and simulation state

Subsystem inventory: [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md).

## Documentation

- [INSTALLATION.md](INSTALLATION.md)
- [QUICKSTART.md](QUICKSTART.md)
- [FEATURES.md](FEATURES.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [FAQ.md](FAQ.md)
- [docs/INTEGRATION_AUDIT.md](docs/INTEGRATION_AUDIT.md)
- [docs/CI_AUDIT.md](docs/CI_AUDIT.md)
- [docs/REPOSITORY_AUDIT.md](docs/REPOSITORY_AUDIT.md)
- [docs/FIRST_RUN_AUDIT.md](docs/FIRST_RUN_AUDIT.md)
- [docs/OPENMESH_V1_ALPHA_REPORT.md](docs/OPENMESH_V1_ALPHA_REPORT.md)

## Validation

Recommended local release checks:

```bash
ruff check .
ruff format --check .
python -m compileall backend/src
python -m unittest discover -s backend/tests
cd frontend && npm run build
```

Wheel smoke:

```bash
python -m pip install build
python -m build --wheel
python -m venv /tmp/openmesh-wheel-smoke
/tmp/openmesh-wheel-smoke/bin/python -m pip install dist/openmesh-*.whl
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-wheel.db \
  /tmp/openmesh-wheel-smoke/bin/openmesh doctor
```

Reset local SQLite state:

```bash
rm -f ./openmesh.db
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=./openmesh.db openmesh doctor
```

Provider demos are explicit. Configure one of these before running
`openmesh run-demo research`:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export OPENROUTER_API_KEY=...
export OLLAMA_BASE_URL=http://localhost:11434
```

## Contributing

OpenMesh welcomes focused contributions that make the existing product easier to
install, validate, observe, and understand. Start with
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
