# OpenMesh Protocol v1 Migration Rules

OpenMesh currently has historical payloads that use pre-v1 values such as:

```text
spec_version: "0.1"
schema_version: "0.1"
```

Protocol v1 formalizes the stable public contract. Implementations may accept pre-v1 payloads during migration.

## Event Migration

To migrate an event from `0.1` to `1.0`:

1. Set `spec_version` to `1.0`.
2. Preserve `event_id`.
3. Preserve `event_type`.
4. Preserve `timestamp`.
5. Preserve `workspace_id` or set it to `local` when absent.
6. Preserve `session_id`.
7. Preserve `trace_id`.
8. Preserve `span_id` or generate one if absent.
9. Preserve `parent_span_id` when present.
10. Preserve `parent_event_id` when present.
11. Preserve `root_event_id` or set it to `event_id` when absent.
12. Preserve `source`.
13. Preserve `target` when present.
14. Preserve `payload`.
15. Preserve `metrics` or set it to `{}` when absent.
16. Preserve `links` or set it to `[]` when absent.
17. Preserve `severity` or set it to `info` when absent.

Migrators MUST NOT rewrite ids unless the original payload is missing them.

## Trace Migration

Trace migration is derived from event migration.

After event migration:

- group events by `trace_id`
- reconstruct event hierarchy from `parent_event_id` and `root_event_id`
- reconstruct span tree from `span_id` and `parent_span_id`
- preserve links for cross-trace references

If parent fields are missing, consumers MAY fall back to timestamp order with a warning.

## Node Migration

To migrate event node references:

1. Preserve `node_id`.
2. Preserve `node_type`.
3. Preserve `name`.
4. Preserve `runtime` when present.
5. Preserve `metadata` or set it to `{}` when absent.

Unknown node types SHOULD remain raw event data until a registry definition exists.

## Relationship Migration

Relationships are derived from migrated events.

Migrators SHOULD:

- derive relationship type from event type and source/target node types
- preserve event ids, trace ids, session ids, span ids, and timestamps in provenance
- preserve observation counts
- mark invalid relationship types through validation instead of deleting evidence

Migrators MUST NOT invent relationships that cannot be traced to an event.

## Workflow Migration

Workflows are migrated as governed `workflow` nodes.

Migrators SHOULD preserve:

- workflow id
- workflow name
- framework or runtime
- source metadata
- trace ids
- session ids
- provenance

Workflow inspection payloads may be regenerated from graph state after events are migrated.

## Snapshot Migration

To migrate a snapshot from `0.1` to `1.0`:

1. Set `schema_version` to `1.0`.
2. Preserve `snapshot_id`.
3. Preserve `created_at`.
4. Preserve `counts`.
5. Preserve `graph_statistics`.
6. Preserve `ecosystem_statistics`.
7. Preserve `contents`.
8. Revalidate contained graph nodes and relationships against v1 registries.
9. Preserve graph provenance exactly.

Snapshots SHOULD NOT be rewritten unless the operator explicitly requests migration.

## Timeline Migration

Timelines are derived read models.

Migrators SHOULD regenerate timelines from migrated events, sessions, and snapshots instead of patching old timeline payloads.

## Replay Migration

Replays are stateless read models.

Migrators SHOULD regenerate replays from migrated timelines or snapshots.

## Query Migration

Query requests do not need data migration.

Query results SHOULD be regenerated from migrated graph, discovery, timeline, snapshot, trace, and session read models.

## Compatibility Window

During v1 adoption, consumers SHOULD accept:

- event `spec_version` `0.1`
- snapshot `schema_version` `0.1`

Consumers SHOULD emit warnings for pre-v1 payloads and SHOULD emit v1 payloads for newly generated protocol data.
