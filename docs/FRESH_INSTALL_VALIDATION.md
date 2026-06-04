# OpenMesh Fresh Install Validation

Date: 2026-06-04

## Goal

Validate OpenMesh as a first-time user on a clean environment:

- no existing database
- no existing virtual environment
- no local configuration
- first graph visible within five minutes

## Environment

Validation was run from a fresh clone in `/tmp/openmesh-fresh-validation`.

```bash
python3.11 --version
# Python 3.11.15

node --version
# v25.8.2

npm --version
# 11.11.1
```

Clean-state check:

```bash
find /tmp/openmesh-fresh-validation -maxdepth 2 \
  \( -name '.venv' -o -name '*.db' -o -name '.env' -o -name 'node_modules' \) -print
```

Result: no pre-existing virtualenv, database, local env file, or frontend dependencies were present.

## Fresh Clone

```bash
rm -rf /tmp/openmesh-fresh-validation
git clone https://github.com/srinivasBJ/OpenMesh.git /tmp/openmesh-fresh-validation
cd /tmp/openmesh-fresh-validation
```

Result: PASS.

## Backend, SDK, and CLI Install

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Result: PASS.

Observed install time: 13 seconds.

The install created the `openmesh` console command:

```bash
.venv/bin/openmesh --help
```

## Database Bootstrap

Use SQLite for the no-Docker first run:

```bash
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=/tmp/openmesh-fresh-validation/openmesh.db
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0
```

Run doctor:

```bash
.venv/bin/openmesh doctor
```

Result: PASS.

Key result:

```text
database: INFO
  connection succeeded
migrations: INFO
  all required tables exist
configuration: INFO
  database_url: sqlite:////tmp/openmesh-fresh-validation/openmesh.db
Overall: OK
```

## Demo Ecosystem

```bash
.venv/bin/openmesh simulate --agents 12 --events 180 --nodes 4 --seed 11
```

Result: PASS.

Observed output:

```text
OpenMesh Simulation Created

Generated
  agents: 12
  guilds: 4
  events: 180
  tool_calls: 36
  workflows: 3
  distributed_nodes: 4
  host_relationships: 20
  runtimes: 4
  mcp_servers: 4
  messages: 18
  posts: 9
  wiki_articles: 5
  traces: 4
```

## CLI Startup

```bash
.venv/bin/openmesh discover
.venv/bin/openmesh ecosystem
.venv/bin/openmesh graph --details
.venv/bin/openmesh timeline
```

Result: PASS.

Graph command produced a populated relationship graph with provenance. The fresh run produced:

```text
Entities: 29
Relationships: 111
```

Observed CLI bootstrap, simulation, graph, discovery, ecosystem, timeline, and TUI check time: 6 seconds.

## TUI Startup

For automated validation:

```bash
TERM=xterm-256color .venv/bin/openmesh tui --once > /tmp/openmesh-fresh-tui.out
```

For an interactive user:

```bash
.venv/bin/openmesh tui
```

Result: PASS.

TUI one-shot capture showed:

```text
OPENMESH CONTROL ROOM
Events 180  Traces 4  Nodes 38  Edges 111  Sessions 1  Registry 39
```

## Backend API Startup

Terminal 1:

```bash
cd /tmp/openmesh-fresh-validation
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH=/tmp/openmesh-fresh-validation/openmesh.db
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0

.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8022
```

Smoke test:

```bash
.venv/bin/python - <<'PY'
import httpx

paths = [
    "/health",
    "/health/ready",
    "/api/openmesh/graph",
    "/api/openmesh/discovery",
    "/api/openmesh/ecosystem",
    "/api/openmesh/timeline",
]

for path in paths:
    response = httpx.get("http://127.0.0.1:8022" + path, timeout=10)
    print(f"{response.status_code} {path} {len(response.content)} bytes")
    response.raise_for_status()
PY
```

Result: PASS.

Observed output:

```text
200 /health 51 bytes
200 /health/ready 391 bytes
200 /api/openmesh/graph 704447 bytes
200 /api/openmesh/discovery 28302 bytes
200 /api/openmesh/ecosystem 8891 bytes
200 /api/openmesh/timeline 279039 bytes
```

## Frontend Startup

Terminal 2:

