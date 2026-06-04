from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from ..db.models import OpenMeshEventRecord
from .node_types import node_type_registry, validate_node
from .registry_compatibility import registry_versions
from .relationship_types import (
    relationship_definition,
    relationship_registry,
    relationship_type_for,
    validate_relationship,
)


ACTIVE_AFTER = timedelta(hours=1)
STALE_AFTER = timedelta(hours=24)


def _node_from_json(
    node: Optional[Dict[str, Any]], fallback_id: str
) -> Optional[Dict[str, Any]]:
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
        "trace_ids": [],
        "session_ids": [],
        "event_ids": [],
        "observations": [],
        "last_seen": None,
        "provenance": {},
    }


def edge_type_for(
    event_type: str,
    target_type: Optional[str],
    source_type: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if isinstance(payload, dict):
        explicit_relationship = payload.get("relationship_type")
        if isinstance(explicit_relationship, str) and relationship_definition(
            explicit_relationship
        ):
            return explicit_relationship
    return relationship_type_for(
        event_type, source_type=source_type, target_type=target_type
    )


def _edge_type_for(
    event_type: str,
    target_type: Optional[str],
    source_type: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    return edge_type_for(event_type, target_type, source_type, payload=payload)


def _node_evidence(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": node["id"],
        "node_type": node["type"],
        "name": node["name"],
    }


def _event_evidence(
    record: OpenMeshEventRecord,
    *,
    event_id: str,
    trace_id: str | None,
    source: Dict[str, Any],
    target: Dict[str, Any],
    timestamp: str,
) -> Dict[str, Any]:
    payload = getattr(record, "payload_json", None) or {}
    return {
        "event_id": event_id,
        "event_type": record.event_type,
        "trace_id": trace_id,
        "session_id": getattr(record, "session_id", None),
        "span_id": getattr(record, "span_id", None),
        "timestamp": timestamp,
        "source": _node_evidence(source),
        "target": _node_evidence(target),
        "payload_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
    }


def _node_observation(
    record: OpenMeshEventRecord,
    *,
    event_id: str,
    trace_id: str | None,
    node: Dict[str, Any],
    role: str,
    timestamp: str,
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": record.event_type,
        "trace_id": trace_id,
        "session_id": getattr(record, "session_id", None),
        "span_id": getattr(record, "span_id", None),
        "timestamp": timestamp,
        "role": role,
        "node": _node_evidence(node),
    }


def _dedupe_append(values: list[Any], value: Any) -> None:
    if value and value not in values:
        values.append(value)


def _sync_node_provenance(node: Dict[str, Any]) -> None:
    observations = node.get("observations", [])
    node["provenance"] = {
        "node_id": node["id"],
        "node_type": node["type"],
        "event_ids": list(node.get("event_ids", [])),
        "trace_ids": list(node.get("trace_ids", [])),
        "session_ids": list(node.get("session_ids", [])),
        "first_seen": node.get("first_seen"),
        "last_seen": node.get("last_seen"),
        "first_event_id": node.get("first_event_id"),
        "last_event_id": node.get("last_event_id"),
        "observations": observations,
    }


def _sync_edge_provenance(edge: Dict[str, Any]) -> None:
    observations = edge.get("observations", [])
    edge["provenance"] = {
        "source": edge["source"],
        "target": edge["target"],
        "relationship_type": edge["type"],
        "event_ids": list(edge.get("event_ids", [])),
        "trace_ids": list(edge.get("trace_ids", [])),
        "session_ids": list(edge.get("session_ids", [])),
        "span_ids": list(edge.get("span_ids", [])),
        "first_seen": edge.get("first_seen"),
        "last_seen": edge.get("last_seen"),
        "first_event_id": edge.get("first_event_id"),
        "last_event_id": edge.get("last_event_id"),
        "first_trace_id": edge.get("first_trace_id"),
        "last_trace_id": edge.get("last_trace_id"),
        "observations": observations,
    }


def reduce_graph_state(records: Iterable[OpenMeshEventRecord]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[str, Dict[str, Any]] = {}
    now = datetime.utcnow()

    for record in sorted(records, key=lambda item: item.timestamp):
        event_id = getattr(
            record, "event_id", f"{record.event_type}:{record.timestamp.isoformat()}"
        )
        source = _node_from_json(record.source_json, f"invalid:{event_id}:source")
        target = _node_from_json(record.target_json, f"invalid:{event_id}:target")
        timestamp = _normalize_datetime(record.timestamp)
        timestamp_text = timestamp.isoformat() + "Z"

        for role, node in (("source", source), ("target", target)):
            if not node:
                continue
            existing = nodes.get(node["id"], node)
            existing["event_count"] = existing.get("event_count", 0) + 1
            if not existing.get("first_seen"):
                existing["first_seen"] = timestamp_text
                existing["first_event_id"] = event_id
            existing["last_seen"] = timestamp_text
            existing["last_event_id"] = event_id
            _dedupe_append(existing["trace_ids"], getattr(record, "trace_id", None))
            _dedupe_append(existing["session_ids"], getattr(record, "session_id", None))
            _dedupe_append(existing["event_ids"], event_id)
            existing["observations"].append(
                _node_observation(
                    record,
                    event_id=event_id,
                    trace_id=getattr(record, "trace_id", None),
                    node=existing,
                    role=role,
                    timestamp=timestamp_text,
                )
            )
            _sync_node_provenance(existing)
            nodes[node["id"]] = existing

        if source and target:
            edge_type = _edge_type_for(
                record.event_type,
                target["type"],
                source["type"],
                payload=getattr(record, "payload_json", None),
            )
            if edge_type:
                trace_id = getattr(record, "trace_id", None)
                edge_id = f"{source['id']}:{edge_type}:{target['id']}"
                relationship_validation = validate_relationship(
                    edge_type, source["type"], target["type"]
                )
                edge = edges.get(
                    edge_id,
                    {
                        "id": edge_id,
                        "source": source["id"],
                        "target": target["id"],
                        "type": edge_type,
                        "relationship_type": edge_type,
                        "relationship_definition": relationship_validation[
                            "definition"
                        ],
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
                        "session_ids": [],
                        "event_ids": [],
                        "span_ids": [],
                        "last_event_id": None,
                        "observations": [],
                        "provenance": {},
                    },
                )
                edge["event_count"] += 1
                edge["observation_count"] += 1
                edge["last_seen"] = timestamp_text
                edge["last_trace_id"] = trace_id
                edge["last_event_id"] = event_id
                span_id = getattr(record, "span_id", None)
                _dedupe_append(edge["trace_ids"], trace_id)
                _dedupe_append(edge["session_ids"], getattr(record, "session_id", None))
                _dedupe_append(edge["event_ids"], event_id)
                _dedupe_append(edge["span_ids"], span_id)
                edge["observations"].append(
                    _event_evidence(
                        record,
                        event_id=event_id,
                        trace_id=trace_id,
                        source=source,
                        target=target,
                        timestamp=timestamp_text,
                    )
                )
                _sync_edge_provenance(edge)
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


def validate_graph_state(
    nodes: Dict[str, Dict[str, Any]], edges: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
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
        node_validation_statuses[node["id"]] = (
            "invalid" if errors else "warning" if warnings else "valid"
        )
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
        if (
            "invalid_node_metadata" in error_codes
            or "unsupported_node_metadata" in warning_codes
        ):
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
        source_status = source.get("validation_status") or node_validation_statuses.get(
            source["id"]
        )
        target_status = target.get("validation_status") or node_validation_statuses.get(
            target["id"]
        )
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
        relationship_validation = validate_relationship(
            edge["type"], source["type"], target["type"]
        )
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
        warning_codes = {
            warning["code"] for warning in relationship_validation.get("warnings", [])
        }
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
        if (
            not edge.get("trace_id")
            or not edge.get("event_id")
            or not edge.get("first_seen")
            or not edge.get("last_seen")
            or not _valid_edge_provenance(edge)
        ):
            missing_provenance.append(edge["id"])

    orphan_nodes = sorted(node_id for node_id in nodes if node_id not in incident_nodes)
    node_issues = (
        unknown_node_types
        or invalid_node_metadata
        or missing_required_identifiers
        or invalid_node_categories
        or removed_node_types
    )
    errors = (
        broken_references
        or invalid_relationships
        or invalid_relationship_endpoints
        or missing_provenance
        or node_issues
    )
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
    observed_at = _normalize_datetime(
        datetime.fromisoformat(last_seen.replace("Z", ""))
    )
    age = now - observed_at
    if age <= ACTIVE_AFTER:
        return "active"
    if age <= STALE_AFTER:
        return "stale"
    return "inactive"


def _valid_edge_provenance(edge: Dict[str, Any]) -> bool:
    provenance = edge.get("provenance")
    if not isinstance(provenance, dict):
        return False
    return all(
        [
            provenance.get("event_ids"),
            provenance.get("trace_ids"),
            provenance.get("first_seen"),
            provenance.get("last_seen"),
            provenance.get("observations"),
        ]
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)
