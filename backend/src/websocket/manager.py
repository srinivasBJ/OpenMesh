"""
WebSocket connection manager.
Broadcasts agent activity to all connected human observers in real time.
"""

from collections import deque
from time import monotonic

from fastapi import WebSocket
from typing import Deque, List
import json

from ..shared.openmesh_events import is_openmesh_event, make_openmesh_event


SYSTEM_NODE = {
    "node_id": "openmeshai.backend",
    "node_type": "service",
    "name": "OpenMeshAI Backend",
    "runtime": "fastapi",
}


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        # Timestamps of recently broadcast events, for the live events/sec stat.
        self._recent_broadcasts: Deque[float] = deque(maxlen=2000)

    def record_broadcast(self) -> None:
        self._recent_broadcasts.append(monotonic())

    def events_per_second(self, window_seconds: float = 30.0) -> float:
        cutoff = monotonic() - window_seconds
        recent = sum(1 for ts in self._recent_broadcasts if ts >= cutoff)
        return round(recent / window_seconds, 2)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        """Send event to all connected observers."""
        event = (
            data
            if is_openmesh_event(data)
            else make_openmesh_event(
                "system.event",
                SYSTEM_NODE,
                {"legacy": data},
            )
        )
        message = json.dumps(event)
        self.record_broadcast()
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)

    async def send_personal(self, websocket: WebSocket, data: dict):
        event = (
            data
            if is_openmesh_event(data)
            else make_openmesh_event(
                "system.event",
                SYSTEM_NODE,
                {"legacy": data},
            )
        )
        await websocket.send_text(json.dumps(event))


manager = ConnectionManager()
