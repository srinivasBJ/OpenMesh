from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..shared.openmesh_events import make_openmesh_event
from ..services.openmesh_collector import collector
from .taxonomy import (
    AFFECTED_NODE_TYPES,
    CAUSE_NODE_TYPES,
    FAILURE_TAXONOMY,
    classify_failure,
    taxonomy_definitions,
)


FAILURE_EVENTS = {"failure.detected", "failure.classified", "failure.resolved"}


@dataclass
class FailureObservation:
    failure_id: str
    category: str
    display_name: str
    confidence: float
    source_event_id: str
    source_event_type: str
    trace_id: str | None
    session_id: str | None
    timestamp: str
    status: str
    error: str | None
    error_type: str | None
    source: dict[str, Any] | None
    target: dict[str, Any] | None
    cause_node: dict[str, Any] | None
    upstream_cause: dict[str, Any]
    downstream_impact: dict[str, Any]
    affected_agents: list[dict[str, Any]]
    affected_workflows: list[dict[str, Any]]
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "category": self.category,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "source_event_id": self.source_event_id,
            "source_event_type": self.source_event_type,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "error": self.error,
            "error_type": self.error_type,
            "source": self.source,
            "target": self.target,
            "cause_node": self.cause_node,
            "upstream_cause": self.upstream_cause,
            "downstream_impact": self.downstream_impact,
            "affected_agents": self.affected_agents,
            "affected_workflows": self.affected_workflows,
            "resolved_at": self.resolved_at,
        }