```bash
cd /tmp/openmesh-fresh-validation/frontend
npm install
npm run build
```

Result: PASS.

Observed install and production build time: 9 seconds.

Note: `npm install` reported 8 existing audit findings, 6 moderate and 2 high. They did not block install or build, but should be reviewed before a public production deployment.

Terminal 2, start the Vite dev server with the backend proxy pointed at the fresh API:

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8022 \
VITE_WS_PROXY_TARGET=ws://127.0.0.1:8022 \
npm run dev -- --host 127.0.0.1 --port 5178
```

Open:

```text
http://127.0.0.1:5178/graph
```

Route and API proxy smoke test:

```bash
cd /tmp/openmesh-fresh-validation
.venv/bin/python - <<'PY'
import httpx

routes = ["/", "/graph", "/feed", "/agents", "/guilds", "/wiki", "/history", "/observatory"]

for route in routes:
    response = httpx.get("http://127.0.0.1:5178" + route, timeout=10)
    print(f"{response.status_code} {route} {len(response.content)} bytes")
    response.raise_for_status()

graph = httpx.get("http://127.0.0.1:5178/api/openmesh/graph", timeout=10)
graph.raise_for_status()
data = graph.json()
print(f"proxy_graph nodes={len(data.get('nodes', []))} edges={len(data.get('edges', []))}")
PY
```

Result: PASS.

Observed output:

```text
200 / 691 bytes
200 /graph 691 bytes
200 /feed 691 bytes
200 /agents 691 bytes
200 /guilds 691 bytes
200 /wiki 691 bytes
200 /history 691 bytes
200 /observatory 691 bytes
proxy_graph nodes=38 edges=111
```

## First Graph Timing

The first usable graph was visible from the CLI path well under the five-minute target:

- clone: about 3 seconds
- Python install: 13 seconds
- doctor, simulation, graph/discovery/ecosystem/timeline/TUI: 6 seconds

The frontend path was also under the target:

- frontend install and build: 9 seconds
- Vite dev server startup: 308 ms
- graph API through frontend proxy: 38 nodes and 111 edges

Result: PASS.

## Exact First-Run Command Set

This is the shortest validated path for a new macOS user:

```bash
git clone https://github.com/srinivasBJ/OpenMesh.git
cd OpenMesh

python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .

export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0

.venv/bin/openmesh doctor
.venv/bin/openmesh simulate --agents 12 --events 180 --nodes 4 --seed 11
.venv/bin/openmesh graph --details
```

To launch the web app:

```bash
# Terminal 1
cd OpenMesh
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
export OPENMESH_SCHEDULER_ENABLED=0
export WARMUP_TICKS=0
.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

```bash
# Terminal 2
cd OpenMesh/frontend
npm install
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 \
VITE_WS_PROXY_TARGET=ws://127.0.0.1:8000 \
npm run dev
```

Then open:

```text
http://localhost:5173/graph
```

To launch the TUI:

```bash
cd OpenMesh
export OPENMESH_DB_MODE=sqlite
export OPENMESH_SQLITE_PATH="$(pwd)/openmesh.db"
.venv/bin/openmesh tui
```

## Validation Summary

| Path | Result |
| --- | --- |
| Fresh clone | PASS |
| Python package install | PASS |
| CLI command install | PASS |
| SQLite bootstrap | PASS |
| Doctor | PASS |
| Demo ecosystem | PASS |
| Graph CLI | PASS |
| Discovery CLI | PASS |
| Ecosystem CLI | PASS |
| Timeline CLI | PASS |
| TUI startup | PASS |
| Backend API startup | PASS |
| Backend API smoke | PASS |
| Frontend install | PASS |
| Frontend build | PASS |
| Frontend route smoke | PASS |
| Frontend graph API proxy | PASS |

## Remaining Warnings

- Frontend dependency audit reports 8 vulnerabilities. This is not a fresh-install blocker, but it is a release-hardening item.
- Full browser console validation was not part of this command-line fresh-install pass.
- Cloud provider demos still require API keys. The validated no-key first run uses `openmesh simulate`.

## Verdict

Fresh machine validation passes.

OpenMesh can go from clone to a populated graph in under five minutes using SQLite and the built-in simulator, without API keys, Docker, Postgres, or prior local configuration.
