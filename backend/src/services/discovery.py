from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from .node_types import node_type_definition, node_type_registry, validate_node


def _empty_registry() -> dict[str, list[dict[str, Any]]]:
    categories = {definition["category"] for definition in node_type_registry()}
    return {category: [] for category in sorted(categories)}


def _status_from_event(event_type: str, severity: Optional[str]) -> str:
    if severity == "error" or event_type.endswith(".failed"):
        return "failed"
    if event_type.endswith(".started"):
        return "active"
    if event_type.endswith(".completed"):
        return "completed"
    return "observed"


def _framework_name(node: dict[str, Any]) -> Optional[str]:
    metadata = node.get("metadata") or {}
    framework = metadata.get("framework")
    if framework:
        return str(framework)
    runtime = node.get("runtime")
    if runtime in {"langgraph"}:
        return "langgraph"
    return None


def _display_framework_name(name: str) -> str:
    known = {"langgraph": "LangGraph"}
    return known.get(name.lower(), name)


def _new_entry(
    node: dict[str, Any],
    category: str,
    timestamp: str,
    event_type: str,
    severity: Optional[str],
) -> dict[str, Any]:
    validation = validate_node(node)
    return {
        "id": node["node_id"],
        "name": node["name"],
        "type": node["node_type"],
        "category": category,
        "type_definition": validation["definition"],
        "validation_status": validation["status"],
        "validation_errors": validation["errors"],
        "validation_warnings": validation["warnings"],
        "runtime": node.get("runtime"),
        "metadata": node.get("metadata") or {},
        "status": _status_from_event(event_type, severity),
        "last_seen": timestamp,
        "event_count": 0,
        "relationship_count": 0,
    }


def _touch_entry(
    entry: dict[str, Any], timestamp: str, event_type: str, severity: Optional[str]
) -> None:
    entry["event_count"] += 1
    if timestamp >= (entry.get("last_seen") or ""):
        entry["last_seen"] = timestamp
        entry["status"] = _status_from_event(event_type, severity)


def build_discovery(
    records: Iterable[OpenMeshEventRecord],
) -> dict[str, list[dict[str, Any]]]:
    registry = _empty_registry()
    entries: dict[str, dict[str, Any]] = {}
    framework_entries: dict[str, dict[str, Any]] = {}

    ordered = sorted(records, key=lambda record: record.timestamp)
    for record in ordered:
        timestamp = record.timestamp.isoformat() + "Z"
        nodes = [node for node in (record.source_json, record.target_json) if node]

        for node in nodes:
            framework = _framework_name(node)
            if framework:
                framework_key = framework.lower()
                framework_entry = framework_entries.setdefault(
                    framework_key,
                    {
                        "id": framework_key,
                        "name": _display_framework_name(framework),
                        "type": "framework",
                        "category": "frameworks",
                        "type_definition": node_type_definition("framework"),
                        "validation_status": "valid",
                        "validation_errors": [],
                        "validation_warnings": [],
                        "runtime": framework,
                        "metadata": {"framework": framework},
                        "status": "observed",
                        "last_seen": timestamp,
                        "event_count": 0,
                        "relationship_count": 0,
                    },
                )
                _touch_entry(
                    framework_entry, timestamp, record.event_type, record.severity
                )

            definition = node_type_definition(node.get("node_type"))
            if not definition:
                continue
            category = str(definition["category"])
            entry_key = (
                f"process:{node['name']}"
                if category == "processes"
                else node["node_id"]
            )
            entry = entries.setdefault(
                entry_key,
                _new_entry(
                    node, category, timestamp, record.event_type, record.severity
                ),
            )
            _touch_entry(entry, timestamp, record.event_type, record.severity)

        if record.source_json and record.target_json:
            for node in (record.source_json, record.target_json):
                definition = node_type_definition(node.get("node_type"))
                category = str(definition["category"]) if definition else None
                entry_key = (
                    f"process:{node['name']}"
                    if category == "processes"
                    else node["node_id"]
                )
                if entry_key in entries:
                    entries[entry_key]["relationship_count"] += 1
            for node in (record.source_json, record.target_json):
                framework = _framework_name(node)
                if framework and framework.lower() in framework_entries:
                    framework_entries[framework.lower()]["relationship_count"] += 1

    for entry in entries.values():
        registry[entry["category"]].append(entry)
    registry["frameworks"] = list(framework_entries.values())

    for values in registry.values():
        values.sort(key=lambda item: (item["name"].lower(), item["id"]))

    return registry


async def get_discovery(
    db: AsyncSession, limit: int = 5000
) -> dict[str, list[dict[str, Any]]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_discovery(records)
