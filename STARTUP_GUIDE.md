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
export OPENMESH_SQLITE_PATH=./openmesh.db
export LLM_MODE=offline
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
export OPENMESH_SQLITE_PATH=./openmesh.db
export LLM_MODE=offline
export WARMUP_TICKS=0
uvicorn src.main:app --reload --port 8000
```

Check:

```text
GET http://localhost:8000/health
GET http://localhost:8000/health/ready
```

Backend startup creates missing tables and seeds the legacy dashboard simulation
data when the database is empty.

## 7. Start The Frontend Dashboard

The dashboard is optional and remains a visualization layer.

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
