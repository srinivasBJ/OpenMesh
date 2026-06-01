from __future__ import annotations

import inspect
from contextvars import ContextVar
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, TypeVar, cast
from uuid import uuid4

from src.sdk.client import OpenMeshClient
from src.shared.openmesh_events import OpenMeshNode
from .registry import mark_integration_active


T = TypeVar("T", bound=Callable[..., Any])


def _safe_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"state_keys": sorted(str(key) for key in value.keys())}
    return {"state_type": value.__class__.__name__}


class OpenMeshLangGraph:
    """Lightweight LangGraph instrumentation backed by the OpenMesh Python SDK."""

    def __init__(
        self,
        *,
        client: Optional[OpenMeshClient] = None,
        graph_name: str = "LangGraph Workflow",
        trace_id: Optional[str] = None,
    ) -> None:
        if not graph_name.strip():
            raise ValueError("LangGraph integration requires a non-empty graph_name")
        self.client = client or OpenMeshClient()
        self.graph_name = graph_name
        self.trace_id = trace_id or f"trace_{uuid4().hex}"
        self._nodes: dict[str, OpenMeshNode] = {}
        self._last_node_id: ContextVar[Optional[str]] = ContextVar(
            f"openmesh_langgraph_last_node_id_{uuid4().hex}",
            default=None,
        )
        mark_integration_active("langgraph")

    def node(self, name: str, fn: T) -> T:
        """Wrap a LangGraph node callable with OpenMesh lifecycle events."""
        self._validate_node_name(name)
        node = self._node(name)

        if inspect.iscoroutinefunction(fn):
            return cast(T, self._wrap_async(name, node, cast(Callable[..., Awaitable[Any]], fn)))
        return cast(T, self._wrap_sync(name, node, fn))

    def transition(self, source: str, target: str) -> None:
        """Emit an explicit graph transition for custom runners or tests."""
        self._validate_node_name(source)
        self._validate_node_name(target)
        self.client.emit(
            "node.transition",
            self._node(source),
            self._transition_payload(source, target),
            target=self._node(target),
            trace_id=self.trace_id,
        )

    def add_edge(self, workflow: Any, source: str, target: str) -> None:
        """Add a LangGraph edge and emit an OpenMesh transition for runtime graph views."""
        workflow.add_edge(source, target)
        if self._is_observable_edge(source, target):
            self.transition(source, target)

    async def transition_async(self, source: str, target: str) -> None:
        self._validate_node_name(source)
        self._validate_node_name(target)
        await self.client.emit_async(
            "node.transition",
            self._node(source),
            self._transition_payload(source, target),
            target=self._node(target),
            trace_id=self.trace_id,
        )

    def reset(self) -> None:
        """Clear execution-order transition memory for a new workflow run."""
        self._last_node_id.set(None)

    def _node(self, name: str) -> OpenMeshNode:
        if name not in self._nodes:
            self._nodes[name] = {
                "node_id": f"langgraph:{self.graph_name}:{name}",
                "node_type": "service",
                "name": name,
                "runtime": "langgraph",
                "metadata": {"framework": "langgraph", "graph": self.graph_name},
            }
        return self._nodes[name]

    def _validate_node_name(self, name: str) -> None:
        if not name.strip():
            raise ValueError("LangGraph node name cannot be empty")

    def _is_observable_edge(self, source: str, target: str) -> bool:
        return not source.startswith("__") and not target.startswith("__")

    def _runtime_payload(self, node: str) -> dict[str, str]:
        return {"framework": "langgraph", "graph": self.graph_name, "node": node}

    def _transition_payload(self, source: str, target: str) -> dict[str, Any]:
        return {
            "graph": self.graph_name,
            "from": source,
            "to": target,
            "runtime": {"framework": "langgraph", "graph": self.graph_name},
        }

    def _transition_from_previous(self, current_name: str) -> None:
        previous_id = self._last_node_id.get()
        current = self._node(current_name)
        if previous_id and previous_id != current["node_id"]:
            previous = self._node_by_id(previous_id)
            self.client.emit(
                "node.transition",
                previous,
                self._transition_payload(previous["name"], current_name),
                target=current,
                trace_id=self.trace_id,
            )

    async def _transition_from_previous_async(self, current_name: str) -> None:
        previous_id = self._last_node_id.get()
        current = self._node(current_name)
        if previous_id and previous_id != current["node_id"]:
            previous = self._node_by_id(previous_id)
            await self.client.emit_async(
                "node.transition",
                previous,
                self._transition_payload(previous["name"], current_name),
                target=current,
                trace_id=self.trace_id,
            )

    def _node_by_id(self, node_id: str) -> OpenMeshNode:
        for node in self._nodes.values():
            if node["node_id"] == node_id:
                return node
        return {
            "node_id": node_id,
            "node_type": "service",
            "name": node_id.rsplit(":", 1)[-1],
            "runtime": "langgraph",
            "metadata": {"framework": "langgraph", "graph": self.graph_name},
        }

    def _wrap_sync(self, name: str, node: OpenMeshNode, fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            self._transition_from_previous(name)
            self.client.emit(
                "node.started",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "input": _safe_payload(args[0] if args else kwargs),
                },
                trace_id=self.trace_id,
            )
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                self.client.emit(
                    "node.failed",
                    node,
                    {
                        "graph": self.graph_name,
                        "node": name,
                        "runtime": self._runtime_payload(name),
                        "error": str(exc),
                        "error_type": exc.__class__.__name__,
                    },
                    trace_id=self.trace_id,
                    severity="error",
                )
                raise
            self.client.emit(
                "node.completed",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "output": _safe_payload(result),
                },
                trace_id=self.trace_id,
            )
            self._last_node_id.set(node["node_id"])
            return result

        return wrapped

    def _wrap_async(
        self,
        name: str,
        node: OpenMeshNode,
        fn: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        @wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            await self._transition_from_previous_async(name)
            await self.client.emit_async(
                "node.started",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "input": _safe_payload(args[0] if args else kwargs),
                },
                trace_id=self.trace_id,
            )
            try:
                result = await fn(*args, **kwargs)
            except Exception as exc:
                await self.client.emit_async(
                    "node.failed",
                    node,
                    {
                        "graph": self.graph_name,
                        "node": name,
                        "runtime": self._runtime_payload(name),
                        "error": str(exc),
                        "error_type": exc.__class__.__name__,
                    },
                    trace_id=self.trace_id,
                    severity="error",
                )
                raise
            await self.client.emit_async(
                "node.completed",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "output": _safe_payload(result),
                },
                trace_id=self.trace_id,
            )
            self._last_node_id.set(node["node_id"])
            return result

        return wrapped
