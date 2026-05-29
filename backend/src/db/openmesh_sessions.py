from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import OpenMeshSessionRecord


async def create_openmesh_session(
    db: AsyncSession,
    *,
    session_id: str,
    command: str,
    started_at: datetime,
) -> OpenMeshSessionRecord:
    record = OpenMeshSessionRecord(
        session_id=session_id,
        command=command,
        started_at=started_at,
        status="running",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def complete_openmesh_session(
    db: AsyncSession,
    *,
    session_id: str,
    ended_at: datetime,
    status: str,
    exit_code: Optional[int],
) -> Optional[OpenMeshSessionRecord]:
    record = await get_openmesh_session(db, session_id)
    if not record:
        return None
    record.ended_at = ended_at
    record.status = status
    record.exit_code = exit_code
    await db.commit()
    await db.refresh(record)
    return record


async def get_openmesh_session(db: AsyncSession, session_id: str) -> Optional[OpenMeshSessionRecord]:
    result = await db.execute(
        select(OpenMeshSessionRecord).where(OpenMeshSessionRecord.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def list_openmesh_sessions(db: AsyncSession, *, limit: int = 100) -> list[OpenMeshSessionRecord]:
    result = await db.execute(
        select(OpenMeshSessionRecord).order_by(desc(OpenMeshSessionRecord.started_at)).limit(limit)
    )
    return list(result.scalars().all())


def session_to_dict(record: OpenMeshSessionRecord) -> dict:
    return {
        "session_id": record.session_id,
        "command": record.command,
        "started_at": record.started_at.isoformat() + "Z",
        "ended_at": record.ended_at.isoformat() + "Z" if record.ended_at else None,
        "status": record.status,
        "exit_code": record.exit_code,
    }
