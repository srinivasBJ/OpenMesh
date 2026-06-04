# OpenMesh v1 Alpha Integration Audit

Date: 2026-06-04

## Scope

Validated the integrated path:

```text
collector -> persistence -> graph -> timeline -> replay -> observatory/API/CLI/TUI/export
```

Systems included:

- Distributed OpenMesh
- Failure Intelligence
- Agent Reputation
- Agent Genome
- Provider Observability
- Local LLM Providers
- Runtime Observability
- MCP Observability
- Multi-Agent Workflows
- Replay Engine
- OpenTelemetry Export
- SQLite
- API
- Frontend route delivery
- TUI

## Validation Database

Validated with an isolated SQLite database:

```text
/tmp/openmesh_v1_alpha_audit.db
```

Data generated:

- `openmesh doctor`
- `openmesh simulate --agents 12 --events 180 --nodes 4 --seed 11`
- `python examples/python_basic_agent.py`
- `python examples/python_async_agent.py`
- `openmesh run -- python -c "print('hello openmesh release audit')"`
- `openmesh run-demo multi-agent --agents 6 --handoffs 22 --messages 52`
- `openmesh mcp discover`
- snapshot creation before and after a second simulation

## Results

### Collector To Persistence

Status: PASS

Events from simulation, SDK examples, process observation, MCP discovery, and
multi-agent workflow generation persisted into `openmesh_events`.

### Persistence To Graph

Status: PASS

`openmesh graph --details` returned nodes, edges, relationship definitions,
lifecycle state, observation counts, trace ids, event ids, and provenance windows.

### Graph To Discovery And Ecosystem

Status: PASS

`openmesh discover` and `openmesh ecosystem` showed agents, tools, workflows,
processes, services, MCP servers, and relationships derived from the same event
store.

### Timeline And Replay

Status: PASS

`openmesh timeline`, `openmesh replay ecosystem --control step`, and
`openmesh workflow replay workflow:openmesh:multi-agent-handoff-demo --control step`
returned chronological frames derived from persisted history.

### Workflow Inspection

Status: PASS

`openmesh workflow inspect workflow:openmesh:multi-agent-handoff-demo` showed
workflow id, runtime, status, participating agents, traces, sessions, and
provenance.

### Failure Intelligence

Status: PASS

The failed provider demo generated model failures and `openmesh failures` /
`openmesh failure report` classified them as active `model_failure` entries.

### Reputation And Genome

Status: PASS

`openmesh rankings` and `openmesh genome <agent>` produced scores, preferred
tools, failure patterns, latency/cost fields, and similarity relationships.

### Provider And Local LLM Observability

Status: PARTIAL PASS

`openmesh providers verify`, `openmesh providers discover`, and
`openmesh models list` run successfully. This machine had no configured cloud
keys and no local model servers, so provider connectivity correctly reported
missing/unavailable statuses.

### Runtime Observability

Status: PASS

`openmesh runtimes discover` detected Codex CLI at:

```text
/Applications/Codex.app/Contents/Resources/codex
```

Other local runtimes were missing on this machine and were reported as missing.

### MCP Observability

Status: PASS

`openmesh mcp discover` discovered the local `node_repl` MCP metadata source and
registered tool/resource metadata.

### OpenTelemetry Export

Status: PASS

`openmesh export otel --summary --limit 1200` returned:

```text
target: otel
format: otlp-http-json
summary: {'spans': 372, 'resource_spans': 1}
```

### API

Status: PASS

Backend launched with:

```bash
PYTHONPATH=backend python -m uvicorn src.main:app --host 127.0.0.1 --port 8011
```

Representative endpoints returned HTTP 200:

- `/health`
- `/health/ready`
- `/api/openmesh/graph`
- `/api/openmesh/discovery`
- `/api/openmesh/ecosystem`
- `/api/openmesh/timeline`
- `/api/openmesh/replay/ecosystem`
- `/api/openmesh/workflows`
- `/api/openmesh/failures`
- `/api/openmesh/reputation`
- `/api/openmesh/genome`
- `/api/openmesh/mcp`
- `/api/openmesh/tools`
- `/api/openmesh/resources`
- `/api/openmesh/local-llm/metrics`
- `/api/openmesh/runtime/metrics`
- `POST /api/openmesh/query`

### Frontend

Status: PASS WITH LIMITATION

`npm run build` passed. Vite preview route smoke returned HTTP 200 for:

- `/`
- `/graph`
- `/feed`
- `/agents`
- `/guilds`
- `/wiki`
- `/history`
- `/observatory`

Browser console validation was not automated because no browser automation tool
or Playwright dependency was available in this environment.

### TUI

Status: PASS

`openmesh tui --once` exited with code 0 and rendered the control-room layout.

## Issues Found

1. Wheel install failed in GitHub Actions because newer source packages were not
   listed in `pyproject.toml`.
2. `openmesh run-demo multi-agent --agents 6` crashed because the command help
   allowed six agents while the demo roster contained five.
3. `openmesh run-demo research` requires a configured provider despite old docs
   implying offline mode was enough.
4. API payloads for graph, timeline, replay, and genome can become large on
   moderate datasets.

## Fixes Applied

- Added missing wheel packages: `src.exporters`, `src.failures`, `src.genome`,
  and `src.reputation`.
- Clamped multi-agent demo agent count to the built-in demo roster.
- Updated release docs to state that real research demo requires provider
  configuration.

## Remaining Risks

- Optional integration examples depend on external packages.
- Large API payloads need pagination or windowing before heavier public demos.
- Browser console smoke remains manual unless Playwright or another browser
  runner is added later.
