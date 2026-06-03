from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord, OpenMeshSessionRecord
from ..db.openmesh_events import list_openmesh_events, record_to_event
from ..db.openmesh_sessions import list_openmesh_sessions, session_to_dict
from ..db.openmesh_snapshots import (
    create_openmesh_snapshot,
    get_openmesh_snapshot,
    list_openmesh_snapshots,
    snapshot_record_to_detail,
    snapshot_record_to_summary,
)
from .discovery import build_discovery
from .ecosystem_registry import build_ecosystem_registry
from .graph_state import reduce_graph_state
from .mcp_capabilities import build_capability_registry
from .mcp_config_discovery import build_mcp_config_registry
from .mcp_discovery import build_mcp_registry
from .openmesh_queries import trace_summary
from .registry_status import build_registry_status
from .workflow_registry import build_workflow_registry


SNAPSHOT_SCHEMA_VERSION = "0.1"


async def create_ecosystem_snapshot(
    db: AsyncSession, *, limit: int = 5000
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    sessions = await list_openmesh_sessions(db, limit=limit)
    snapshot = build_ecosystem_snapshot(records, sessions)
    record = await create_openmesh_snapshot(db, snapshot)
    return snapshot_record_to_detail(record)


async def list_ecosystem_snapshots(
    db: AsyncSession, *, limit: int = 100
) -> list[dict[str, Any]]:
    records = await list_openmesh_snapshots(db, limit=limit)
    return [snapshot_record_to_summary(record) for record in records]


async def inspect_ecosystem_snapshot(
    db: AsyncSession, snapshot_id: str
) -> dict[str, Any] | None:
    record = await get_openmesh_snapshot(db, snapshot_id)
    return snapshot_record_to_detail(record) if record else None


async def diff_ecosystem_snapshots(
    db: AsyncSession, snapshot_a: str, snapshot_b: str
) -> dict[str, Any] | None:
    record_a = await get_openmesh_snapshot(db, snapshot_a)
    record_b = await get_openmesh_snapshot(db, snapshot_b)
    if not record_a or not record_b:
        return None
    return compare_snapshot_payloads(
        snapshot_record_to_detail(record_a), snapshot_record_to_detail(record_b)
    )


def compare_snapshot_payloads(
    snapshot_a: dict[str, Any], snapshot_b: dict[str, Any]
) -> dict[str, Any]:
    contents_a = snapshot_a.get("contents", {})
    contents_b = snapshot_b.get("contents", {})
    nodes = _diff_collection(
        _snapshot_nodes(snapshot_a),
        _snapshot_nodes(snapshot_b),
        _node_key,
        _NODE_COMPARISON_FIELDS,
    )
    relationships = _diff_collection(
        _snapshot_relationships(snapshot_a),
        _snapshot_relationships(snapshot_b),
        _relationship_key,
        _RELATIONSHIP_COMPARISON_FIELDS,
    )
    workflows = _presence_diff(
        contents_a.get("workflows", []),
        contents_b.get("workflows", []),
        _workflow_key,
    )
    mcp_servers = _presence_diff(
        contents_a.get("mcp_servers", []),
        contents_b.get("mcp_servers", []),
        _mcp_server_key,
    )
    capabilities = _presence_diff(
        contents_a.get("capabilities", []),
        contents_b.get("capabilities", []),
        _capability_key,
    )
    count_deltas = _numeric_delta(
        snapshot_a.get("counts", {}), snapshot_b.get("counts", {})
    )
    graph_statistics_delta = _statistics_delta(
        snapshot_a.get("graph_statistics", {}), snapshot_b.get("graph_statistics", {})
    )
    return {
        "snapshot_a": _snapshot_identity(snapshot_a),
        "snapshot_b": _snapshot_identity(snapshot_b),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "nodes": nodes,
        "relationships": relationships,
        "workflows": workflows,
        "mcp_servers": mcp_servers,
        "capabilities": capabilities,
        "trace_count_delta": count_deltas.get("traces", {}).get("delta", 0),
        "session_count_delta": count_deltas.get("sessions", {}).get("delta", 0),
        "graph_statistics_delta": graph_statistics_delta,
        "count_deltas": count_deltas,
        "summary": _diff_summary(
            nodes=nodes,
            relationships=relationships,
            workflows=workflows,
            mcp_servers=mcp_servers,
            capabilities=capabilities,
            count_deltas=count_deltas,
            graph_statistics_delta=graph_statistics_delta,
        ),
    }


def build_ecosystem_snapshot(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
) -> dict[str, Any]:
    record_list = sorted(records, key=lambda record: record.timestamp)
    session_list = list(sessions)
    graph = reduce_graph_state(record_list)
    ecosystem = build_ecosystem_registry(record_list)
    discovery = build_discovery(record_list)
    traces = _trace_summaries(record_list)
    sessions_payload = [session_to_dict(record) for record in session_list]
    workflows = build_workflow_registry(record_list)
    mcp_servers = build_mcp_registry(record_list)
    mcp_configs = build_mcp_config_registry(record_list)
    capabilities = build_capability_registry(record_list)
    events = [record_to_event(record) for record in record_list]
    counts = _counts(
        graph=graph,
        ecosystem=ecosystem,
        traces=traces,
        sessions=sessions_payload,
        events=events,
        workflows=workflows,
        mcp_servers=mcp_servers,
        capabilities=capabilities,
    )
    created_at = datetime.utcnow().isoformat() + "Z"
    return {
        "snapshot_id": f"snap_{uuid4().hex}",
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "created_at": created_at,
        "counts": counts,
        "graph_statistics": _graph_statistics(graph),
        "ecosystem_statistics": _ecosystem_statistics(ecosystem),
        "contents": {
            "agents": ecosystem.get("entities", {}).get("agents", []),
            "tools": ecosystem.get("entities", {}).get("tools", []),
            "workflows": workflows,
            "processes": ecosystem.get("entities", {}).get("processes", []),
            "services": ecosystem.get("entities", {}).get("services", []),
            "mcp_servers": mcp_servers,
            "mcp_configs": mcp_configs,
            "capabilities": capabilities,
            "relationships": graph.get("edges", []),
            "graph_provenance": {
                edge["id"]: edge.get("provenance", {})
                for edge in graph.get("edges", [])
            },
            "traces": traces,
            "sessions": sessions_payload,
            "discovery": discovery,
            "ecosystem": ecosystem,
            "graph": graph,
            "events": events,
            "registry": build_registry_status(record_list),
        },
    }


def _trace_summaries(records: list[OpenMeshEventRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[OpenMeshEventRecord]] = {}
    for record in records:
        grouped.setdefault(record.trace_id, []).append(record)
    return sorted(
        [
            trace_summary(trace_id, trace_records)
            for trace_id, trace_records in grouped.items()
        ],
        key=lambda item: item.get("started_at") or "",
        reverse=True,
    )


def _counts(
    *,
    graph: dict[str, Any],
    ecosystem: dict[str, Any],
    traces: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
    events: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    mcp_servers: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
) -> dict[str, int]:
    entities = ecosystem.get("entities", {})
    return {
        "events": len(events),
        "traces": len(traces),
        "sessions": len(sessions),
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "relationships": len(graph.get("edges", [])),
        "agents": len(entities.get("agents", [])),
        "tools": len(entities.get("tools", [])),
        "workflows": len(workflows),
        "processes": len(entities.get("processes", [])),
        "services": len(entities.get("services", [])),
        "mcp_servers": len(mcp_servers),
        "capabilities": len(capabilities),
    }


def _graph_statistics(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": _count_by(nodes, "type"),
        "relationship_types": _count_by(edges, "type"),
        "validation_status": graph.get("validation", {}).get("status", "UNKNOWN"),
    }


def _ecosystem_statistics(ecosystem: dict[str, Any]) -> dict[str, Any]:
    summary = ecosystem.get("summary", {})
    entities = ecosystem.get("entities", {})
    return {
        "entity_count": summary.get("entity_count", 0),
        "relationship_count": summary.get("relationship_count", 0),
        "groups": {
            group: len(values)
            for group, values in entities.items()
            if isinstance(values, list)
        },
        "validation_status": ecosystem.get("validation", {}).get("status", "UNKNOWN"),
    }


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


_NODE_COMPARISON_FIELDS = (
    "id",
    "type",
    "name",
    "category",
    "runtime",
    "metadata",
    "event_count",
    "trace_ids",
    "session_ids",
    "first_seen",
    "last_seen",
    "validation_status",
)

_RELATIONSHIP_COMPARISON_FIELDS = (
    "id",
    "source",
    "target",
    "type",
    "relationship_type",
    "event_count",
    "observation_count",
    "first_seen",
    "last_seen",
    "trace_ids",
    "session_ids",
    "event_ids",
    "span_ids",
    "validation_status",
    "provenance",
)


def _snapshot_identity(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.get("snapshot_id"),
        "created_at": snapshot.get("created_at"),
        "schema_version": snapshot.get("schema_version"),
        "counts": snapshot.get("counts", {}),
    }


def _snapshot_nodes(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    contents = snapshot.get("contents", {})
    graph = contents.get("graph", {})
    nodes = graph.get("nodes")
    return list(nodes if isinstance(nodes, list) else contents.get("nodes", []))


def _snapshot_relationships(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    contents = snapshot.get("contents", {})
    relationships = contents.get("relationships")
    if isinstance(relationships, list):
        return list(relationships)
    graph = contents.get("graph", {})
    return list(graph.get("edges", []))


def _diff_collection(
    before: Iterable[dict[str, Any]],
    after: Iterable[dict[str, Any]],
    key_fn,
    comparison_fields: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    before_by_key = _index_by(before, key_fn)
    after_by_key = _index_by(after, key_fn)
    before_keys = set(before_by_key)
    after_keys = set(after_by_key)
    shared_keys = before_keys & after_keys
    return {
        "added": [
            _summarize_item(after_by_key[key])
            for key in sorted(after_keys - before_keys)
        ],
        "removed": [
            _summarize_item(before_by_key[key])
            for key in sorted(before_keys - after_keys)
        ],
        "changed": [
            change
            for key in sorted(shared_keys)
            if (
                change := _changed_item(
                    before_by_key[key], after_by_key[key], comparison_fields
                )
            )
        ],
    }


def _presence_diff(
    before: Iterable[dict[str, Any]],
    after: Iterable[dict[str, Any]],
    key_fn,
) -> dict[str, list[dict[str, Any]]]:
    before_by_key = _index_by(before, key_fn)
    after_by_key = _index_by(after, key_fn)
    before_keys = set(before_by_key)
    after_keys = set(after_by_key)
    return {
        "added": [
            _summarize_item(after_by_key[key])
            for key in sorted(after_keys - before_keys)
        ],
        "removed": [
            _summarize_item(before_by_key[key])
            for key in sorted(before_keys - after_keys)
        ],
    }


def _changed_item(
    before: dict[str, Any], after: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any] | None:
    changed_fields = [
        field
        for field in fields
        if _canonical(before.get(field)) != _canonical(after.get(field))
    ]
    if not changed_fields:
        return None
    return {
        "id": _display_id(after) or _display_id(before),
        "name": _display_name(after) or _display_name(before),
        "type": after.get("type")
        or after.get("relationship_type")
        or before.get("type"),
        "changed_fields": changed_fields,
        "before": _summarize_item(before),
        "after": _summarize_item(after),
    }


def _index_by(items: Iterable[dict[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        key = key_fn(item)
        if key:
            indexed[str(key)] = item
    return indexed


def _node_key(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("node_id") or item.get("name") or "")


def _relationship_key(item: dict[str, Any]) -> str:
    return str(
        item.get("id")
        or ":".join(
            str(value)
            for value in (
                item.get("source"),
                item.get("type") or item.get("relationship_type"),
                item.get("target"),
            )
        )
    )


def _workflow_key(item: dict[str, Any]) -> str:
    return str(
        item.get("workflow_id")
        or item.get("id")
        or ":".join(str(item.get(field) or "") for field in ("framework", "workflow"))
    )


def _mcp_server_key(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("endpoint") or item.get("server") or "")


def _capability_key(item: dict[str, Any]) -> str:
    return str(
        item.get("id")
        or ":".join(str(item.get(field) or "") for field in ("server", "capability"))
    )


def _summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    summary = dict(item)
    if "provenance" in item:
        summary["provenance"] = item["provenance"]
    return summary


def _display_id(item: dict[str, Any]) -> str | None:
    for key in (
        "id",
        "node_id",
        "workflow_id",
        "server",
        "capability",
        "snapshot_id",
    ):
        if item.get(key):
            return str(item[key])
    return None


def _display_name(item: dict[str, Any]) -> str | None:
    for key in ("name", "workflow", "server", "capability"):
        if item.get(key):
            return str(item[key])
    if item.get("source") and item.get("target") and item.get("type"):
        return f"{item['source']} {item['type']} {item['target']}"
    return _display_id(item)


def _numeric_delta(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, dict[str, int]]:
    deltas: dict[str, dict[str, int]] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key, 0)
        after_value = after.get(key, 0)
        if isinstance(before_value, int) and isinstance(after_value, int):
            deltas[key] = {
                "before": before_value,
                "after": after_value,
                "delta": after_value - before_value,
            }
    return deltas


def _statistics_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, int) or isinstance(after_value, int):
            before_int = before_value if isinstance(before_value, int) else 0
            after_int = after_value if isinstance(after_value, int) else 0
            delta[key] = {
                "before": before_int,
                "after": after_int,
                "delta": after_int - before_int,
            }
        elif isinstance(before_value, dict) or isinstance(after_value, dict):
            delta[key] = _map_delta(
                before_value if isinstance(before_value, dict) else {},
                after_value if isinstance(after_value, dict) else {},
            )
        elif before_value != after_value:
            delta[key] = {"before": before_value, "after": after_value}
    return delta


def _map_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key, 0)
        after_value = after.get(key, 0)
        if isinstance(before_value, int) and isinstance(after_value, int):
            result[key] = {
                "before": before_value,
                "after": after_value,
                "delta": after_value - before_value,
            }
        elif before_value != after_value:
            result[key] = {"before": before_value, "after": after_value}
    return result


def _diff_summary(
    *,
    nodes: dict[str, list[dict[str, Any]]],
    relationships: dict[str, list[dict[str, Any]]],
    workflows: dict[str, list[dict[str, Any]]],
    mcp_servers: dict[str, list[dict[str, Any]]],
    capabilities: dict[str, list[dict[str, Any]]],
    count_deltas: dict[str, dict[str, int]],
    graph_statistics_delta: dict[str, Any],
) -> dict[str, Any]:
    return {
        "nodes_added": len(nodes["added"]),
        "nodes_removed": len(nodes["removed"]),
        "nodes_changed": len(nodes["changed"]),
        "relationships_added": len(relationships["added"]),
        "relationships_removed": len(relationships["removed"]),
        "relationships_changed": len(relationships["changed"]),
        "workflows_added": len(workflows["added"]),
        "workflows_removed": len(workflows["removed"]),
        "mcp_servers_added": len(mcp_servers["added"]),
        "mcp_servers_removed": len(mcp_servers["removed"]),
        "capabilities_added": len(capabilities["added"]),
        "capabilities_removed": len(capabilities["removed"]),
        "trace_count_delta": count_deltas.get("traces", {}).get("delta", 0),
        "session_count_delta": count_deltas.get("sessions", {}).get("delta", 0),
        "graph_node_delta": graph_statistics_delta.get("node_count", {}).get(
            "delta", 0
        ),
        "graph_edge_delta": graph_statistics_delta.get("edge_count", {}).get(
            "delta", 0
        ),
    }


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return sorted((_canonical(item) for item in value), key=repr)
    return value
