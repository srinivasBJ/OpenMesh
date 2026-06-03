from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from ..db.models import OpenMeshEventRecord
from .node_types import node_type_registry, validate_node
from .registry_compatibility import registry_versions
from .relationship_types import relationship_registry, relationship_type_for, validate_relationship


ACTIVE_AFTER = timedelta(hours=1)
STALE_AFTER = timedelta(hours=24)


def _node_from_json(node: Optional[Dict[str, Any]], fallback_id: str) -> Optional[Dict[str, Any]]:
    if not node:
        return None
    validation = validate_node(node)
    definition = validation["definition"] or {}
    return {
        "id": node.get("node_id") or fallback_id,
        "type": node.get("node_type") or "unknown",
        "name": node.get("name") or node.get("node_id") or "Unknown Node",
        "category": definition.get("category", "unknown"),
        "type_definition": validation["definition"],
        "validation_status": validation["status"],
        "validation_errors": validation["errors"],
        "validation_warnings": validation["warnings"],
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
        event_id = getattr(record, "event_id", f"{record.event_type}:{record.timestamp.isoformat()}")
        source = _node_from_json(record.source_json, f"invalid:{event_id}:source")
        target = _node_from_json(record.target_json, f"invalid:{event_id}:target")
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
                trace_id = getattr(record, "trace_id", None)
                edge_id = f"{source['id']}:{edge_type}:{target['id']}"
                relationship_validation = validate_relationship(edge_type, source["type"], target["type"])
                edge = edges.get(edge_id, {
                    "id": edge_id,
                    "source": source["id"],
                    "target": target["id"],
                    "type": edge_type,
                    "relationship_type": edge_type,
                    "relationship_definition": relationship_validation["definition"],
                    "validation_status": relationship_validation["status"],
                    "validation_errors": relationship_validation["errors"],
                    "validation_warnings": relationship_validation["warnings"],
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

    for node in nodes.values():
        node["lifecycle_state"] = _lifecycle_state(node["last_seen"], now)

    for edge in edges.values():
        edge["lifecycle_state"] = _lifecycle_state(edge["last_seen"], now)

    validation = validate_graph_state(nodes, edges)
    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "metadata": {
            "generated_at": now.isoformat() + "Z",
            "registry_versions": registry_versions(),
            "node_types": node_type_registry(),
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
    invalid_relationship_types = []
    invalid_source_types = []
    invalid_target_types = []
    unknown_node_types = []
    invalid_node_metadata = []
    missing_required_identifiers = []
    invalid_node_categories = []
    invalid_relationship_endpoints = []
    deprecated_node_types = []
    removed_node_types = []
    deprecated_relationship_types = []
    removed_relationship_types = []
    missing_provenance = []
    node_validation_statuses: dict[str, str] = {}

    for node in nodes.values():
        validation = validate_node(
            {
                "node_id": node.get("id"),
                "node_type": node.get("type"),
                "name": node.get("name"),
                "metadata": node.get("metadata", {}),
            }
        )
        errors = node.get("validation_errors", validation["errors"])
        warnings = node.get("validation_warnings", validation["warnings"])
        error_codes = {error["code"] for error in errors}
        warning_codes = {warning["code"] for warning in warnings}
        node_validation_statuses[node["id"]] = "invalid" if errors else "warning" if warnings else "valid"
        detail = {
            "node_id": node["id"],
            "type": node["type"],
            "category": node.get("category"),
            "errors": errors,
            "warnings": warnings,
        }
        if "unknown_node_type" in error_codes:
            unknown_node_types.append(detail)
        if "removed_node_type" in error_codes:
            removed_node_types.append(detail)
        if "deprecated_node_type" in warning_codes:
            deprecated_node_types.append(detail)
        if "invalid_node_metadata" in error_codes or "unsupported_node_metadata" in warning_codes:
            invalid_node_metadata.append(detail)
        if "missing_required_identifiers" in error_codes:
            missing_required_identifiers.append(detail)
        definition = node.get("type_definition") or validation["definition"]
        if definition and node.get("category") != definition.get("category"):
            invalid_node_categories.append(detail)

    for edge in edges.values():
        source = nodes.get(edge["source"])
        target = nodes.get(edge["target"])
        if not source or not target:
            broken_references.append(edge["id"])
            continue
        incident_nodes.add(edge["source"])
        incident_nodes.add(edge["target"])
        source_status = source.get("validation_status") or node_validation_statuses.get(source["id"])
        target_status = target.get("validation_status") or node_validation_statuses.get(target["id"])
        if source_status == "invalid" or target_status == "invalid":
            invalid_relationship_endpoints.append(
                {
                    "edge_id": edge["id"],
                    "source": source["id"],
                    "target": target["id"],
                    "source_status": source_status,
                    "target_status": target_status,
                }
            )
        relationship_validation = validate_relationship(edge["type"], source["type"], target["type"])
        if not relationship_validation["valid"]:
            invalid_relationship = {
                "edge_id": edge["id"],
                "type": edge["type"],
                "source_type": source["type"],
                "target_type": target["type"],
                "errors": relationship_validation["errors"],
            }
            invalid_relationships.append(invalid_relationship)
            error_codes = {error["code"] for error in relationship_validation["errors"]}
            if "invalid_relationship_type" in error_codes:
                invalid_relationship_types.append(invalid_relationship)
            if "invalid_source_type" in error_codes:
                invalid_source_types.append(invalid_relationship)
            if "invalid_target_type" in error_codes:
                invalid_target_types.append(invalid_relationship)
            if "removed_relationship_type" in error_codes:
                removed_relationship_types.append(invalid_relationship)
        warning_codes = {warning["code"] for warning in relationship_validation.get("warnings", [])}
        if "deprecated_relationship_type" in warning_codes:
            deprecated_relationship_types.append(
                {
                    "edge_id": edge["id"],
                    "type": edge["type"],
                    "source_type": source["type"],
                    "target_type": target["type"],
                    "warnings": relationship_validation["warnings"],
                }
            )
        if not edge.get("trace_id") or not edge.get("event_id") or not edge.get("first_seen") or not edge.get("last_seen"):
            missing_provenance.append(edge["id"])

    orphan_nodes = sorted(node_id for node_id in nodes if node_id not in incident_nodes)
    node_issues = (
        unknown_node_types
        or invalid_node_metadata
        or missing_required_identifiers
        or invalid_node_categories
        or removed_node_types
    )
    errors = broken_references or invalid_relationships or invalid_relationship_endpoints or missing_provenance or node_issues
    warnings = deprecated_node_types or deprecated_relationship_types
    status = "OK" if not errors and not warnings else "WARNING"
    return {
        "status": status,
        "orphan_nodes": orphan_nodes,
        "unknown_node_types": unknown_node_types,
        "deprecated_node_types": deprecated_node_types,
        "removed_node_types": removed_node_types,
        "invalid_node_metadata": invalid_node_metadata,
        "missing_required_identifiers": missing_required_identifiers,
        "invalid_node_categories": invalid_node_categories,
        "invalid_relationship_endpoints": invalid_relationship_endpoints,
        "invalid_relationships": invalid_relationships,
        "invalid_relationship_types": invalid_relationship_types,
        "deprecated_relationship_types": deprecated_relationship_types,
        "removed_relationship_types": removed_relationship_types,
        "invalid_source_types": invalid_source_types,
        "invalid_target_types": invalid_target_types,
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
