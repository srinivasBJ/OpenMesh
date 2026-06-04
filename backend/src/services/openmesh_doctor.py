from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..exporters import build_exporter_diagnostics
from ..failures import build_failure_registry
from ..genome import genome_diagnostics
from ..reputation import reputation_diagnostics
from ..db.openmesh_events import list_openmesh_events, records_to_events
from ..db.session import ASYNC_URL, DATABASE_URL
from ..sdk.integrations import list_integrations
from .ecosystem_registry import build_ecosystem_registry
from .graph_state import reduce_graph_state
from .mcp_capabilities import build_capability_registry, validate_capability_entries
from .mcp_config_discovery import (
    build_mcp_config_registry,
    discover_mcp_configs,
    validate_mcp_config_entries,
)
from .openmesh_collector import collector
from .registry_status import build_registry_status
from .trace_semantics import build_span_summary, validate_trace_semantics
from .workflow_registry import build_workflow_registry, validate_workflow_entries


REQUIRED_TABLES = {
    "openmesh_events",
    "openmesh_sessions",
    "openmesh_snapshots",
    "agents",
    "agent_events",
}
ACTIVE_SPAN_WARNING_AFTER = timedelta(hours=1)


def _safe_url(url: str) -> str:
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***@{host}"


async def run_doctor(db: AsyncSession) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    try:
        await db.execute(text("SELECT 1"))
        checks.append(
            {
                "name": "database",
                "status": "OK",
                "severity": "INFO",
                "detail": "connection succeeded",
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "database",
                "status": "ERROR",
                "severity": "ERROR",
                "detail": str(exc),
            }
        )

    try:
        connection = await db.connection()
        tables = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )
        missing = sorted(REQUIRED_TABLES - tables)
        checks.append(
            {
                "name": "migrations",
                "status": "OK" if not missing else "ERROR",
                "severity": "INFO" if not missing else "ERROR",
                "detail": "all required tables exist"
                if not missing
                else f"missing tables: {', '.join(missing)}",
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "migrations",
                "status": "ERROR",
                "severity": "ERROR",
                "detail": str(exc),
            }
        )

    checks.append(
        {
            "name": "collector",
            "status": "OK" if collector else "ERROR",
            "severity": "INFO" if collector else "ERROR",
            "detail": "collector service importable",
        }
    )

    try:
        integrations = list_integrations()
        langgraph = next(
            (item for item in integrations if item["key"] == "langgraph"), None
        )
        checks.append(
            {
                "name": "Integration Health",
                "status": "OK",
                "severity": "INFO",
                "detail": {
                    "LangGraph": langgraph["status_label"] if langgraph else "Unknown",
                    "Graph Reducer": "OK",
                    "integrations": [
                        f"{item['name']}: {item['status_label']}"
                        for item in integrations
                    ],
                },
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "integration health",
                "status": "ERROR",
                "severity": "ERROR",
                "detail": str(exc),
            }
        )

    try:
        records = await list_openmesh_events(db, limit=5000)
        checks.extend(build_trace_diagnostics(records))
        checks.append(build_graph_diagnostics(records))
        checks.append(build_node_diagnostics(records))
        checks.append(build_relationship_diagnostics(records))
        checks.append(build_registry_compatibility_diagnostics(records))
        checks.append(build_capability_diagnostics(records))
        checks.append(build_workflow_registry_diagnostics(records))
        checks.append(build_ecosystem_diagnostics(records))
        checks.append(build_failure_intelligence_diagnostics(records))
        checks.append(reputation_diagnostics(records))
        checks.append(genome_diagnostics(records))
        checks.append(build_exporter_diagnostics(records))
        checks.append(
            build_mcp_config_diagnostics(records, discovered=discover_mcp_configs())
        )
    except Exception as exc:
        checks.append(
            {
                "name": "OpenMesh Diagnostics",
                "status": "ERROR",
                "severity": "ERROR",
                "detail": str(exc),
            }
        )

    migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
    migration_files = sorted(path.name for path in migrations_dir.glob("*.sql"))
    checks.append(
        {
            "name": "configuration",
            "status": "OK",
            "severity": "INFO",
            "detail": {
                "database_url": _safe_url(DATABASE_URL),
                "async_url": _safe_url(ASYNC_URL),
                "migrations": migration_files,
            },
        }
    )

    severities = {check.get("severity", check["status"]) for check in checks}
    return {
        "status": "ERROR"
        if "ERROR" in severities
        else "WARNING"
        if "WARNING" in severities
        else "OK",
        "checks": checks,
    }


