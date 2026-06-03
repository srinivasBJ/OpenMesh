from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from .registry_compatibility import RELATIONSHIP_REGISTRY_VERSION


@dataclass(frozen=True)
class RelationshipType:
    type: str
    label: str
    description: str
    source_types: tuple[str, ...]
    target_types: tuple[str, ...]
    introduced_in: str = RELATIONSHIP_REGISTRY_VERSION
    deprecated_in: Optional[str] = None
    removed_in: Optional[str] = None
    replaced_by: Optional[str] = None


RELATIONSHIP_TYPES: dict[str, RelationshipType] = {
    "uses": RelationshipType(
        type="uses",
        label="uses",
        description="An agent, process, workflow, or service uses a tool or model.",
        source_types=("agent", "process", "service", "workflow"),
        target_types=("tool", "model"),
    ),
    "runs": RelationshipType(
        type="runs",
        label="runs",
        description="An agent or service runs a workflow.",
        source_types=("agent", "service"),
        target_types=("workflow",),
    ),
    "spawns": RelationshipType(
        type="spawns",
        label="spawns",
        description="A workflow, service, agent, or CLI process spawns a process.",
        source_types=("workflow", "service", "agent", "process"),
        target_types=("process",),
    ),
    "executes": RelationshipType(
        type="executes",
        label="executes",
        description="An agent, process, workflow, or service executes a command.",
        source_types=("agent", "process", "workflow", "service"),
        target_types=("command",),
    ),
    "reads": RelationshipType(
        type="reads",
        label="reads",
        description="An agent, process, workflow, or service reads a file.",
        source_types=("agent", "process", "workflow", "service"),
        target_types=("file",),
    ),
    "writes": RelationshipType(
        type="writes",
        label="writes",
        description="An agent, process, workflow, or service writes a file.",
        source_types=("agent", "process", "workflow", "service"),
        target_types=("file",),
    ),
    "modifies": RelationshipType(
        type="modifies",
        label="modifies",
        description="An agent, process, workflow, or service modifies a file.",
        source_types=("agent", "process", "workflow", "service"),
        target_types=("file",),
    ),
    "connects_to": RelationshipType(
        type="connects_to",
        label="connects_to",
        description="An agent, tool, workflow, or service connects to a service or MCP server.",
        source_types=("agent", "tool", "workflow", "service"),
        target_types=("service", "mcp_server"),
    ),
    "defines": RelationshipType(
        type="defines",
        label="defines",
        description="A configuration source defines an MCP server.",
        source_types=("service",),
        target_types=("mcp_server",),
    ),
    "exposes": RelationshipType(
        type="exposes",
        label="exposes",
        description="A service or MCP server exposes a capability.",
        source_types=("service", "mcp_server"),
        target_types=("capability",),
    ),
    "served_by": RelationshipType(
        type="served_by",
        label="served_by",
        description="A model is served by a local or remote provider service.",
        source_types=("model",),
        target_types=("service",),
    ),
    "communicates_with": RelationshipType(
        type="communicates_with",
        label="communicates_with",
        description="One agent, service, or process communicates with another entity.",
        source_types=("agent", "service", "process", "workflow"),
        target_types=("agent", "service", "process", "workflow"),
    ),
    "collaborates_with": RelationshipType(
        type="collaborates_with",
        label="collaborates_with",
        description="One agent, workflow, or service collaborates with another ecosystem entity.",
        source_types=("agent", "workflow", "service"),
        target_types=("agent", "workflow", "service"),
    ),
    "delegates_to": RelationshipType(
        type="delegates_to",
        label="delegates_to",
        description="One agent or workflow delegates work to another agent or workflow.",
        source_types=("agent", "workflow"),
        target_types=("agent", "workflow"),
    ),
    "transitions_to": RelationshipType(
        type="transitions_to",
        label="transitions_to",
        description="A workflow node transitions to another workflow node.",
        source_types=("service", "workflow"),
        target_types=("service", "workflow"),
    ),
    "federates_with": RelationshipType(
        type="federates_with",
        label="federates_with",
        description="One OpenMesh federation node exchanges ecosystem metadata with another federation node.",
        source_types=("federation_node",),
        target_types=("federation_node",),
    ),
}


