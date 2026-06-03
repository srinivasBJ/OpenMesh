from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from .registry_compatibility import NODE_REGISTRY_VERSION


COMMON_METADATA = ("framework", "provider", "version")
REQUIRED_IDENTIFIERS = ("node_id", "node_type", "name")


@dataclass(frozen=True)
class NodeType:
    type: str
    display_name: str
    description: str
    category: str
    allowed_metadata: tuple[str, ...]
    introduced_in: str = NODE_REGISTRY_VERSION
    deprecated_in: Optional[str] = None
    removed_in: Optional[str] = None
    replaced_by: Optional[str] = None


NODE_TYPES: dict[str, NodeType] = {
    "agent": NodeType(
        "agent",
        "Agent",
        "An autonomous or assisted agent.",
        "agents",
        COMMON_METADATA + ("role",),
    ),
    "tool": NodeType(
        "tool",
        "Tool",
        "A callable tool used by an agent or runtime.",
        "tools",
        COMMON_METADATA + ("capabilities", "server", "description", "category", "name"),
    ),
    "workflow": NodeType(
        "workflow",
        "Workflow",
        "A coordinated execution flow.",
        "workflows",
        COMMON_METADATA + ("graph", "source"),
    ),
    "process": NodeType(
        "process",
        "Process",
        "An observed operating system process.",
        "processes",
        COMMON_METADATA + ("session_id", "pid"),
    ),
    "command": NodeType(
        "command",
        "Command",
        "A command executed by a process.",
        "processes",
        COMMON_METADATA + ("executable",),
    ),
    "service": NodeType(
        "service",
        "Service",
        "A long-lived service or runtime component.",
        "services",
        COMMON_METADATA + ("graph", "endpoint", "source", "config_path"),
    ),
    "framework": NodeType(
        "framework",
        "Framework",
        "An observed agent framework.",
        "frameworks",
        COMMON_METADATA,
    ),
    "federation_node": NodeType(
        "federation_node",
        "Federation Node",
        "An OpenMesh instance participating in metadata federation.",
        "federation",
        COMMON_METADATA
        + (
            "instance_id",
            "organization",
            "cluster",
            "endpoint",
            "protocol_version",
            "federation_schema_version",
        ),
    ),
    "mcp_server": NodeType(
        "mcp_server",
        "MCP Server",
        "An observed Model Context Protocol server.",
        "services",
        COMMON_METADATA
        + (
            "endpoint",
            "transport",
            "config_source",
            "config_path",
            "args",
            "tools",
            "resources",
        ),
    ),
    "capability": NodeType(
        "capability",
        "Capability",
        "A capability exposed by a service, tool, or MCP server.",
        "capabilities",
        COMMON_METADATA + ("server", "description", "category"),
    ),
    "model": NodeType(
        "model",
        "Model",
        "An AI model used by an agent or service.",
        "models",
        COMMON_METADATA + ("endpoint", "local"),
    ),
    "memory": NodeType(
        "memory",
        "Memory",
        "A memory store or memory operation target.",
        "memory",
        COMMON_METADATA,
    ),
    "file": NodeType(
        "file",
        "File",
        "A file observed in an execution.",
        "files",
        COMMON_METADATA
        + ("path", "server", "resource_type", "locator", "name", "type"),
    ),
    "database": NodeType(
        "database",
        "Database",
        "A database resource accessed by a tool or agent.",
        "resources",
        COMMON_METADATA
        + ("server", "resource_type", "locator", "endpoint", "name", "type"),
    ),
    "github_repository": NodeType(
        "github_repository",
        "GitHub Repository",
        "A GitHub repository resource accessed by a tool or agent.",
        "resources",
        COMMON_METADATA
        + (
            "server",
            "resource_type",
            "locator",
            "owner",
            "repo",
            "url",
            "name",
            "type",
        ),
    ),
    "api_endpoint": NodeType(
        "api_endpoint",
        "API Endpoint",
        "An API endpoint resource accessed by a tool or agent.",
        "resources",
        COMMON_METADATA
        + ("server", "resource_type", "locator", "url", "method", "name", "type"),
    ),
    "memory_store": NodeType(
        "memory_store",
        "Memory Store",
        "A memory store resource accessed by a tool or agent.",
        "resources",
        COMMON_METADATA
        + ("server", "resource_type", "locator", "scope", "name", "type"),
    ),
    "browser": NodeType(
        "browser",
        "Browser",
        "A browser or browser automation runtime.",
        "services",
        COMMON_METADATA + ("session_id",),
    ),
    "user": NodeType(
        "user",
        "User",
        "A human participant in an observed system.",
        "users",
        COMMON_METADATA,
    ),
    "runtime": NodeType(
        "runtime",
        "Runtime",
        "An execution runtime hosting agents or workflows.",
        "services",
        COMMON_METADATA + ("executable", "path", "status", "detected"),
    ),
    "guild": NodeType(
        "guild",
        "Guild",
        "A legacy OpenMesh collaboration group.",
        "services",
        COMMON_METADATA,
    ),
    "wiki": NodeType(
        "wiki",
        "Wiki",
        "A legacy OpenMesh knowledge surface.",
        "services",
        COMMON_METADATA,
    ),
    "post": NodeType(
        "post", "Post", "A legacy OpenMesh content entity.", "services", COMMON_METADATA
    ),
}


