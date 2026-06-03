from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..shared.openmesh_events import OpenMeshNode


RESOURCE_KIND_TO_NODE_TYPE = {
    "file": "file",
    "database": "database",
    "github_repository": "github_repository",
    "api_endpoint": "api_endpoint",
    "memory_store": "memory_store",
}


@dataclass(frozen=True)
class MCPToolEntry:
    server: str
    tool: str
    description: str | None = None
    category: str | None = None
    version: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "tool": self.tool,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "metadata": self.metadata or {},
        }


@dataclass(frozen=True)
class MCPResourceEntry:
    server: str
    resource: str
    resource_type: str
    locator: str
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "server": self.server,
            "resource": self.resource,
            "resource_type": self.resource_type,
            "locator": self.locator,
            "metadata": self.metadata or {},
        }


def tool_node(entry: MCPToolEntry | dict[str, Any]) -> OpenMeshNode:
    raw = entry.to_dict() if isinstance(entry, MCPToolEntry) else entry
    server = str(raw.get("server") or "mcp")
    tool = str(raw.get("tool") or raw.get("name") or "tool")
    metadata = {
        "server": server,
        "description": raw.get("description"),
        "category": raw.get("category"),
        "version": raw.get("version"),
        **(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
    }
    return {
        "node_id": f"tool:mcp:{_stable_id(server)}:{_stable_id(tool)}",
        "node_type": "tool",
        "name": tool,
        "runtime": "mcp",
        "metadata": {
            key: value for key, value in metadata.items() if value is not None
        },
    }


def resource_node(entry: MCPResourceEntry | dict[str, Any]) -> OpenMeshNode:
    raw = entry.to_dict() if isinstance(entry, MCPResourceEntry) else entry
    resource_type = str(raw.get("resource_type") or "api_endpoint")
    node_type = RESOURCE_KIND_TO_NODE_TYPE.get(resource_type, "api_endpoint")
    server = str(raw.get("server") or "mcp")
    name = str(raw.get("resource") or raw.get("locator") or "resource")
    locator = str(raw.get("locator") or name)
    metadata = {
        "server": server,
        "resource_type": resource_type,
        "locator": locator,
        **(raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}),
    }
    return {
        "node_id": f"{node_type}:mcp:{_stable_id(server)}:{_stable_id(locator)}",
        "node_type": node_type,
        "name": name,
        "runtime": "mcp.resource",
        "metadata": metadata,
    }


def infer_tools_for_server(server: dict[str, Any]) -> list[MCPToolEntry]:
    metadata = server.get("metadata") or {}
    declared = metadata.get("tools") or metadata.get("capabilities")
    if isinstance(declared, list) and declared:
        return [
            MCPToolEntry(
                server=str(server["server"]),
                tool=str(item.get("name") if isinstance(item, dict) else item),
                description=item.get("description") if isinstance(item, dict) else None,
                category=item.get("category") if isinstance(item, dict) else None,
                version=str(server.get("version")) if server.get("version") else None,
                metadata=item if isinstance(item, dict) else {},
            )
            for item in declared
        ]

    name = str(server.get("server") or "").lower()
    if "github" in name:
        names = ("search_repositories", "create_issue")
        category = "github"
    elif any(token in name for token in ("postgres", "database", "sql")):
        names = ("query_database",)
        category = "database"
    elif "memory" in name:
        names = ("read_memory", "write_memory")
        category = "memory"
    elif any(token in name for token in ("file", "filesystem", "fs")):
        names = ("read_file", "write_file")
        category = "filesystem"
    else:
        names = ("invoke_tool",)
        category = "api"
    return [
        MCPToolEntry(
            server=str(server["server"]),
            tool=name,
            category=category,
            version=str(server.get("version")) if server.get("version") else None,
        )
        for name in names
    ]


def infer_resources_for_server(server: dict[str, Any]) -> list[MCPResourceEntry]:
    metadata = server.get("metadata") or {}
    declared = metadata.get("resources")
    if isinstance(declared, list) and declared:
        return [
            MCPResourceEntry(
                server=str(server["server"]),
                resource=str(
                    item.get("name") or item.get("resource") or item.get("locator")
                )
                if isinstance(item, dict)
                else str(item),
                resource_type=str(item.get("type") or item.get("resource_type"))
                if isinstance(item, dict)
                else "api_endpoint",
                locator=str(item.get("locator") or item.get("url") or item.get("path"))
                if isinstance(item, dict)
                else str(item),
                metadata=item if isinstance(item, dict) else {},
            )
            for item in declared
        ]

    name = str(server.get("server") or "").lower()
    endpoint = str(server.get("endpoint") or "")
    if "github" in name:
        return [
            MCPResourceEntry(
                server=str(server["server"]),
                resource="GitHub Repository",
                resource_type="github_repository",
                locator=endpoint or "github://repository",
            )
        ]
    if any(token in name for token in ("postgres", "database", "sql")):
        return [
            MCPResourceEntry(
                server=str(server["server"]),
                resource="Database",
                resource_type="database",
                locator=endpoint or "database://local",
            )
        ]
    if "memory" in name:
        return [
            MCPResourceEntry(
                server=str(server["server"]),
                resource="Memory Store",
                resource_type="memory_store",
                locator=endpoint or "memory://local",
            )
        ]
    if any(token in name for token in ("file", "filesystem", "fs")):
        return [
            MCPResourceEntry(
                server=str(server["server"]),
                resource="File System",
                resource_type="file",
                locator=endpoint or ".",
            )
        ]
    return [
        MCPResourceEntry(
            server=str(server["server"]),
            resource="API Endpoint",
            resource_type="api_endpoint",
            locator=endpoint or "api://local",
        )
    ]


def _stable_id(value: str) -> str:
    return (
        "".join(
            character.lower() if character.isalnum() else "-" for character in value
        ).strip("-")
        or "resource"
    )
