# OpenMesh Installation Audit

Date: 2026-06-03

Scope: first-user install, startup, database bootstrap, repository cleanliness,
documentation consistency, and command validation.

## Summary

OpenMesh is installable and usable from a fresh Python 3.11 environment after
this audit fix. The main blocker was that CLI commands opened database sessions
without creating the required schema. `openmesh doctor` could connect to a fresh
SQLite database, but then reported missing tables and failed diagnostics because
`openmesh_events` did not exist.

The CLI now quietly runs the same SQLAlchemy schema bootstrap used by backend
startup before database-backed commands. Errors are not hidden: if schema
creation fails, the CLI reports the database exception.

Follow-up validation found and fixed two additional first-user blockers:

- Python SDK examples could fail on a fresh database with `no such table:
  openmesh_events` because the SDK opened sessions without schema bootstrap.
- The LangGraph example created a workflow node with no graph relationship,
  causing `openmesh doctor` ecosystem warnings after the example ran.

## Phase 1 - Repository Audit

### Backend

- `backend/src/main.py` is the FastAPI backend entrypoint.
- `backend/src/cli/openmesh.py` is the primary CLI entrypoint.
- `backend/src/cli/tui.py` is the terminal UI.
- `backend/src/db/session.py` owns database URL resolution, async engine setup,
  and schema initialization.
- `backend/src/services/*` contains current OpenMesh read models, collectors,
  discovery, graph, trace, snapshot, timeline, replay, query, plugin, federation,
  and evaluation services.
- `backend/src/agents/*`, `backend/src/services/seeder.py`, and legacy API/feed
  routes are still active for the temporary dashboard and simulation layer.

### Entrypoints

Canonical startup paths:

- CLI: console script `openmesh`, installed from `scripts/openmesh`.
- Python CLI module: `openmesh.cli`, which delegates to `src.cli.openmesh.main`.
- Backend API: `uvicorn src.main:app --reload --port 8000`.
- Frontend dashboard: `cd frontend && npm run dev`.

Other files that look like entrypoints are compatibility or implementation
details:

- `backend/src/openmesh.py` exposes package metadata and SDK exports.
- `backend/src/cli/openmesh.py` implements the CLI commands.
- `backend/src/cli/tui.py` implements the TUI.

This should be clearer in onboarding docs because first users otherwise have to
infer which startup path is canonical.

### Frontend

- `frontend/` is a React/Vite dashboard.
- It remains functional, but it is not the primary OpenMesh user experience.
- The dashboard should be described as a temporary visualization layer over the
  protocol and collector data.

### Docs

- `README.md` previously led with backend/frontend startup before CLI install.
- `docs/INSTALLATION.md` previously said tables were initialized by starting the
  backend once and that CLI-only validation could report missing tables.
- Release docs and hardening docs already described the need for explicit wheel
  and install validation.

### Examples

- Python SDK examples exist and are runnable.
- Integration examples exist for LangGraph, CrewAI, AutoGen, OpenHands, Claude
  Code, and OpenCode.
- Some framework examples require optional external packages. Metadata-only
  examples for CLI-style integrations run without those optional packages.

### Legacy OpenMeshAI Remnants

The repository still contains legacy OpenMeshAI terminology in:

- README vision sections
- FastAPI app title and health payloads
- agent simulator, brain prompts, seed data, and WebSocket metadata
- frontend package name `@openmeshai/frontend`

These are not first-user install blockers, but they make the product story less
clear. They should be cleaned in a later naming pass, not during install
hardening.

## Phase 2 - Startup Audit

### Exact Installation Steps

```bash
git clone <repo-url>
cd <repo>
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Supported Python range: `>=3.11,<3.14`.

### Exact Database Initialization Path

For CLI users:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
openmesh doctor
```

Database-backed CLI commands now call `init_db(announce=False)` before opening a
session, so fresh SQLite schemas are created automatically.

For backend users:

```bash
uvicorn src.main:app --reload --port 8000
```

Backend startup calls `init_db()` and then seeds the legacy dashboard data when
the database is empty.

### Exact Backend Startup Path

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
export LLM_MODE=offline
uvicorn src.main:app --reload --port 8000
```

Validated health endpoint:

```text
GET http://localhost:8000/health
```

### Exact Frontend Startup Path

```bash
cd frontend
npm install
npm run dev
```

Validated URL:

```text
http://localhost:5173
```

### Exact CLI Startup Path

```bash
openmesh doctor
openmesh run -- python -c "print('hello openmesh')"
openmesh discover
openmesh graph --details
openmesh inspect openmesh.cli
```

### Exact TUI Startup Path

```bash
openmesh tui
```

For non-interactive validation:

```bash
openmesh tui --once
```

## Phase 3 - Database Audit

### Root Cause

`backend/src/main.py` called `init_db()` during FastAPI startup, but
`backend/src/cli/openmesh.py` did not. A new user using only the CLI would get:

```text
migrations: ERROR
  missing tables: agent_events, agents, openmesh_events, openmesh_sessions, openmesh_snapshots
OpenMesh Diagnostics: ERROR
  no such table: openmesh_events
