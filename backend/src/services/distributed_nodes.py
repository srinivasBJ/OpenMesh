from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import socket
from typing import Any, Iterable
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..shared.openmesh_events import make_openmesh_event
from .graph_state import reduce_graph_state
from .openmesh_collector import collector


DISTRIBUTED_NODE_TYPES = ("laptop", "workstation", "server", "cloud")
NODE_CONFIG_ENV = "OPENMESH_NODE_CONFIG"


@dataclass(frozen=True)
class DistributedNodeIdentity:
    node_id: str
    node_name: str
    node_type: str
    config_path: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def default_node_config_path() -> Path:
    override = os.getenv(NODE_CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openmesh" / "node.json"


def load_or_create_node_identity(
    *,
    node_id: str | None = None,
    node_name: str | None = None,
    node_type: str | None = None,
    config_path: Path | None = None,
    create: bool = True,
) -> DistributedNodeIdentity:
    path = config_path or default_node_config_path()
    data = _read_node_config(path)

    resolved_id = (
        node_id
        or os.getenv("OPENMESH_NODE_ID")
        or data.get("node_id")
        or f"node_{uuid4().hex[:12]}"
    )
    resolved_name = (
        node_name
        or os.getenv("OPENMESH_NODE_NAME")
        or data.get("node_name")
        or _default_node_name()
    )
    resolved_type = _normalize_node_type(
        node_type or os.getenv("OPENMESH_NODE_TYPE") or data.get("node_type")
    )

    identity = DistributedNodeIdentity(
        node_id=str(resolved_id),
        node_name=str(resolved_name),
        node_type=resolved_type,
        config_path=str(path),
    )
    if create:
        _write_node_config(path, identity)
    return identity


async def register_distributed_node(
    db: AsyncSession,
    *,
    node_id: str | None = None,
    node_name: str | None = None,
    node_type: str | None = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    identity = load_or_create_node_identity(
        node_id=node_id, node_name=node_name, node_type=node_type, create=True
    )
    joined = make_openmesh_event(
        "node.joined",
        distributed_node(identity),
        {
            "node_id": identity.node_id,
            "node_name": identity.node_name,
            "node_type": identity.node_type,
            "status": "active",
        },
        session_id=f"sess_node_{identity.node_id}",
        trace_id=f"trace_node_{identity.node_id}",
        span_id=f"span_node_{identity.node_id}_join",
    )
    await collector.accept(db, joined, broadcast=broadcast)

    heartbeat = make_openmesh_event(
        "node.heartbeat",
        distributed_node(identity),
        {
            "node_id": identity.node_id,
            "node_name": identity.node_name,
            "node_type": identity.node_type,
            "status": "active",
        },
        session_id=joined["session_id"],
        trace_id=joined["trace_id"],
        span_id=f"span_node_{identity.node_id}_heartbeat",
        parent_event_id=joined["event_id"],
        root_event_id=joined["root_event_id"],
    )
    await collector.accept(db, heartbeat, broadcast=broadcast)

    return {"node": identity.to_dict(), "events": [joined, heartbeat]}


async def get_node_status(db: AsyncSession, *, limit: int = 5000) -> dict[str, Any]:
    identity = load_or_create_node_identity(create=True)
    registry = await get_distributed_node_registry(db, limit=limit)
    observed = next(
        (node for node in registry["nodes"] if node["node_id"] == identity.node_id),
        None,
    )
    return {
        "local_node": identity.to_dict(),
        "registered": observed is not None,
        "observed_node": observed,
        "summary": registry["summary"],
    }


async def get_distributed_node_registry(
    db: AsyncSession, *, limit: int = 5000
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    return build_distributed_node_registry(records)


async def ingest_federated_events(
    db: AsyncSession,
    events: Iterable[dict[str, Any]],
    *,
    broadcast: bool = True,
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        try:
            accepted.append(await collector.accept(db, event, broadcast=broadcast))
        except HTTPException as exc:
            errors.append(
                {
                    "index": index,
                    "status_code": exc.status_code,
                    "detail": exc.detail,
                }
            )
    return {
        "accepted": len(accepted),
        "failed": len(errors),
        "errors": errors,
        "events": accepted,
    }


def build_distributed_node_registry(
    records: Iterable[OpenMeshEventRecord],
) -> dict[str, Any]:
    record_list = list(records)
    graph = reduce_graph_state(record_list)
    node_map = {node["id"]: node for node in graph.get("nodes", [])}
    host_edges = [
        edge
        for edge in graph.get("edges", [])
        if edge.get("relationship_type") == "hosts"
    ]
    hosted_by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in host_edges:
        hosted_by_source.setdefault(edge["source"], []).append(edge)

    nodes = []
    for graph_node in graph.get("nodes", []):
        if graph_node.get("type") != "openmesh_node":
            continue
        hosted_edges = hosted_by_source.get(graph_node["id"], [])
        hosted = _hosted_entities(hosted_edges, node_map)
        nodes.append(
            {
                "node_id": graph_node["id"],
                "node_name": graph_node.get("name") or graph_node["id"],
                "node_type": _distributed_node_kind(graph_node),
                "graph_node_type": graph_node.get("type"),
                "status": graph_node.get("lifecycle_state", "observed"),
                "first_seen": graph_node.get("first_seen"),
                "last_seen": graph_node.get("last_seen"),
                "uptime_seconds": _duration_seconds(
                    graph_node.get("first_seen"), graph_node.get("last_seen")
                ),
                "event_count": graph_node.get("event_count", 0),
                "relationship_count": len(hosted_edges),
                "hosted_agents": hosted["agents"],
                "hosted_runtimes": hosted["runtimes"],
                "hosted_mcp_servers": hosted["mcp_servers"],
                "hosted_counts": {
                    "agents": len(hosted["agents"]),
                    "runtimes": len(hosted["runtimes"]),
                    "mcp_servers": len(hosted["mcp_servers"]),
                },
                "metadata": graph_node.get("metadata") or {},
                "validation_status": graph_node.get("validation_status"),
                "provenance": graph_node.get("provenance", {}),
            }
        )

    nodes.sort(key=lambda item: (item["node_name"].lower(), item["node_id"]))
    summary = {
        "node_count": len(nodes),
        "active_nodes": sum(1 for node in nodes if node["status"] == "active"),
        "hosted_agents": sum(node["hosted_counts"]["agents"] for node in nodes),
        "hosted_runtimes": sum(node["hosted_counts"]["runtimes"] for node in nodes),
        "hosted_mcp_servers": sum(
            node["hosted_counts"]["mcp_servers"] for node in nodes
        ),
        "host_relationships": len(host_edges),
    }
    return {
        "nodes": nodes,
        "summary": summary,
        "graph": {
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "validation_status": graph.get("validation", {}).get("status", "UNKNOWN"),
        },
    }


def distributed_node(identity: DistributedNodeIdentity) -> dict[str, Any]:
    return {
        "node_id": identity.node_id,
        "node_type": "openmesh_node",
        "name": identity.node_name,
        "runtime": "openmesh.distributed",
        "metadata": {
            "node_type": identity.node_type,
            "node_kind": identity.node_type,
            "hostname": socket.gethostname(),
            "platform": platform.system().lower(),
            "config_path": identity.config_path,
        },
    }


def _hosted_entities(
    edges: list[dict[str, Any]], node_map: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    hosted = {"agents": [], "runtimes": [], "mcp_servers": []}
    buckets = {
        "agent": "agents",
        "runtime": "runtimes",
        "mcp_server": "mcp_servers",
    }
    for edge in edges:
        target = node_map.get(edge["target"])
        if not target:
            continue
        bucket = buckets.get(target.get("type"))
        if not bucket:
            continue
        hosted[bucket].append(
            {
                "id": target["id"],
                "name": target.get("name") or target["id"],
                "type": target.get("type"),
                "last_seen": target.get("last_seen"),
                "relationship_id": edge.get("id"),
                "event_count": edge.get("event_count", 0),
                "provenance": edge.get("provenance", {}),
            }
        )
    return hosted


def _distributed_node_kind(graph_node: dict[str, Any]) -> str:
    metadata = graph_node.get("metadata") or {}
    value = metadata.get("node_type") or metadata.get("node_kind")
    if isinstance(value, str) and value.strip():
        return value
    return "workstation"


def _duration_seconds(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    try:
        start_at = datetime.fromisoformat(start.replace("Z", ""))
        end_at = datetime.fromisoformat(end.replace("Z", ""))
    except ValueError:
        return 0
    return max(0, int((end_at - start_at).total_seconds()))


def _read_node_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_node_config(path: Path, identity: DistributedNodeIdentity) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(identity.to_dict(), indent=2, sort_keys=True) + "\n")


def _default_node_name() -> str:
    hostname = socket.gethostname().split(".")[0]
    return hostname or "Local OpenMesh"


def _default_node_type() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "laptop"
    if system in {"linux", "windows"}:
        return "workstation"
    return "server"


def _normalize_node_type(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return _default_node_type()
    normalized = value.strip().lower()
    return normalized if normalized in DISTRIBUTED_NODE_TYPES else "workstation"
