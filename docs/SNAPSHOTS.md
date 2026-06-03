# OpenMesh Snapshots

OpenMesh snapshots freeze the observed ecosystem at a point in time.

They are not analysis, recommendations, root-cause detection, or AI summaries. A snapshot is an exportable read model built from the current OpenMesh event store.

## What A Snapshot Contains

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
- discovery output
- ecosystem registry output
- graph reducer output

## How Snapshots Are Built

```text
openmesh_events + openmesh_sessions
  -> graph reducer
  -> discovery registry
  -> workflow registry
  -> MCP registries
  -> capability registry
  -> ecosystem registry
  -> openmesh_snapshots
```

The snapshot engine reuses existing reducers. It does not create a parallel graph model.

## CLI

```bash
openmesh snapshot create
openmesh snapshot list
openmesh snapshot inspect <snapshot_id>
openmesh snapshot diff <snapshot_a> <snapshot_b>
```

## API

```text
GET /api/openmesh/snapshots
GET /api/openmesh/snapshots/{snapshot_id}
GET /api/openmesh/snapshots/{snapshot_a}/diff/{snapshot_b}
```

## Storage

Snapshots are stored in `openmesh_snapshots`.

Each record includes:

- `snapshot_id`
- `created_at`
- counts
- graph statistics
- ecosystem statistics
- frozen snapshot payload

## TUI

Press `s` in `openmesh tui` to browse saved snapshots.

The snapshot view shows snapshot ids, creation time, node counts, relationship counts, trace counts, session counts, and latest snapshot statistics.

Press `d` to view a snapshot diff. The TUI keeps the Network panel visible while the lower-right panel shows the selected A/B snapshot pair and high-level node, relationship, workflow, MCP, capability, trace, session, and graph-stat deltas. Use `a` and `b` to cycle the selected snapshots.
