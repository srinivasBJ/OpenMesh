# OpenMesh Installation

OpenMesh can be installed as a Python package for local CLI, SDK, API, and TUI
use. The fastest first-user path uses SQLite and does not require Docker.

## Supported Python

Use Python 3.11, 3.12, or 3.13.

Python 3.14 is not supported by this release because pinned database
dependencies do not install cleanly there yet.

## Editable Install

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

This installs:

- `from openmesh import OpenMeshClient`
- the `openmesh` CLI command

For the complete startup flow, see [../STARTUP_GUIDE.md](../STARTUP_GUIDE.md).

## Local SQLite Mode

OpenMesh defaults to SQLite in development when `aiosqlite` is installed. You
can make the path explicit:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
export LLM_MODE=offline
export OPENMESH_SCHEDULER_ENABLED=0
```

Database-backed CLI commands now bootstrap the local schema automatically. A
fresh install can run:

```bash
openmesh doctor
```

Expected result:

```text
Overall: OK
```

## First Workflow

Generate a local demo ecosystem with no API keys or cloud services:

```bash
openmesh simulate --agents 20 --events 500
```

You can also observe a real process:

```bash
openmesh run -- python -c "print('hello openmesh')"
```

Inspect the observed ecosystem:

```bash
openmesh discover
openmesh graph --details
openmesh inspect openmesh.cli
openmesh timeline
openmesh replay --control step
openmesh query relationships created since 2020-01-01T00:00:00Z
openmesh tui --once
```

## SDK Examples

Run the core SDK examples:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
```

LangGraph is optional:

```bash
python -m pip install langgraph
python examples/langgraph_basic.py
```

Validate example output:

```bash
openmesh doctor
openmesh discover
openmesh graph --details
openmesh timeline
openmesh replay --control step
openmesh query traces involving research-agent
```

## Backend API

The backend is optional for CLI-only use. Start it when you want REST APIs,
WebSocket streaming, or the browser dashboard:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
export LLM_MODE=offline
export WARMUP_TICKS=0
export OPENMESH_SCHEDULER_ENABLED=0
uvicorn src.main:app --reload --port 8000
```

Health checks:

```text
GET http://localhost:8000/health
GET http://localhost:8000/health/ready
```

## Frontend Dashboard

The dashboard is a temporary browser visualization layer:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Set `OPENMESH_SCHEDULER_ENABLED=1` only when you intentionally want the legacy
scheduled simulator to run in the background.

## Postgres Mode

SQLite is recommended for local first use. To use Postgres:

```bash
export OPENMESH_DB_MODE=postgres
export DATABASE_URL=postgresql://openmeshai:password@localhost:5432/openmeshai_db
docker compose up -d postgres redis
openmesh doctor
```

## Package Install

When published to PyPI:

```bash
python -m pip install openmesh
```

Then validate:

```bash
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh graph
openmesh tui --once
```

## Troubleshooting

- `openmesh: command not found`: activate the virtualenv where you installed OpenMesh.
- `Requires-Python` or `psycopg2` build errors: use Python 3.11, 3.12, or 3.13.
- `openmesh doctor` reports missing tables: upgrade to the latest checkout and rerun `openmesh doctor`; schema bootstrap now runs before database-backed CLI commands.
- SDK examples report `no such table: openmesh_events`: upgrade to the latest checkout and reinstall; the SDK now bootstraps schema before its first event.
- `Not installed` integration status: the OpenMesh plugin exists, but the optional external framework package is not installed.
- Postgres connection errors: verify `DATABASE_URL`, the database server, and credentials, then rerun `openmesh doctor`.

For more recovery paths, see [../TROUBLESHOOTING.md](../TROUBLESHOOTING.md).
