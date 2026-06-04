# OpenMesh Quickstart

Goal: clone to graph in under five minutes.

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
