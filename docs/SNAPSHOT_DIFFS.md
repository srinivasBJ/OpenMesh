# OpenMesh Snapshot Diffs

OpenMesh snapshot diffs compare two persisted ecosystem snapshots.

They are infrastructure only. They are not AI summaries, recommendations, health scoring, root-cause analysis, or security analysis.

## What A Diff Compares

- nodes added, removed, and changed
- relationships added, removed, and changed
- workflows added and removed
- MCP servers added and removed
- capabilities added and removed
- trace count delta
- session count delta
- graph statistics delta

Relationship diff entries preserve graph provenance from the original snapshots, including event ids, trace ids, timestamps, and observation evidence when present.

## How Diffs Are Built

```text
openmesh_snapshots
  -> saved snapshot payload A
  -> saved snapshot payload B
  -> compare existing graph, discovery, registry, trace, and session read models
  -> CLI, TUI, and API diff output
```

The diff engine does not create a second graph model and does not duplicate snapshot storage.

## CLI

```bash
openmesh snapshot diff <snapshot_a> <snapshot_b>
```

Use the earlier snapshot as `snapshot_a` and the later snapshot as `snapshot_b` when you want positive deltas to mean growth.

## API

```text
GET /api/openmesh/snapshots/{snapshot_a}/diff/{snapshot_b}
```

## TUI

Press `d` in `openmesh tui` to view snapshot diffs.

The Network panel remains visible. The lower-right panel shows the selected A/B snapshot pair and high-level changes. Press `a` or `b` to cycle the selected snapshots used for comparison.
