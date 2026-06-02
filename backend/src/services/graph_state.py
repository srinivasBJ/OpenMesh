from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from ..db.models import OpenMeshEventRecord
from .relationship_types import is_relationship_valid, relationship_registry, relationship_type_for


ACTIVE_AFTER = timedelta(hours=1)
STALE_AFTER = timedelta(hours=24)


def _node_from_json(node: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not node:
        return None
    return {
        "id": node["node_id"],
        "type": node["node_type"],
        "name": node["name"],
        "runtime": node.get("runtime"),
        "metadata": node.get("metadata", {}),
        "event_count": 0,
        "last_seen": None,
    }


def edge_type_for(event_type: str, target_type: Optional[str], source_type: Optional[str] = None) -> Optional[str]:
    return relationship_type_for(event_type, source_type=source_type, target_type=target_type)


def _edge_type_for(
    event_type: str,
    target_type: Optional[str],
    source_type: Optional[str] = None,
) -> Optional[str]:
    return edge_type_for(event_type, target_type, source_type)


def reduce_graph_state(records: Iterable[OpenMeshEventRecord]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[str, Dict[str, Any]] = {}
    now = datetime.utcnow()

    for record in sorted(records, key=lambda item: item.timestamp):
        source = _node_from_json(record.source_json)
        target = _node_from_json(record.target_json)
        timestamp = _normalize_datetime(record.timestamp)
        timestamp_text = timestamp.isoformat() + "Z"

        for node in (source, target):
            if not node:
                continue
            existing = nodes.get(node["id"], node)
            existing["event_count"] = existing.get("event_count", 0) + 1
            if not existing.get("first_seen"):
                existing["first_seen"] = timestamp_text
            existing["last_seen"] = timestamp_text
            nodes[node["id"]] = existing

        if source and target:
            edge_type = _edge_type_for(record.event_type, target["type"], source["type"])
            if edge_type:
                event_id = getattr(record, "event_id", f"{record.event_type}:{timestamp.isoformat()}")
                trace_id = getattr(record, "trace_id", None)
                edge_id = f"{source['id']}:{edge_type}:{target['id']}"
                edge = edges.get(edge_id, {
                    "id": edge_id,
                    "source": source["id"],
                    "target": target["id"],
                    "type": edge_type,
                    "relationship_type": edge_type,
                    "event_count": 0,
                    "observation_count": 0,
                    "first_seen": timestamp_text,
                    "last_seen": None,
                    "trace_id": trace_id,
                    "event_id": event_id,
                    "first_trace_id": trace_id,
                    "first_event_id": event_id,
                    "last_trace_id": trace_id,
                    "trace_ids": [],
                    "event_ids": [],
                    "last_event_id": None,
                    "observations": [],
                })
                edge["event_count"] += 1
                edge["observation_count"] += 1
                edge["last_seen"] = timestamp_text
                edge["last_trace_id"] = trace_id
                edge["last_event_id"] = event_id
                if trace_id and trace_id not in edge["trace_ids"]:
                    edge["trace_ids"].append(trace_id)
                if event_id not in edge["event_ids"]:
                    edge["event_ids"].append(event_id)
                edge["observations"].append(
                    {
                        "trace_id": trace_id,
                        "event_id": event_id,
                        "event_type": record.event_type,
                        "span_id": getattr(record, "span_id", None),
                        "timestamp": timestamp_text,
                    }
                )
                edges[edge_id] = edge

    for edge in edges.values():
        edge["lifecycle_state"] = _lifecycle_state(edge["last_seen"], now)

    validation = validate_graph_state(nodes, edges)
    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "metadata": {
            "generated_at": now.isoformat() + "Z",
            "relationship_types": relationship_registry(),
            "lifecycle": {
                "active_after_seconds": int(ACTIVE_AFTER.total_seconds()),
                "stale_after_seconds": int(STALE_AFTER.total_seconds()),
            },
        },
        "validation": validation,
    }


def validate_graph_state(nodes: Dict[str, Dict[str, Any]], edges: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    incident_nodes = set()
    broken_references = []
    invalid_relationships = []
    missing_provenance = []

    for edge in edges.values():
        source = nodes.get(edge["source"])
        target = nodes.get(edge["target"])
        if not source or not target:
            broken_references.append(edge["id"])
            continue
        incident_nodes.add(edge["source"])
        incident_nodes.add(edge["target"])
        if not is_relationship_valid(edge["type"], source["type"], target["type"]):
            invalid_relationships.append(
                {
                    "edge_id": edge["id"],
                    "type": edge["type"],
                    "source_type": source["type"],
                    "target_type": target["type"],
                }
            )
        if not edge.get("trace_id") or not edge.get("event_id") or not edge.get("first_seen") or not edge.get("last_seen"):
            missing_provenance.append(edge["id"])

    orphan_nodes = sorted(node_id for node_id in nodes if node_id not in incident_nodes)
    status = "OK" if not broken_references and not invalid_relationships and not missing_provenance else "WARNING"
    return {
        "status": status,
        "orphan_nodes": orphan_nodes,
        "invalid_relationships": invalid_relationships,
        "missing_provenance": missing_provenance,
        "broken_references": broken_references,
    }


def _lifecycle_state(last_seen: str | None, now: datetime) -> str:
    if not last_seen:
        return "inactive"
    observed_at = _normalize_datetime(datetime.fromisoformat(last_seen.replace("Z", "")))
    age = now - observed_at
    if age <= ACTIVE_AFTER:
        return "active"
    if age <= STALE_AFTER:
        return "stale"
    return "inactive"


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
