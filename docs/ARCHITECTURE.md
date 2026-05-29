# OpenMesh Architecture

Current event flow:

```text
simulator or CLI runtime
  -> OpenMesh event builder
  -> OpenMesh collector
  -> database persistence
  -> WebSocket broadcast
  -> frontend store / CLI queries
```

Core backend pieces:

- `backend/src/shared/openmesh_events.py`: event envelope helpers.
- `backend/src/services/openmesh_collector.py`: validates, persists, and broadcasts events.
- `backend/src/db/openmesh_events.py`: event persistence helpers.
- `backend/src/db/openmesh_sessions.py`: CLI process session persistence helpers.
- `backend/src/services/openmesh_queries.py`: shared read model for API and CLI.
- `backend/src/services/graph_state.py`: derives nodes and edges from events.
- `backend/src/cli/openmesh.py`: terminal consumer and process observer.

Storage:

- `openmesh_events`: immutable protocol event records.
- `openmesh_sessions`: CLI execution sessions.
- Legacy tables such as `agent_events` remain in place for existing functionality.

Local development can use SQLite by setting:

```bash
OPENMESH_DB_MODE=sqlite
OPENMESH_SQLITE_PATH=./openmesh.db
```

Postgres remains supported through `DATABASE_URL`.
