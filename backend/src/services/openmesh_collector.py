from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.openmesh_events import create_openmesh_event
from ..shared.openmesh_events import is_openmesh_event
from ..websocket.manager import manager
from .node_types import validate_node


LINK_IDENTITY_FIELDS = {"url", "trace_id", "span_id", "event_id"}


class OpenMeshCollector:
    def validate_event(self, event: Dict[str, Any]) -> None:
        if not isinstance(event, dict):
            raise HTTPException(
                status_code=422, detail="OpenMesh event must be a JSON object"
            )
        if not is_openmesh_event(event):
            raise HTTPException(
                status_code=422,
                detail="Invalid OpenMesh event envelope: expected spec_version='0.1', event_type, and source",
            )
        missing = [
            field
            for field in (
                "event_id",
                "event_type",
                "timestamp",
                "trace_id",
                "session_id",
                "payload",
            )
            if not event.get(field)
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Missing OpenMesh event fields: {', '.join(missing)}",
            )
        if not isinstance(event.get("payload"), dict):
            raise HTTPException(
                status_code=422, detail="Invalid OpenMesh payload: expected object"
            )
        if event.get("severity") and event["severity"] not in {
            "debug",
            "info",
            "warning",
            "error",
        }:
            raise HTTPException(status_code=422, detail="Invalid OpenMesh severity")
        links = event.get("links", [])
        if links is None:
            links = []
        if not isinstance(links, list):
            raise HTTPException(
                status_code=422, detail="Invalid OpenMesh links: expected list"
            )
        for index, link in enumerate(links):
            if not isinstance(link, dict):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid OpenMesh link at index {index}: expected object",
                )
            if not any(link.get(field) for field in LINK_IDENTITY_FIELDS):
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid OpenMesh link at index {index}: expected url, trace_id, span_id, or event_id",
                )

        for node_key in ("source", "target"):
            node = event.get(node_key)
            if node is None and node_key == "target":
                continue
            validation = validate_node(node)
            if not validation["valid"]:
                messages = "; ".join(error["message"] for error in validation["errors"])
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid OpenMesh {node_key} node: {messages}",
                )

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
        except SQLAlchemyError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=503,
                detail=f"Could not persist OpenMesh event: {exc.__class__.__name__}",
            ) from exc
        if broadcast:
            await manager.broadcast(event)
        return event


collector = OpenMeshCollector()
