# OpenMesh Timelines

OpenMesh timelines let operators navigate how the observed ecosystem changed over time.

They are infrastructure only. They are not AI summaries, recommendations, health scoring, root-cause analysis, or security analysis.

## What Timelines Show

- first appearance
- last appearance
- relationship changes
- workflow changes
- capability changes
- MCP changes
- session history
- snapshot history

## How Timelines Are Built

```text
openmesh_events
openmesh_sessions
openmesh_snapshots
  -> trace summaries
  -> graph reducer and provenance
  -> workflow inspection
  -> snapshot diff engine
  -> timeline read model
```

The timeline engine reuses existing persisted history and reducers. It does not create a second graph model or duplicate snapshot data.

## CLI

```bash
openmesh timeline
openmesh timeline node <node_id>
openmesh timeline workflow <workflow_id>
openmesh timeline trace <trace_id>
```

## API

```text
GET /api/openmesh/timeline
GET /api/openmesh/timeline/node/{node_id}
GET /api/openmesh/timeline/workflow/{workflow_id}
GET /api/openmesh/timeline/trace/{trace_id}
```

## TUI

Press `l` in `openmesh tui` to open the Timeline view.

The Network panel remains visible. The lower-right panel shows the ecosystem timeline, recent evolution events, and snapshot history.
