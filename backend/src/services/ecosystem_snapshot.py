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
