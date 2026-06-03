# OpenMesh Replays

OpenMesh replays let operators play back observed ecosystem history from persisted OpenMesh state.

Replay is infrastructure, not analysis. It does not generate recommendations, health scores, root-cause explanations, or AI summaries.

## Architecture

```text
Event Store + Trace Store + Snapshot Engine + Diff Engine + Timeline Engine
  -> ordered replay frames
  -> stateless playback controls
  -> CLI, API, and TUI replay views
```

The replay engine reuses existing timelines and snapshots. It does not create a second graph model, second timeline model, or replay-specific storage table.

## Reconstructed Activity

Replay frames can represent:

- node appearance
- relationship creation
- workflow evolution
- capability evolution
- MCP evolution
- session progression
- snapshot creation or loading
- observed events

## CLI

```bash
openmesh replay
openmesh replay --control pause --position 10
openmesh replay --control step --position 10
openmesh replay --control stop

openmesh replay snapshot <snapshot_id>
openmesh replay trace <trace_id>
openmesh replay workflow <workflow_id>
```

Supported controls:

- `start`: show playback through the selected frame
- `pause`: hold playback at the selected frame
- `stop`: clear visible frames
- `step`: advance one frame from the selected position

## API

```text
GET /api/openmesh/replay/snapshot/{snapshot_id}
GET /api/openmesh/replay/trace/{trace_id}
GET /api/openmesh/replay/workflow/{workflow_id}
```

Each endpoint accepts:

- `control`
- `position`

Trace and workflow replay endpoints also accept:

- `limit`

## TUI

Press `r` in `openmesh tui` to open Replay Mode.

Controls:

- `space`: start or pause
- `n`: step
- `x`: stop

The Network panel remains visible while the replay panel shows current frame, visible frames, and playback status.

## Payload Shape

Replay payloads include:

- `scope`
- `subject`
- `source`
- `controls`
- `state`
- `frames`
- `visible_frames`
- `summary`

Frames are ordered by timestamp and include an action, category, description, frame index, and source metadata when available.
