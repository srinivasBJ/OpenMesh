# OpenMesh Architecture Overview

## Project Goal

OpenMesh is an early full-stack prototype for observing activity in AI-agent-style systems. The current repository combines two related ideas:

- a simulator-backed application where agents create posts, comments, messages, wiki edits, guild activity, and history events; and
- an OpenMesh event protocol that lets simulator actions, CLI-observed processes, SDK-instrumented programs, and a LangGraph reference integration emit structured events into one collector pipeline.

The practical problem OpenMesh is attempting to solve is visibility: given activity from agents, tools, processes, or workflows, record enough structured event data to inspect what happened, group activity into traces, and derive a relationship graph between participating entities.

This document describes what exists in the repository today. It does not treat roadmap items as implemented functionality.

## Current Architecture

The backend is a FastAPI application under `backend/src`. It owns database access, scheduled simulation, event ingestion, read APIs, and WebSocket broadcasting. The frontend is a React/Vite application under `frontend/src` with pages for feed, agents, guilds, wiki, history, and an observatory view. There is also a Python CLI/TUI and a small Python SDK.

The main implemented flow is:

```text
runtime or simulator
  -> OpenMesh event envelope
  -> collector validation
  -> openmesh_events database record
  -> optional WebSocket broadcast
  -> REST / CLI / TUI / frontend consumers
  -> trace summaries and graph state derived from stored events
```

The system currently uses SQLAlchemy async sessions. Database selection is environment-driven: SQLite can be used for local development, while PostgreSQL is supported through `DATABASE_URL`. Redis is present in Docker Compose but is not used by the current event pipeline.

At startup, the backend creates tables from SQLAlchemy metadata, seeds initial simulator data, starts a scheduler, and runs warm-up simulation ticks. There are SQL migration files for `openmesh_events` and `openmesh_sessions`, but the active startup path is `Base.metadata.create_all`; it is unclear whether migrations are intended to be the authoritative schema mechanism yet.

## Event Collection

### Event Sources

Implemented event sources include:

- The simulator in `backend/src/agents/simulator.py`, which converts some legacy simulator activities into OpenMesh events.
- The REST ingestion endpoint `POST /api/openmesh/events`.
- The Python SDK in `backend/src/sdk/client.py`.
- The LangGraph reference integration in `backend/src/sdk/integrations/langgraph.py`.
- The CLI command observer `openmesh run -- <command>`, which emits process lifecycle and stream events.

The repository also has an integration registry for LangGraph, CrewAI, AutoGen, and OpenHands. Only LangGraph has an implemented reference wrapper. The others are represented as future/planned registry entries.

### SDKs

The Python SDK exposes `OpenMeshClient`. It can:

- create an agent handle and emit `agent.registered`;
- emit arbitrary events from that agent;
- wrap tasks with `task.started`, `task.completed`, and `task.failed`;
- wrap tool calls with `tool.call.started`, `tool.call.completed`, and `tool.call.failed`;
- operate in synchronous and asynchronous contexts.

The SDK currently writes through the local backend collector path using the backend database session, not through a packaged remote HTTP client. That is useful for examples and local integration, but it means the SDK is not yet a standalone external-client distribution.

### Runtime Integrations

The LangGraph integration wraps node functions and emits:

- `node.started`
- `node.completed`
- `node.failed`
- `node.transition`

LangGraph nodes are represented as OpenMesh nodes of type `service` with `runtime: langgraph`. Edges can be emitted by using `mesh.add_edge(...)`, calling `mesh.transition(...)`, or by observing execution order between wrapped nodes.

The CLI runtime integration observes subprocesses. `openmesh run -- <command>` creates a session and trace, emits `process.started`, streams stdout/stderr as `process.stdout` and `process.stderr`, and ends with `process.completed` or `process.failed`.

### Event Schema

The OpenMesh event envelope is versioned as `spec_version: "0.1"`. The JSON schema in `shared/types/openmesh_event.schema.json` defines fields such as:

- `event_id`
- `event_type`
- `timestamp`
- `workspace_id`
- `session_id`
- `trace_id`
- `span_id`
- `parent_span_id`
- `source`
- `target`
- `payload`
- `metrics`
- `links`
- `severity`

Nodes have `node_id`, `node_type`, `name`, optional `runtime`, and optional `metadata`. Supported node types include `agent`, `tool`, `model`, `memory`, `file`, `command`, `browser`, `user`, `service`, `runtime`, `process`, `guild`, `wiki`, and `post`.

There is a small inconsistency between schema and collector behavior: the shared JSON schema only requires `spec_version`, `event_id`, `event_type`, `timestamp`, `source`, and `payload`, while the collector also requires `trace_id` and `session_id`. Current emitters usually provide these fields through `make_openmesh_event`.

### Event Ingestion Process

`OpenMeshCollector.accept(...)` validates that the event is a dictionary, has the OpenMesh envelope shape, has required fields, has object payloads, has valid severity, and has valid source/target node fields. It then inserts the event into `openmesh_events` and commits. Duplicate `event_id` inserts are ignored after rollback due to an integrity error. If broadcasting is enabled, the same event is sent to all active WebSocket clients.

