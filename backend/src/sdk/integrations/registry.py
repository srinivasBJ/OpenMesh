from __future__ import annotations

from typing import Optional

from src.services.plugins import get_plugin, list_plugins, mark_plugin_active


def mark_integration_active(key: str) -> None:
    mark_plugin_active(key)


def list_integrations() -> list[dict[str, object]]:
    return list_plugins(kind="integration")


def integration_status(key: str) -> dict[str, object]:
    plugin = get_integration(key)
    if not plugin:
        raise KeyError(key)
    return plugin


def get_integration(key: str) -> Optional[dict[str, object]]:
    plugin = get_plugin(key)
    if not plugin or plugin.get("kind") != "integration":
        return None
    return plugin
