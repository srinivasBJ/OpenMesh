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


async def create_openmesh_event(
    db: AsyncSession,
    event: Dict[str, Any],
) -> OpenMeshEventRecord:
    record = OpenMeshEventRecord(
        event_id=event["event_id"],
        event_type=event["event_type"],
        timestamp=parse_event_timestamp(event["timestamp"]),
        trace_id=event["trace_id"],
        session_id=event["session_id"],
        source_json=event["source"],
        target_json=event.get("target"),
        payload_json=event.get("payload", {}),
        metrics_json=event.get("metrics", {}),
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
) -> list[OpenMeshEventRecord]:
    query = select(OpenMeshEventRecord)
    if trace_id:
        query = query.where(OpenMeshEventRecord.trace_id == trace_id)
    if session_id:
        query = query.where(OpenMeshEventRecord.session_id == session_id)
    query = query.order_by(desc(OpenMeshEventRecord.timestamp)).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


def record_to_event(record: OpenMeshEventRecord) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "spec_version": "0.1",
        "event_id": record.event_id,
        "event_type": record.event_type,
        "timestamp": record.timestamp.isoformat() + "Z",
        "trace_id": record.trace_id,
        "session_id": record.session_id,
        "source": record.source_json,
        "payload": record.payload_json or {},
        "metrics": record.metrics_json or {},
        "links": [],
        "severity": record.severity,
    }
    if record.target_json:
        event["target"] = record.target_json
    return event


def records_to_events(records: Iterable[OpenMeshEventRecord]) -> list[Dict[str, Any]]:
    return [record_to_event(record) for record in records]
