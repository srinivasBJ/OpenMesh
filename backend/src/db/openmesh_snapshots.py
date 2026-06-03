from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import OpenMeshSnapshotRecord


async def create_openmesh_snapshot(
    db: AsyncSession, snapshot: dict[str, Any]
) -> OpenMeshSnapshotRecord:
    counts = snapshot.get("counts", {})
    graph_stats = snapshot.get("graph_statistics", {})
    ecosystem_stats = snapshot.get("ecosystem_statistics", {})
    record = OpenMeshSnapshotRecord(
        snapshot_id=snapshot["snapshot_id"],
        created_at=_parse_timestamp(snapshot["created_at"]),
        event_count=counts.get("events", 0),
        trace_count=counts.get("traces", 0),
        session_count=counts.get("sessions", 0),
        node_count=counts.get("nodes", 0),
        edge_count=counts.get("edges", 0),
        counts_json=counts,
        graph_stats_json=graph_stats,
        ecosystem_stats_json=ecosystem_stats,
        snapshot_json=snapshot,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_openmesh_snapshot(
    db: AsyncSession, snapshot_id: str
) -> Optional[OpenMeshSnapshotRecord]:
    result = await db.execute(
        select(OpenMeshSnapshotRecord).where(
            OpenMeshSnapshotRecord.snapshot_id == snapshot_id
        )
    )
    return result.scalar_one_or_none()


async def list_openmesh_snapshots(
    db: AsyncSession, *, limit: int = 100
) -> list[OpenMeshSnapshotRecord]:
    result = await db.execute(
        select(OpenMeshSnapshotRecord)
        .order_by(desc(OpenMeshSnapshotRecord.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


def snapshot_record_to_summary(record: OpenMeshSnapshotRecord) -> dict[str, Any]:
    return {
        "snapshot_id": record.snapshot_id,
        "created_at": record.created_at.isoformat() + "Z",
        "counts": record.counts_json or {},
        "graph_statistics": record.graph_stats_json or {},
        "ecosystem_statistics": record.ecosystem_stats_json or {},
    }


def snapshot_record_to_detail(record: OpenMeshSnapshotRecord) -> dict[str, Any]:
    return record.snapshot_json or {
        **snapshot_record_to_summary(record),
        "contents": {},
    }


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
