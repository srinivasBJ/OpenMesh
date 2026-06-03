# Graph Exploration

OpenMesh graph exploration is a read-only layer over the existing graph reducer.
It does not create another graph model, run analysis, or produce recommendations.

The exploration layer supports:

- node selection
- relationship traversal
- neighborhood expansion
- graph filtering
- graph search
- graph statistics
- provenance-preserving inspection

## API

```bash
GET /api/openmesh/graph/search?q=web
GET /api/openmesh/graph/filter?node_type=agent
GET /api/openmesh/graph/filter?relationship_type=connects_to
GET /api/openmesh/graph/explore/{node_id}
```

`/graph/explore/{node_id}` accepts:

- `depth`: neighborhood depth from `0` to `4`
- `direction`: `incoming`, `outgoing`, or `both`
- `relationship_type`: optional relationship filter
- `node_type`: optional neighbor node type filter
- `q`: optional search query
- `limit`: result limit

Responses reuse the existing graph node and edge records, including provenance,
trace ids, event ids, lifecycle state, validation state, and relationship
definitions.

## TUI

The network panel remains visible.

- Arrow keys select graph rows.
- `Enter` inspects the selected node or relationship.
- `g` cycles network filters.
- `f` focuses the graph on the selected node.
- `p` expands the focused neighborhood depth.
- `c` collapses the focused neighborhood depth.
- `o` clears focus and returns to the full graph.
- `k` searches from the selected entity.

Node inspection shows:

- incoming relationships
- outgoing relationships
- traversal targets
- one-hop neighborhood counts
- local search matches
- provenance

Relationship inspection shows:

- source node
- target node
- relationship type
- provenance
- traversal path

## Frontend Graph View

The browser graph view lives at `/graph` and is documented in
[GRAPH_VIEW_V0_2.md](GRAPH_VIEW_V0_2.md). It reuses the same graph, trace,
inspection, timeline, and ecosystem APIs as the CLI and TUI.

## CLI

The default command still renders the whole graph:

```bash
openmesh graph
openmesh graph --details
```

Graph Explorer options add terminal-first navigation without creating a second
graph model:

```bash
openmesh graph --focus research-agent --depth 2 --details
openmesh graph --focus web_search --direction incoming
openmesh graph --search filesystem
openmesh graph --node-type agent --relationship-type uses --stats
openmesh graph --lifecycle-state active
```

Focused output includes:

- selected node metadata
- first and last seen timestamps
- event and relationship counts
- traces and sessions from provenance
- traversal targets
- neighborhood graph output
- relationship provenance when `--details` is enabled

## Navigation Model

The intended exploration flow is:

```text
Agent
  -> Tool
  -> Workflow
  -> MCP Server
  -> Service
```

The model is not limited to that chain. Any governed OpenMesh node and
relationship can participate as long as it is present in the reducer output.

## Architecture

Graph exploration derives from:

```text
openmesh_events
  -> graph reducer
  -> graph exploration service
  -> API / TUI
```

The exploration service lives in `backend/src/services/graph_exploration.py`.
It consumes the same graph dict returned by `reduce_graph_state()` and preserves
existing provenance.
