from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.openmesh_events import create_openmesh_event
from ..shared.openmesh_events import is_openmesh_event
from ..websocket.manager import manager


REQUIRED_NODE_FIELDS = {"node_id", "node_type", "name"}


class OpenMeshCollector:
    def validate_event(self, event: Dict[str, Any]) -> None:
        if not is_openmesh_event(event):
            raise HTTPException(status_code=422, detail="Invalid OpenMesh event envelope")
        missing = [
            field
            for field in ("event_id", "event_type", "timestamp", "trace_id", "session_id", "payload")
            if not event.get(field)
        ]
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing OpenMesh event fields: {', '.join(missing)}")

        for node_key in ("source", "target"):
            node = event.get(node_key)
            if node is None and node_key == "target":
                continue
            if not isinstance(node, dict) or not REQUIRED_NODE_FIELDS.issubset(node.keys()):
                raise HTTPException(status_code=422, detail=f"Invalid OpenMesh {node_key} node")

    async def accept(
        self,
        db: AsyncSession,
        event: Dict[str, Any],
        *,
        broadcast: bool = True,
    ) -> Dict[str, Any]:
        self.validate_event(event)
        try:
            await create_openmesh_event(db, event)
            await db.commit()
        except IntegrityError:
            await db.rollback()
        if broadcast:
            await manager.broadcast(event)
        return event


collector = OpenMeshCollector()
