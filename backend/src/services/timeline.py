from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord, OpenMeshSessionRecord
from ..db.openmesh_events import list_openmesh_events, record_to_event
from ..db.openmesh_sessions import list_openmesh_sessions, session_to_dict
from ..db.openmesh_snapshots import (
    list_openmesh_snapshots,
    snapshot_record_to_detail,
)
from .ecosystem_snapshot import compare_snapshot_payloads
from .graph_state import reduce_graph_state
from .openmesh_queries import (
    inspect_graph_node,
    inspect_graph_workflow,
    trace_summary,
)
from .trace_semantics import graph_edges_for_trace
from .workflow_registry import build_workflow_registry


async def get_timeline(
    db: AsyncSession, *, limit: int = 5000, snapshot_limit: int = 100
) -> dict[str, Any]:
    records, sessions, snapshots = await _load_history(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return build_timeline(records, sessions, snapshots)


async def get_node_timeline(
    db: AsyncSession, node_id: str, *, limit: int = 5000, snapshot_limit: int = 100
) -> dict[str, Any] | None:
    records, sessions, snapshots = await _load_history(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return build_node_timeline(records, sessions, snapshots, node_id)


async def get_workflow_timeline(
    db: AsyncSession,
    workflow_id: str,
    *,
    limit: int = 5000,
    snapshot_limit: int = 100,
) -> dict[str, Any] | None:
    records, sessions, snapshots = await _load_history(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return build_workflow_timeline(records, sessions, snapshots, workflow_id)


async def get_trace_timeline(
    db: AsyncSession, trace_id: str, *, limit: int = 5000, snapshot_limit: int = 100
) -> dict[str, Any] | None:
    records, sessions, snapshots = await _load_history(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return build_trace_timeline(records, sessions, snapshots, trace_id)


def build_timeline(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    record_list = _ordered_records(records)
    session_history = _session_history(sessions)
    snapshot_history = _snapshot_history(snapshots)
    graph = reduce_graph_state(record_list)
    relationship_changes = _relationship_observations(graph) + _snapshot_changes(
        snapshot_history, "relationships"
    )
    workflow_changes = _entity_observations(graph, "workflow") + _snapshot_changes(
        snapshot_history, "workflows"
    )
    mcp_changes = _entity_observations(graph, "mcp_server") + _snapshot_changes(
        snapshot_history, "mcp_servers"
    )
    capability_changes = _entity_observations(graph, "capability") + _snapshot_changes(
        snapshot_history, "capabilities"
    )
    timeline = _event_entries(record_list)
    timeline.extend(_session_entries(session_history))
    timeline.extend(_snapshot_entries(snapshot_history))
    timeline.extend(_compact_changes(relationship_changes, "relationship"))
    timeline.extend(_compact_changes(workflow_changes, "workflow"))
    timeline.extend(_compact_changes(mcp_changes, "mcp"))
    timeline.extend(_compact_changes(capability_changes, "capability"))
    timeline = _sort_entries(timeline)
    return {
        "scope": "ecosystem",
        "subject": {"type": "ecosystem", "id": "openmesh.ecosystem"},
        "first_appearance": _first_timestamp(timeline),
        "last_appearance": _last_timestamp(timeline),
        "relationship_changes": _sort_entries(relationship_changes),
        "workflow_changes": _sort_entries(workflow_changes),
        "capability_changes": _sort_entries(capability_changes),
        "mcp_changes": _sort_entries(mcp_changes),
        "session_history": session_history,
        "snapshot_history": snapshot_history,
        "timeline": timeline,
        "summary": _summary(
            records=record_list,
            sessions=session_history,
            snapshots=snapshot_history,
            relationships=relationship_changes,
            workflows=workflow_changes,
            capabilities=capability_changes,
            mcp=mcp_changes,
        ),
    }


def build_node_timeline(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
    node_ref: str,
) -> dict[str, Any] | None:
    record_list = _ordered_records(records)
    snapshot_history = _snapshot_history(snapshots)
    graph = reduce_graph_state(record_list)
    node = _resolve_node(graph, snapshot_history, node_ref)
    if not node:
        return None
    node_id = node["id"]
    matched_records = [
        record
        for record in record_list
        if _event_has_node(record_to_event(record), node_id)
    ]
    session_ids = {record.session_id for record in matched_records if record.session_id}
    relationship_changes = _filter_relationship_changes(
        _relationship_observations(graph)
        + _snapshot_changes(snapshot_history, "relationships"),
        node_id,
    )
    workflow_changes = _filter_entity_changes(
        _entity_observations(graph, "workflow")
        + _snapshot_changes(snapshot_history, "workflows"),
        node_id,
    )
    mcp_changes = _filter_entity_changes(
        _entity_observations(graph, "mcp_server")
        + _snapshot_changes(snapshot_history, "mcp_servers"),
        node_id,
    )
    capability_changes = _filter_entity_changes(
        _entity_observations(graph, "capability")
        + _snapshot_changes(snapshot_history, "capabilities"),
        node_id,
    )
    node_snapshots = _filter_snapshot_history_for_node(snapshot_history, node_id)
    session_history = [
        item for item in _session_history(sessions) if item["session_id"] in session_ids
    ]
    timeline = _event_entries(matched_records)
    timeline.extend(_session_entries(session_history))
    timeline.extend(_snapshot_entries(node_snapshots))
    timeline.extend(_compact_changes(relationship_changes, "relationship"))
    timeline.extend(_compact_changes(workflow_changes, "workflow"))
    timeline.extend(_compact_changes(mcp_changes, "mcp"))
    timeline.extend(_compact_changes(capability_changes, "capability"))
    timeline = _sort_entries(timeline)
    return {
        "scope": "node",
        "subject": node,
        "first_appearance": _first_timestamp(timeline) or node.get("first_seen"),
        "last_appearance": _last_timestamp(timeline) or node.get("last_seen"),
        "relationship_changes": _sort_entries(relationship_changes),
        "workflow_changes": _sort_entries(workflow_changes),
        "capability_changes": _sort_entries(capability_changes),
        "mcp_changes": _sort_entries(mcp_changes),
        "session_history": session_history,
        "snapshot_history": node_snapshots,
        "timeline": timeline,
        "summary": _summary(
            records=matched_records,
            sessions=session_history,
            snapshots=node_snapshots,
            relationships=relationship_changes,
            workflows=workflow_changes,
            capabilities=capability_changes,
            mcp=mcp_changes,
        ),
    }


def build_workflow_timeline(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
    workflow_ref: str,
) -> dict[str, Any] | None:
    record_list = _ordered_records(records)
    snapshot_history = _snapshot_history(snapshots)
    graph = reduce_graph_state(record_list)
    workflow = inspect_graph_workflow(
        graph,
        workflow_ref,
        registry_by_id={
            entry["id"]: entry for entry in build_workflow_registry(record_list)
        },
    )
    if not workflow:
        workflow = _resolve_workflow_from_snapshots(snapshot_history, workflow_ref)
    if not workflow:
        return None
    workflow_id = workflow["workflow_id"]
    node_timeline = build_node_timeline(
        record_list, sessions, snapshot_history, workflow_id
    )
    if not node_timeline:
        return None
    return {
        **node_timeline,
        "scope": "workflow",
        "subject": workflow,
    }


def build_trace_timeline(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
    trace_id: str,
) -> dict[str, Any] | None:
    record_list = [
        record for record in _ordered_records(records) if record.trace_id == trace_id
    ]
    if not record_list:
        return None
    events = [record_to_event(record) for record in record_list]
    session_ids = {record.session_id for record in record_list if record.session_id}
    session_history = [
        item for item in _session_history(sessions) if item["session_id"] in session_ids
    ]
    snapshot_history = _filter_snapshot_history_for_trace(
        _snapshot_history(snapshots), trace_id
    )
    relationship_changes = [
        {
            "timestamp": event.get("timestamp"),
            "kind": "relationship.observed",
            "source": edge.get("source"),
            "target": edge.get("target"),
            "relationship_type": edge.get("type"),
            "trace_id": trace_id,
            "event_id": edge.get("event_id"),
        }
        for event in events
        for edge in graph_edges_for_trace([event])
    ]
    timeline = _event_entries(record_list)
    timeline.extend(_session_entries(session_history))
    timeline.extend(_snapshot_entries(snapshot_history))
    timeline.extend(_compact_changes(relationship_changes, "relationship"))
    timeline = _sort_entries(timeline)
    return {
        "scope": "trace",
        "subject": trace_summary(trace_id, record_list),
        "first_appearance": _first_timestamp(timeline),
        "last_appearance": _last_timestamp(timeline),
        "relationship_changes": _sort_entries(relationship_changes),
        "workflow_changes": [],
        "capability_changes": [],
        "mcp_changes": [],
        "session_history": session_history,
        "snapshot_history": snapshot_history,
        "timeline": timeline,
        "summary": _summary(
            records=record_list,
            sessions=session_history,
            snapshots=snapshot_history,
            relationships=relationship_changes,
            workflows=[],
            capabilities=[],
            mcp=[],
        ),
    }


async def _load_history(
    db: AsyncSession, *, limit: int, snapshot_limit: int
) -> tuple[
    list[OpenMeshEventRecord],
    list[OpenMeshSessionRecord],
    list[dict[str, Any]],
]:
    records = await list_openmesh_events(db, limit=limit)
    sessions = await list_openmesh_sessions(db, limit=limit)
    snapshot_records = await list_openmesh_snapshots(db, limit=snapshot_limit)
    snapshots = [snapshot_record_to_detail(record) for record in snapshot_records]
    return records, sessions, snapshots


def _ordered_records(
    records: Iterable[OpenMeshEventRecord],
) -> list[OpenMeshEventRecord]:
    return sorted(records, key=lambda record: record.timestamp)


def _event_entries(records: Iterable[OpenMeshEventRecord]) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": record.timestamp.isoformat() + "Z",
            "kind": "event",
            "event_id": record.event_id,
            "event_type": record.event_type,
            "trace_id": record.trace_id,
            "session_id": record.session_id,
            "source": _node_label(record.source_json),
            "target": _node_label(record.target_json),
        }
        for record in records
    ]


def _session_history(
    sessions: Iterable[OpenMeshSessionRecord],
) -> list[dict[str, Any]]:
    return sorted(
        [session_to_dict(record) for record in sessions],
        key=lambda item: item.get("started_at") or "",
    )


def _session_entries(sessions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for session in sessions:
        entries.append(
            {
                "timestamp": session.get("started_at"),
                "kind": "session.started",
                "session_id": session.get("session_id"),
                "command": session.get("command"),
                "status": session.get("status"),
            }
        )
        if session.get("ended_at"):
            entries.append(
                {
                    "timestamp": session.get("ended_at"),
                    "kind": f"session.{session.get('status')}",
                    "session_id": session.get("session_id"),
                    "command": session.get("command"),
                    "status": session.get("status"),
                    "exit_code": session.get("exit_code"),
                }
            )
    return entries


def _snapshot_history(snapshots: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [snapshot for snapshot in snapshots],
        key=lambda item: item.get("created_at") or "",
    )


def _snapshot_nodes(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    contents = snapshot.get("contents", {})
    graph = contents.get("graph", {})
    nodes = graph.get("nodes")
    return list(nodes if isinstance(nodes, list) else contents.get("nodes", []))


def _snapshot_entries(snapshots: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": snapshot.get("created_at"),
            "kind": "snapshot.created",
            "snapshot_id": snapshot.get("snapshot_id"),
            "counts": snapshot.get("counts", {}),
        }
        for snapshot in snapshots
    ]


def _relationship_observations(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    changes = []
    for edge in graph.get("edges", []):
        provenance = edge.get("provenance", {})
        changes.append(
            {
                "timestamp": edge.get("first_seen"),
                "last_seen": edge.get("last_seen"),
                "kind": "relationship.observed",
                "source": edge.get("source"),
                "source_name": nodes.get(edge.get("source"), {}).get("name"),
                "target": edge.get("target"),
                "target_name": nodes.get(edge.get("target"), {}).get("name"),
                "relationship_type": edge.get("type"),
                "event_count": edge.get("event_count", 0),
                "provenance": provenance,
            }
        )
    return changes


def _entity_observations(graph: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": node.get("first_seen"),
            "last_seen": node.get("last_seen"),
            "kind": f"{node_type}.observed",
            "id": node.get("id"),
            "name": node.get("name"),
            "type": node_type,
            "event_count": node.get("event_count", 0),
            "provenance": node.get("provenance", {}),
        }
        for node in graph.get("nodes", [])
        if node.get("type") == node_type
    ]


def _snapshot_changes(
    snapshots: list[dict[str, Any]], section: str
) -> list[dict[str, Any]]:
    changes = []
    for before, after in zip(snapshots, snapshots[1:]):
        diff = compare_snapshot_payloads(before, after)
        section_diff = diff.get(section, {})
        for operation in ("added", "removed", "changed"):
            for item in section_diff.get(operation, []):
                changes.append(
                    _snapshot_change(
                        after.get("created_at"), operation, section, before, after, item
                    )
                )
    return changes


def _snapshot_change(
    timestamp: str | None,
    operation: str,
    section: str,
    before: dict[str, Any],
    after: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    source_item = item.get("after", item)
    return {
        "timestamp": timestamp,
        "kind": f"{section}.{operation}",
        "operation": operation,
        "section": section,
        "snapshot_a": before.get("snapshot_id"),
        "snapshot_b": after.get("snapshot_id"),
        "id": _item_id(source_item),
        "name": _item_name(source_item),
        "source": source_item.get("source"),
        "target": source_item.get("target"),
        "relationship_type": source_item.get("type")
        or source_item.get("relationship_type"),
        "changed_fields": item.get("changed_fields", []),
        "provenance": source_item.get("provenance", {}),
        "item": item,
    }


def _compact_changes(
    changes: Iterable[dict[str, Any]], category: str
) -> list[dict[str, Any]]:
    entries = []
    for change in changes:
        entries.append(
            {
                "timestamp": change.get("timestamp"),
                "kind": change.get("kind", f"{category}.change"),
                "category": category,
                "id": change.get("id"),
                "name": change.get("name"),
                "source": change.get("source"),
                "target": change.get("target"),
                "relationship_type": change.get("relationship_type"),
            }
        )
    return entries


def _resolve_node(
    graph: dict[str, Any],
    snapshots: list[dict[str, Any]],
    node_ref: str,
) -> dict[str, Any] | None:
    node = inspect_graph_node(graph, node_ref)
    if node:
        return node["node"]
    normalized_ref = _normalize_ref(node_ref)
    for snapshot in reversed(snapshots):
        for candidate in _snapshot_nodes(snapshot):
            aliases = _node_aliases(candidate)
            if normalized_ref in aliases:
                return candidate
    return None


def _resolve_workflow_from_snapshots(
    snapshots: list[dict[str, Any]], workflow_ref: str
) -> dict[str, Any] | None:
    normalized_ref = _normalize_ref(workflow_ref)
    for snapshot in reversed(snapshots):
        contents = snapshot.get("contents", {})
        for workflow in contents.get("workflows", []):
            aliases = {
                _normalize_ref(str(value))
                for value in (
                    workflow.get("workflow_id"),
                    workflow.get("id"),
                    workflow.get("workflow"),
                    workflow.get("name"),
                )
                if value
            }
            if normalized_ref in aliases:
                return {
                    "workflow_id": workflow.get("workflow_id") or workflow.get("id"),
                    "workflow": workflow.get("workflow") or workflow.get("name"),
                    "name": workflow.get("workflow") or workflow.get("name"),
                    "workflow_type": workflow.get("workflow_type")
                    or workflow.get("framework"),
                    "runtime": workflow.get("framework"),
                    "status": workflow.get("status", "observed"),
                    "first_seen": workflow.get("first_seen"),
                    "last_seen": workflow.get("last_seen"),
                    "provenance": workflow.get("provenance", {}),
                }
    return None


def _event_has_node(event: dict[str, Any], node_id: str) -> bool:
    return any(
        node and node.get("node_id") == node_id
        for node in (event.get("source"), event.get("target"))
    )


def _filter_relationship_changes(
    changes: Iterable[dict[str, Any]], node_id: str
) -> list[dict[str, Any]]:
    return [
        change
        for change in changes
        if node_id in {change.get("source"), change.get("target")}
    ]


def _filter_entity_changes(
    changes: Iterable[dict[str, Any]], entity_id: str
) -> list[dict[str, Any]]:
    return [
        change
        for change in changes
        if entity_id
        in {
            change.get("id"),
            change.get("source"),
            change.get("target"),
            (change.get("item") or {}).get("id"),
        }
    ]


def _filter_snapshot_history_for_node(
    snapshots: Iterable[dict[str, Any]], node_id: str
) -> list[dict[str, Any]]:
    return [
        snapshot
        for snapshot in snapshots
        if any(node.get("id") == node_id for node in _snapshot_nodes(snapshot))
    ]


def _filter_snapshot_history_for_trace(
    snapshots: Iterable[dict[str, Any]], trace_id: str
) -> list[dict[str, Any]]:
    matched = []
    for snapshot in snapshots:
        traces = snapshot.get("contents", {}).get("traces", [])
        if any(trace.get("trace_id") == trace_id for trace in traces):
            matched.append(snapshot)
    return matched


def _sort_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [entry for entry in entries if entry.get("timestamp")],
        key=lambda item: (item.get("timestamp") or "", item.get("kind") or ""),
    )


def _summary(
    *,
    records: list[OpenMeshEventRecord],
    sessions: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
    mcp: list[dict[str, Any]],
) -> dict[str, int]:
    return {
        "events": len(records),
        "traces": len({record.trace_id for record in records if record.trace_id}),
        "sessions": len(sessions),
        "snapshots": len(snapshots),
        "relationship_changes": len(relationships),
        "workflow_changes": len(workflows),
        "capability_changes": len(capabilities),
        "mcp_changes": len(mcp),
    }


def _first_timestamp(entries: list[dict[str, Any]]) -> str | None:
    return entries[0]["timestamp"] if entries else None


def _last_timestamp(entries: list[dict[str, Any]]) -> str | None:
    return entries[-1]["timestamp"] if entries else None


def _node_label(node: dict[str, Any] | None) -> str | None:
    if not node:
        return None
    return str(node.get("name") or node.get("node_id") or "Unknown Node")


def _node_aliases(node: dict[str, Any]) -> set[str]:
    return {
        _normalize_ref(str(value))
        for value in (
            node.get("id"),
            node.get("node_id"),
            node.get("name"),
            str(node.get("id", "")).split(":", 1)[-1],
        )
        if value
    }


def _item_id(item: dict[str, Any]) -> str | None:
    for key in ("id", "workflow_id", "server", "capability"):
        if item.get(key):
            return str(item[key])
    return None


def _item_name(item: dict[str, Any]) -> str | None:
    for key in ("name", "workflow", "server", "capability", "id"):
        if item.get(key):
            return str(item[key])
    if item.get("source") and item.get("target") and item.get("type"):
        return f"{item['source']} {item['type']} {item['target']}"
    return None


def _normalize_ref(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("_", "-")
