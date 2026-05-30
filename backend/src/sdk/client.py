from __future__ import annotations

import asyncio
from contextvars import ContextVar
from pathlib import Path
import sys
from types import TracebackType
from typing import Any, Optional
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.db.session import AsyncSessionLocal
from src.services.openmesh_collector import collector
from src.shared.openmesh_events import OpenMeshEvent, OpenMeshNode, make_openmesh_event


_current_trace_id: ContextVar[Optional[str]] = ContextVar("openmesh_trace_id", default=None)


def _agent_node(agent_id: str, name: str, role: Optional[str], metadata: Optional[dict[str, Any]]) -> OpenMeshNode:
    node_metadata = dict(metadata or {})
    if role:
        node_metadata["role"] = role
    return {
        "node_id": agent_id,
        "node_type": "agent",
        "name": name,
        "runtime": "openmesh.sdk.python",
        "metadata": node_metadata,
    }


def _tool_node(name: str) -> OpenMeshNode:
    return {
        "node_id": f"tool:{name}",
        "node_type": "tool",
        "name": name,
        "runtime": "openmesh.sdk.python",
    }


class OpenMeshClient:
    def __init__(
        self,
        *,
        workspace_id: str = "local",
        session_id: Optional[str] = None,
        broadcast: bool = True,
    ) -> None:
        self.workspace_id = workspace_id
        self.session_id = session_id or f"sess_{uuid4().hex}"
        self.broadcast = broadcast

    def agent(
        self,
        *,
        id: str,
        name: str,
        role: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "AgentHandle":
        agent = AgentHandle(self, _agent_node(id, name, role, metadata))
        agent.emit(
            "agent.registered",
            {
                "agent_id": id,
                "name": name,
                "role": role,
                "metadata": metadata or {},
            },
        )
        return agent

    def emit(
        self,
        event_type: str,
        source: OpenMeshNode,
        payload: Optional[dict[str, Any]] = None,
        *,
        target: Optional[OpenMeshNode] = None,
        trace_id: Optional[str] = None,
        severity: str = "info",
    ) -> OpenMeshEvent:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.emit_async(
                    event_type,
                    source,
                    payload,
                    target=target,
                    trace_id=trace_id,
                    severity=severity,
                )
            )
        raise RuntimeError("OpenMeshClient.emit() cannot run inside an active event loop; use emit_async().")

    async def emit_async(
        self,
        event_type: str,
        source: OpenMeshNode,
        payload: Optional[dict[str, Any]] = None,
        *,
        target: Optional[OpenMeshNode] = None,
        trace_id: Optional[str] = None,
        severity: str = "info",
    ) -> OpenMeshEvent:
        event = make_openmesh_event(
            event_type,
            source,
            payload,
            target=target,
            severity=severity,  # type: ignore[arg-type]
            workspace_id=self.workspace_id,
            session_id=self.session_id,
            trace_id=trace_id or _current_trace_id.get(),
        )
        async with AsyncSessionLocal() as db:
            await collector.accept(db, event, broadcast=self.broadcast)
        return event


class AgentHandle:
    def __init__(self, client: OpenMeshClient, node: OpenMeshNode) -> None:
        self.client = client
        self.node = node

    @property
    def id(self) -> str:
        return self.node["node_id"]

    @property
    def name(self) -> str:
        return self.node["name"]

    def emit(
        self,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
        *,
        target: Optional[OpenMeshNode] = None,
        trace_id: Optional[str] = None,
        severity: str = "info",
    ) -> OpenMeshEvent:
        return self.client.emit(
            event_type,
            self.node,
            payload or {},
            target=target,
            trace_id=trace_id,
            severity=severity,
        )

    async def emit_async(
        self,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
        *,
        target: Optional[OpenMeshNode] = None,
        trace_id: Optional[str] = None,
        severity: str = "info",
    ) -> OpenMeshEvent:
        return await self.client.emit_async(
            event_type,
            self.node,
            payload or {},
            target=target,
            trace_id=trace_id,
            severity=severity,
        )

    def task(self, name: str, *, trace_id: Optional[str] = None) -> "TaskContext":
        return TaskContext(self, name, trace_id=trace_id)

    def tool(self, name: str) -> "ToolContext":
        return ToolContext(self, name)


class TaskContext:
    def __init__(self, agent: AgentHandle, name: str, *, trace_id: Optional[str] = None) -> None:
        self.agent = agent
        self.name = name
        self.trace_id = trace_id or _current_trace_id.get() or f"trace_{uuid4().hex}"
        self._token = None

    def __enter__(self) -> "TaskContext":
        self._token = _current_trace_id.set(self.trace_id)
        self.agent.emit(
            "task.started",
            {"task": self.name},
            trace_id=self.trace_id,
        )
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        event_type = "task.failed" if exc else "task.completed"
        severity = "error" if exc else "info"
        payload: dict[str, Any] = {"task": self.name}
        if exc:
            payload["error"] = str(exc)
            payload["error_type"] = exc.__class__.__name__
        self.agent.emit(event_type, payload, trace_id=self.trace_id, severity=severity)
        if self._token is not None:
            _current_trace_id.reset(self._token)
        return False


class ToolContext:
    def __init__(self, agent: AgentHandle, name: str) -> None:
        self.agent = agent
        self.name = name
        self.node = _tool_node(name)
        self.trace_id = _current_trace_id.get() or f"trace_{uuid4().hex}"

    def __enter__(self) -> "ToolContext":
        self.agent.emit(
            "tool.call.started",
            {"tool": self.name},
            target=self.node,
            trace_id=self.trace_id,
        )
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        event_type = "tool.call.failed" if exc else "tool.call.completed"
        severity = "error" if exc else "info"
        payload: dict[str, Any] = {"tool": self.name}
        if exc:
            payload["error"] = str(exc)
            payload["error_type"] = exc.__class__.__name__
        self.agent.emit(event_type, payload, target=self.node, trace_id=self.trace_id, severity=severity)
        return False
