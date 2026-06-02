# OpenMesh Doctor

`openmesh doctor` checks local OpenMesh health and persisted observability integrity.

Severity levels:

- `INFO`: healthy or informational.
- `WARNING`: usable, but attention is recommended.
- `ERROR`: broken integrity or configuration that should be fixed.

Example healthy trace and graph output:

```text
OpenMesh Doctor

database: INFO
  connection succeeded
Trace Integrity: INFO
  traces_checked: 4
  broken_parent_span_events: 0
  missing_root_event_events: 0
  orphan_spans: 0
  malformed_link_events: 0
Graph Integrity: INFO
  nodes_checked: 10
  edges_checked: 6
  missing_provenance: 0
  invalid_relationships: 0
  stale_relationships: 0

Overall: OK
```

Example warning:

```text
Workflow Integrity: WARNING
  incomplete_workflow_spans: 1
    - {'trace_id': 'trace_abc', 'span_id': 'span_workflow', 'started_at': '2026-06-02T04:25:41Z'}

Overall: WARNING
```

Example error:

```text
Trace Integrity: ERROR
  broken_parent_span_events: 1
    - {'trace_id': 'trace_abc', 'event_id': 'evt_child'}
  invalid_cross_trace_links: 1
    - {'trace_id': 'trace_abc', 'event_id': 'evt_link', 'linked_trace_id': 'trace_missing'}

Overall: ERROR
```
