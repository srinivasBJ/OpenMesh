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

OPENMESH_PLUGIN = {
    "plugin_id": "langgraph",
    "name": "LangGraph",
    "version": "0.1.0",
    "plugin_api_version": "1.0",
    "kind": "integration",
    "status": "reference",
    "package": "langgraph",
    "entrypoint": "OpenMeshLangGraph",
    "description": "Observe LangGraph workflow, node lifecycle, and transition events.",
    "capabilities": [
        "workflow.lifecycle",
        "node.lifecycle",
        "node.transition",
        "trace.spans",
        "graph.relationships",
    ],
    "metadata": {"framework": "LangGraph"},
}


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
        self._workflow_span_id = f"span_{uuid4().hex}"
        self._workflow_event_id: Optional[str] = None
        self._root_event_id: Optional[str] = None
        self._last_node_context: ContextVar[Optional[dict[str, str]]] = ContextVar(
            f"openmesh_langgraph_last_node_context_{uuid4().hex}",
            default=None,
        )
        mark_integration_active("langgraph")

    def node(self, name: str, fn: T) -> T:
        """Wrap a LangGraph node callable with OpenMesh lifecycle events."""
        self._validate_node_name(name)
        node = self._node(name)

        if inspect.iscoroutinefunction(fn):
            return cast(
                T, self._wrap_async(name, node, cast(Callable[..., Awaitable[Any]], fn))
            )
        return cast(T, self._wrap_sync(name, node, fn))

    def transition(self, source: str, target: str) -> None:
        """Emit an explicit graph transition for custom runners or tests."""
        self._validate_node_name(source)
        self._validate_node_name(target)
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "node.transition",
            self._node(source),
            self._transition_payload(source, target),
            target=self._node(target),
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        self._remember_root(event)

    def add_edge(self, workflow: Any, source: str, target: str) -> None:
        """Add a LangGraph edge and emit an OpenMesh transition for runtime graph views."""
        workflow.add_edge(source, target)
        if self._is_observable_edge(source, target):
            self.transition(source, target)

    async def transition_async(self, source: str, target: str) -> None:
        self._validate_node_name(source)
        self._validate_node_name(target)
        workflow_event = await self._ensure_workflow_started_async()
        event = await self.client.emit_async(
            "node.transition",
            self._node(source),
            self._transition_payload(source, target),
            target=self._node(target),
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        self._remember_root(event)

    def reset(self) -> None:
        """Clear execution-order transition memory for a new workflow run."""
        self._workflow_span_id = f"span_{uuid4().hex}"
        self._workflow_event_id = None
        self._root_event_id = None
        self._last_node_context.set(None)

    def complete(self, output: Any = None) -> dict[str, Any]:
        """Mark the current LangGraph workflow span as completed."""
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.completed",
            self._workflow_node(),
            {
                "graph": self.graph_name,
                "source": "langgraph",
                "runtime": {"framework": "langgraph", "graph": self.graph_name},
                "output": _safe_payload(output) if output is not None else {},
            },
            trace_id=self.trace_id,
            parent_event_id=workflow_event["event_id"],
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
        )
        self._remember_root(event)
        return event

    async def complete_async(self, output: Any = None) -> dict[str, Any]:
        """Mark the current LangGraph workflow span as completed from async runners."""
        workflow_event = await self._ensure_workflow_started_async()
        event = await self.client.emit_async(
            "workflow.completed",
            self._workflow_node(),
            {
                "graph": self.graph_name,
                "source": "langgraph",
                "runtime": {"framework": "langgraph", "graph": self.graph_name},
                "output": _safe_payload(output) if output is not None else {},
            },
            trace_id=self.trace_id,
            parent_event_id=workflow_event["event_id"],
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
        )
        self._remember_root(event)
        return event

    def fail(self, exc: BaseException) -> dict[str, Any]:
        """Mark the current LangGraph workflow span as failed."""
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.failed",
            self._workflow_node(),
            {
                "graph": self.graph_name,
                "source": "langgraph",
                "runtime": {"framework": "langgraph", "graph": self.graph_name},
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
            trace_id=self.trace_id,
            parent_event_id=workflow_event["event_id"],
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            severity="error",
        )
        self._remember_root(event)
        return event

    async def fail_async(self, exc: BaseException) -> dict[str, Any]:
        """Mark the current LangGraph workflow span as failed from async runners."""
        workflow_event = await self._ensure_workflow_started_async()
        event = await self.client.emit_async(
            "workflow.failed",
            self._workflow_node(),
            {
                "graph": self.graph_name,
                "source": "langgraph",
                "runtime": {"framework": "langgraph", "graph": self.graph_name},
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
            trace_id=self.trace_id,
            parent_event_id=workflow_event["event_id"],
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            severity="error",
        )
        self._remember_root(event)
        return event

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

    def _workflow_node(self) -> OpenMeshNode:
        return {
            "node_id": f"workflow:{self.graph_name}",
            "node_type": "workflow",
            "name": self.graph_name,
            "runtime": "langgraph",
            "metadata": {
                "framework": "langgraph",
                "graph": self.graph_name,
                "source": "langgraph",
            },
        }

    def _runtime_node(self) -> OpenMeshNode:
        return {
            "node_id": "framework:langgraph",
            "node_type": "service",
            "name": "LangGraph",
            "runtime": "langgraph",
            "metadata": {"framework": "langgraph", "source": "langgraph"},
        }

    def _remember_root(self, event: dict[str, Any]) -> None:
        if self._root_event_id is None:
            self._root_event_id = event.get("root_event_id") or event["event_id"]

    def _ensure_workflow_started(self) -> dict[str, Any]:
        if self._workflow_event_id:
            return {
                "event_id": self._workflow_event_id,
                "root_event_id": self._root_event_id,
            }
        event = self.client.emit(
            "workflow.started",
            self._runtime_node(),
            {
                "graph": self.graph_name,
                "source": "langgraph",
                "runtime": {"framework": "langgraph", "graph": self.graph_name},
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            span_id=self._workflow_span_id,
        )
        self._workflow_event_id = event["event_id"]
        self._remember_root(event)
        return event

    async def _ensure_workflow_started_async(self) -> dict[str, Any]:
        if self._workflow_event_id:
            return {
                "event_id": self._workflow_event_id,
                "root_event_id": self._root_event_id,
            }
        event = await self.client.emit_async(
            "workflow.started",
            self._runtime_node(),
            {
                "graph": self.graph_name,
                "source": "langgraph",
                "runtime": {"framework": "langgraph", "graph": self.graph_name},
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            span_id=self._workflow_span_id,
        )
        self._workflow_event_id = event["event_id"]
        self._remember_root(event)
        return event

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

    def _transition_from_previous(self, current_name: str) -> dict[str, Any] | None:
        previous = self._last_node_context.get()
        current = self._node(current_name)
        if previous and previous["node_id"] != current["node_id"]:
            previous_node = self._node_by_id(previous["node_id"])
            event = self.client.emit(
                "node.transition",
                previous_node,
                self._transition_payload(previous_node["name"], current_name),
                target=current,
                trace_id=self.trace_id,
                root_event_id=self._root_event_id,
                span_id=self._workflow_span_id,
                parent_event_id=previous.get("event_id") or self._workflow_event_id,
                links=[self._node_span_link(previous, "follows_from")],
            )
            self._remember_root(event)
            return event
        return None

    async def _transition_from_previous_async(
        self, current_name: str
    ) -> dict[str, Any] | None:
        previous = self._last_node_context.get()
        current = self._node(current_name)
        if previous and previous["node_id"] != current["node_id"]:
            previous_node = self._node_by_id(previous["node_id"])
            event = await self.client.emit_async(
                "node.transition",
                previous_node,
                self._transition_payload(previous_node["name"], current_name),
                target=current,
                trace_id=self.trace_id,
                root_event_id=self._root_event_id,
                span_id=self._workflow_span_id,
                parent_event_id=previous.get("event_id") or self._workflow_event_id,
                links=[self._node_span_link(previous, "follows_from")],
            )
            self._remember_root(event)
            return event
        return None

    def _node_span_link(
        self, node_context: dict[str, str], relationship: str
    ) -> dict[str, str]:
        return {
            "trace_id": self.trace_id,
            "span_id": node_context["span_id"],
            "event_id": node_context["event_id"],
            "relationship": relationship,
        }

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

    def _wrap_sync(
        self, name: str, node: OpenMeshNode, fn: Callable[..., Any]
    ) -> Callable[..., Any]:
        @wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            workflow_event = self._ensure_workflow_started()
            transition_event = self._transition_from_previous(name)
            span_id = f"span_{uuid4().hex}"
            started = self.client.emit(
                "node.started",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "input": _safe_payload(args[0] if args else kwargs),
                },
                trace_id=self.trace_id,
                root_event_id=self._root_event_id,
                span_id=span_id,
                parent_span_id=self._workflow_span_id,
                parent_event_id=(transition_event or workflow_event)["event_id"],
            )
            self._remember_root(started)
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
                    parent_event_id=started["event_id"],
                    root_event_id=self._root_event_id,
                    span_id=span_id,
                    parent_span_id=self._workflow_span_id,
                    severity="error",
                )
                raise
            completed = self.client.emit(
                "node.completed",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "output": _safe_payload(result),
                },
                trace_id=self.trace_id,
                parent_event_id=started["event_id"],
                root_event_id=self._root_event_id,
                span_id=span_id,
                parent_span_id=self._workflow_span_id,
            )
            self._last_node_context.set(
                {
                    "node_id": node["node_id"],
                    "span_id": span_id,
                    "event_id": completed["event_id"],
                }
            )
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
            workflow_event = await self._ensure_workflow_started_async()
            transition_event = await self._transition_from_previous_async(name)
            span_id = f"span_{uuid4().hex}"
            started = await self.client.emit_async(
                "node.started",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "input": _safe_payload(args[0] if args else kwargs),
                },
                trace_id=self.trace_id,
                root_event_id=self._root_event_id,
                span_id=span_id,
                parent_span_id=self._workflow_span_id,
                parent_event_id=(transition_event or workflow_event)["event_id"],
            )
            self._remember_root(started)
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
                    parent_event_id=started["event_id"],
                    root_event_id=self._root_event_id,
                    span_id=span_id,
                    parent_span_id=self._workflow_span_id,
                    severity="error",
                )
                raise
            completed = await self.client.emit_async(
                "node.completed",
                node,
                {
                    "graph": self.graph_name,
                    "node": name,
                    "runtime": self._runtime_payload(name),
                    "output": _safe_payload(result),
                },
                trace_id=self.trace_id,
                parent_event_id=started["event_id"],
                root_event_id=self._root_event_id,
                span_id=span_id,
                parent_span_id=self._workflow_span_id,
            )
            self._last_node_context.set(
                {
                    "node_id": node["node_id"],
                    "span_id": span_id,
                    "event_id": completed["event_id"],
                }
            )
            return result

        return wrapped
