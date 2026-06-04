from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from .graph_state import reduce_graph_state
from .mcp_config_discovery import build_mcp_config_registry


ECOSYSTEM_NODE_TYPES = {
    "agent": "agents",
    "tool": "tools",
    "process": "processes",
    "workflow": "workflows",
    "mcp_server": "mcp_servers",
    "capability": "capabilities",
    "openmesh_node": "nodes",
}
ECOSYSTEM_GROUPS = (*ECOSYSTEM_NODE_TYPES.values(), "mcp_configs")


def build_ecosystem_registry(records: Iterable[OpenMeshEventRecord]) -> dict[str, Any]:
    record_list = list(records)
    graph = reduce_graph_state(record_list)
    relationship_counts = _relationship_counts(graph.get("edges", []))
    registry: dict[str, list[dict[str, Any]]] = {
        group: [] for group in ECOSYSTEM_GROUPS
    }

    for node in graph.get("nodes", []):
        group = ECOSYSTEM_NODE_TYPES.get(node.get("type"))
        if not group:
            continue
        entity = _entity_from_node(node, relationship_counts.get(node["id"], 0))
        registry[group].append(entity)

    for config in build_mcp_config_registry(record_list):
        registry["mcp_configs"].append(_entity_from_config(config))

    for entities in registry.values():
        entities.sort(key=lambda item: (str(item["name"]).lower(), item["id"]))

    entities = [entity for group in ECOSYSTEM_GROUPS for entity in registry[group]]
    validation = validate_ecosystem_entities(entities)
    return {
        "entities": registry,
        "summary": {
            "entity_count": len(entities),
            "relationship_count": len(graph.get("edges", [])),
            "groups": {group: len(registry[group]) for group in ECOSYSTEM_GROUPS},
        },
        "validation": validation,
    }


async def get_ecosystem_registry(db: AsyncSession, limit: int = 5000) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    return build_ecosystem_registry(records)


def validate_ecosystem_entities(entities: Iterable[dict[str, Any]]) -> dict[str, Any]:
    entity_list = list(entities)
    by_type_name: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    orphan_entities = []
    missing_relationships = []
    conflicting_definitions = []

    for entity in entity_list:
        by_type_name[(str(entity.get("type")), str(entity.get("name")).lower())].append(
            entity
        )
        by_id[str(entity.get("id"))].append(entity)
        if entity.get("relationship_count", 0) == 0:
            orphan_entities.append(entity)
        if (
            entity.get("type")
            in {"agent", "tool", "workflow", "mcp_server", "capability"}
            and entity.get("relationship_count", 0) == 0
        ):
            missing_relationships.append(entity)

    duplicates = [
        {
            "type": entity_type,
            "name": name,
            "count": len(values),
            "ids": [item["id"] for item in values],
        }
        for (entity_type, name), values in by_type_name.items()
        if len(values) > 1
    ]

    for entity_id, values in by_id.items():
        signatures = {
            (
                item.get("type"),
                item.get("name"),
                tuple(
                    sorted(
                        (key, repr(value))
                        for key, value in (item.get("metadata") or {}).items()
                    )
                ),
            )
            for item in values
        }
        if len(signatures) > 1:
            conflicting_definitions.append({"id": entity_id, "definitions": values})

    status = "OK"
    if duplicates or conflicting_definitions:
        status = "ERROR"
    elif orphan_entities or missing_relationships:
        status = "WARNING"

    return {
        "status": status,
        "duplicate_entities": duplicates,
        "conflicting_definitions": conflicting_definitions,
        "orphan_entities": orphan_entities,
        "missing_relationships": missing_relationships,
    }


def _entity_from_node(node: dict[str, Any], relationship_count: int) -> dict[str, Any]:
    return {
        "id": node["id"],
        "type": node["type"],
        "name": node["name"],
        "status": node.get("lifecycle_state", "observed"),
        "first_seen": node.get("first_seen"),
        "last_seen": node.get("last_seen"),
        "relationship_count": relationship_count,
        "event_count": node.get("event_count", 0),
        "metadata": node.get("metadata") or {},
    }


def _entity_from_config(config: dict[str, Any]) -> dict[str, Any]:
    entity_id = f"mcp_config:{_stable_id(str(config.get('source')))}:{_stable_id(str(config.get('config_path')))}:{_stable_id(str(config.get('server')))}"
    return {
        "id": entity_id,
        "type": "mcp_config",
        "name": f"{config.get('source')} -> {config.get('server')}",
        "status": "observed",
        "first_seen": config.get("first_seen") or config.get("last_seen"),
        "last_seen": config.get("last_seen"),
        "relationship_count": config.get(
            "relationship_count", 1 if config.get("server") else 0
        ),
        "event_count": config.get("event_count", 0),
        "metadata": {
            "source": config.get("source"),
            "config_path": config.get("config_path"),
            "server": config.get("server"),
            "transport": config.get("transport"),
            "endpoint": config.get("endpoint"),
            "version": config.get("version"),
        },
    }


def _relationship_counts(edges: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for edge in edges:
        counts[edge["source"]] += 1
        counts[edge["target"]] += 1
    return counts


def _stable_id(value: str) -> str:
    return (
        "".join(
            character.lower() if character.isalnum() else "-" for character in value
        ).strip("-")
        or "entity"
    )
