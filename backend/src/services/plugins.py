from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, entry_points, version
from importlib.util import find_spec
from typing import Any


PLUGIN_API_VERSION = "1.0"
PLUGIN_REGISTRY_VERSION = "0.1"
PLUGIN_ENTRY_POINT_GROUP = "openmesh.plugins"
PLUGIN_DISCOVERY_PACKAGES = ("src.sdk.integrations",)

_active_plugins: set[str] = set()


class PluginError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedPlugin:
    plugin: dict[str, Any]
    module: Any
    entrypoint: Any | None


def mark_plugin_active(plugin_id: str) -> None:
    if get_plugin(plugin_id):
        _active_plugins.add(plugin_id)


def list_plugins(*, kind: str | None = None) -> list[dict[str, Any]]:
    plugins = list(_discover_plugin_metadata().values())
    if kind:
        plugins = [plugin for plugin in plugins if plugin.get("kind") == kind]
    return sorted([plugin_status(plugin) for plugin in plugins], key=_plugin_sort_key)


def get_plugin(plugin_id: str) -> dict[str, Any] | None:
    plugin = _discover_plugin_metadata().get(plugin_id)
    return plugin_status(plugin) if plugin else None


def plugin_status(plugin: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_plugin(plugin)
    validation = validate_plugin(normalized)
    package = normalized.get("package")
    available = _dependency_available(package) if package else True
    package_version = _package_version(package) if available and package else None
    active = normalized["plugin_id"] in _active_plugins
    return {
        **normalized,
        "key": normalized["plugin_id"],
        "registry_version": PLUGIN_REGISTRY_VERSION,
        "supported_plugin_api_version": PLUGIN_API_VERSION,
        "available": available,
        "active": active,
        "package_version": package_version,
        "status_label": _status_label(normalized, available, active),
        "validation": validation,
    }


def validate_plugin(plugin: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for field in (
        "plugin_id",
        "name",
        "version",
        "plugin_api_version",
        "kind",
        "module",
    ):
        if not plugin.get(field):
            errors.append(
                {
                    "code": "missing_required_field",
                    "message": f"Plugin metadata missing required field: {field}",
                }
            )
    plugin_id = str(plugin.get("plugin_id") or "")
    if plugin_id and not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", plugin_id):
        errors.append(
            {
                "code": "invalid_plugin_id",
                "message": "Plugin id must use lowercase letters, numbers, dots, underscores, or hyphens.",
            }
        )
    api_version = str(plugin.get("plugin_api_version") or "")
    if (
        api_version
        and api_version.split(".", 1)[0] != PLUGIN_API_VERSION.split(".", 1)[0]
    ):
        errors.append(
            {
                "code": "unsupported_plugin_api_version",
                "message": f"Plugin API {api_version} is not compatible with {PLUGIN_API_VERSION}.",
            }
        )
    module_name = plugin.get("module")
    if module_name and not _module_available(str(module_name)):
        errors.append(
            {
                "code": "module_not_found",
                "message": f"Plugin module not found: {module_name}",
            }
        )
    if plugin.get("status") != "planned" and not plugin.get("entrypoint"):
        warnings.append(
            {
                "code": "missing_entrypoint",
                "message": "Plugin has no entrypoint and can only expose metadata.",
            }
        )
    package = plugin.get("package")
    if package and not _dependency_available(str(package)):
        warnings.append(
            {
                "code": "optional_dependency_missing",
                "message": f"Optional dependency is not installed: {package}",
            }
        )
    return {
        "status": "invalid" if errors else "warning" if warnings else "valid",
        "registry_version": PLUGIN_REGISTRY_VERSION,
        "supported_plugin_api_version": PLUGIN_API_VERSION,
        "errors": errors,
        "warnings": warnings,
    }


def plugin_registry_metadata() -> dict[str, Any]:
    plugins = list_plugins()
    return {
        "registry_version": PLUGIN_REGISTRY_VERSION,
        "plugin_api_version": PLUGIN_API_VERSION,
        "entry_point_group": PLUGIN_ENTRY_POINT_GROUP,
        "discovery_packages": list(PLUGIN_DISCOVERY_PACKAGES),
        "plugin_count": len(plugins),
        "plugins": plugins,
    }


def load_plugin(plugin_id: str) -> LoadedPlugin:
    plugin = get_plugin(plugin_id)
    if not plugin:
        raise PluginError(f"OpenMesh plugin not found: {plugin_id}")
    validation = plugin.get("validation", {})
    if validation.get("status") == "invalid":
        raise PluginError(f"OpenMesh plugin is invalid: {plugin_id}")
    module_name = str(plugin["module"])
    module = importlib.import_module(module_name)
    entrypoint_name = plugin.get("entrypoint")
    entrypoint = (
        getattr(module, str(entrypoint_name), None) if entrypoint_name else None
    )
    if entrypoint_name and entrypoint is None:
        raise PluginError(f"Plugin entrypoint not found: {entrypoint_name}")
    return LoadedPlugin(plugin=plugin, module=module, entrypoint=entrypoint)


def _discover_plugin_metadata() -> dict[str, dict[str, Any]]:
    plugins: dict[str, dict[str, Any]] = {}
    for plugin in _discover_module_plugins():
        plugins[plugin["plugin_id"]] = plugin
    for plugin in _discover_entry_point_plugins():
        plugins[plugin["plugin_id"]] = plugin
    return plugins


def _discover_module_plugins() -> list[dict[str, Any]]:
    plugins = []
    for package_name in PLUGIN_DISCOVERY_PACKAGES:
        try:
            package = importlib.import_module(package_name)
        except ModuleNotFoundError:
            continue
        package_path = getattr(package, "__path__", None)
        if package_path is None:
            continue
        for module_info in pkgutil.iter_modules(package_path, f"{package_name}."):
            module_name = module_info.name
            if module_info.ispkg or module_name.rsplit(".", 1)[-1] in {
                "__init__",
                "registry",
            }:
                continue
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            metadata = getattr(module, "OPENMESH_PLUGIN", None)
            if isinstance(metadata, dict):
                plugins.append(_normalize_plugin({**metadata, "module": module_name}))
    return plugins


def _discover_entry_point_plugins() -> list[dict[str, Any]]:
    plugins = []
    try:
        selected = entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    except TypeError:
        selected = entry_points().get(PLUGIN_ENTRY_POINT_GROUP, [])
    for entry_point in selected:
        try:
            metadata = entry_point.load()
        except Exception:
            continue
        if callable(metadata):
            metadata = metadata()
        if isinstance(metadata, dict):
            plugins.append(
                _normalize_plugin(
                    {
                        **metadata,
                        "entry_point": f"{entry_point.module}:{entry_point.attr}",
                    }
                )
            )
    return plugins


def _normalize_plugin(plugin: dict[str, Any]) -> dict[str, Any]:
    plugin_id = str(plugin.get("plugin_id") or plugin.get("key") or "").strip()
    return {
        "plugin_id": plugin_id,
        "name": str(plugin.get("name") or plugin_id),
        "version": str(plugin.get("version") or "0.1.0"),
        "plugin_api_version": str(
            plugin.get("plugin_api_version") or PLUGIN_API_VERSION
        ),
        "kind": str(plugin.get("kind") or "integration"),
        "status": str(plugin.get("status") or "reference"),
        "module": str(plugin.get("module") or ""),
        "entrypoint": plugin.get("entrypoint"),
        "package": plugin.get("package"),
        "description": str(plugin.get("description") or ""),
        "capabilities": list(plugin.get("capabilities") or []),
        "metadata": dict(plugin.get("metadata") or {}),
    }


def _dependency_available(package: str | None) -> bool:
    return _module_available(package) if package else True


def _module_available(module_name: str | None) -> bool:
    if not module_name:
        return False
    try:
        return find_spec(module_name) is not None
    except (AttributeError, ImportError, ModuleNotFoundError, ValueError):
        return False


def _package_version(package: str | None) -> str | None:
    if not package:
        return None
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def _status_label(plugin: dict[str, Any], available: bool, active: bool) -> str:
    if active:
        return "Active"
    if available:
        return "Available"
    if plugin.get("status") == "planned":
        return "Future"
    return "Not installed"


def _plugin_sort_key(plugin: dict[str, Any]) -> tuple[str, str]:
    return (str(plugin.get("kind") or ""), str(plugin.get("name") or ""))
