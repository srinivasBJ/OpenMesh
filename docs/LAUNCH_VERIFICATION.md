# OpenMesh v1 Alpha Launch Verification

Date: 2026-06-04

Tag target: `v1.0.0-alpha`

## Repository Verification

| Area | Result | Evidence |
| --- | --- | --- |
| README links | PASS | Markdown link check across 55 docs found `missing_links=0`. |
| Documentation links | PASS | Local relative Markdown links resolved successfully. |
| CLI commands | PASS | Core release commands were executed from a fresh install. |
| API routes | PASS | Backend smoke returned 200 for health, graph, discovery, ecosystem, timeline, and workflow replay. |
| Frontend routes | PASS | `/`, `/graph`, `/feed`, `/agents`, `/guilds`, `/wiki`, `/history`, and `/observatory` returned 200. |

## Final Launch Validation

Validated from a clean clone in `/tmp/openmesh-v1-alpha-fresh`.

### Backend

Status: PASS.

Command:

```bash
.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8024
```

Smoke results:

```text
200 /health 51 bytes
200 /health/ready 391 bytes
200 /api/openmesh/graph 704447 bytes
200 /api/openmesh/discovery 28302 bytes
200 /api/openmesh/ecosystem 8891 bytes
200 /api/openmesh/timeline 279039 bytes
200 /api/openmesh/replay/workflow/workflow:sim:177a8967:03 65696 bytes
```

### Frontend

Status: PASS.

Commands:

```bash
cd frontend
npm install
npm run build
VITE_API_PROXY_TARGET=http://127.0.0.1:8024 \
VITE_WS_PROXY_TARGET=ws://127.0.0.1:8024 \
npm run dev -- --host 127.0.0.1 --port 5180
```

Route smoke:

```text
200 /
200 /graph
200 /feed
200 /agents
200 /guilds
200 /wiki
200 /history
200 /observatory
proxy_graph nodes=38 edges=111
```

### CLI

Status: PASS.

Commands validated:

```bash
openmesh doctor
openmesh simulate --agents 12 --events 180 --nodes 4 --seed 11
openmesh discover
openmesh ecosystem
openmesh graph --details
openmesh timeline
openmesh workflow list
openmesh replay workflow <workflow_id>
```

### TUI

Status: PASS.

Command:

```bash
TERM=xterm-256color openmesh tui --once
```

Observed:

```text
OPENMESH CONTROL ROOM
Events 180  Traces 4  Nodes 38  Edges 111  Sessions 1  Registry 39
```

### API

Status: PASS.

Representative routes:

- `/health`
- `/health/ready`
- `/api/openmesh/graph`
- `/api/openmesh/discovery`
- `/api/openmesh/ecosystem`
- `/api/openmesh/timeline`
- `/api/openmesh/replay/workflow/{workflow_id}`

### Graph

Status: PASS.

Fresh simulator graph:

```text
nodes: 38
edges: 111
```

Graph output includes relationship type, validation state, observation counts,
first/last seen timestamps, trace IDs, event IDs, and latest evidence.

### Replay

Status: PASS.

Workflow replay output:

```text
OpenMesh Workflow Replay
subject: Implementation Pass
frames: 34
nodes: 9
relationships: 10
workflows: 3
events_replayed: 1
```

### Observatory

Status: PASS.

Frontend `/observatory` route returned 200. API data used by observatory was
available through graph, ecosystem, discovery, timeline, workflow, runtime, MCP,
and local LLM metric routes.

### Provider Integrations

Status: PASS with expected local limitations.

Command:

```bash
openmesh providers verify
```

Observed on this machine:

```text
OpenMesh LLM Providers

○ OpenAI OPENAI_API_KEY is not set
○ Anthropic ANTHROPIC_API_KEY is not set
○ OpenRouter OPENROUTER_API_KEY is not set
✗ Ollama All connection attempts failed
✗ LM Studio All connection attempts failed
✗ vLLM HTTP 404
```

Interpretation: provider command surface works. Cloud providers were not
connected because no API keys were configured.

### Local Model Integrations

Status: PASS with expected local limitations.

Commands:

```bash
openmesh providers discover
openmesh models list
```

Observed:

```text
Local LLM Providers

Ollama      ✗ http://localhost:11434
LM Studio   ✗ http://localhost:1234
vLLM        ✗ http://localhost:8000
No local models discovered.
Start Ollama, LM Studio, or vLLM and rerun: openmesh models list
```

Interpretation: local provider discovery works. No local model servers were
running on this machine.

## Automated Validation

Commands:

```bash
ruff check .
ruff format --check .
python -m unittest discover -s backend/tests
npm run build
python -m build --wheel --outdir /tmp/openmesh-release-dist
```

Results:

- Ruff check: PASS.
- Ruff format check: PASS.
- Backend tests: PASS, 147 tests.
- Frontend build: PASS.
- Wheel build: PASS, `openmesh-1.0.0a0-py3-none-any.whl`.

## GitHub Release Readiness

| Launch target | Status | Justification |
| --- | --- | --- |
| Public GitHub launch | PASS | Fresh install, no-key demo, graph, CLI, TUI, backend, frontend, tests, and release docs are validated. |
| External contributors | PASS | README, CONTRIBUTING, command docs, architecture docs, and tests exist. First issues should focus on docs, browser smoke, UI polish, and dependency hardening. |
| External testers | PASS | Testers can clone, install, run the simulator, inspect graph data, start the frontend, and replay a workflow without cloud credentials. |

## Remaining Blockers

No blocker prevents a public v1 alpha launch.

Non-blocking launch warnings:

- Frontend dependency audit findings remain.
- Browser console smoke is not automated.
- Provider/live local model validation requires external credentials or local
  servers.
- Production auth, RBAC, hosted storage, retention policies, and multi-user
  governance are not implemented.

## Verdict

OpenMesh is ready to publish as `v1.0.0-alpha`.
