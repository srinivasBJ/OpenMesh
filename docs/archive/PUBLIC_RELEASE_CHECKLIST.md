# OpenMesh Public Release Checklist

Use this checklist before sharing OpenMesh publicly, recording demos, or inviting
first external contributors.

## Installation Validation

- [ ] Fresh clone succeeds.
- [ ] Local Python is 3.11, 3.12, or 3.13; Python 3.14 is not used for this release.
- [ ] `python3.11 -m venv .venv` succeeds.
- [ ] `python -m pip install -e .` succeeds.
- [ ] `openmesh --help` works without `python -m`.
- [ ] `openmesh doctor` bootstraps SQLite and reports `Overall: OK`.
- [ ] `OPENMESH_DB_MODE=sqlite` and `OPENMESH_SQLITE_PATH=./openmesh.db` are documented.

## Backend Validation

- [ ] Backend starts with:
  ```bash
  export OPENMESH_DB_MODE=sqlite
  export OPENMESH_SQLITE_PATH=./openmesh.db
  export LLM_MODE=offline
  export WARMUP_TICKS=0
  export OPENMESH_SCHEDULER_ENABLED=0
  uvicorn src.main:app --reload --port 8000
  ```
- [ ] `GET /health` returns alive.
- [ ] `GET /health/ready` returns ready.
- [ ] No background scheduler errors appear during first-user startup.
- [ ] `OPENMESH_SCHEDULER_ENABLED=1` is reserved for intentional legacy scheduled simulation.

## Frontend Validation

- [ ] `cd frontend && npm install` succeeds.
- [ ] `npm run build` succeeds.
- [ ] `npm run dev` starts Vite.
- [ ] These routes render without blank screens, console errors, infinite loaders, or visible `undefined`/`NaN`:
  - [ ] `/`
  - [ ] `/graph`
  - [ ] `/feed`
  - [ ] `/agents`
  - [ ] `/guilds`
  - [ ] `/wiki`
  - [ ] `/history`
  - [ ] `/observatory`
- [ ] History route renders timeline, loading, error, or empty state instead of a blank page.

## Graph Validation

- [ ] `openmesh simulate --agents 20 --events 500` succeeds.
- [ ] `openmesh graph --stats --limit 1000` shows nodes and relationships.
- [ ] Graph relationships validate as governed relationship types.
- [ ] Graph empty state provides copyable onboarding commands.
- [ ] Browser UI does not claim it can directly execute local shell commands.
- [ ] Downloaded graph demo snippet runs from the repository root.

## Observability Validation

- [ ] `python examples/python_basic_agent.py` emits data.
- [ ] `python examples/python_async_agent.py` emits data.
- [ ] `python examples/langgraph_basic.py` emits data when LangGraph is installed.
- [ ] Generated data appears in:
  - [ ] `openmesh discover`
  - [ ] `openmesh ecosystem`
  - [ ] `openmesh graph --details`
  - [ ] `openmesh timeline`
  - [ ] `openmesh tui --once`
  - [ ] Frontend graph explorer
  - [ ] Observatory

## TUI Validation

- [ ] `openmesh tui --once` renders a terminal capture.
- [ ] Network panel shows relationships when events exist.
- [ ] Empty or low-data state remains readable.

## Documentation Validation

- [ ] `README.md` quick start matches validated commands.
- [ ] `STARTUP_GUIDE.md` matches validated commands.
- [ ] `docs/INSTALLATION.md` matches validated commands.
- [ ] `TROUBLESHOOTING.md` covers missing tables, Python versions, and optional integrations.
- [ ] Public docs describe OpenMesh as agent ecosystem observability, not only a web dashboard.

## Demo Validation

- [ ] Fresh SQLite database can be populated in under one minute.
- [ ] Graph page shows a non-empty ecosystem after `openmesh simulate`.
- [ ] Observatory shows operational state, not blank cards.
- [ ] CLI, TUI, and frontend all read the same persisted state.
- [ ] No API keys, external LLMs, browser extensions, or cloud services are required for the demo path.
