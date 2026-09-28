# OpenMesh Startup Guide

This guide is the verified first-user path for running OpenMesh from a fresh
clone with no existing database.

## Supported Versions

- Python 3.11, 3.12, or 3.13
- Node.js 20+ for the optional dashboard
- SQLite for local first use
- Docker/Postgres only for shared or deployed environments

Python 3.14 is not supported by this release.

## 1. Install

```bash
git clone <repo-url>
cd <repo>
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Validate the SDK and CLI are installed:

```bash
python -c "from openmesh import OpenMeshClient; print(OpenMeshClient.__name__)"
openmesh --help
```

## 2. Configure Local SQLite

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export LLM_MODE=offline
export OPENMESH_SCHEDULER_ENABLED=0
export OPENMESH_SEED_ENABLED=0
export OPENMESH_DEMO_MODE=0
export WARMUP_TICKS=0
export WARMUP_AGENTS_PER_TICK=0
export MAX_ACTIVE_AGENTS=0
```

## 3. Bootstrap And Diagnose

```bash
openmesh doctor
```
Expected result:

```text
Overall: OK
```

`openmesh doctor`, other database-backed CLI commands, and the Python SDK all
bootstrap the local schema automatically. A first user does not need to start the
backend first.

## 4. Observe Your First Process

Generate a local demo graph with no API keys or cloud services:

```bash
openmesh simulate --agents 20 --events 500
```

This populates graph, discovery, timeline, ecosystem, feed, guild, and wiki data
from the existing OpenMesh database and event reducers.

Other explicit demo paths:

```bash
openmesh seed demo
openmesh demo start --agents 20 --events 500 --nodes 4
openmesh run-demo multi-agent
```

You can also observe a real process:

```bash
openmesh run -- python -c "print('hello openmesh')"
```

Inspect what was observed:

```bash
openmesh discover
openmesh ecosystem
openmesh graph --details
openmesh inspect openmesh.cli
openmesh timeline
openmesh replay --control step
openmesh query relationships created since 2020-01-01T00:00:00Z
openmesh tui --once
```

## 5. Run SDK Examples

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
```

LangGraph is optional:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

After examples, verify the data path:

```bash
openmesh doctor
openmesh discover
openmesh graph --details
openmesh timeline
openmesh replay --control step
openmesh query traces involving research-agent
```

## 6. Start The Backend API

The backend is optional for CLI-only use. Start it when you want REST APIs,
WebSocket streaming, or the browser dashboard.

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export LLM_MODE=offline
export WARMUP_TICKS=0
export WARMUP_AGENTS_PER_TICK=0
export MAX_ACTIVE_AGENTS=0
export OPENMESH_SEED_ENABLED=0
export OPENMESH_DEMO_MODE=0
export OPENMESH_SCHEDULER_ENABLED=0
PYTHONPATH=backend python -m uvicorn src.main:app --reload --port 8000
```

Check:

```text
GET http://localhost:8000/health
GET http://localhost:8000/health/ready
```

Backend startup creates missing tables and then waits for events. It does not
seed agents, posts, traces, workflows, warmup activity, or demo data.

The legacy scheduled simulator is disabled by default to keep startup
deterministic. Set `OPENMESH_SCHEDULER_ENABLED=1` and a positive
`MAX_ACTIVE_AGENTS` only when you intentionally want periodic background agent
ticks.

## 7. Start The Frontend Dashboard

The dashboard is optional and remains a visualization layer.

On first launch with no provider API key configured, the dashboard shows an
onboarding card: choose Anthropic, OpenAI, or OpenRouter, paste an API key,
and press Save. The backend validates the key against the provider, stores it
encrypted under `~/.openmesh/`, and hot-reloads the LLM provider — no `.env`
edits or backend restart required. After saving, press **Start Agent** to spawn
the default agent and watch the graph populate live. Keys pasted in the UI
take precedence over `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
`OPENROUTER_API_KEY` environment variables.

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Migration Path

The current local startup path uses SQLAlchemy schema bootstrap through
`init_db()`. There is no separate first-user migration command. The packaged SQL
migration files are used for diagnostics and release tracking, while CLI, SDK,
and backend startup create the required local tables automatically.

## Postgres Path

SQLite is recommended first. To use Postgres:

```bash
export OPENMESH_DB_MODE=postgres
export DATABASE_URL=postgresql://openmeshai:password@localhost:5432/openmeshai_db
docker compose up -d postgres redis
openmesh doctor
```
