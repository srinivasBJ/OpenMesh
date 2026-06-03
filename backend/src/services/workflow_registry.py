from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event
from .openmesh_collector import collector


WORKFLOW_REGISTRY_SOURCE: OpenMeshNode = {
    "node_id": "openmesh.workflow_registry",
    "node_type": "service",
    "name": "OpenMesh Workflow Registry",
    "runtime": "openmesh.discovery",
}


@dataclass(frozen=True)
class WorkflowEntry:
    workflow: str
    framework: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "framework": self.framework,
            "version": self.version,
            "source": self.source,
            "metadata": self.metadata or {},
        }


def workflow_node(entry: WorkflowEntry | dict[str, Any]) -> OpenMeshNode:
    raw = entry.to_dict() if isinstance(entry, WorkflowEntry) else entry
    metadata = {
        "framework": raw.get("framework"),
        "version": raw.get("version"),
        "source": raw.get("source"),
    }
    if isinstance(raw.get("metadata"), dict):
        metadata.update(raw["metadata"])
    return {
        "node_id": raw.get("node_id")
        or f"workflow:{_stable_id(str(raw.get('framework') or raw.get('source') or 'openmesh'))}:{_stable_id(str(raw.get('workflow') or raw.get('name') or 'workflow'))}",
        "node_type": "workflow",
        "name": str(raw.get("workflow") or raw.get("name") or "Unknown Workflow"),
        "runtime": str(raw.get("framework") or "workflow"),
        "metadata": {
            key: value for key, value in metadata.items() if value is not None
        },
    }


def build_workflow_registry(
    records: Iterable[OpenMeshEventRecord],
) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for record in sorted(records, key=lambda item: item.timestamp):
        timestamp = record.timestamp.isoformat() + "Z"
        for node in (record.source_json, record.target_json):
            if not node or node.get("node_type") != "workflow":
                continue
            payload = record.payload_json or {}
            metadata = node.get("metadata") or {}
            entry = entries.setdefault(
                node["node_id"],
                {
                    "id": node["node_id"],
                    "workflow": node.get("name"),
                    "name": node.get("name"),
                    "framework": payload.get("framework")
                    or metadata.get("framework")
                    or node.get("runtime"),
                    "version": payload.get("version") or metadata.get("version"),
                    "source": payload.get("source") or metadata.get("source"),
                    "last_seen": timestamp,
                    "event_count": 0,
                    "relationship_count": 0,
                    "metadata": metadata,
                },
            )
            entry["workflow"] = node.get("name", entry.get("workflow"))
            entry["name"] = node.get("name", entry.get("name"))
            entry["framework"] = payload.get(
                "framework", entry.get("framework")
            ) or metadata.get("framework")
            entry["version"] = payload.get(
                "version", entry.get("version")
            ) or metadata.get("version")
            entry["source"] = payload.get(
                "source", entry.get("source")
            ) or metadata.get("source")
            entry["metadata"] = {**entry.get("metadata", {}), **metadata}
            entry["event_count"] += 1
            entry["last_seen"] = timestamp

        if record.source_json and record.target_json:
            for node in (record.source_json, record.target_json):
                if (
                    node
                    and node.get("node_type") == "workflow"
                    and node["node_id"] in entries
                ):
                    entries[node["node_id"]]["relationship_count"] += 1

    return sorted(
        entries.values(),
        key=lambda item: (str(item.get("workflow")).lower(), item["id"]),
    )


async def get_workflow_registry(
    db: AsyncSession, limit: int = 5000
) -> list[dict[str, Any]]:
    records = await list_openmesh_events(db, limit=limit)
    return build_workflow_registry(records)


async def register_workflow(
    db: AsyncSession,
    entry: WorkflowEntry,
    *,
    source: Optional[OpenMeshNode] = None,
    broadcast: bool = True,
) -> dict[str, Any]:
    target = workflow_node(entry)
    event = make_openmesh_event(
        "workflow.registered",
        source or WORKFLOW_REGISTRY_SOURCE,
        {
            **entry.to_dict(),
            "registered_at": datetime.utcnow().isoformat() + "Z",
        },
        target=target,
    )
    return await collector.accept(db, event, broadcast=broadcast)


def validate_workflow_entries(
    entries: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    seen: dict[tuple[str, str], list[dict[str, Any]]] = {}
    missing = []
    malformed = []
    for entry in entries:
        missing_fields = [
            field
            for field in ("workflow", "framework", "source")
            if not entry.get(field)
        ]
        if missing_fields:
            missing.append({"entry": entry, "missing": missing_fields})
        metadata = entry.get("metadata", {})
        if metadata is not None and not isinstance(metadata, dict):
            malformed.append(
                {
                    "entry": entry,
                    "field": "metadata",
                    "message": "metadata must be an object",
                }
            )
        seen.setdefault(
            (str(entry.get("framework")), str(entry.get("workflow"))), []
        ).append(entry)
    duplicates = [
        {"framework": framework, "workflow": workflow, "count": len(values)}
        for (framework, workflow), values in seen.items()
        if len(values) > 1
    ]
    return {
        "duplicates": duplicates,
        "malformed_metadata": malformed,
        "missing_required_metadata": missing,
    }


def _stable_id(value: str) -> str:
    return (
        "".join(
            character.lower() if character.isalnum() else "-" for character in value
        ).strip("-")
        or "workflow"
    )
