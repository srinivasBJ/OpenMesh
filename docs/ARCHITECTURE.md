# OpenMesh Architecture

Current event flow:

```text
simulator, CLI runtime, SDK example, or OpenMesh plugin
  -> OpenMesh event builder
  -> OpenMesh collector
  -> database persistence
  -> WebSocket broadcast
  -> shared query services
  -> frontend dashboard / CLI / TUI / API consumers
```

Core backend pieces:

- `backend/src/shared/openmesh_events.py`: event envelope helpers.
- `backend/src/services/openmesh_collector.py`: validates, persists, and broadcasts events.
- `backend/src/db/openmesh_events.py`: event persistence helpers.
- `backend/src/db/openmesh_sessions.py`: CLI process session persistence helpers.
- `backend/src/services/openmesh_queries.py`: shared read model for API and CLI.
- `backend/src/services/graph_state.py`: derives nodes and edges from events.
- `backend/src/services/graph_exploration.py`: derives node selection, traversal, neighborhood, filter, and search views from graph state.
- `backend/src/services/discovery.py`: derives observed frameworks, agents, tools, workflows, services, and processes.
- `backend/src/services/ecosystem_registry.py`: aggregates observed entities into one ecosystem inventory.
- `backend/src/services/federation.py`: derives metadata-only federation registry, peer, snapshot, timeline, and replay views from existing OpenMesh state.
- `backend/src/services/evaluation.py`: generates synthetic ecosystems and measures collector, trace, graph, inspection, query, snapshot, diff, timeline, replay, and federation read-model costs.
- `backend/src/services/plugins.py`: discovers, validates, and loads OpenMesh plugins.
- `backend/src/sdk/client.py`: Python SDK entry point for agent, task, and tool events.
- `backend/src/sdk/integrations/langgraph.py`: LangGraph reference integration.
- `backend/src/sdk/integrations/crewai.py`: CrewAI reference integration.
- `backend/src/cli/openmesh.py`: terminal consumer and process observer.
- `backend/src/cli/tui.py`: terminal control-room UI.

Storage:

- `openmesh_events`: immutable protocol event records.
- `openmesh_sessions`: CLI execution sessions.
- `openmesh_snapshots`: persisted point-in-time ecosystem snapshot metadata and payloads.
- Legacy tables such as `agent_events` remain in place for existing functionality.

Local development can use SQLite by setting:

```bash
OPENMESH_DB_MODE=sqlite
OPENMESH_SQLITE_PATH=./openmesh.db
```

Postgres remains supported through `DATABASE_URL`.

Integration flow:

```text
OpenMesh plugin, such as LangGraph or CrewAI
  -> Python SDK client
  -> collector
  -> openmesh_events
  -> trace reconstruction, graph reducer, discovery, ecosystem registry
  -> CLI, TUI, dashboard, and API views
```

The compatibility command `openmesh integrations` reads from the plugin registry.
New integration metadata should be exposed through module-level `OPENMESH_PLUGIN`
definitions or Python entry points in the `openmesh.plugins` group rather than
adding central hardcoded integration records. The registry validates plugin API
major-version compatibility before loading a plugin entrypoint.

Snapshot flow:

```text
stored events and sessions
  -> graph reducer, discovery, ecosystem, workflow, MCP, and capability registries
  -> ecosystem snapshot payload
  -> openmesh_snapshots
  -> CLI, TUI, and API inspection
```

Snapshots are point-in-time exports of existing OpenMesh state. They do not create a second graph system and do not perform analysis. Snapshot contents preserve graph provenance, traces, sessions, relationships, and ecosystem registry outputs exactly as derived by the current reducers.

Snapshot diff flow:

```text
openmesh_snapshots
  -> snapshot payload A
  -> snapshot payload B
  -> compare nodes, relationships, workflows, MCP servers, capabilities, traces, sessions, and graph statistics
  -> CLI, TUI, and API diff views
```

Snapshot diffs are derived from stored snapshot payloads. They preserve relationship provenance in diff output and do not create new storage, graph models, recommendations, or analysis layers.

Timeline flow:

```text
openmesh_events + openmesh_sessions + openmesh_snapshots
  -> trace summaries, graph reducer, workflow inspection, snapshot diffs, and provenance
  -> ecosystem, node, workflow, and trace timelines
  -> CLI, TUI, and API timeline views
```

Timelines are derived read models over existing persisted history. They do not create a second timeline store, graph model, analysis system, recommendation engine, or health scoring layer.

Replay flow:

```text
timeline payloads + snapshot payloads
  -> ordered replay frames
  -> stateless playback controls
  -> CLI, TUI, and API replay views
```

Replays are derived from the Timeline Engine, Snapshot Engine, Diff Engine, Event Store, and Trace Store. They reconstruct node appearance, relationship creation, workflow evolution, capability evolution, MCP evolution, and session progression without writing a replay table or duplicating graph state.

Query flow:

```text
structured query text
  -> query parser
  -> graph, discovery, provenance, timelines, snapshots, diffs, traces, and sessions
  -> CLI, TUI, and API query results
```

Queries are derived from existing OpenMesh state. The Query Engine does not create a second graph, new storage model, analysis layer, recommendation layer, or AI summarization path.

Registry flow:

```text
stored events
  -> graph reducer
  -> governed node and relationship validation
  -> discovery registry
  -> workflow, MCP metadata, capability, and ecosystem registries
  -> doctor diagnostics and terminal views
```