EVENT_RELATIONSHIPS = {
    "process.started": "spawns",
    "process.completed": "executes",
    "process.failed": "executes",
    "command.executed": "executes",
    "file.read": "reads",
    "file.write": "writes",
    "file.modified": "modifies",
    "tool.call.started": "uses",
    "tool.call.completed": "uses",
    "tool.call.failed": "uses",
    "tool.called": "uses",
    "llm.request": "uses",
    "llm.response": "uses",
    "model.request": "uses",
    "model.response": "uses",
    "model.loaded": "served_by",
    "message.sent": "communicates_with",
    "collaboration.created": "collaborates_with",
    "delegation.created": "delegates_to",
    "node.transition": "transitions_to",
    "mcp.config.discovered": "defines",
    "mcp.capability.discovered": "exposes",
    "federation.peer.discovered": "federates_with",
}


def relationship_type_for(
    event_type: str,
    *,
    source_type: Optional[str] = None,
    target_type: Optional[str] = None,
) -> Optional[str]:
    relationship_type = EVENT_RELATIONSHIPS.get(event_type)
    if relationship_type:
        return relationship_type
    if target_type == "tool":
        return "uses"
    if target_type == "workflow":
        return "runs"
    if target_type == "process":
        return "spawns"
    if source_type in {"agent", "tool", "workflow", "service"} and target_type in {
        "service",
        "mcp_server",
    }:
        return "connects_to"
    if source_type in {"service", "mcp_server"} and target_type == "capability":
        return "exposes"
    if target_type in {"agent", "service", "process"}:
        return "communicates_with"
    return None


def is_relationship_valid(
    relationship_type: str, source_type: str, target_type: str
) -> bool:
    return validate_relationship(relationship_type, source_type, target_type)["valid"]


def relationship_registry() -> list[dict[str, object]]:
    return [
        definition
        for spec in RELATIONSHIP_TYPES.values()
        if (definition := relationship_definition(spec.type)) is not None
    ]


def relationship_definition(relationship_type: str) -> Optional[dict[str, object]]:
    spec = RELATIONSHIP_TYPES.get(relationship_type)
    if not spec:
        return None
    definition = asdict(spec)
    definition["name"] = spec.type
    return definition


def validate_relationship(
    relationship_type: str, source_type: str, target_type: str
) -> dict[str, Any]:
    spec = RELATIONSHIP_TYPES.get(relationship_type)
    definition = relationship_definition(relationship_type)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not spec:
        errors.append(
            {
                "code": "invalid_relationship_type",
                "message": f"Unknown relationship type: {relationship_type}",
            }
        )
    else:
        if spec.removed_in:
            errors.append(
                {
                    "code": "removed_relationship_type",
                    "message": f"Relationship type {relationship_type} was removed in {spec.removed_in}",
                }
            )
        elif spec.deprecated_in:
            warnings.append(
                {
                    "code": "deprecated_relationship_type",
                    "message": f"Relationship type {relationship_type} is deprecated as of {spec.deprecated_in}",
                }
            )
        if source_type not in spec.source_types:
            errors.append(
                {
                    "code": "invalid_source_type",
                    "message": f"{source_type} cannot be the source of {relationship_type}",
                }
            )
        if target_type not in spec.target_types:
            errors.append(
                {
                    "code": "invalid_target_type",
                    "message": f"{target_type} cannot be the target of {relationship_type}",
                }
            )

    return {
        "status": "invalid" if errors else "warning" if warnings else "valid",
        "valid": not errors,
        "relationship_type": relationship_type,
        "source_type": source_type,
        "target_type": target_type,
        "definition": definition,
        "errors": errors,
        "warnings": warnings,
    }


def relationship_registry_metadata() -> dict[str, object]:
    return {
        "version": RELATIONSHIP_REGISTRY_VERSION,
        "compatibility": {
            "additive_changes": "Backward compatible within the supported major version.",
            "deprecated_types": "Accepted with warnings.",
            "removed_types": "Rejected as invalid.",
            "renamed_types": "Rejected under the old name with replacement guidance.",
        },
    }
