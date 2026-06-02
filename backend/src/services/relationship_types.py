from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class RelationshipType:
    type: str
    label: str
    description: str
    source_types: tuple[str, ...]
    target_types: tuple[str, ...]


RELATIONSHIP_TYPES: dict[str, RelationshipType] = {
    "uses": RelationshipType(
        type="uses",
        label="uses",
        description="An agent, process, or service uses a tool.",
        source_types=("agent", "process", "service", "workflow"),
        target_types=("tool",),
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
        description="A process executes a command.",
        source_types=("process",),
        target_types=("command",),
    ),
    "connects_to": RelationshipType(
        type="connects_to",
        label="connects_to",
        description="A tool connects to a service.",
        source_types=("tool",),
        target_types=("service",),
    ),
    "exposes": RelationshipType(
        type="exposes",
        label="exposes",
        description="A service exposes a capability.",
        source_types=("service",),
        target_types=("capability",),
    ),
    "communicates_with": RelationshipType(
        type="communicates_with",
        label="communicates_with",
        description="One agent, service, or process communicates with another entity.",
        source_types=("agent", "service", "process", "workflow"),
        target_types=("agent", "service", "process", "workflow"),
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
}


EVENT_RELATIONSHIPS = {
    "process.started": "spawns",
    "process.completed": "executes",
    "process.failed": "executes",
    "tool.call.started": "uses",
    "tool.call.completed": "uses",
    "tool.call.failed": "uses",
    "message.sent": "communicates_with",
    "delegation.created": "delegates_to",
    "node.transition": "transitions_to",
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
    if source_type == "tool" and target_type == "service":
        return "connects_to"
    if source_type == "service" and target_type == "capability":
        return "exposes"
    if target_type in {"agent", "service", "process"}:
        return "communicates_with"
    return None


def is_relationship_valid(relationship_type: str, source_type: str, target_type: str) -> bool:
    spec = RELATIONSHIP_TYPES.get(relationship_type)
    if not spec:
        return False
    return source_type in spec.source_types and target_type in spec.target_types


def relationship_registry() -> list[dict[str, object]]:
    return [asdict(spec) for spec in RELATIONSHIP_TYPES.values()]
