from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event
from .mcp_discovery import mcp_server_node
from .openmesh_collector import collector


@dataclass(frozen=True)
class MCPCapabilityEntry:
    server: str
    capability: str
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "capability": self.capability,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "metadata": self.metadata or {},
        }


def capability_node(entry: MCPCapabilityEntry | dict[str, Any]) -> OpenMeshNode:
    raw = entry.to_dict() if isinstance(entry, MCPCapabilityEntry) else entry
    metadata = {
        "server": raw.get("server"),
        "description": raw.get("description"),
        "category": raw.get("category"),
    }
    if raw.get("version"):
        metadata["version"] = raw.get("version")
    if isinstance(raw.get("metadata"), dict):
        metadata.update(raw["metadata"])
    return {
        "node_id": f"capability:{_stable_id(str(raw.get('server') or 'mcp'))}:{_stable_id(str(raw.get('capability') or 'capability'))}",
        "node_type": "capability",
        "name": str(raw.get("capability") or "Unknown Capability"),
        "runtime": "mcp",
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def build_capability_registry(records: Iterable[OpenMeshEventRecord]) -> list[dict[str, Any]]:
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for record in sorted(records, key=lambda item: item.timestamp):
        if record.event_type != "mcp.capability.discovered" or not record.target_json:
            continue
        payload = record.payload_json or {}
        target_metadata = record.target_json.get("metadata") or {}
        source_metadata = (record.source_json or {}).get("metadata") or {}
        server = payload.get("server") or target_metadata.get("server") or (record.source_json or {}).get("name")
        capability = payload.get("capability") or record.target_json.get("name")
        key = (str(server), str(capability))
        timestamp = record.timestamp.isoformat() + "Z"
        entry = entries.setdefault(
            key,
            {
                "server": server,
                "capability": capability,
                "description": payload.get("description") or target_metadata.get("description"),
                "category": payload.get("category") or target_metadata.get("category"),
                "version": payload.get("version") or target_metadata.get("version"),
                "transport": payload.get("transport") or source_metadata.get("transport"),
                "endpoint": payload.get("endpoint") or source_metadata.get("endpoint"),
                "last_seen": timestamp,
                "event_count": 0,
                "metadata": payload.get("metadata") or {},
            },
        )
        entry["description"] = payload.get("description", entry.get("description"))
        entry["category"] = payload.get("category", entry.get("category"))
        entry["version"] = payload.get("version", entry.get("version"))
        entry["transport"] = payload.get("transport", entry.get("transport"))
        entry["endpoint"] = payload.get("endpoint", entry.get("endpoint"))
        if isinstance(payload.get("metadata"), dict):
            entry["metadata"] = {**entry.get("metadata", {}), **payload["metadata"]}
        entry["event_count"] += 1
        entry["last_seen"] = timestamp
    return sorted(entries.values(), key=lambda item: (str(item["server"]).lower(), str(item["capability"]).lower()))


async def get_capability_registry(db: AsyncSession, limit: int = 5000) -> list[dict[str, Any]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_capability_registry(records)


async def register_mcp_capability(
    db: AsyncSession,
    entry: MCPCapabilityEntry,
    *,
    transport: str = "metadata",
    endpoint: Optional[str] = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    source = mcp_server_node(
        name=entry.server,
        transport=transport,
        endpoint=endpoint or f"mcp://{_stable_id(entry.server)}",
        version=entry.version,
    )
    target = capability_node(entry)
    event = make_openmesh_event(
        "mcp.capability.discovered",
        source,
        {
            **entry.to_dict(),
            "transport": transport,
            "endpoint": endpoint or f"mcp://{_stable_id(entry.server)}",
            "discovered_at": datetime.utcnow().isoformat() + "Z",
        },
        target=target,
    )
    return await collector.accept(db, event, broadcast=broadcast)


def validate_capability_entries(entries: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    seen: dict[tuple[str, str], list[dict[str, Any]]] = {}
    missing = []
    malformed = []
    for entry in entries:
        missing_fields = [
            field for field in ("server", "capability", "category")
            if not entry.get(field)
        ]
        if missing_fields:
            missing.append({"entry": entry, "missing": missing_fields})
        metadata = entry.get("metadata", {})
        if metadata is not None and not isinstance(metadata, dict):
            malformed.append({"entry": entry, "field": "metadata", "message": "metadata must be an object"})
        seen.setdefault((str(entry.get("server")), str(entry.get("capability"))), []).append(entry)
    duplicates = [
        {"server": server, "capability": capability, "count": len(values)}
        for (server, capability), values in seen.items()
        if len(values) > 1
    ]
    return {
        "duplicates": duplicates,
        "malformed_metadata": malformed,
        "missing_required_metadata": missing,
    }


def _stable_id(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "capability"
