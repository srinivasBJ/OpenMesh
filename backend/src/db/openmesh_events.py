from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import OpenMeshEventRecord


def parse_event_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=None)


async def resolve_event_provenance(
    db: AsyncSession, event: Dict[str, Any]
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(workspace_id, project_id, agent_source) for an event: explicit
    payload tags win, else resolved from the source agent. Keeps demo events
    scoped to the demo workspace and marks every event with its origin
    (simulation vs a real integration)."""
    payload = event.get("payload") or {}
    workspace_id = payload.get("workspace_id") or payload.get("workspace")
    project_id = payload.get("project_id")
    agent_source = payload.get("agent_source") or payload.get("source_kind")
    if workspace_id and agent_source:
        return str(workspace_id), project_id and str(project_id), str(agent_source)
    source = event.get("source") or {}
    if source.get("node_type") == "agent" and source.get("node_id"):
        from .models import Agent

        try:
            result = await db.execute(
                select(Agent.workspace_id, Agent.project_id, Agent.source).where(
                    Agent.id == source["node_id"]
                )
            )
            row = result.first()
            if row:
                return (
                    str(workspace_id) if workspace_id else row[0],
                    str(project_id) if project_id else row[1],
                    str(agent_source) if agent_source else row[2],
                )
        except Exception:
            # Tagging is best-effort: exporters and tests may pass session
            # shims that cannot run queries.
            pass
    return (
        str(workspace_id) if workspace_id else None,
        str(project_id) if project_id else None,
        str(agent_source) if agent_source else None,
    )


async def create_openmesh_event(
    db: AsyncSession,
    event: Dict[str, Any],
) -> OpenMeshEventRecord:
    workspace_id, project_id, agent_source = await resolve_event_provenance(db, event)
    record = OpenMeshEventRecord(
        event_id=event["event_id"],
        workspace_id=workspace_id,
        project_id=project_id,
        agent_source=agent_source,
        event_type=event["event_type"],
        timestamp=parse_event_timestamp(event["timestamp"]),
        trace_id=event["trace_id"],
        session_id=event["session_id"],
        span_id=event.get("span_id"),
        parent_span_id=event.get("parent_span_id"),
        parent_event_id=event.get("parent_event_id"),
        root_event_id=event.get("root_event_id"),
        source_json=event["source"],
        target_json=event.get("target"),
        payload_json=event.get("payload", {}),
        metrics_json=event.get("metrics", {}),
        links_json=event.get("links", []),
        severity=event.get("severity", "info"),
    )
    db.add(record)
    await db.flush()
    return record


async def list_openmesh_events(
    db: AsyncSession,
    *,
    limit: int = 100,
    trace_id: Optional[str] = None,
    session_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> list[OpenMeshEventRecord]:
    query = select(OpenMeshEventRecord)
    if trace_id:
        query = query.where(OpenMeshEventRecord.trace_id == trace_id)
    if session_id:
        query = query.where(OpenMeshEventRecord.session_id == session_id)
    if workspace_id:
        query = query.where(OpenMeshEventRecord.workspace_id == workspace_id)
    query = query.order_by(desc(OpenMeshEventRecord.timestamp)).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


def record_to_event(record: OpenMeshEventRecord) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "spec_version": "0.1",
        "workspace_id": getattr(record, "workspace_id", None),
        "project_id": getattr(record, "project_id", None),
        "agent_source": getattr(record, "agent_source", None),
        "event_id": record.event_id,
        "event_type": record.event_type,
        "timestamp": record.timestamp.isoformat() + "Z",
        "trace_id": record.trace_id,
        "session_id": record.session_id,
        "span_id": getattr(record, "span_id", None),
        "parent_span_id": getattr(record, "parent_span_id", None),
        "parent_event_id": getattr(record, "parent_event_id", None),
        "root_event_id": getattr(record, "root_event_id", None) or record.event_id,
        "source": record.source_json,
        "payload": record.payload_json or {},
        "metrics": record.metrics_json or {},
        "links": getattr(record, "links_json", None) or [],
        "severity": record.severity,
    }
    if record.target_json:
        event["target"] = record.target_json
    return event


def records_to_events(records: Iterable[OpenMeshEventRecord]) -> list[Dict[str, Any]]:
    return [record_to_event(record) for record in records]
