from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional, TypedDict
from uuid import uuid4


OpenMeshNodeType = Literal[
    "agent",
    "tool",
    "model",
    "memory",
    "file",
    "database",
    "github_repository",
    "api_endpoint",
    "memory_store",
    "command",
    "browser",
    "user",
    "service",
    "runtime",
    "process",
    "workflow",
    "framework",
    "mcp_server",
    "capability",
    "guild",
    "wiki",
    "post",
    "openmesh_node",
]

OpenMeshSeverity = Literal["debug", "info", "warning", "error"]


class OpenMeshNode(TypedDict, total=False):
    node_id: str
    node_type: OpenMeshNodeType
    name: str
    runtime: str
    metadata: Dict[str, Any]


class OpenMeshEvent(TypedDict, total=False):
    spec_version: str
    event_id: str
    event_type: str
    timestamp: str
    workspace_id: str
    session_id: str
    trace_id: str
    span_id: str
    parent_span_id: str
    parent_event_id: str
    root_event_id: str
    source: OpenMeshNode
    target: OpenMeshNode
    payload: Dict[str, Any]
    metrics: Dict[str, Any]
    links: list[Dict[str, Any]]
    severity: OpenMeshSeverity


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def agent_node(agent_id: str, name: str, role: Optional[str] = None) -> OpenMeshNode:
    metadata: Dict[str, Any] = {}
    if role:
        metadata["role"] = role
    return {
        "node_id": agent_id,
        "node_type": "agent",
        "name": name,
        "runtime": "openmeshai.simulator",
        "metadata": metadata,
    }


def make_openmesh_event(
    event_type: str,
    source: OpenMeshNode,
    payload: Optional[Dict[str, Any]] = None,
    *,
    target: Optional[OpenMeshNode] = None,
    metrics: Optional[Dict[str, Any]] = None,
    severity: OpenMeshSeverity = "info",
    workspace_id: str = "local",
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    root_event_id: Optional[str] = None,
    links: Optional[list[Dict[str, Any]]] = None,
) -> OpenMeshEvent:
    event_id = f"evt_{uuid4().hex}"
    event: OpenMeshEvent = {
        "spec_version": "0.1",
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": _utc_now(),
        "workspace_id": workspace_id,
        "session_id": session_id or f"sess_{uuid4().hex}",
        "trace_id": trace_id or f"trace_{uuid4().hex}",
        "span_id": span_id or f"span_{uuid4().hex}",
        "source": source,
        "payload": payload or {},
        "metrics": metrics or {},
        "links": links or [],
        "severity": severity,
        "root_event_id": root_event_id or event_id,
    }
    if parent_span_id:
        event["parent_span_id"] = parent_span_id
    if parent_event_id:
        event["parent_event_id"] = parent_event_id
    if target:
        event["target"] = target
    return event


def is_openmesh_event(data: Dict[str, Any]) -> bool:
    return (
        data.get("spec_version") == "0.1" and "event_type" in data and "source" in data
    )