def node_type_definition(node_type: str) -> Optional[dict[str, object]]:
    spec = NODE_TYPES.get(node_type)
    if not spec:
        return None
    return asdict(spec)


def node_type_registry() -> list[dict[str, object]]:
    return [
        definition
        for spec in NODE_TYPES.values()
        if (definition := node_type_definition(spec.type)) is not None
    ]


def node_type_validation_metadata() -> dict[str, object]:
    return {
        "version": NODE_REGISTRY_VERSION,
        "required_identifiers": REQUIRED_IDENTIFIERS,
        "metadata_policy": "Unsupported metadata keys are reported as warnings; non-object metadata is invalid.",
        "compatibility": {
            "additive_changes": "Backward compatible within the supported major version.",
            "deprecated_types": "Accepted with warnings.",
            "removed_types": "Rejected as invalid.",
            "renamed_types": "Rejected under the old name with replacement guidance.",
        },
    }


def validate_node(node: Any) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not isinstance(node, dict):
        errors.append({"code": "invalid_node", "message": "Node must be an object"})
        return _validation_result(None, None, errors, warnings)

    missing_identifiers = [
        field
        for field in REQUIRED_IDENTIFIERS
        if not isinstance(node.get(field), str) or not node.get(field, "").strip()
    ]
    if missing_identifiers:
        errors.append(
            {
                "code": "missing_required_identifiers",
                "message": f"Missing required node identifiers: {', '.join(missing_identifiers)}",
            }
        )

    node_type = node.get("node_type")
    definition = node_type_definition(node_type) if isinstance(node_type, str) else None
    if node_type and not definition:
        errors.append(
            {"code": "unknown_node_type", "message": f"Unknown node type: {node_type}"}
        )

    metadata = node.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        errors.append(
            {
                "code": "invalid_node_metadata",
                "message": "Node metadata must be an object",
            }
        )
    elif definition:
        if definition.get("removed_in"):
            errors.append(
                {
                    "code": "removed_node_type",
                    "message": f"Node type {node_type} was removed in {definition['removed_in']}",
                }
            )
        elif definition.get("deprecated_in"):
            warnings.append(
                {
                    "code": "deprecated_node_type",
                    "message": f"Node type {node_type} is deprecated as of {definition['deprecated_in']}",
                }
            )
        allowed_metadata = set(definition["allowed_metadata"])
        unsupported = sorted(
            str(key) for key in metadata if key not in allowed_metadata
        )
        if unsupported:
            warnings.append(
                {
                    "code": "unsupported_node_metadata",
                    "message": f"Unsupported metadata for {node_type}: {', '.join(unsupported)}",
                }
            )

    return _validation_result(node_type, definition, errors, warnings)


def _validation_result(
    node_type: Optional[str],
    definition: Optional[dict[str, object]],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    status = "invalid" if errors else "warning" if warnings else "valid"
    return {
        "status": status,
        "valid": not errors,
        "node_type": node_type,
        "definition": definition,
        "errors": errors,
        "warnings": warnings,
    }
