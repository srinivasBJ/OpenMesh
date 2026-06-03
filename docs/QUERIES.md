# OpenMesh Queries

OpenMesh queries let operators ask structured questions about the observed ecosystem.

The Query Engine is infrastructure, not analysis. It does not generate recommendations, health scores, root-cause explanations, or AI summaries.

## Architecture

```text
Discovery + Graph + Provenance + Timeline + Replay + Snapshot Diff
  -> structured query parser
  -> derived query results
  -> CLI, API, and TUI query views
```

Queries reuse existing OpenMesh state. They do not create a second graph, new query storage model, or alternate event pipeline.

## Supported Queries

```bash
openmesh query agents using <tool>
openmesh query workflows using <capability>
openmesh query relationships created since <timestamp>
openmesh query nodes added between snapshots
openmesh query nodes added between snapshots <snapshot_a> <snapshot_b>
openmesh query nodes removed between snapshots
openmesh query nodes removed between snapshots <snapshot_a> <snapshot_b>
openmesh query traces involving <node>
openmesh query sessions involving <node>
openmesh query capabilities exposed by <mcp>
```

Examples:

```bash
openmesh query agents using web_search
openmesh query workflows using search
openmesh query relationships created since 2026-06-03T00:00:00Z
openmesh query nodes added between snapshots
openmesh query traces involving "Research Agent"
openmesh query capabilities exposed by "Search MCP"
```

## API

```text
POST /api/openmesh/query
```

Request:

```json
{
  "query": "agents using web_search",
  "limit": 5000
}
```

Response payloads include:

- query
- status
- category
- intent
- source
- parameters
- count
- results
- errors
- examples

## TUI

Press `y` in `openmesh tui` to open Query Mode.

Press `u` to cycle through built-in saved queries.

The Network panel remains visible while query results render in the lower-right panel.

## Notes

Unsupported query text returns a structured `unsupported` response. Missing graph entities or snapshot pairs return `not_found` with explicit error codes.
