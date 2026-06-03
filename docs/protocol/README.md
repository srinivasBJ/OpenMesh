# OpenMesh Protocol v1

OpenMesh Protocol v1 is the stable wire and read-model contract for OpenMesh agent observability.

The protocol defines how observed ecosystems are represented across events, traces, nodes, relationships, workflows, snapshots, timelines, replays, and structured queries.

Protocol v1 is not an analysis system. It does not define root-cause detection, health scoring, recommendations, or AI-generated summaries.

## Goals

- Make agent activity portable across SDKs, CLIs, collectors, TUIs, APIs, and dashboards.
- Preserve event -> trace -> graph -> provenance consistency.
- Keep terminal-first consumers able to inspect the same data as API and dashboard consumers.
- Provide versioned JSON Schemas that external integrations can validate against.
- Allow additive evolution without breaking existing v1 consumers.

## Schemas

JSON Schemas use JSON Schema 2020-12.

| Spec | Schema |
| --- | --- |
| Common definitions | [schemas/openmesh-common.v1.schema.json](schemas/openmesh-common.v1.schema.json) |
| Event | [schemas/openmesh-event.v1.schema.json](schemas/openmesh-event.v1.schema.json) |
| Trace | [schemas/openmesh-trace.v1.schema.json](schemas/openmesh-trace.v1.schema.json) |
| Node | [schemas/openmesh-node.v1.schema.json](schemas/openmesh-node.v1.schema.json) |
| Relationship | [schemas/openmesh-relationship.v1.schema.json](schemas/openmesh-relationship.v1.schema.json) |
| Workflow | [schemas/openmesh-workflow.v1.schema.json](schemas/openmesh-workflow.v1.schema.json) |
| Snapshot | [schemas/openmesh-snapshot.v1.schema.json](schemas/openmesh-snapshot.v1.schema.json) |
| Timeline | [schemas/openmesh-timeline.v1.schema.json](schemas/openmesh-timeline.v1.schema.json) |
| Replay | [schemas/openmesh-replay.v1.schema.json](schemas/openmesh-replay.v1.schema.json) |
| Query | [schemas/openmesh-query.v1.schema.json](schemas/openmesh-query.v1.schema.json) |

## Normative Language

The words `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` are normative.

## Event Spec

An OpenMesh event is the source of truth for observed activity.

Events MUST include:

- `spec_version`: `1.0`
- `event_id`
- `event_type`
- `timestamp`
- `workspace_id`
- `session_id`
- `trace_id`
- `span_id`
- `root_event_id`
- `source`
- `payload`
- `metrics`
- `links`
- `severity`

Events MAY include:

- `target`
- `parent_span_id`
- `parent_event_id`

Events SHOULD use dot-separated event types such as:

- `agent.started`
- `agent.registered`
- `task.started`
- `task.completed`
- `task.failed`
- `tool.call.started`
- `tool.call.completed`
- `tool.call.failed`
- `message.sent`
- `file.modified`
- `command.executed`
- `process.started`
- `process.stdout`
- `process.stderr`
- `process.completed`
- `process.failed`
- `workflow.registered`
- `node.started`
- `node.completed`
- `node.failed`
- `node.transition`
- `mcp.config.discovered`
- `mcp.capability.discovered`

Event payloads MAY contain integration-specific data. Consumers MUST NOT require unknown payload keys.

## Trace Spec

A trace groups events that belong to the same observed execution.

Trace identity:

- `trace_id` MUST be stable across all events in the trace.
- `root_event_id` SHOULD point to the first causally meaningful event in the trace.
- `session_id` MAY span multiple traces when one runtime session creates multiple executions.

Trace status:

- `failed` if any event has severity `error` or ends with `.failed`
- `active` if the latest event ends with `.started`
- `completed` otherwise

Trace reconstruction MUST use explicit parent fields when available:

- `parent_event_id`
- `root_event_id`
- `span_id`
- `parent_span_id`
- `links`

Consumers SHOULD NOT rely on timestamp order alone when parent fields are present.

## Span Spec

Spans are lightweight execution scopes inside traces.

Each event MUST have a `span_id`.

Nested scopes SHOULD set `parent_span_id`.

Span lifecycle is derived from event types:

- `*.started` opens or activates a span
- `*.completed` completes a span
- `*.failed` fails a span
- non-lifecycle events are observations inside the span

Spans MAY link across traces using `links`.

## Link Spec

Links represent references that are not strict parent-child relationships.

A link MUST include at least one of:

- `trace_id`
- `span_id`
- `event_id`
- `url`

Links SHOULD include `relationship`, for example:

- `follows_from`
- `related_to`
- `caused_by`
- `derived_from`

Links MUST NOT imply parent-child ownership unless the parent fields also identify that relationship.

## Node Spec

Nodes are governed ecosystem entities.

