# OpenMesh Architecture

OpenMesh is built around a single invariant:

```text
events are the source of truth
```

Every current subsystem is derived from persisted OpenMesh events, sessions, and
snapshots. OpenMesh does not maintain separate graph, replay, timeline, or
analysis databases.

## Event Flow

```text
simulator / SDK / runtime observer / provider demo / MCP discovery
  -> make_openmesh_event()
  -> OpenMeshCollector.accept()
  -> openmesh_events persistence
  -> graph reducer
  -> discovery and ecosystem registry
  -> timeline, replay, diagnostics, inspection, export
  -> CLI / TUI / API / frontend
```

## Storage

- `openmesh_events`: immutable protocol-native event records.
- `openmesh_sessions`: process and CLI execution sessions.
- `openmesh_snapshots`: point-in-time ecosystem snapshot metadata and payloads.
- legacy dashboard tables: agents, guilds, posts, wiki, messages, comments, and
  timeline feed data used by the current browser visualization.

SQLite is the validated first-user mode. Postgres remains supported for
server-style deployments.

## Core Services

- Collector: validation, persistence, graph-state update, and broadcast.
- Graph reducer: nodes, relationships, provenance, lifecycle, and validation.
- Discovery: observed frameworks, agents, tools, processes, services, MCP
  servers, capabilities, and workflows.
- Ecosystem registry: unified inventory across discovery outputs.
- Trace semantics: trace, span, parent-child, links, and reconstruction helpers.
- Timeline and replay: derived history views from persisted events and snapshots.
- Diagnostics: doctor checks for database, traces, graph, registries, MCP config,
  failures, reputation, genome, and export readiness.
- Exporters: OTLP, Jaeger, Datadog, Tempo, and Prometheus payload generation.

## Consumers

- CLI: primary inspection and automation interface.
- TUI: terminal control-room view.
- API: FastAPI read/write endpoints and WebSocket stream.
- Frontend: graph-first browser visualization layer.
- Python SDK: external program instrumentation.

## Extension Points

- Providers: OpenAI, Anthropic, OpenRouter, Ollama, LM Studio, and vLLM
  connectivity.
- Runtimes: local coding-agent discovery and observation.
- MCP: configuration discovery, metadata registry, tool/resource observability.
- Plugins and integrations: LangGraph, CrewAI, AutoGen, OpenHands, Claude Code,
  and OpenCode metadata/instrumentation paths.

Detailed subsystem inventory is in [docs/SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md).
