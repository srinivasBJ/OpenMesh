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
```

Validate:

```bash
openmesh doctor
```

Expected: `Overall: OK`.

## Generate First Data

```bash
openmesh simulate --agents 12 --events 180 --nodes 4
openmesh graph --details
openmesh discover
openmesh ecosystem
```

## Backend API

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0
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
