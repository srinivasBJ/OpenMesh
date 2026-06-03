from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..mcp import (
    MCPResourceEntry,
    MCPToolEntry,
    discover_mcp_ecosystem,
    infer_resources_for_server,
    infer_tools_for_server,
    resource_node,
    tool_node,
)
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event
from .graph_state import reduce_graph_state
from .mcp_discovery import mcp_server_node
from .openmesh_collector import collector


RESOURCE_NODE_TYPES = {
    "file",
    "database",
    "github_repository",
    "api_endpoint",
    "memory_store",
}

MCP_OBSERVER_AGENT: OpenMeshNode = {
    "node_id": "agent:openmesh-mcp-observer",
    "node_type": "agent",
    "name": "OpenMesh MCP Observer",
    "runtime": "openmesh.mcp",
    "metadata": {"role": "ecosystem-observer"},
}


async def register_discovered_mcp_ecosystem(
    db: AsyncSession,
    *,
    paths_by_source: dict[str, Iterable[Path]] | None = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    discovery = discover_mcp_ecosystem(paths_by_source=paths_by_source)
    session_id = f"sess_mcp_{uuid4().hex}"
    trace_id = f"trace_mcp_{uuid4().hex}"
    root_span_id = f"span_{uuid4().hex}"
    events: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []

    async def emit(
        event_type: str,
        source: OpenMeshNode,
        payload: dict[str, Any],
        *,
        target: OpenMeshNode | None = None,
        parent_event_id: str | None = None,
        root_event_id: str | None = None,
        severity: str = "info",
    ) -> dict[str, Any]:
        event = make_openmesh_event(
            event_type,
            source,
            payload,
            target=target,
            session_id=session_id,
            trace_id=trace_id,
            span_id=root_span_id,
            parent_event_id=parent_event_id,
            root_event_id=root_event_id,
            severity=severity,
        )
        await collector.accept(db, event, broadcast=broadcast)
        events.append(event)
        return event

    for server in discovery.servers:
        mcp_node = mcp_server_node(
            name=str(server["server"]),
            transport=str(server["transport"]),
            endpoint=str(server["endpoint"]),
            version=str(server["version"]) if server.get("version") else None,
            metadata={
                "config_source": server.get("source"),
                "config_path": server.get("config_path"),
                **(
                    server.get("metadata")
                    if isinstance(server.get("metadata"), dict)
                    else {}
                ),
            },
        )
        connected = await emit(
            "mcp.connected",
            MCP_OBSERVER_AGENT,
            {
                **server,
                "status": "connected",
                "metadata_only": True,
            },
            target=mcp_node,
        )
        root_event_id = connected["event_id"]

        for tool_entry in infer_tools_for_server(server):
            tool_event = await emit(
                "tool.registered",
                mcp_node,
                {
                    **tool_entry.to_dict(),
                    "metadata_only": True,
                },
                target=tool_node(tool_entry),
                parent_event_id=root_event_id,
                root_event_id=root_event_id,
            )
            tools.append({**tool_entry.to_dict(), "event_id": tool_event["event_id"]})

        for resource_entry in infer_resources_for_server(server):
            resource_event = await emit(
                "resource.discovered",
                mcp_node,
                {
                    **resource_entry.to_dict(),
                    "metadata_only": True,
                },
                target=resource_node(resource_entry),
                parent_event_id=root_event_id,
                root_event_id=root_event_id,
            )
            resources.append(
                {**resource_entry.to_dict(), "event_id": resource_event["event_id"]}
            )

    return {
        "servers": discovery.servers,
        "tools": tools,
        "resources": resources,
        "issues": discovery.issues,
        "events": events,
        "trace_id": trace_id,
        "session_id": session_id,
    }


async def record_tool_interaction(
    db: AsyncSession,
    *,
    agent: OpenMeshNode,
    tool: MCPToolEntry,
    resource: MCPResourceEntry | None = None,
    status: str = "completed",
    error: str | None = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    session_id = f"sess_tool_{uuid4().hex}"
    trace_id = f"trace_tool_{uuid4().hex}"
    span_id = f"span_{uuid4().hex}"
    events: list[dict[str, Any]] = []
    tool_target = tool_node(tool)

    async def emit(
        event_type: str,
        source: OpenMeshNode,
        payload: dict[str, Any],
        *,
        target: OpenMeshNode | None = None,
        parent_event_id: str | None = None,
        root_event_id: str | None = None,
        severity: str = "info",
    ) -> dict[str, Any]:
        event = make_openmesh_event(
            event_type,
            source,
            payload,
            target=target,
            session_id=session_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_event_id=parent_event_id,
            root_event_id=root_event_id,
            severity=severity,
        )
        await collector.accept(db, event, broadcast=broadcast)
        events.append(event)
        return event

    called = await emit(
        "tool.called",
        agent,
        {**tool.to_dict(), "status": "started"},
        target=tool_target,
    )
    if status == "failed":
        await emit(
            "tool.failed",
            agent,
            {**tool.to_dict(), "status": "failed", "error": error},
            target=tool_target,
            parent_event_id=called["event_id"],
            root_event_id=called["event_id"],
            severity="error",
        )
    else:
        completed_target = resource_node(resource) if resource else tool_target
        completed_source = tool_target if resource else agent
        await emit(
            "tool.completed",
            completed_source,
            {
                **tool.to_dict(),
                "status": "completed",
                "resource": resource.to_dict() if resource else None,
            },
            target=completed_target,
            parent_event_id=called["event_id"],
            root_event_id=called["event_id"],
        )
    return {"trace_id": trace_id, "session_id": session_id, "events": events}


def build_tool_registry(records: Iterable[OpenMeshEventRecord]) -> list[dict[str, Any]]:
    graph = reduce_graph_state(records)
    relationship_counts = _relationship_counts(graph.get("edges", []))
    tools = []
    for node in graph.get("nodes", []):
        if node.get("type") != "tool":
            continue
        metadata = node.get("metadata") or {}
        tools.append(
            {
                "id": node["id"],
                "tool": node["name"],
                "name": node["name"],
                "server": metadata.get("server"),
                "category": metadata.get("category"),
                "description": metadata.get("description"),
                "version": metadata.get("version"),
                "last_seen": node.get("last_seen"),
                "event_count": node.get("event_count", 0),
                "relationship_count": relationship_counts.get(node["id"], 0),
                "metadata": metadata,
            }
        )
    return sorted(tools, key=lambda item: (str(item.get("server")), item["tool"]))


def build_resource_registry(
    records: Iterable[OpenMeshEventRecord],
) -> list[dict[str, Any]]:
    graph = reduce_graph_state(records)
    relationship_counts = _relationship_counts(graph.get("edges", []))
    resources = []
    for node in graph.get("nodes", []):
        if node.get("type") not in RESOURCE_NODE_TYPES:
            continue
        metadata = node.get("metadata") or {}
        resources.append(
            {
                "id": node["id"],
                "resource": node["name"],
                "name": node["name"],
                "resource_type": metadata.get("resource_type") or node.get("type"),
                "locator": metadata.get("locator") or metadata.get("path"),
                "server": metadata.get("server"),
                "last_seen": node.get("last_seen"),
                "event_count": node.get("event_count", 0),
                "relationship_count": relationship_counts.get(node["id"], 0),
                "metadata": metadata,
            }
        )
    return sorted(
        resources, key=lambda item: (str(item.get("resource_type")), item["resource"])
    )


async def get_tool_registry(
    db: AsyncSession, limit: int = 5000
) -> list[dict[str, Any]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_tool_registry(records)


async def get_resource_registry(
    db: AsyncSession, limit: int = 5000
) -> list[dict[str, Any]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_resource_registry(records)


async def get_mcp_observability_metrics(
    db: AsyncSession, limit: int = 5000
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    event_types = [record.event_type for record in records]
    graph = reduce_graph_state(records)
    tool_counts: Counter[str] = Counter()
    resource_activity = 0
    for edge in graph.get("edges", []):
        if edge.get("type") == "calls":
            tool_counts[edge.get("target", "")] += edge.get("event_count", 0)
        if edge.get("type") == "accesses":
            resource_activity += edge.get("event_count", 0)
    active_servers = _active_mcp_server_count(records)
    node_names = {node["id"]: node["name"] for node in graph.get("nodes", [])}
    most_used_tools = [
        {"tool_id": tool_id, "tool": node_names.get(tool_id, tool_id), "calls": count}
        for tool_id, count in tool_counts.most_common(5)
    ]
    return {
        "active_mcp_servers": active_servers,
        "tool_calls": event_types.count("tool.called"),
        "failed_tool_calls": event_types.count("tool.failed"),
        "most_used_tools": most_used_tools,
        "resource_activity": resource_activity,
    }


def _active_mcp_server_count(records: Iterable[OpenMeshEventRecord]) -> int:
    state: dict[str, bool] = {}
    for record in sorted(records, key=lambda item: item.timestamp):
        target = record.target_json or {}
        if target.get("node_type") != "mcp_server":
            continue
        if record.event_type == "mcp.connected":
            state[target["node_id"]] = True
        elif record.event_type == "mcp.disconnected":
            state[target["node_id"]] = False
    return sum(1 for active in state.values() if active)


def _relationship_counts(edges: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        counts[edge["source"]] = counts.get(edge["source"], 0) + 1
        counts[edge["target"]] = counts.get(edge["target"], 0) + 1
    return counts
