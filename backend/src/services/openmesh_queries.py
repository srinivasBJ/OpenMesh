from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import (
    list_openmesh_events,
    record_to_event,
    records_to_events,
)
from ..db.openmesh_sessions import (
    get_openmesh_session,
    list_openmesh_sessions,
    session_to_dict,
)
from .graph_state import reduce_graph_state
from .trace_semantics import (
    build_event_hierarchy,
    build_span_summary,
    build_span_tree,
    graph_edges_for_trace,
    validate_trace_semantics,
)


def trace_status(events: list[dict]) -> str:
    if any(
        e.get("severity") == "error" or e.get("event_type", "").endswith(".failed")
        for e in events
    ):
        return "failed"
    if events and events[-1].get("event_type", "").endswith(".started"):
        return "active"
    return "completed"


def trace_summary(trace_id: str, records: list[OpenMeshEventRecord]) -> Dict[str, Any]:
    events = [
        record_to_event(record) for record in sorted(records, key=lambda r: r.timestamp)
    ]
    agents = set()
    tools = set()
    for event in events:
        for node in (event.get("source"), event.get("target")):
            if not node:
                continue
            if node.get("node_type") == "agent":
                agents.add(node.get("name"))
            if node.get("node_type") == "tool":
                tools.add(node.get("name"))

    return {
        "trace_id": trace_id,
        "started_at": events[0]["timestamp"] if events else None,
        "ended_at": events[-1]["timestamp"] if events else None,
        "event_count": len(events),
        "agents": sorted(agents),
        "tools": sorted(tools),
        "status": trace_status(events),
    }


async def get_events(db: AsyncSession, limit: int = 100) -> list[dict]:
    records = await list_openmesh_events(db, limit=limit)
    return records_to_events(records)


async def get_traces(db: AsyncSession, limit: int = 1000) -> list[dict]:
    records = await list_openmesh_events(db, limit=max(limit * 100, 1000))
    grouped: Dict[str, list[OpenMeshEventRecord]] = {}
    for record in records:
        grouped.setdefault(record.trace_id, []).append(record)
    summaries = [
        trace_summary(trace_id, trace_records)
        for trace_id, trace_records in grouped.items()
    ]
    return sorted(summaries, key=lambda t: t["started_at"] or "", reverse=True)[:limit]


async def get_trace(db: AsyncSession, trace_id: str) -> dict | None:
    records = await list_openmesh_events(db, trace_id=trace_id, limit=1000)
    if not records:
        return None
    ordered = sorted(records, key=lambda r: r.timestamp)
    events = records_to_events(ordered)
    return {
        **trace_summary(trace_id, ordered),
        "events": events,
        "hierarchy": build_event_hierarchy(events),
        "spans": build_span_summary(events),
        "span_tree": build_span_tree(events),
        "relationships": graph_edges_for_trace(events),
        "validation": validate_trace_semantics(events),
    }


async def get_graph(db: AsyncSession, limit: int = 1000) -> dict:
    records = await list_openmesh_events(db, limit=limit)
    return reduce_graph_state(records)


async def inspect_node(
    db: AsyncSession, node_id: str, limit: int = 1000
) -> dict | None:
    graph = await get_graph(db, limit=limit)
    return inspect_graph_node(graph, node_id)


