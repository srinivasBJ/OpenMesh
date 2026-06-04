# OpenMesh Installation

## Supported Versions

- Python: 3.11, 3.12, or 3.13
- Node.js: 20+ for the frontend
- SQLite: default local mode
- Postgres: optional server mode

Python 3.14 is not supported in this alpha.

## Install From Source

```bash
git clone https://github.com/srinivasBJ/OpenMesh.git
cd OpenMesh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Configure SQLite

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export OPENMESH_SEED_ENABLED=0
export OPENMESH_DEMO_MODE=0
export WARMUP_TICKS=0
export WARMUP_AGENTS_PER_TICK=0
export MAX_ACTIVE_AGENTS=0
```

Validate:

```bash
openmesh doctor
```

Expected: `Overall: OK`.

## Empty Startup

OpenMesh starts as an empty observability platform. Starting the backend creates
database tables and accepts API, CLI, SDK, TUI, and frontend traffic. It does
not automatically create agents, posts, workflows, traces, warmup ticks, or demo
ecosystems.

## Generate First Data

```bash
openmesh simulate --agents 12 --events 180 --nodes 4
openmesh graph --details
openmesh discover
openmesh ecosystem
```

Other explicit demo commands:

```bash
openmesh seed demo
openmesh demo start --agents 20 --events 500 --nodes 4
openmesh run-demo multi-agent
openmesh run-demo research --provider openai
```

## Backend API

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0
export WARMUP_AGENTS_PER_TICK=0
export MAX_ACTIVE_AGENTS=0
PYTHONPATH=backend python -m uvicorn src.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Wheel Smoke

```bash
python -m pip install build
python -m build --wheel
python -m venv /tmp/openmesh-wheel-smoke
/tmp/openmesh-wheel-smoke/bin/python -m pip install dist/openmesh-*.whl
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=/tmp/openmesh-wheel.db \
  /tmp/openmesh-wheel-smoke/bin/openmesh doctor
```

If building from the repository root fails because a local ignored `build/`
directory shadows the PyPI package, run the build from outside the repository:

```bash
cd /tmp
python -m build --wheel --outdir /tmp/openmesh-dist /path/to/OpenMesh
```

## Remove Demo Data

SQLite reset:

```bash
rm -f ./openmesh.db
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=./openmesh.db
openmesh doctor
```

Postgres reset depends on your deployment policy. For local development, drop
and recreate the configured database, then run `openmesh doctor`.

## Real Provider Configuration

Cloud providers:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export OPENROUTER_API_KEY=...
openmesh providers verify
openmesh run-demo research --provider openai
```

Local providers:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export LMSTUDIO_BASE_URL=http://localhost:1234
export VLLM_BASE_URL=http://localhost:8000
openmesh providers discover
openmesh models list
openmesh run-demo research --provider ollama --model llama3.2
```
