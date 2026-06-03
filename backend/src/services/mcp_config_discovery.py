from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event
from .mcp_discovery import mcp_server_node
from .openmesh_collector import collector


@dataclass(frozen=True)
class MCPConfigEntry:
    source: str
    config_path: str
    server: str
    transport: str
    endpoint: str
    version: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "config_path": self.config_path,
            "server": self.server,
            "transport": self.transport,
            "endpoint": self.endpoint,
            "version": self.version,
            "metadata": self.metadata or {},
        }


@dataclass(frozen=True)
class MCPConfigIssue:
    source: str
    config_path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "config_path": self.config_path,
            "code": self.code,
            "message": self.message,
        }


class MCPConfigProvider:
    source: str = "unknown"
    candidate_paths: tuple[str, ...] = ()

    def discover(
        self, paths: Optional[Iterable[Path]] = None
    ) -> tuple[list[MCPConfigEntry], list[MCPConfigIssue]]:
        entries: list[MCPConfigEntry] = []
        issues: list[MCPConfigIssue] = []
        for path in paths or self.paths():
            if not path.exists():
                continue
            parsed_entries, parsed_issues = self.parse(path)
            entries.extend(parsed_entries)
            issues.extend(parsed_issues)
        return entries, issues

    def paths(self) -> list[Path]:
        return [Path(path).expanduser() for path in self.candidate_paths]

    def parse(self, path: Path) -> tuple[list[MCPConfigEntry], list[MCPConfigIssue]]:
        try:
            data = _load_config(path)
        except Exception as exc:
            return [], [
                MCPConfigIssue(self.source, str(path), "malformed_config", str(exc))
            ]
        return _entries_from_config(self.source, path, data)


class ClaudeDesktopConfigProvider(MCPConfigProvider):
    source = "Claude Desktop"
    candidate_paths = (
        "~/Library/Application Support/Claude/claude_desktop_config.json",
        "~/.config/Claude/claude_desktop_config.json",
    )


class ClaudeCodeConfigProvider(MCPConfigProvider):
    source = "Claude Code"
    candidate_paths = (
        "~/.claude.json",
        "~/.claude/settings.json",
    )


class CodexConfigProvider(MCPConfigProvider):
    source = "Codex"
    candidate_paths = (
        "~/.codex/config.toml",
        "~/.codex/config.json",
    )


class CursorConfigProvider(MCPConfigProvider):
    source = "Cursor"
    candidate_paths = (
        "~/Library/Application Support/Cursor/User/mcp.json",
        "~/.cursor/mcp.json",
        "~/.cursor/mcp_config.json",
        ".cursor/mcp.json",
    )


class OpenCodeConfigProvider(MCPConfigProvider):
    source = "OpenCode"
    candidate_paths = (
        "~/.config/opencode/mcp.json",
        "~/.opencode/mcp.json",
        ".opencode/mcp.json",
        "opencode.json",
    )


class OpenHandsConfigProvider(MCPConfigProvider):
    source = "OpenHands"
    candidate_paths = (
        "~/.openhands/config.toml",
        "~/.openhands/config.json",
    )


class LocalMCPConfigProvider(MCPConfigProvider):
    source = "Local MCP"
    candidate_paths = (
        "~/.mcp/servers.json",
        "~/.config/mcp/servers.json",
    )


class ProjectMCPManifestProvider(MCPConfigProvider):
    source = "Project"
    candidate_paths = (
        "mcp.json",
        ".mcp.json",
        ".openmesh/mcp.json",
        ".vscode/mcp.json",
    )


DEFAULT_MCP_CONFIG_PROVIDERS: tuple[MCPConfigProvider, ...] = (
    ClaudeDesktopConfigProvider(),
    ClaudeCodeConfigProvider(),
    CodexConfigProvider(),
    CursorConfigProvider(),
    OpenCodeConfigProvider(),
    OpenHandsConfigProvider(),
    LocalMCPConfigProvider(),
    ProjectMCPManifestProvider(),
)


def discover_mcp_configs(
    *,
    providers: Iterable[MCPConfigProvider] = DEFAULT_MCP_CONFIG_PROVIDERS,
    paths_by_source: Optional[dict[str, Iterable[Path]]] = None,
) -> dict[str, list[dict[str, Any]]]:
    entries: list[MCPConfigEntry] = []
    issues: list[MCPConfigIssue] = []
    paths_by_source = paths_by_source or {}
    for provider in providers:
        if paths_by_source and provider.source not in paths_by_source:
            continue
        provider_entries, provider_issues = provider.discover(
            paths_by_source.get(provider.source)
        )
        entries.extend(provider_entries)
        issues.extend(provider_issues)
    return {
        "entries": [entry.to_dict() for entry in entries],
        "issues": [issue.to_dict() for issue in issues],
    }


def build_mcp_config_registry(
    records: Iterable[OpenMeshEventRecord],
) -> list[dict[str, Any]]:
    entries: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in sorted(records, key=lambda item: item.timestamp):
        if record.event_type != "mcp.config.discovered" or not record.target_json:
            continue
        payload = record.payload_json or {}
        source = payload.get("source") or (record.source_json or {}).get("name")
        config_path = payload.get("config_path") or (record.source_json or {}).get(
            "metadata", {}
        ).get("config_path")
        server = payload.get("server") or record.target_json.get("name")
        key = (str(source), str(config_path), str(server))
        entry = entries.setdefault(
            key,
            {
                "source": source,
                "config_path": config_path,
                "server": server,
                "transport": payload.get("transport"),
                "endpoint": payload.get("endpoint"),
                "version": payload.get("version"),
                "last_seen": record.timestamp.isoformat() + "Z",
                "event_count": 0,
                "metadata": payload.get("metadata") or {},
            },
        )
        entry["transport"] = payload.get("transport", entry.get("transport"))
        entry["endpoint"] = payload.get("endpoint", entry.get("endpoint"))
        entry["version"] = payload.get("version", entry.get("version"))
        entry["event_count"] += 1
        entry["last_seen"] = record.timestamp.isoformat() + "Z"
    return sorted(
        entries.values(),
        key=lambda item: (item["source"], item["server"], item["config_path"]),
    )