def inspect_graph_node(graph: dict[str, Any], node_ref: str) -> dict | None:
    node = _find_graph_node(graph.get("nodes", []), node_ref)
    if not node:
        return None

    node_id = node["id"]
    incoming = [edge for edge in graph.get("edges", []) if edge["target"] == node_id]
    outgoing = [edge for edge in graph.get("edges", []) if edge["source"] == node_id]
    relationships = incoming + outgoing
    trace_ids = _dedupe(
        [
            *(node.get("provenance", {}).get("trace_ids") or node.get("trace_ids", [])),
            *[
                trace_id
                for edge in relationships
                for trace_id in (
                    edge.get("provenance", {}).get("trace_ids")
                    or edge.get("trace_ids", [])
                )
            ],
        ]
    )
    session_ids = _dedupe(
        [
            *(
                node.get("provenance", {}).get("session_ids")
                or node.get("session_ids", [])
            ),
            *[
                session_id
                for edge in relationships
                for session_id in (
                    edge.get("provenance", {}).get("session_ids")
                    or edge.get("session_ids", [])
                )
            ],
        ]
    )
    event_ids = _dedupe(
        [
            *(node.get("provenance", {}).get("event_ids") or node.get("event_ids", [])),
            *[
                event_id
                for edge in relationships
                for event_id in (
                    edge.get("provenance", {}).get("event_ids")
                    or edge.get("event_ids", [])
                )
            ],
        ]
    )
    return {
        "node": node,
        "node_id": node["id"],
        "name": node["name"],
        "node_type": node["type"],
        "first_seen": node.get("first_seen"),
        "last_seen": node.get("last_seen"),
        "event_count": node.get("event_count", 0),
        "relationship_count": len(relationships),
        "incoming_relationships": incoming,
        "outgoing_relationships": outgoing,
        "trace_ids": trace_ids,
        "session_ids": session_ids,
        "provenance": {
            "event_ids": event_ids,
            "trace_ids": trace_ids,
            "session_ids": session_ids,
            "first_seen": node.get("provenance", {}).get("first_seen")
            or node.get("first_seen"),
            "last_seen": node.get("provenance", {}).get("last_seen")
            or node.get("last_seen"),
            "first_event_id": node.get("provenance", {}).get("first_event_id"),
            "last_event_id": node.get("provenance", {}).get("last_event_id"),
            "observations": node.get("provenance", {}).get("observations", []),
            "relationship_event_count": sum(
                edge.get("event_count", 0) for edge in relationships
            ),
        },
        "validation": {
            "status": node.get("validation_status", "unknown"),
            "errors": node.get("validation_errors", []),
            "warnings": node.get("validation_warnings", []),
        },
    }


async def get_sessions(db: AsyncSession, limit: int = 100) -> list[dict]:
    records = await list_openmesh_sessions(db, limit=limit)
    return [session_to_dict(record) for record in records]


async def get_session(db: AsyncSession, session_id: str) -> dict | None:
    record = await get_openmesh_session(db, session_id)
    if not record:
        return None
    events = await list_openmesh_events(db, session_id=session_id, limit=1000)
    session_events = [record_to_event(event) for event in events]
    return {
        **session_to_dict(record),
        "events": sorted(session_events, key=lambda event: event["timestamp"]),
    }


async def get_health(db: AsyncSession) -> dict:
    await db.execute(text("SELECT 1"))
    event_count = (
        await db.execute(select(func.count(OpenMeshEventRecord.id)))
    ).scalar() or 0
    trace_count = (
        await db.execute(
            select(func.count(func.distinct(OpenMeshEventRecord.trace_id)))
        )
    ).scalar() or 0
    graph = await get_graph(db)
    return {
        "collector": "OK",
        "database": "OK",
        "events": event_count,
        "traces": trace_count,
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
    }


def _find_graph_node(nodes: list[dict[str, Any]], node_ref: str) -> dict | None:
    normalized_ref = _normalize_node_ref(node_ref)
    candidates = []
    for node in nodes:
        node_id = node.get("id", "")
        name = node.get("name", "")
        aliases = {
            node_id,
            name,
            node_id.split(":", 1)[-1],
            name.replace(" ", "-"),
            name.replace(" ", "_"),
        }
        if node_ref in aliases or normalized_ref in {
            _normalize_node_ref(alias) for alias in aliases
        }:
            candidates.append(node)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.get("type", ""), item["id"]))[0]


def _normalize_node_ref(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("_", "-")


def _dedupe(values: list[Any]) -> list[Any]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
