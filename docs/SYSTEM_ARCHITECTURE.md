# OpenMesh v1 Alpha System Architecture

## Principle

OpenMesh derives everything from persisted events, sessions, and snapshots.

```text
Observe -> Event -> Trace -> Graph -> Inspect -> Snapshot -> Diff -> Timeline -> Replay -> Query -> Export
```

## Subsystems

### Event Model

Location: `backend/src/shared/openmesh_events.py`

Creates unified OpenMesh events with event id, event type, timestamp, trace id,
session id, source, target, payload, metrics, severity, span ids, parent ids,
root event id, and links.

### Collector

Location: `backend/src/services/openmesh_collector.py`

Accepts events, validates event shape, persists records, updates graph state,
and optionally broadcasts over WebSocket.

### Persistence

Locations:

- `backend/src/db/openmesh_events.py`
- `backend/src/db/openmesh_sessions.py`
- `backend/src/db/openmesh_snapshots.py`
- `backend/src/db/session.py`

Supports SQLite and Postgres.

### Trace And Span Semantics

Location: `backend/src/services/trace_semantics.py`

Reconstructs trace hierarchy, span lifecycle, parent-child relationships, links,
span summaries, and graph relationships for a trace.

### Graph

Locations:

- `backend/src/services/graph_state.py`
- `backend/src/services/graph_exploration.py`
- `backend/src/services/node_types.py`
- `backend/src/services/relationship_types.py`
- `backend/src/services/registry_compatibility.py`

Reduces events into governed nodes and relationships with provenance.

### Discovery And Ecosystem

Locations:

- `backend/src/services/discovery.py`
- `backend/src/services/ecosystem_registry.py`

Builds observed inventory for frameworks, agents, tools, processes, services,
workflows, MCP servers, and capabilities.

### Workflows

Locations:

- `backend/src/services/workflow_registry.py`
- `backend/src/workflows/multi_agent.py`

Tracks workflow metadata, handoffs, messages, participating entities, and replay.

### MCP And Tools

Locations:

- `backend/src/mcp/`
- `backend/src/services/mcp_discovery.py`
- `backend/src/services/mcp_config_discovery.py`
- `backend/src/services/mcp_tool_observability.py`
- `backend/src/services/mcp_capabilities.py`

Discovers MCP metadata and registers servers, tools, resources, and capabilities
without executing remote tools during discovery.

### Providers And Local Models

Location: `backend/src/providers/`

Supports configured provider verification and local provider discovery for
OpenAI, Anthropic, OpenRouter, Ollama, LM Studio, and vLLM.

### Runtime Observability

Locations:

- `backend/src/runtimes/`
- `backend/src/services/runtime_observability.py`

Discovers local coding-agent runtimes and emits runtime/file/command/model
events when observing supported runtimes.

### Distributed Nodes And Federation

Locations:

- `backend/src/services/distributed_nodes.py`
- `backend/src/services/federation.py`

Models OpenMesh installations and metadata-only federation views.

### Snapshots, Diffs, Timeline, Replay

Locations:

- `backend/src/services/ecosystem_snapshot.py`
- `backend/src/services/timeline.py`
- `backend/src/replay/engine.py`
- `backend/src/services/replay.py`

Builds point-in-time snapshots, historical diffs, timeline events, and replay
frames from existing persisted history.

### Query

Location: `backend/src/services/query_engine.py`

Parses structured ecosystem questions and answers from graph, discovery,
snapshots, traces, sessions, provenance, and timelines.

### Failure, Reputation, Genome

Locations:

- `backend/src/failures/`
- `backend/src/reputation/`
- `backend/src/genome/`

Builds failure classification, reputation scores, trust edges, behavioral
profiles, and similarity relationships from observed events.

### Export

Location: `backend/src/exporters/`

Exports OpenMesh events to OTLP HTTP JSON, Tempo, Jaeger JSON, Datadog trace
JSON, and Prometheus text metrics.

### Interfaces

- CLI: `backend/src/cli/openmesh.py`
- TUI: `backend/src/cli/tui.py`
- API: `backend/src/api/routes/main.py`
- Frontend: `frontend/src`
- SDK: `backend/src/sdk`

## Current API Groups

- Legacy dashboard: agents, feed, guilds, wiki, stats, events.
- OpenMesh core: events, traces, graph, sessions, discovery, ecosystem.
- Governance: registry, node types, relationships.
- Runtime/provider/MCP/workflow observability.
- Snapshots, timeline, replay, query.
- Failures, reputation, genome.
- Federation and distributed nodes.

## Known Architecture Risks

- Some API payloads can be large because pagination/windowing is limited.
- `backend/src/api/routes/main.py` is large and should eventually split by route
  domain.
- Wheel package list is manual and must stay synchronized with `backend/src`.
- Optional integrations should stay optional to preserve fast local installs.
