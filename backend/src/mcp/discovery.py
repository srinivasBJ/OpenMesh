from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..services.mcp_config_discovery import (
    DEFAULT_MCP_CONFIG_PROVIDERS,
    MCPConfigProvider,
    discover_mcp_configs,
)


@dataclass(frozen=True)
class MCPDiscoveryResult:
    servers: list[dict[str, object]]
    issues: list[dict[str, object]]


def discover_mcp_ecosystem(
    *,
    providers: Iterable[MCPConfigProvider] = DEFAULT_MCP_CONFIG_PROVIDERS,
    paths_by_source: dict[str, Iterable[Path]] | None = None,
) -> MCPDiscoveryResult:
    discovered = discover_mcp_configs(
        providers=providers,
        paths_by_source=paths_by_source,
    )
    return MCPDiscoveryResult(
        servers=discovered["entries"],
        issues=discovered["issues"],
    )
