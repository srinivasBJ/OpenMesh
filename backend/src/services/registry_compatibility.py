from __future__ import annotations

from typing import Any, Iterable, Optional


NODE_REGISTRY_VERSION = "0.1.0"
RELATIONSHIP_REGISTRY_VERSION = "0.1.0"
SUPPORTED_NODE_REGISTRY_MAJOR = 0
SUPPORTED_RELATIONSHIP_REGISTRY_MAJOR = 0


COMPATIBILITY_RULES = {
    "additive_changes": "Adding new active definitions is backward compatible within a supported major version.",
    "deprecated_types": "Deprecated definitions remain valid and produce warnings when observed.",
    "removed_types": "Removed definitions are invalid and produce errors when observed.",
    "renamed_types": "Renamed definitions are invalid under the old name and include replacement guidance.",
    "unsupported_versions": "Unsupported registry major versions produce errors.",
}


def registry_versions() -> dict[str, str]:
    return {
        "node_registry": NODE_REGISTRY_VERSION,
        "relationship_registry": RELATIONSHIP_REGISTRY_VERSION,
    }


def validate_registry_versions(
    *,
    node_registry_version: Optional[str] = None,
    relationship_registry_version: Optional[str] = None,
) -> dict[str, Any]:
    checks = [
        (
            "node_registry",
            node_registry_version or NODE_REGISTRY_VERSION,
            SUPPORTED_NODE_REGISTRY_MAJOR,
        ),
        (
            "relationship_registry",
            relationship_registry_version or RELATIONSHIP_REGISTRY_VERSION,
            SUPPORTED_RELATIONSHIP_REGISTRY_MAJOR,
        ),
    ]
    errors: list[dict[str, str]] = []
    for registry_name, version, supported_major in checks:
        major = _major_version(version)
        if major is None or major != supported_major:
            errors.append(
                {
                    "code": "unsupported_registry_version",
                    "registry": registry_name,
                    "version": version,
                    "message": f"{registry_name} version {version} is not supported",
                }
            )
    return {
        "status": "error" if errors else "ok",
        "errors": errors,
        "versions": {
            "node_registry": node_registry_version or NODE_REGISTRY_VERSION,
            "relationship_registry": relationship_registry_version
            or RELATIONSHIP_REGISTRY_VERSION,
        },
        "rules": COMPATIBILITY_RULES,
    }


def compatibility_status(
    *,
    version_validation: Optional[dict[str, Any]] = None,
    deprecated_nodes: Optional[Iterable[dict[str, Any]]] = None,
    deprecated_relationships: Optional[Iterable[dict[str, Any]]] = None,
    removed_nodes: Optional[Iterable[dict[str, Any]]] = None,
    removed_relationships: Optional[Iterable[dict[str, Any]]] = None,
) -> dict[str, Any]:
    version_validation = version_validation or validate_registry_versions()
    warnings = []
    errors = list(version_validation.get("errors", []))

    warnings.extend(
        _definition_warning("deprecated_node_type", item)
        for item in deprecated_nodes or []
    )
    warnings.extend(
        _definition_warning("deprecated_relationship_type", item)
        for item in deprecated_relationships or []
    )
    errors.extend(
        _definition_error("removed_node_type", item) for item in removed_nodes or []
    )
    errors.extend(
        _definition_error("removed_relationship_type", item)
        for item in removed_relationships or []
    )

    return {
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "warnings": warnings,
        "errors": errors,
    }


def _definition_warning(code: str, definition: dict[str, Any]) -> dict[str, str]:
    return {
        "code": code,
        "type": str(definition.get("type") or definition.get("name")),
        "message": str(
            definition.get("deprecation_message") or "Definition is deprecated"
        ),
    }


def _definition_error(code: str, definition: dict[str, Any]) -> dict[str, str]:
    replacement = definition.get("replaced_by")
    message = str(definition.get("removal_message") or "Definition has been removed")
    if replacement:
        message = f"{message}; use {replacement}"
    return {
        "code": code,
        "type": str(definition.get("type") or definition.get("name")),
        "message": message,
    }


def _major_version(version: str) -> Optional[int]:
    try:
        return int(version.split(".", 1)[0])
    except (AttributeError, ValueError):
        return None