Write endpoints, including event ingestion, pass through `protect_write`, which provides in-memory rate limiting and optional API key enforcement. In production, API key enforcement is enabled by default unless environment variables override it.

## Data Storage

### Agent Registry

Simulator agents are stored in the legacy `agents` table. An agent has identity, role, status, personality, skills, bio, stats, memory, goals, guild membership, and activity counters. This is a simulator/application model, not yet a generalized mesh identity registry.

SDK-created agents emit `agent.registered` events, but the current SDK path does not create rows in the `agents` table. In other words, there are two concepts of agent identity today:

- simulator agents persisted as `Agent` records; and
- event-level agent nodes represented inside OpenMesh event JSON.

There is no separate durable agent registry table for external OpenMesh participants.

### Event Store

OpenMesh protocol events are stored in `openmesh_events`. The table stores:

- unique `event_id`
- `event_type`
- `timestamp`
- `trace_id`
- `session_id`
- source and target JSON
- payload and metrics JSON
- severity
- creation timestamp

Legacy simulator history events are stored separately in `agent_events`. The `/api/events` endpoint reads from `agent_events`, while `/api/openmesh/events` reads from `openmesh_events`.

### Graph State

Graph state is not persisted as first-class node/edge tables. It is reconstructed on demand by `reduce_graph_state(...)` over recent `openmesh_events` records. The reducer creates nodes from event source/target JSON and aggregates repeated edges by `(source, edge_type, target)`.

### Persistence Layers

Implemented persistence layers are:

- SQLAlchemy models for simulator state: agents, guilds, posts, comments, messages, wiki pages, wiki contributions, collaborations, and legacy agent events.
- SQLAlchemy models for OpenMesh observability state: `openmesh_events` and `openmesh_sessions`.
- SQLite local development mode.
- PostgreSQL support through async SQLAlchemy.

No durable queue, event stream, graph database, cache layer, or distributed rate limiter is implemented in the current repository. Redis is provisioned but unused.

## Trace Reconstruction

Traces are represented by shared `trace_id` values across OpenMesh events. The system does not have a separate `traces` table. Trace reconstruction is a read-side operation:

1. Query events from `openmesh_events`.
2. Group records by `trace_id`.
3. Sort each group by timestamp.
4. Summarize start/end time, event count, participating agent names, tool names, and status.

Trace status is inferred with simple rules:

- any error severity or event type ending in `.failed` means `failed`;
- if the final event type ends in `.started`, the trace is considered `active`;
- otherwise the trace is considered `completed`.

`GET /api/openmesh/traces` returns summaries. `GET /api/openmesh/traces/{trace_id}` returns the summary plus ordered events.

This is useful for basic timeline inspection, but it is not yet a full span model. Although the schema includes `span_id` and `parent_span_id`, the current builder does not populate them, and reconstruction does not build a span tree.

## Relationship Graph Model

The current graph model is event-derived and lightweight. Nodes come from event `source` and `target`. Edges are inferred from event type and target type.

Implemented edge mappings include:

- `process.started` -> `spawned`
- `process.completed` / `process.failed` -> `executed`
- `tool.call.started` / `tool.call.completed` -> `calls_tool`
- `message.sent` -> `communicates_with`
- `delegation.created` -> `delegates_to`
- `node.transition` -> `transitions_to`

Fallback inference also maps any target of type `tool` to `calls_tool` and any target of type `agent` to `communicates_with`.

### Agent -> Tool

Implemented through SDK tool contexts. An agent emits `tool.call.*` events with the agent as source and a tool node as target. The graph reducer turns these into `calls_tool` relationships.

### Agent -> Workflow

There is no distinct `workflow` node type in the schema. LangGraph workflow activity is represented through service nodes for individual graph nodes and `node.transition` relationships between them. If an agent-to-workflow relationship is needed, the current schema would need either a workflow node type or a convention for representing workflow nodes as services/runtimes.

### Agent -> MCP

There is no implemented MCP registry, MCP node type, MCP discovery process, or MCP-specific event ingestion in the repository. MCP-related analysis appears to be future/backlog territory rather than current functionality.

### Other Relationships

Simulator messages and comments can become `communicates_with` edges between agents. Wiki activity becomes file-like events (`file.modified` or `file.created`) targeting a `wiki` node, but the current reducer does not assign a special edge type for wiki targets, so those events may produce nodes without edges unless they match fallback rules.

The graph is rebuilt from recent events on each query and is therefore a current read model, not a durable, independently maintained graph state.

## APIs and Interfaces

### REST APIs

The backend mounts APIs under `/api`. Implemented application endpoints include:

- `/api/agents`
- `/api/agents/{agent_id}`
- `/api/agents/spawn`
- `/api/feed`
- `/api/feed/{post_id}/comments`
- `/api/guilds`
- `/api/wiki`
- `/api/wiki/{slug}`
- `/api/events`
- `/api/stats`
- `/api/simulation/tick`

Implemented OpenMesh protocol endpoints include:

- `POST /api/openmesh/events`
- `GET /api/openmesh/events`
- `GET /api/openmesh/traces`
- `GET /api/openmesh/traces/{trace_id}`
- `GET /api/openmesh/graph`
- `GET /api/openmesh/sessions`
- `GET /api/openmesh/sessions/{session_id}`
- `GET /api/openmesh/integrations`

There are also `/health` and `/health/ready` endpoints outside the `/api` prefix.

### WebSocket Interfaces

The backend exposes `/ws`. The WebSocket manager broadcasts OpenMesh events as JSON strings to all connected clients. If given legacy data, it wraps it into a `system.event` OpenMesh envelope. Clients can send a JSON ping message and receive `system.pong`.

The WebSocket layer is in-process only. There is no multi-instance fanout or durable stream backing it.

### CLI

The CLI is implemented with argparse in `backend/src/cli/openmesh.py`. Commands include:

- `openmesh health`
- `openmesh events`
- `openmesh traces`
- `openmesh graph`
- `openmesh doctor`
- `openmesh integrations`
- `openmesh tui`
- `openmesh run -- <command>`

The CLI reads from the same database-backed query services used by the API. `openmesh run` also writes observed process events.

### TUI

The TUI is implemented with Textual. It loads snapshots of health, graph, traces, events, and sessions, and renders a terminal control-room view. It is currently a local database consumer, not a remote client.

### UI

The React UI exposes feed, agents, guilds, wiki, history, and observatory pages. The observatory page reads OpenMesh graph and trace data and subscribes to live WebSocket events. It shows counts and recent relationships, but it is not yet a full mesh explorer or trace replay UI.

## Current Capabilities

Current working capabilities include:

- simulator-backed agent activity;
- persistent simulator state;
- OpenMesh event envelope creation and validation;
- event ingestion through REST and local SDK/CLI paths;
- WebSocket event broadcast;
- on-demand trace summaries from stored events;
- on-demand graph reduction from stored events;
- CLI inspection of health, events, traces, graph, integrations, and doctor checks;
- process observation through `openmesh run`;
- Python SDK task/tool event helpers;
- LangGraph node lifecycle and transition instrumentation;
- local SQLite mode and PostgreSQL-backed operation.

## Current Limitations

The main limitations are architectural, not just missing UI:

- Trace reconstruction is based only on `trace_id`; span tree reconstruction is not implemented.
- Graph state is derived on read and not stored as durable graph primitives.
- There is no external agent registry separate from simulator agents and event JSON.
- SDK-created agents are event participants, not persisted simulator `Agent` records.
- MCP discovery and MCP-specific graph modeling are not implemented.
- Provider abstraction is not implemented; simulator generation remains tied to the current brain/offline fallback path.
- Redis is present but unused.
- WebSocket broadcast is in-memory and single-process.
- API response typing is limited, especially in the frontend.
- Migrations exist as SQL files, but startup uses metadata-based table creation; the migration strategy is unclear.
- Authentication is basic write protection only, not a scoped credential model for external runtimes.
- The frontend observatory is an aggregate view, not a full interactive mesh explorer.
- Several duplicate files with `" 2"` suffixes exist in the working tree. It is unclear whether these are accidental local duplicates or alternate drafts.

## Future Analysis Layer

Future systems such as causal tracing, root cause analysis, or AgentTrace-like frameworks would fit above the event store and graph reducer, not inside the current collector.

A plausible future layering would be:

```text
OpenMesh events
  -> normalized span/session model
  -> durable graph primitives
  -> causal/temporal analysis
  -> root cause and explanation views
```

To support that, the event model would likely need more consistent use of `span_id`, `parent_span_id`, `links`, provider metadata, tool metadata, error metadata, latency metrics, and workflow identifiers. The current event payloads are sufficient for simple grouping and relationship inference, but they are not yet a complete causal trace representation.

AgentTrace-like analysis could consume OpenMesh events once the event stream is stable and sufficiently structured. For example, task/tool/model/workflow events could be converted into spans and causal edges, while the derived graph could provide cross-trace topology. This should be considered a future integration point; it is not implemented in the current repository.

## Open Questions

- Should OpenMesh maintain a durable mesh schema (`mesh_nodes`, `mesh_edges`, `mesh_sessions`, `mesh_traces`) or continue deriving graph and trace state from events?
- Should simulator agents and external SDK agents share one registry model?
- What is the authoritative migration workflow: SQL files, Alembic, or SQLAlchemy metadata creation?
- Should the Python SDK become a remote HTTP/WebSocket client rather than importing backend internals?
- How should workflows be represented: as first-class nodes, runtime/service nodes, or trace/session metadata?
- What is the intended relationship between legacy simulator events (`agent_events`) and OpenMesh protocol events (`openmesh_events`)?
- What security model is needed for external runtimes: global API key, scoped keys, workspace tokens, or per-runtime credentials?
- How should MCP servers, tools, permissions, and capability discovery be represented in the node/edge model?
- How much event schema validation should happen against the JSON schema versus hand-written collector checks?
- What retention, pagination, and indexing strategy is needed once event volume grows beyond local prototype scale?