async def get_failure_registry(
    db: AsyncSession, *, limit: int = 5000, persist: bool = True
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    registry = build_failure_registry(records)
    if persist:
        await detect_and_persist_failures(db, records=records, registry=registry)
        records = await list_openmesh_events(db, limit=limit)
        registry = build_failure_registry(records)
    return registry


async def get_failure_report(
    db: AsyncSession, *, limit: int = 5000, persist: bool = False
) -> dict[str, Any]:
    registry = await get_failure_registry(db, limit=limit, persist=persist)
    return failure_report(registry["failures"], total_events=registry["total_events"])


async def detect_and_persist_failures(
    db: AsyncSession,
    *,
    records: list[OpenMeshEventRecord] | None = None,
    registry: dict[str, Any] | None = None,
    limit: int = 5000,
    broadcast: bool = True,
) -> dict[str, Any]:
    if records is None:
        records = await list_openmesh_events(db, limit=limit)
    if registry is None:
        registry = build_failure_registry(records)
    existing_failure_events = _existing_failure_event_types(records)
    created: list[dict[str, Any]] = []
    for failure in registry["failures"]:
        created.extend(
            await _persist_failure_events(
                db,
                failure,
                existing_event_types=existing_failure_events.get(
                    failure["source_event_id"], set()
                ),
                broadcast=broadcast,
            )
        )
    return {"created": len(created), "events": created}


def build_failure_registry(records: Iterable[OpenMeshEventRecord]) -> dict[str, Any]:
    record_list = sorted(list(records), key=lambda record: record.timestamp)
    trace_records = _records_by_trace(record_list)
    resolved = _resolved_failure_events(record_list)
    observations = [
        _observation_for_record(record, trace_records, resolved)
        for record in record_list
        if _is_failure_source(record)
    ]
    failures = [observation.to_dict() for observation in observations]
    report = failure_report(failures, total_events=len(record_list))
    return {
        "failures": failures,
        "summary": report["summary"],
        "report": report,
        "taxonomy": taxonomy_definitions(),
        "total_events": len(record_list),
    }


def inspect_failure(
    records: Iterable[OpenMeshEventRecord], failure_ref: str
) -> dict[str, Any] | None:
    registry = build_failure_registry(records)
    normalized = failure_ref.lower()
    for failure in registry["failures"]:
        candidates = {
            str(failure.get("failure_id", "")).lower(),
            str(failure.get("source_event_id", "")).lower(),
            str(failure.get("category", "")).lower(),
        }
        if normalized in candidates:
            return failure_detail(failure, registry)
    return None


def failure_detail(failure: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "failure": failure,
        "taxonomy": FAILURE_TAXONOMY[failure["category"]].__dict__,
        "related_failures": [
            item
            for item in registry["failures"]
            if item["failure_id"] != failure["failure_id"]
            and item.get("trace_id") == failure.get("trace_id")
        ],
        "report_summary": registry["summary"],
    }


def failure_report(
    failures: list[dict[str, Any]], *, total_events: int = 0
) -> dict[str, Any]:
    category_counts = Counter(failure["category"] for failure in failures)
    failing_agents = Counter()
    failing_tools = Counter()
    affected_workflows = Counter()
    mttr_values: list[int] = []
    active = 0
    resolved = 0

    for failure in failures:
        if failure.get("status") == "resolved":
            resolved += 1
            duration = _duration_seconds(
                failure.get("timestamp"), failure.get("resolved_at")
            )
            if duration is not None:
                mttr_values.append(duration)
        else:
            active += 1
        for agent in failure.get("affected_agents", []):
            failing_agents[agent.get("name") or agent.get("node_id")] += 1
        cause = failure.get("cause_node") or {}
        if cause.get("node_type") == "tool":
            failing_tools[cause.get("name") or cause.get("node_id")] += 1
        for workflow in failure.get("affected_workflows", []):
            affected_workflows[workflow.get("name") or workflow.get("node_id")] += 1

    failure_count = len(failures)
    return {
        "summary": {
            "failure_count": failure_count,
            "active_failures": active,
            "resolved_failures": resolved,
            "failure_rate": round((failure_count / total_events) * 100, 2)
            if total_events
            else 0,
            "mttr_seconds": round(sum(mttr_values) / len(mttr_values), 2)
            if mttr_values
            else None,
        },
        "most_common_failures": _counter_rows(category_counts),
        "failing_agents": _counter_rows(failing_agents),
        "failing_tools": _counter_rows(failing_tools),
        "affected_workflows": _counter_rows(affected_workflows),
        "taxonomy": taxonomy_definitions(),
    }


async def _persist_failure_events(
    db: AsyncSession,
    failure: dict[str, Any],
    *,
    existing_event_types: set[str],
    broadcast: bool,
) -> list[dict[str, Any]]:
    source = failure_node(failure)
    created: list[dict[str, Any]] = []

    affected_targets = _unique_nodes(
        [
            *failure.get("affected_agents", []),
            *failure.get("affected_workflows", []),
        ]
    )
    primary_target = affected_targets[0] if affected_targets else None
    if "failure.detected" not in existing_event_types:
        for target in affected_targets or [None]:
            event = make_openmesh_event(
                "failure.detected",
                source,
                _failure_payload(failure, relationship_type="affects"),
                target=target,
                severity="warning",
                session_id=failure.get("session_id"),
                trace_id=failure.get("trace_id"),
                links=[
                    {
                        "event_id": failure["source_event_id"],
                        "relationship": "detected_from",
                    }
                ],
            )
            created.append(await collector.accept(db, event, broadcast=broadcast))

    cause_node = failure.get("cause_node")
    if cause_node and "failure.classified" not in existing_event_types:
        classified = make_openmesh_event(
            "failure.classified",
            source,
            _failure_payload(failure, relationship_type="caused_by"),
            target=cause_node,
            severity="warning",
            session_id=failure.get("session_id"),
            trace_id=failure.get("trace_id"),
            links=[
                {
                    "event_id": failure["source_event_id"],
                    "relationship": "classified_from",
                }
            ],
        )
        created.append(await collector.accept(db, classified, broadcast=broadcast))

    if (
        failure.get("status") == "resolved"
        and "failure.resolved" not in existing_event_types
    ):
        resolved = make_openmesh_event(
            "failure.resolved",
            source,
            _failure_payload(failure, relationship_type="affects"),
            target=primary_target,
            severity="info",
            session_id=failure.get("session_id"),
            trace_id=failure.get("trace_id"),
            links=[
                {
                    "event_id": failure["source_event_id"],
                    "relationship": "resolved_from",
                }
            ],
        )
        created.append(await collector.accept(db, resolved, broadcast=broadcast))

    return created


def failure_node(failure: dict[str, Any]) -> dict[str, Any]:
    name = f"{failure['display_name']}: {failure['source_event_type']}"
    return {
        "node_id": failure["failure_id"],
        "node_type": "failure",
        "name": name,
        "runtime": "openmesh.failure-intelligence",
        "metadata": {
            "category": failure["category"],
            "status": failure["status"],
            "source_event_id": failure["source_event_id"],
            "source_event_type": failure["source_event_type"],
            "confidence": failure["confidence"],
            "upstream_cause": failure.get("upstream_cause"),
            "downstream_impact": failure.get("downstream_impact"),
        },
    }


def _observation_for_record(
    record: OpenMeshEventRecord,
    trace_records: dict[str, list[OpenMeshEventRecord]],
    resolved: dict[str, str],
) -> FailureObservation:
    source = record.source_json or {}
    target = record.target_json or {}
    payload = record.payload_json or {}
    classification = classify_failure(record.event_type, payload, source, target)
    trace_id = getattr(record, "trace_id", None)
    related = trace_records.get(trace_id or "", [])
    cause_node, upstream_cause = _upstream_cause(
        record, related, classification["category"]
    )
    affected_agents = _affected_nodes(record, related, "agent")
    affected_workflows = _affected_nodes(record, related, "workflow")
    downstream_impact = _downstream_impact(record, related)
    resolved_at = resolved.get(record.event_id) or _resolution_timestamp(
        record, related
    )
    status = "resolved" if resolved_at else "active"
    return FailureObservation(
        failure_id=f"failure:{record.event_id}",
        category=classification["category"],
        display_name=classification["display_name"],
        confidence=classification["confidence"],
        source_event_id=record.event_id,
        source_event_type=record.event_type,
        trace_id=trace_id,
        session_id=getattr(record, "session_id", None),
        timestamp=record.timestamp.isoformat() + "Z",
        status=status,
        error=str(payload.get("error")) if payload.get("error") else None,
        error_type=str(payload.get("error_type"))
        if payload.get("error_type")
        else None,
        source=source or None,
        target=target or None,
        cause_node=cause_node,
        upstream_cause=upstream_cause,
        downstream_impact=downstream_impact,
        affected_agents=affected_agents,
        affected_workflows=affected_workflows,
        resolved_at=resolved_at,
    )


def _is_failure_source(record: OpenMeshEventRecord) -> bool:
    if record.event_type in FAILURE_EVENTS or record.event_type.startswith("failure."):
        return False
    return record.severity == "error" or record.event_type.endswith(".failed")


def _existing_failure_event_types(
    records: Iterable[OpenMeshEventRecord],
) -> dict[str, set[str]]:
    events: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.event_type not in FAILURE_EVENTS:
            continue
        payload = record.payload_json or {}
        source_event_id = payload.get("source_event_id")
        if isinstance(source_event_id, str):
            events[source_event_id].add(record.event_type)
    return events


def _resolved_failure_events(records: Iterable[OpenMeshEventRecord]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for record in records:
        if record.event_type != "failure.resolved":
            continue
        source_event_id = (record.payload_json or {}).get("source_event_id")
        if isinstance(source_event_id, str):
            resolved[source_event_id] = record.timestamp.isoformat() + "Z"
    return resolved


def _records_by_trace(
    records: Iterable[OpenMeshEventRecord],
) -> dict[str, list[OpenMeshEventRecord]]:
    grouped: dict[str, list[OpenMeshEventRecord]] = defaultdict(list)
    for record in records:
        if record.trace_id:
            grouped[record.trace_id].append(record)
    return grouped


def _upstream_cause(
    record: OpenMeshEventRecord,
    related: list[OpenMeshEventRecord],
    category: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    direct = _direct_cause_node(record, category)
    if direct:
        return direct, {
            "event_id": record.event_id,
            "event_type": record.event_type,
            "node": direct,
            "reason": "failure event directly referenced the likely cause",
        }

    previous = [
        item
        for item in related
        if item.timestamp <= record.timestamp and item.event_id != record.event_id
    ]
    for candidate in reversed(previous):
        for node in (candidate.target_json, candidate.source_json):
            if node and node.get("node_type") in CAUSE_NODE_TYPES:
                return node, {
                    "event_id": candidate.event_id,
                    "event_type": candidate.event_type,
                    "node": node,
                    "reason": "nearest upstream cause-like node in the same trace",
                }
    return None, {
        "event_id": record.event_id,
        "event_type": record.event_type,
        "node": None,
        "reason": "no upstream cause node found in the trace",
    }


def _direct_cause_node(
    record: OpenMeshEventRecord, category: str
) -> dict[str, Any] | None:
    nodes = [record.target_json, record.source_json]
    preferred: tuple[str, ...]
    if category == "tool_failure":
        preferred = ("tool",)
    elif category == "model_failure":
        preferred = ("model", "service")
    elif category == "mcp_failure":
        preferred = ("mcp_server", "tool", "service")
    elif category == "resource_failure":
        preferred = tuple(CAUSE_NODE_TYPES)
    else:
        preferred = tuple(CAUSE_NODE_TYPES)
    for node_type in preferred:
        for node in nodes:
            if node and node.get("node_type") == node_type:
                return node
    return None


def _affected_nodes(
    record: OpenMeshEventRecord, related: list[OpenMeshEventRecord], node_type: str
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for node in (record.source_json, record.target_json):
        if node and node.get("node_type") == node_type:
            nodes.append(node)
    for candidate in related:
        for node in (candidate.source_json, candidate.target_json):
            if node and node.get("node_type") == node_type:
                nodes.append(node)
    return _unique_nodes(nodes)


def _downstream_impact(
    record: OpenMeshEventRecord, related: list[OpenMeshEventRecord]
) -> dict[str, Any]:
    downstream = [item for item in related if item.timestamp > record.timestamp]
    impacted_nodes = []
    for candidate in downstream:
        for node in (candidate.source_json, candidate.target_json):
            if node and node.get("node_type") in AFFECTED_NODE_TYPES:
                impacted_nodes.append(node)
    return {
        "downstream_event_count": len(downstream),
        "downstream_failure_count": sum(
            1 for item in downstream if _is_failure_source(item)
        ),
        "impacted_nodes": _unique_nodes(impacted_nodes),
    }


def _resolution_timestamp(
    record: OpenMeshEventRecord, related: list[OpenMeshEventRecord]
) -> str | None:
    source_id = (record.source_json or {}).get("node_id")
    target_id = (record.target_json or {}).get("node_id")
    for candidate in related:
        if candidate.timestamp <= record.timestamp:
            continue
        if not candidate.event_type.endswith(".completed"):
            continue
        candidate_source_id = (candidate.source_json or {}).get("node_id")
        candidate_target_id = (candidate.target_json or {}).get("node_id")
        if candidate_source_id == source_id and candidate_target_id == target_id:
            return candidate.timestamp.isoformat() + "Z"
    return None


def _failure_payload(
    failure: dict[str, Any], *, relationship_type: str
) -> dict[str, Any]:
    return {
        "failure_id": failure["failure_id"],
        "category": failure["category"],
        "status": failure["status"],
        "confidence": failure["confidence"],
        "source_event_id": failure["source_event_id"],
        "source_event_type": failure["source_event_type"],
        "relationship_type": relationship_type,
        "upstream_cause": failure.get("upstream_cause"),
        "downstream_impact": failure.get("downstream_impact"),
        "affected_agents": failure.get("affected_agents", []),
        "affected_workflows": failure.get("affected_workflows", []),
        "resolved_at": failure.get("resolved_at"),
    }


def _unique_nodes(nodes: Iterable[dict[str, Any] | None]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not node:
            continue
        node_id = node.get("node_id")
        if isinstance(node_id, str) and node_id not in unique:
            unique[node_id] = node
    return list(unique.values())


def _counter_rows(counter: Counter) -> list[dict[str, Any]]:
    return [
        {"name": name, "count": count} for name, count in counter.most_common() if name
    ]


def _duration_seconds(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        start_at = datetime.fromisoformat(start.replace("Z", ""))
        end_at = datetime.fromisoformat(end.replace("Z", ""))
    except ValueError:
        return None
    return max(0, int((end_at - start_at).total_seconds()))
