# OpenMesh Workflow Replay

OpenMesh replay reconstructs ecosystem evolution from persisted OpenMesh events and
timeline reducers. It does not create another graph store.

## Commands

```bash
openmesh run-demo multi-agent
openmesh replay ecosystem
openmesh replay trace <trace_id>
openmesh replay workflow <workflow_id>
```

The workflow demo prints the workflow id after generation. Replay also accepts the
stable demo workflow id:

```bash
openmesh replay workflow workflow:openmesh:multi-agent-handoff-demo
```

## Time Travel Controls

Replay supports these controls:

- `start`: show playback from the selected position.
- `pause`: hold playback at the selected position.
- `step`: move one frame forward.
- `previous`: move one frame backward.
- `jump`: jump to a timestamp or event id.
- `stop`: clear visible frames.

Examples:

```bash
openmesh replay ecosystem --control step --position 4
openmesh replay workflow workflow:openmesh:multi-agent-handoff-demo --control previous --position 8
openmesh replay trace trace_abc123 --control jump --event-id evt_abc123
openmesh replay ecosystem --control jump --timestamp 2026-06-04T10:00:00Z
```

## Replay Frames

Replay frames are derived from existing timeline entries and event history.

Frame actions include:

- `node.appeared`
- `relationship.created`
- `relationship.removed`
- `workflow.started`
- `workflow.completed`
- `handoff.occurred`
- `message.exchanged`
- `session.started`
- `session.completed`
- `snapshot.created`

## API

```http
GET /api/openmesh/replay/ecosystem
GET /api/openmesh/replay/trace/{trace_id}
GET /api/openmesh/replay/workflow/{workflow_id}
```

Query parameters:

- `control`
- `position`
- `timestamp`
- `event_id`
- `speed`
- `limit`

## Frontend

The History page includes a time travel console with play, pause, previous, next,
stop, and speed controls. The Observatory page surfaces replay metrics:

- events replayed
- replay duration
- graph mutations
- workflow duration

## Architecture

Replay uses:

```text
Persisted Events
  -> Timeline Service
  -> Replay Engine
  -> CLI / API / TUI / Frontend
```

It reuses the existing timeline, graph, workflow, trace, and snapshot reducers.
No replay-specific storage is introduced.
