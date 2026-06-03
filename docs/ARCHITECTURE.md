# OpenMesh Architecture

Current event flow:

```text
simulator, CLI runtime, SDK example, LangGraph, or CrewAI
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
- `backend/src/services/discovery.py`: derives observed frameworks, agents, tools, workflows, services, and processes.
- `backend/src/services/ecosystem_registry.py`: aggregates observed entities into one ecosystem inventory.
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
LangGraph / CrewAI adapter
  -> Python SDK client
  -> collector
  -> openmesh_events
  -> trace reconstruction, graph reducer, discovery, ecosystem registry
  -> CLI, TUI, dashboard, and API views
```

Snapshot flow:

```text
stored events and sessions
  -> graph reducer, discovery, ecosystem, workflow, MCP, and capability registries
  -> ecosystem snapshot payload
  -> openmesh_snapshots
  -> CLI, TUI, and API inspection
```

Snapshots are point-in-time exports of existing OpenMesh state. They do not create a second graph system and do not perform analysis. Snapshot contents preserve graph provenance, traces, sessions, relationships, and ecosystem registry outputs exactly as derived by the current reducers.

Registry flow:

```text
stored events
  -> graph reducer
  -> governed node and relationship validation
  -> discovery registry
  -> workflow, MCP metadata, capability, and ecosystem registries
  -> doctor diagnostics and terminal views
```
