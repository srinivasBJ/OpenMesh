# OpenMesh v1 Alpha First-Run Audit

Date: 2026-06-04

## Target

Fresh clone to graph in under five minutes.

## Validated Path

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

openmesh doctor
openmesh simulate --agents 12 --events 180 --nodes 4
openmesh graph --details
```

Result: PASS.

## First Useful Commands

```bash
openmesh discover
openmesh ecosystem
openmesh nodes
openmesh inspect "Research Agent"
openmesh timeline
openmesh replay ecosystem --control step
openmesh query --limit 1000 agents using web_search
openmesh tui --once
```

Result: PASS.

## Backend Startup

```bash
PYTHONPATH=backend python -m uvicorn src.main:app --reload --port 8000
```

Required environment:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0
```

Result: PASS.

## Frontend Startup

```bash
cd frontend
npm install
npm run dev
```

Production build result: PASS.

Preview route smoke result: PASS for `/`, `/graph`, `/feed`, `/agents`,
`/guilds`, `/wiki`, `/history`, and `/observatory`.

## Optional Paths

- LangGraph example requires `pip install langgraph`.
- Cloud provider demos require provider API keys.
- Local provider demos require Ollama, LM Studio, or vLLM running locally.

## First-Run Blockers Fixed

- Wheel installs now include all imported backend packages.
- Multi-agent demo no longer crashes when requesting more agents than the demo
  roster contains.
- README and quickstart now use the simulation path as the no-key first run.

## Remaining First-Run Warnings

- `openmesh query` options must appear before query text.
- Browser console validation is manual until a browser test runner is added.
- API graph/timeline payloads can be large after generated demos.