```

### Fix

- `backend/src/db/session.py` now supports `init_db(announce=False)`.
- `backend/src/cli/openmesh.py` calls `init_db(announce=False)` inside `_with_db`
  before opening a database session.
- `backend/src/sdk/client.py` calls `init_db(announce=False)` once per
  `OpenMeshClient` before its first persisted event.

This creates the schema for SQLite or Postgres-backed CLI commands. If database
creation fails, the command still returns a database error.

### Example Flow Finding

The SDK examples previously failed on a clean database unless `openmesh doctor`
or backend startup had already created tables. This is fixed by SDK bootstrap.

The LangGraph example previously generated a workflow node without a
relationship, so ecosystem diagnostics reported the workflow as orphaned. The
LangGraph integration now emits `LangGraph -> runs -> <workflow>` through the
existing `workflow.started` event shape.

### Packaging Finding

A fresh install using the system `python3` resolved to Python 3.14 and failed
while building pinned database dependencies. `pyproject.toml` previously allowed
`>=3.11` even though this dependency stack is only validated on Python
3.11-3.13. The package metadata now declares `>=3.11,<3.14`.

## Phase 4 - Cleanup Audit

Duplicate files were identified but not deleted.

### Safe To Delete After Maintainer Confirmation

These are exact duplicates of current source files:

- `backend/src/cli/__init__ 2.py`
- `backend/src/db/migrations/001_create_openmesh_events 2.sql`
- `backend/src/db/migrations/002_create_openmesh_sessions 2.sql`
- `backend/src/shared/__init__ 2.py`
- `docs/VISION 2.md`

Generated build copies under `build/lib/` and duplicate `__pycache__/* 2.pyc`
files are untracked build/cache artifacts and can also be removed with the
build/cache directories after confirmation.

### Unsafe To Delete Without Review

These duplicate-named files differ from their canonical versions and may contain
old implementation work:

- `backend/src/cli/openmesh 2.py`
- `backend/src/cli/tui 2.py`
- `backend/src/db/openmesh_events 2.py`
- `backend/src/db/openmesh_sessions 2.py`
- `backend/src/services/graph_state 2.py`
- `backend/src/services/openmesh_collector 2.py`
- `backend/src/services/openmesh_doctor 2.py`
- `backend/src/services/openmesh_queries 2.py`
- `backend/src/shared/openmesh_events 2.py`
- `backend/tests/test_openmesh_core 2.py`
- `docs/ARCHITECTURE 2.md`
- `docs/DECISIONS 2.md`
- `docs/ROADMAP 2.md`
- `frontend/src/types/openmesh 2.ts`

Recommendation: review diffs, archive anything valuable, then delete these in a
dedicated cleanup commit.

### Other Untracked Files To Review

- `ARCHITECTURE_AUDIT.md` and `OpenMesh_Architecture_Overview.md` appear to be
  standalone documentation drafts from previous work.
- `docs/protocol/` appears to be protocol documentation from previous work.
- root `package-lock.json` is suspicious because the tracked frontend lockfile
  lives at `frontend/package-lock.json`.

These were not modified or deleted during this install audit.

## Phase 5 - User Journey Validation

Validated in a fresh Python 3.11 virtualenv:

```bash
python -m pip install -e .
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh doctor
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh discover
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh graph
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh run -- python -c "print('hello openmesh')"
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh inspect openmesh.cli
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh timeline
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh replay --control step
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh query relationships created since 2020-01-01T00:00:00Z
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-first-user.db openmesh tui --once
```

All commands completed successfully after schema bootstrap.

### Clean Clone Product Audit

Validated from a clean `git archive HEAD` copy with no local database:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
npm install --prefix frontend
```

Validation commands:

```bash
openmesh doctor
openmesh discover
openmesh ecosystem
openmesh graph
openmesh integrations
openmesh run -- python -c "print('hello openmesh product audit')"
openmesh graph --details
openmesh inspect openmesh.cli
openmesh timeline
openmesh replay --control step
openmesh query relationships created since 2020-01-01T00:00:00Z
openmesh tui --once
```

All commands completed successfully.

SDK and LangGraph examples were validated from a fresh database:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
python -m pip install langgraph
python examples/langgraph_basic.py
openmesh doctor
openmesh discover
openmesh graph --details
openmesh timeline
openmesh replay --control step
openmesh query traces involving research-agent
```

The fixed example database ended with `openmesh doctor` reporting `Overall: OK`.
Graph output included:

```text
Research Agent --uses--> web_search
Async Research Agent --uses--> web_search
LangGraph --runs--> LangGraph Basic
Node A --transitions_to--> Node B
Node B --transitions_to--> Node C
```

Backend startup was validated with:

```bash
OPENMESH_DB_MODE=sqlite \
OPENMESH_SQLITE_PATH=/tmp/openmesh-backend-startup.db \
LLM_MODE=offline \
WARMUP_TICKS=0 \
uvicorn src.main:app --host 127.0.0.1 --port 8127
```

`GET /health` returned:

```json
{"status":"alive","civilization":"OpenMeshAI v1.0"}
```

Frontend startup was validated with:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5193
```

The Vite dev server returned the dashboard HTML.

## Phase 6 - Documentation Validation

Updated:

- `README.md`
- `docs/INSTALLATION.md`
- `STARTUP_GUIDE.md`
- `TROUBLESHOOTING.md`

Together they document:

- Python 3.11-3.13 support
- SQLite-first setup
- automatic CLI schema bootstrap
- first observed workflow
- backend startup
- frontend startup
- CLI/TUI commands
- troubleshooting

`STARTUP_GUIDE.md` documents the exact first-user path. `TROUBLESHOOTING.md`
documents observed install, schema, SDK, LangGraph, frontend, and legacy naming
issues.

## Remaining Risks

- Repository still contains duplicate `* 2.*` files in the working tree.
- Some legacy OpenMeshAI naming remains in active simulation/dashboard code.
- Optional integrations report `Not installed` unless their external framework
  packages are installed.
- Python 3.14 should remain unsupported until dependencies are validated there.
- `npm install` in the frontend reports existing dependency audit warnings.
- There is no standalone migration command; first-user schema creation is
  currently handled by CLI, SDK, and backend bootstrap.
