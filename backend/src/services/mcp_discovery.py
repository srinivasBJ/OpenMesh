from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event
from .openmesh_collector import collector


MCP_DISCOVERY_SOURCE: OpenMeshNode = {
    "node_id": "openmesh.mcp_discovery",
    "node_type": "service",
    "name": "OpenMesh MCP Discovery",
    "runtime": "openmesh.discovery",
}


def mcp_server_node(
    *,
    name: str,
    transport: str,
    endpoint: str,
    version: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> OpenMeshNode:
    node_metadata = {
        "transport": transport,
        "endpoint": endpoint,
    }
    if version:
        node_metadata["version"] = version
    if metadata:
        node_metadata.update(metadata)
    return {
        "node_id": f"mcp:{_stable_id(endpoint or name)}",
        "node_type": "mcp_server",
        "name": name,
        "runtime": "mcp",
        "metadata": node_metadata,
    }


def build_mcp_registry(records: Iterable[OpenMeshEventRecord]) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for record in sorted(records, key=lambda item: item.timestamp):
        timestamp = record.timestamp.isoformat() + "Z"
        for node in (record.source_json, record.target_json):
            if not node or node.get("node_type") != "mcp_server":
                continue
            metadata = node.get("metadata") or {}
            entry = entries.setdefault(
                node["node_id"],
                {
                    "id": node["node_id"],
                    "server": node["name"],
                    "name": node["name"],
                    "transport": metadata.get("transport"),
                    "endpoint": metadata.get("endpoint"),
                    "version": metadata.get("version"),
                    "metadata": metadata,
                    "last_seen": timestamp,
                    "event_count": 0,
                    "relationship_count": 0,
                },
            )
            entry["server"] = node["name"]
            entry["name"] = node["name"]
            entry["transport"] = metadata.get("transport", entry.get("transport"))
            entry["endpoint"] = metadata.get("endpoint", entry.get("endpoint"))
            entry["version"] = metadata.get("version", entry.get("version"))
            entry["metadata"] = {**entry.get("metadata", {}), **metadata}
            entry["event_count"] += 1
            if timestamp >= (entry.get("last_seen") or ""):
                entry["last_seen"] = timestamp

        if record.source_json and record.target_json:
            for node in (record.source_json, record.target_json):
                if node and node.get("node_type") == "mcp_server" and node["node_id"] in entries:
                    entries[node["node_id"]]["relationship_count"] += 1

    return sorted(entries.values(), key=lambda item: (item["server"].lower(), item["id"]))


async def get_mcp_registry(db: AsyncSession, limit: int = 5000) -> list[dict[str, Any]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_mcp_registry(records)


async def register_mcp_server(
    db: AsyncSession,
    *,
    name: str,
    transport: str,
    endpoint: str,
    version: Optional[str] = None,
    source: Optional[OpenMeshNode] = None,
    metadata: Optional[dict[str, Any]] = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    target = mcp_server_node(
        name=name,
        transport=transport,
        endpoint=endpoint,
        version=version,
        metadata=metadata,
    )
    event = make_openmesh_event(
        "mcp.server.discovered",
        source or MCP_DISCOVERY_SOURCE,
        {
            "server": name,
            "transport": transport,
            "endpoint": endpoint,
            "version": version,
            "discovered_at": datetime.utcnow().isoformat() + "Z",
        },
        target=target,
    )
    return await collector.accept(db, event, broadcast=broadcast)


def _stable_id(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "server"
