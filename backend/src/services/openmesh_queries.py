from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events, record_to_event, records_to_events
from ..db.openmesh_sessions import get_openmesh_session, list_openmesh_sessions, session_to_dict
from .graph_state import reduce_graph_state
from .trace_semantics import build_event_hierarchy, build_span_summary, build_span_tree, graph_edges_for_trace, validate_trace_semantics


def trace_status(events: list[dict]) -> str:
    if any(e.get("severity") == "error" or e.get("event_type", "").endswith(".failed") for e in events):
        return "failed"
    if events and events[-1].get("event_type", "").endswith(".started"):
        return "active"
    return "completed"


def trace_summary(trace_id: str, records: list[OpenMeshEventRecord]) -> Dict[str, Any]:
    events = [record_to_event(record) for record in sorted(records, key=lambda r: r.timestamp)]
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
    summaries = [trace_summary(trace_id, trace_records) for trace_id, trace_records in grouped.items()]
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
    event_count = (await db.execute(select(func.count(OpenMeshEventRecord.id)))).scalar() or 0
    trace_count = (await db.execute(select(func.count(func.distinct(OpenMeshEventRecord.trace_id))))).scalar() or 0
    graph = await get_graph(db)
    return {
        "collector": "OK",
        "database": "OK",
        "events": event_count,
        "traces": trace_count,
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
    }