def build_trace_diagnostics(
    records: list[Any], *, now: datetime | None = None
) -> list[dict[str, Any]]:
    now = now or datetime.utcnow()
    sorted_records = sorted(records, key=lambda item: item.timestamp)
    events = records_to_events(sorted_records)
    events_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    records_by_trace: dict[str, list[Any]] = defaultdict(list)
    for event, record in zip(events, sorted_records):
        events_by_trace[event["trace_id"]].append(event)
        records_by_trace[event["trace_id"]].append(record)

    trace_detail = {
        "traces_checked": len(events_by_trace),
        "broken_parent_span_events": [],
        "missing_root_event_events": [],
        "broken_root_event_events": [],
        "orphan_spans": [],
        "malformed_link_events": [],
        "invalid_cross_trace_links": [],
        "valid_cross_trace_links": 0,
        "long_running_active_spans": [],
    }
    workflow_detail = {
        "incomplete_workflow_spans": [],
    }

    all_trace_ids = set(events_by_trace)
    all_event_ids_by_trace = {
        trace_id: {event["event_id"] for event in trace_events}
        for trace_id, trace_events in events_by_trace.items()
    }
    all_span_ids_by_trace = {
        trace_id: {
            event.get("span_id") for event in trace_events if event.get("span_id")
        }
        for trace_id, trace_events in events_by_trace.items()
    }

    for trace_id, trace_events in events_by_trace.items():
        validation = validate_trace_semantics(trace_events)
        trace_detail["broken_parent_span_events"].extend(
            _with_trace(trace_id, event_id)
            for event_id in validation.get("missing_parent_spans", [])
        )
        trace_detail["malformed_link_events"].extend(
            _with_trace(trace_id, event_id)
            for event_id in validation.get("malformed_links", [])
        )

        trace_event_ids = all_event_ids_by_trace[trace_id]
        trace_span_ids = all_span_ids_by_trace[trace_id]
        for record in records_by_trace[trace_id]:
            root_event_id = getattr(record, "root_event_id", None)
            if not root_event_id:
                trace_detail["missing_root_event_events"].append(
                    _with_trace(trace_id, record.event_id)
                )
            elif root_event_id not in trace_event_ids:
                trace_detail["broken_root_event_events"].append(
                    {
                        "trace_id": trace_id,
                        "event_id": record.event_id,
                        "root_event_id": root_event_id,
                    }
                )

        spans = build_span_summary(trace_events)
        for span in spans:
            parent_span_id = span.get("parent_span_id")
            if parent_span_id and parent_span_id not in trace_span_ids:
                trace_detail["orphan_spans"].append(
                    {
                        "trace_id": trace_id,
                        "span_id": span["span_id"],
                        "parent_span_id": parent_span_id,
                    }
                )
            if span.get("status") == "active" and _is_long_running(
                span.get("started_at"), now
            ):
                trace_detail["long_running_active_spans"].append(
                    {
                        "trace_id": trace_id,
                        "span_id": span["span_id"],
                        "started_at": span.get("started_at"),
                    }
                )
            if "workflow.started" in span.get("event_types", []) and not any(
                event_type in {"workflow.completed", "workflow.failed"}
                for event_type in span.get("event_types", [])
            ):
                workflow_detail["incomplete_workflow_spans"].append(
                    {
                        "trace_id": trace_id,
                        "span_id": span["span_id"],
                        "started_at": span.get("started_at"),
                    }
                )

        for event in trace_events:
            for link in event.get("links", []):
                if not isinstance(link, dict):
                    continue
                linked_trace_id = link.get("trace_id")
                if not linked_trace_id or linked_trace_id == trace_id:
                    continue
                if _is_valid_cross_trace_link(
                    link, all_trace_ids, all_event_ids_by_trace, all_span_ids_by_trace
                ):
                    trace_detail["valid_cross_trace_links"] += 1
                else:
                    trace_detail["invalid_cross_trace_links"].append(
                        {
                            "trace_id": trace_id,
                            "event_id": event["event_id"],
                            "linked_trace_id": linked_trace_id,
                            "linked_span_id": link.get("span_id"),
                            "linked_event_id": link.get("event_id"),
                        }
                    )

    trace_errors = (
        trace_detail["broken_parent_span_events"]
        or trace_detail["missing_root_event_events"]
        or trace_detail["broken_root_event_events"]
        or trace_detail["orphan_spans"]
        or trace_detail["malformed_link_events"]
        or trace_detail["invalid_cross_trace_links"]
    )
    trace_warnings = trace_detail["long_running_active_spans"]
    workflow_warnings = workflow_detail["incomplete_workflow_spans"]

    return [
        {
            "name": "Trace Integrity",
            "status": "ERROR"
            if trace_errors
            else "WARNING"
            if trace_warnings
            else "OK",
            "severity": "ERROR"
            if trace_errors
            else "WARNING"
            if trace_warnings
            else "INFO",
            "detail": trace_detail,
        },
        {
            "name": "Workflow Integrity",
            "status": "WARNING" if workflow_warnings else "OK",
            "severity": "WARNING" if workflow_warnings else "INFO",
            "detail": workflow_detail,
        },
    ]


