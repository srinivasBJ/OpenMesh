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
    "command",
    "browser",
    "user",
    "service",
    "runtime",
    "guild",
    "wiki",
    "post",
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
    source: OpenMeshNode
    target: OpenMeshNode
    payload: Dict[str, Any]
    metrics: Dict[str, Any]
    links: list[Dict[str, str]]
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
) -> OpenMeshEvent:
    event: OpenMeshEvent = {
        "spec_version": "0.1",
        "event_id": f"evt_{uuid4().hex}",
        "event_type": event_type,
        "timestamp": _utc_now(),
        "workspace_id": workspace_id,
        "source": source,
        "payload": payload or {},
        "metrics": metrics or {},
        "links": [],
        "severity": severity,
    }
    if target:
        event["target"] = target
    return event


def is_openmesh_event(data: Dict[str, Any]) -> bool:
    return data.get("spec_version") == "0.1" and "event_type" in data and "source" in data
