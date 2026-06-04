# OpenMesh Quickstart

Goal: clone to graph in under five minutes.

OpenMesh starts empty by default. Backend startup creates tables and waits for
events; it does not seed agents, run warmup ticks, or create demo activity.

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
openmesh graph --details
```

Generate demo graph data when you want it:

```bash
openmesh simulate --agents 12 --events 180 --nodes 4
openmesh graph --details
```

Explore:

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

Other explicit demo commands:

```bash
openmesh seed demo
openmesh demo start --agents 20 --events 500 --nodes 4
openmesh run-demo multi-agent
openmesh run-demo research --provider openai
```

Run SDK examples:

```bash
python examples/python_basic_agent.py
python examples/python_async_agent.py
```

Start browser dashboard:

```bash
PYTHONPATH=backend python -m uvicorn src.main:app --reload --port 8000
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/graph`.

Reset local demo data:

```bash
rm -f ./openmesh.db
OPENMESH_DB_MODE=sqlite OPENMESH_SQLITE_PATH=./openmesh.db openmesh doctor
```
