# OpenMesh v1.0 Alpha Release Notes

Tag: `v1.0.0-alpha`

Status: alpha / prerelease.

OpenMesh v1.0 Alpha is the first public release candidate for a terminal-first,
graph-first observability layer for AI agent ecosystems.

## Major Features

- Protocol-native OpenMesh event model.
- Collector pipeline with SQLite and Postgres-compatible persistence.
- Trace, span, session, links, and hierarchy reconstruction.
- Graph reducer with relationship provenance, lifecycle state, node governance,
  relationship governance, and registry compatibility.
- Discovery and unified ecosystem registry.
- Entity inspection for agents, tools, workflows, MCP servers, capabilities, and
  resources.
- Workflow inspection and workflow replay.
- Historical snapshots, snapshot diffs, timelines, replay, and query surfaces.
- Terminal CLI and Textual-based TUI.
- React frontend with graph-first navigation and control-room styling.
- Python SDK with sync and async usage.
- Simulation engine for no-key demo data.
- Provider, runtime, MCP, multi-agent, failure, reputation, genome, and export
  observability surfaces.

## Architecture Summary

OpenMesh follows this data path:

```text
Observe
-> Event
-> Trace / Span / Session
-> Graph + Provenance
-> Discovery
-> Inspection
-> Snapshot
-> Diff
-> Timeline
-> Replay
-> Query
```

The v1 alpha release keeps the current architecture intact. No second graph
model, second event store, or parallel collector pipeline is introduced for the
release.

## Supported Providers

Cloud provider adapters:

- OpenAI
- Anthropic
- OpenRouter

Local provider adapters:

- Ollama
- LM Studio
- vLLM

Provider verification commands:

```bash
openmesh providers verify
openmesh providers discover
openmesh models list
```

Cloud providers require API keys. Local providers require the corresponding
local server to be running.

## Supported Runtimes

Runtime discovery and observation surfaces exist for:

- Claude Code
- Codex CLI
- OpenCode
- Aider
- Cursor agent workflows

Commands:

```bash
openmesh runtimes discover
openmesh observe codex
openmesh observe claude
```

Runtime support is alpha and varies by what is installed on the local machine.

## Supported Exports

OpenMesh v1 alpha includes export commands for:

- OpenTelemetry / OTLP HTTP JSON
- Jaeger
- Grafana Tempo
- Datadog
- Prometheus

Commands:

```bash
openmesh export otel
openmesh export jaeger
openmesh export tempo
openmesh export datadog
openmesh export prometheus
```

External exporter endpoints must be provided by the operator.

## Installation

Validated no-key local install:

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

Start backend:

```bash
.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Start frontend:

```bash
cd frontend
npm install
VITE_API_PROXY_TARGET=http://127.0.0.1:8000 \
VITE_WS_PROXY_TARGET=ws://127.0.0.1:8000 \
npm run dev
```

Open:

```text
http://localhost:5173/graph
```

More install detail:

- [README.md](https://github.com/srinivasBJ/OpenMesh/blob/main/README.md)
- [INSTALLATION.md](https://github.com/srinivasBJ/OpenMesh/blob/main/INSTALLATION.md)
- [QUICKSTART.md](https://github.com/srinivasBJ/OpenMesh/blob/main/QUICKSTART.md)
- [docs/FRESH_INSTALL_VALIDATION.md](https://github.com/srinivasBJ/OpenMesh/blob/main/docs/FRESH_INSTALL_VALIDATION.md)

## Known Limitations

- This is an alpha release, not production-stable software.
- Python 3.11 is the validated development path.
- Frontend `npm install` currently reports audit findings that should be handled
  before a production deployment.
- Browser console smoke testing is still manual.
- Large graph, timeline, replay, and genome payloads need pagination/windowing.
- Cloud providers require API keys.
- Local model providers require running local servers.
- Optional framework integrations may require extra packages.
- Multi-user organizations, RBAC, SSO, hosted storage, and enterprise audit
  controls are not implemented.

## Launch Recommendation

Recommended launch posture:

- Public GitHub alpha: yes.
- External testers: yes.
- External contributors: yes, with scoped issues.
- Production deployment: no.

OpenMesh should be described as a terminal-first, graph-first alpha for observing
AI agent ecosystems locally.