Event node references MUST include:

- `node_id`
- `node_type`
- `name`

Event node references MAY include:

- `runtime`
- `metadata`

Graph nodes MAY add:

- `id`
- `category`
- `event_count`
- `trace_ids`
- `session_ids`
- `first_seen`
- `last_seen`
- `provenance`
- `validation_status`
- `lifecycle_state`

Node types in v1:

- `agent`
- `tool`
- `model`
- `memory`
- `file`
- `command`
- `browser`
- `user`
- `service`
- `runtime`
- `process`
- `workflow`
- `framework`
- `mcp_server`
- `capability`
- `guild`
- `wiki`
- `post`

Unknown node types MUST be treated as invalid for v1 graph validation.

## Relationship Spec

Relationships are directed graph edges derived from events.

Relationships MUST include:

- `id`
- `source`
- `target`
- `type`
- `relationship_type`
- `provenance`

Relationship types in v1:

- `uses`
- `runs`
- `spawns`
- `executes`
- `connects_to`
- `defines`
- `exposes`
- `communicates_with`
- `delegates_to`
- `transitions_to`

Every relationship MUST be explainable through provenance:

- originating event ids
- trace ids
- timestamps
- observation count

Relationships MUST NOT be deleted from historical snapshots. Runtime graph views MAY mark relationships `active`, `stale`, or `inactive`.

## Workflow Spec

Workflows are first-class ecosystem entities.

Workflow inspection payloads SHOULD include:

- `workflow_id`
- `workflow`
- `workflow_type`
- `runtime`
- `status`
- `started_at`
- `ended_at`
- `participating_agents`
- `participating_tools`
- `participating_mcp_servers`
- `participating_services`
- `trace_ids`
- `session_ids`
- `provenance`
- `metadata`

Workflow events SHOULD create graph relationships:

- `agent -> runs -> workflow`
- `workflow -> uses -> tool`
- `workflow -> connects_to -> mcp_server`
- `workflow -> connects_to -> service`

## Snapshot Spec

Snapshots are point-in-time exports of derived OpenMesh state.

Snapshots MUST include:

- `snapshot_id`
- `schema_version`: `1.0`
- `created_at`
- `counts`
- `graph_statistics`
- `ecosystem_statistics`
- `contents`

Snapshot contents SHOULD include:

- agents
- tools
- workflows
- processes
- services
- MCP servers
- capabilities
- relationships
- graph provenance
- traces
- sessions
- discovery
- ecosystem registry
- graph
- events
- registry metadata

Snapshots MUST preserve relationship provenance. Snapshots MUST NOT create a second graph model.

## Timeline Spec

Timelines are chronological read models derived from persisted history.

Timelines MUST include:

- `scope`
- `subject`
- `timeline`
- `summary`

Timelines SHOULD include:

- `first_appearance`
- `last_appearance`
- `relationship_changes`
- `workflow_changes`
- `capability_changes`
- `mcp_changes`
- `session_history`
- `snapshot_history`

Timeline scopes in v1:

- `ecosystem`
- `node`
- `workflow`
- `trace`

Timelines MUST be derived from existing event, session, snapshot, trace, graph, and provenance state.

## Replay Spec

Replays are stateless playback views derived from timelines or snapshots.

Replay payloads MUST include:

- `scope`
- `subject`
- `source`
- `controls`
- `state`
- `frames`
- `visible_frames`
- `summary`

Controls in v1:

- `start`
- `pause`
- `stop`
- `step`

Replay frames SHOULD represent:

- node appearance
- relationship creation
- workflow evolution
- capability evolution
- MCP evolution
- session progression
- snapshot loading or creation
- observed events

Replays MUST NOT create replay-specific storage.

## Query Spec

Queries are structured questions over existing OpenMesh state.

Query requests MUST include:

- `query`

Query requests MAY include:

- `limit`

Query responses MUST include:

- `query`
- `normalized_query`
- `status`
- `category`
- `intent`
- `parameters`
- `source`
- `count`
- `results`
- `errors`

Query status values in v1:

- `ok`
- `not_found`
- `unsupported`
- `error`

Supported v1 query forms:

- `agents using <tool>`
- `workflows using <capability>`
- `relationships created since <timestamp>`
- `nodes added between snapshots`
- `nodes added between snapshots <snapshot_a> <snapshot_b>`
- `nodes removed between snapshots`
- `nodes removed between snapshots <snapshot_a> <snapshot_b>`
- `traces involving <node>`
- `sessions involving <node>`
- `capabilities exposed by <mcp>`

Queries MUST derive answers from existing graph, discovery, provenance, timeline, snapshot, diff, trace, and session read models.

## Related Documents

- [Versioning Strategy](VERSIONING.md)
- [Compatibility Rules](COMPATIBILITY.md)
- [Migration Rules](MIGRATIONS.md)