def build_graph_diagnostics(records: list[Any]) -> dict[str, Any]:
    graph = reduce_graph_state(records)
    validation = graph.get("validation", {})
    stale_edges = [
        {
            "edge_id": edge["id"],
            "relationship": edge["type"],
            "last_seen": edge.get("last_seen"),
            "state": edge.get("lifecycle_state"),
        }
        for edge in graph.get("edges", [])
        if edge.get("lifecycle_state") in {"stale", "inactive"}
    ]
    detail = {
        "nodes_checked": len(graph.get("nodes", [])),
        "edges_checked": len(graph.get("edges", [])),
        "missing_provenance": validation.get("missing_provenance", []),
        "invalid_relationships": validation.get("invalid_relationships", []),
        "broken_references": validation.get("broken_references", []),
        "stale_relationships": stale_edges,
    }
    errors = (
        detail["missing_provenance"]
        or detail["invalid_relationships"]
        or detail["broken_references"]
    )
    warnings = detail["stale_relationships"]
    return {
        "name": "Graph Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_relationship_diagnostics(records: list[Any]) -> dict[str, Any]:
    graph = reduce_graph_state(records)
    validation = graph.get("validation", {})
    invalid_relationships = validation.get("invalid_relationships", [])
    detail = {
        "edges_checked": len(graph.get("edges", [])),
        "valid_relationships": len(graph.get("edges", [])) - len(invalid_relationships),
        "invalid_relationship_types": validation.get("invalid_relationship_types", []),
        "deprecated_relationship_types": validation.get(
            "deprecated_relationship_types", []
        ),
        "removed_relationship_types": validation.get("removed_relationship_types", []),
        "invalid_source_types": validation.get("invalid_source_types", []),
        "invalid_target_types": validation.get("invalid_target_types", []),
    }
    errors = (
        detail["invalid_relationship_types"]
        or detail["removed_relationship_types"]
        or detail["invalid_source_types"]
        or detail["invalid_target_types"]
    )
    warnings = detail["deprecated_relationship_types"]
    return {
        "name": "Relationship Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_node_diagnostics(records: list[Any]) -> dict[str, Any]:
    graph = reduce_graph_state(records)
    validation = graph.get("validation", {})
    detail = {
        "nodes_checked": len(graph.get("nodes", [])),
        "unknown_node_types": validation.get("unknown_node_types", []),
        "deprecated_node_types": validation.get("deprecated_node_types", []),
        "removed_node_types": validation.get("removed_node_types", []),
        "invalid_node_metadata": validation.get("invalid_node_metadata", []),
        "missing_required_identifiers": validation.get(
            "missing_required_identifiers", []
        ),
        "invalid_node_categories": validation.get("invalid_node_categories", []),
        "invalid_relationship_endpoints": validation.get(
            "invalid_relationship_endpoints", []
        ),
    }
    errors = (
        detail["unknown_node_types"]
        or detail["removed_node_types"]
        or detail["missing_required_identifiers"]
        or detail["invalid_node_categories"]
        or detail["invalid_relationship_endpoints"]
    )
    warnings = detail["invalid_node_metadata"]
    warnings = warnings or detail["deprecated_node_types"]
    return {
        "name": "Node Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_registry_compatibility_diagnostics(
    records: list[Any],
    *,
    node_registry_version: str | None = None,
    relationship_registry_version: str | None = None,
) -> dict[str, Any]:
    status = build_registry_status(
        records,
        node_registry_version=node_registry_version,
        relationship_registry_version=relationship_registry_version,
    )
    compatibility = status["compatibility"]
    return {
        "name": "Registry Compatibility",
        "status": compatibility["status"],
        "severity": compatibility["severity"],
        "detail": {
            "versions": status["versions"],
            "checked_versions": status["checked_versions"],
            "rules": status["rules"],
            "warnings": compatibility["warnings"],
            "errors": compatibility["errors"],
        },
    }


def build_mcp_config_diagnostics(
    records: list[Any],
    *,
    discovered: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    persisted = build_mcp_config_registry(records)
    discovered = discovered or {"entries": [], "issues": []}
    validation = validate_mcp_config_entries(
        [*persisted, *discovered.get("entries", [])]
    )
    detail = {
        "persisted_configs": len(persisted),
        "discovered_configs": len(discovered.get("entries", [])),
        "duplicate_definitions": validation["duplicates"],
        "malformed_configs": discovered.get("issues", []),
        "missing_required_metadata": validation["missing_required_metadata"],
    }
    errors = detail["malformed_configs"] or detail["missing_required_metadata"]
    warnings = detail["duplicate_definitions"]
    return {
        "name": "MCP Configuration Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_capability_diagnostics(records: list[Any]) -> dict[str, Any]:
    capabilities = build_capability_registry(records)
    validation = validate_capability_entries(capabilities)
    detail = {
        "capabilities_checked": len(capabilities),
        "duplicate_capabilities": validation["duplicates"],
        "malformed_metadata": validation["malformed_metadata"],
        "missing_required_metadata": validation["missing_required_metadata"],
    }
    errors = detail["malformed_metadata"] or detail["missing_required_metadata"]
    warnings = detail["duplicate_capabilities"]
    return {
        "name": "Capability Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_workflow_registry_diagnostics(records: list[Any]) -> dict[str, Any]:
    workflows = build_workflow_registry(records)
    validation = validate_workflow_entries(workflows)
    detail = {
        "workflows_checked": len(workflows),
        "duplicate_workflows": validation["duplicates"],
        "malformed_metadata": validation["malformed_metadata"],
        "missing_required_metadata": validation["missing_required_metadata"],
    }
    errors = detail["malformed_metadata"] or detail["missing_required_metadata"]
    warnings = detail["duplicate_workflows"]
    return {
        "name": "Workflow Registry Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_ecosystem_diagnostics(records: list[Any]) -> dict[str, Any]:
    ecosystem = build_ecosystem_registry(records)
    validation = ecosystem["validation"]
    detail = {
        "entities_checked": ecosystem["summary"]["entity_count"],
        "duplicate_entities": validation["duplicate_entities"],
        "conflicting_definitions": validation["conflicting_definitions"],
        "orphan_entities": validation["orphan_entities"],
        "missing_relationships": validation["missing_relationships"],
    }
    errors = detail["duplicate_entities"] or detail["conflicting_definitions"]
    warnings = detail["orphan_entities"] or detail["missing_relationships"]
    return {
        "name": "Ecosystem Integrity",
        "status": "ERROR" if errors else "WARNING" if warnings else "OK",
        "severity": "ERROR" if errors else "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def build_failure_intelligence_diagnostics(records: list[Any]) -> dict[str, Any]:
    registry = build_failure_registry(records)
    summary = registry["summary"]
    detail = {
        "failures_checked": summary["failure_count"],
        "active_failures": summary["active_failures"],
        "resolved_failures": summary["resolved_failures"],
        "failure_rate": summary["failure_rate"],
        "most_common_failures": registry["report"]["most_common_failures"],
    }
    warnings = detail["active_failures"]
    return {
        "name": "Failure Intelligence",
        "status": "WARNING" if warnings else "OK",
        "severity": "WARNING" if warnings else "INFO",
        "detail": detail,
    }


def _with_trace(trace_id: str, event_id: str) -> dict[str, str]:
    return {"trace_id": trace_id, "event_id": event_id}


def _is_valid_cross_trace_link(
    link: dict[str, Any],
    trace_ids: set[str],
    event_ids_by_trace: dict[str, set[str]],
    span_ids_by_trace: dict[str, set[str]],
) -> bool:
    linked_trace_id = link.get("trace_id")
    if linked_trace_id not in trace_ids:
        return False
    linked_event_id = link.get("event_id")
    if linked_event_id and linked_event_id not in event_ids_by_trace.get(
        linked_trace_id, set()
    ):
        return False
    linked_span_id = link.get("span_id")
    if linked_span_id and linked_span_id not in span_ids_by_trace.get(
        linked_trace_id, set()
    ):
        return False
    return True


def _is_long_running(started_at: str | None, now: datetime) -> bool:
    if not started_at:
        return False
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return False
    return now - started > ACTIVE_SPAN_WARNING_AFTER