async def get_mcp_config_registry(
    db: AsyncSession, limit: int = 5000
) -> list[dict[str, Any]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_mcp_config_registry(records)


async def register_mcp_config_entry(
    db: AsyncSession,
    entry: MCPConfigEntry,
    *,
    broadcast: bool = True,
) -> dict[str, Any]:
    source = _config_source_node(entry.source, entry.config_path)
    target = mcp_server_node(
        name=entry.server,
        transport=entry.transport,
        endpoint=entry.endpoint,
        version=entry.version,
        metadata={
            "config_source": entry.source,
            "config_path": entry.config_path,
            **(entry.metadata or {}),
        },
    )
    event = make_openmesh_event(
        "mcp.config.discovered",
        source,
        {
            **entry.to_dict(),
            "discovered_at": datetime.utcnow().isoformat() + "Z",
        },
        target=target,
    )
    return await collector.accept(db, event, broadcast=broadcast)


async def register_discovered_mcp_configs(
    db: AsyncSession,
    *,
    providers: Iterable[MCPConfigProvider] = DEFAULT_MCP_CONFIG_PROVIDERS,
    paths_by_source: Optional[dict[str, Iterable[Path]]] = None,
    broadcast: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    discovered = discover_mcp_configs(
        providers=providers, paths_by_source=paths_by_source
    )
    events = []
    for raw_entry in discovered["entries"]:
        entry = MCPConfigEntry(**raw_entry)
        events.append(await register_mcp_config_entry(db, entry, broadcast=broadcast))
    return {
        "entries": discovered["entries"],
        "issues": discovered["issues"],
        "events": events,
    }


def validate_mcp_config_entries(
    entries: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    seen: dict[tuple[str, str], list[dict[str, Any]]] = {}
    missing = []
    for entry in entries:
        missing_fields = [
            field
            for field in ("source", "config_path", "server", "transport", "endpoint")
            if not entry.get(field)
        ]
        if missing_fields:
            missing.append({"entry": entry, "missing": missing_fields})
        seen.setdefault(
            (str(entry.get("source")), str(entry.get("server"))), []
        ).append(entry)
    duplicates = [
        {
            "source": source,
            "server": server,
            "count": len(values),
            "paths": [item.get("config_path") for item in values],
        }
        for (source, server), values in seen.items()
        if len(values) > 1
    ]
    return {"duplicates": duplicates, "missing_required_metadata": missing}


def _config_source_node(source: str, config_path: str) -> OpenMeshNode:
    return {
        "node_id": f"mcp_config:{_stable_id(source)}:{_stable_id(config_path)}",
        "node_type": "service",
        "name": f"{source} MCP Config",
        "runtime": "mcp.config",
        "metadata": {
            "source": source,
            "config_path": config_path,
        },
    }


def _load_config(path: Path) -> dict[str, Any]:
    if path.suffix == ".toml":
        with path.open("rb") as handle:
            return tomllib.load(handle)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _entries_from_config(
    source: str, path: Path, data: Any
) -> tuple[list[MCPConfigEntry], list[MCPConfigIssue]]:
    if not isinstance(data, dict):
        return [], [
            MCPConfigIssue(
                source, str(path), "malformed_config", "Config root must be an object"
            )
        ]
    servers = _server_mapping(data)
    if not isinstance(servers, dict):
        return [], []
    entries = []
    issues = []
    for server_name, raw_server in servers.items():
        if not isinstance(raw_server, dict):
            issues.append(
                MCPConfigIssue(
                    source,
                    str(path),
                    "malformed_server",
                    f"{server_name} must be an object",
                )
            )
            continue
        entry = _entry_from_server(source, path, str(server_name), raw_server)
        if entry:
            entries.append(entry)
        else:
            issues.append(
                MCPConfigIssue(
                    source,
                    str(path),
                    "missing_required_metadata",
                    f"{server_name} is missing transport or endpoint",
                )
            )
    return entries, issues


def _server_mapping(data: dict[str, Any]) -> Any:
    if "mcpServers" in data:
        return data["mcpServers"]
    if "mcp_servers" in data:
        return data["mcp_servers"]
    mcp = data.get("mcp")
    if isinstance(mcp, dict):
        return mcp.get("servers") or mcp.get("mcpServers") or mcp.get("mcp_servers")
    return None


def _entry_from_server(
    source: str, path: Path, server_name: str, server: dict[str, Any]
) -> Optional[MCPConfigEntry]:
    transport = server.get("transport") or _transport_from_server(server)
    endpoint = server.get("endpoint") or server.get("url") or server.get("command")
    version = server.get("version")
    if not transport or not endpoint:
        return None
    metadata = {
        key: value
        for key, value in server.items()
        if key not in {"transport", "endpoint", "url", "command", "version"}
    }
    return MCPConfigEntry(
        source=source,
        config_path=str(path),
        server=server_name,
        transport=str(transport),
        endpoint=str(endpoint),
        version=str(version) if version else None,
        metadata=metadata,
    )


def _transport_from_server(server: dict[str, Any]) -> Optional[str]:
    if server.get("url"):
        return "http"
    if server.get("command"):
        return "stdio"
    return None


def _stable_id(value: str) -> str:
    return (
        "".join(
            character.lower() if character.isalnum() else "-" for character in value
        ).strip("-")
        or "config"
    )
