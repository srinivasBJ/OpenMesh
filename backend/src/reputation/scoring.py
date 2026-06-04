from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..services.openmesh_collector import collector
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event


REPUTATION_EVENT_TYPES = {"agent.reputation.trusts"}
SUCCESS_EVENT_SUFFIXES = (".completed",)
FAILURE_EVENT_SUFFIXES = (".failed",)


@dataclass
class AgentStats:
    node: dict[str, Any]
    event_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    event_ids: list[str] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)
    success_events: int = 0
    failure_events: int = 0
    workflow_started_traces: list[str] = field(default_factory=list)
    workflow_completed_traces: list[str] = field(default_factory=list)
    workflow_failed_traces: list[str] = field(default_factory=list)
    tool_successes: int = 0
    tool_failures: int = 0
    handoffs_started: int = 0
    handoffs_completed: int = 0
    handoffs_failed: int = 0
    reviews_completed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    latency_ms: list[float] = field(default_factory=list)
    total_tokens: float = 0
    total_cost_usd: float = 0


@dataclass
class TrustStats:
    source: dict[str, Any]
    target: dict[str, Any]
    started_handoffs: int = 0
    completed_handoffs: int = 0
    failed_handoffs: int = 0
    reviews: int = 0
    messages: int = 0
    evidence_event_ids: list[str] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None


async def get_agent_reputation(
    db: AsyncSession, *, limit: int = 5000, persist: bool = False
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    report = build_agent_reputation(records)
    if persist:
        await detect_and_persist_reputation(db, records=records, report=report)
        records = await list_openmesh_events(db, limit=limit)
        report = build_agent_reputation(records)
    return report


async def get_agent_score(
    db: AsyncSession,
    agent_ref: str,
    *,
    limit: int = 5000,
    persist: bool = False,
) -> dict[str, Any] | None:
    report = await get_agent_reputation(db, limit=limit, persist=persist)
    return inspect_agent_score(report, agent_ref)


async def detect_and_persist_reputation(
    db: AsyncSession,
    *,
    records: list[OpenMeshEventRecord] | None = None,
    report: dict[str, Any] | None = None,
    limit: int = 5000,
    broadcast: bool = True,
) -> dict[str, Any]:
    if records is None:
        records = await list_openmesh_events(db, limit=limit)
    if report is None:
        report = build_agent_reputation(records)

    existing = _existing_trust_evidence(records)
    created: list[dict[str, Any]] = []
    rankings_by_id = {item["agent_id"]: item for item in report.get("rankings", [])}
    for trust in report.get("trust_relationships", []):
        key = (trust["source_agent_id"], trust["target_agent_id"])
        evidence = set(trust.get("evidence_event_ids", []))
        new_evidence = evidence - existing.get(key, set())
        if not new_evidence:
            continue

        source_score = rankings_by_id.get(trust["source_agent_id"], {})
        target_score = rankings_by_id.get(trust["target_agent_id"], {})
        source = _agent_node_with_score(trust["source"], source_score)
        target = _agent_node_with_score(trust["target"], target_score)
        payload = {
            "relationship_type": "trusts",
            "trust_score": trust["trust_score"],
            "source_agent_score": source_score.get("agent_score"),
            "target_agent_score": target_score.get("agent_score"),
            "evidence_event_ids": sorted(new_evidence),
            "evidence_count": len(evidence),
            "completed_handoffs": trust["completed_handoffs"],
            "messages": trust["messages"],
            "reviews": trust["reviews"],
            "failed_handoffs": trust["failed_handoffs"],
        }
        event = make_openmesh_event(
            "agent.reputation.trusts",
            source,
            payload,
            target=target,
            metrics={"trust_score": trust["trust_score"]},
            severity="info",
            trace_id=_last(trust.get("trace_ids")),
            session_id=_last(trust.get("session_ids")),
            links=[
                {"event_id": event_id, "relationship": "trust_evidence"}
                for event_id in sorted(new_evidence)[:25]
            ],
        )
        created.append(await collector.accept(db, event, broadcast=broadcast))
    return {"created": len(created), "events": created}


def build_agent_reputation(records: Iterable[OpenMeshEventRecord]) -> dict[str, Any]:
    record_list = sorted(list(records), key=lambda record: record.timestamp)
    agents: dict[str, AgentStats] = {}
    trusts: dict[tuple[str, str], TrustStats] = {}
    workflow_participants: dict[str, set[str]] = defaultdict(set)
    completed_workflow_traces: set[str] = set()
    failed_workflow_traces: set[str] = set()
    scored_event_count = 0

    for record in record_list:
        if record.event_type in REPUTATION_EVENT_TYPES:
            continue
        scored_event_count += 1
        source = _agent(record.source_json)
        target = _agent(record.target_json)
        timestamp = _timestamp(record)
        involved = _unique_agents([source, target])
        trace_key = _trace_key(record)

        for node in involved:
            stats = agents.setdefault(node["node_id"], AgentStats(node=node))
            _observe_agent_event(stats, record, timestamp)
            if record.event_type == "workflow.started":
                workflow_participants[trace_key].add(node["node_id"])

        if record.event_type == "workflow.completed":
            completed_workflow_traces.add(trace_key)
        elif record.event_type == "workflow.failed":
            failed_workflow_traces.add(trace_key)

        if source and target and source["node_id"] != target["node_id"]:
            _observe_trust(trusts, record, source, target, timestamp)

    for trace_id, agent_ids in workflow_participants.items():
        for agent_id in agent_ids:
            stats = agents.get(agent_id)
            if not stats:
                continue
            if trace_id in completed_workflow_traces:
                _dedupe(stats.workflow_completed_traces, trace_id)
            if trace_id in failed_workflow_traces:
                _dedupe(stats.workflow_failed_traces, trace_id)

    rankings = [_score_agent(stats) for stats in agents.values()]
    rankings.sort(key=lambda item: (-item["agent_score"], item["agent_name"]))
    ranking_by_id = {item["agent_id"]: item for item in rankings}
    trust_relationships = [
        _score_trust(stats, ranking_by_id)
        for stats in trusts.values()
        if _trust_has_positive_signal(stats)
    ]
    trust_relationships.sort(
        key=lambda item: (-item["trust_score"], item["source_agent_name"])
    )

    return {
        "rankings": rankings,
        "summary": {
            "agent_count": len(rankings),
            "scored_event_count": scored_event_count,
            "trust_relationship_count": len(trust_relationships),
            "average_agent_score": round(
                mean([item["agent_score"] for item in rankings]), 2
            )
            if rankings
            else 0,
        },
        "trust_relationships": trust_relationships,
        "top_agents": rankings[:5],
        "top_reviewers": [
            item for item in rankings if item["metrics"]["reviews_completed"] > 0
        ][:5],
        "most_reliable_agents": sorted(
            rankings,
            key=lambda item: (
                -item["metrics"]["tool_reliability"],
                -item["metrics"]["success_rate"],
                item["agent_name"],
            ),
        )[:5],
        "fastest_agents": sorted(
            [item for item in rankings if item["metrics"]["latency_samples"] > 0],
            key=lambda item: (
                item["metrics"]["average_latency_ms"],
                -item["agent_score"],
                item["agent_name"],
            ),
        )[:5],
    }


def inspect_agent_score(
    report: dict[str, Any], agent_ref: str
) -> dict[str, Any] | None:
    normalized = agent_ref.lower()
    for agent in report.get("rankings", []):
        candidates = {
            str(agent.get("agent_id", "")).lower(),
            str(agent.get("agent_name", "")).lower(),
        }
        if normalized in candidates:
            return {
                "agent": agent,
                "outgoing_trust": [
                    item
                    for item in report.get("trust_relationships", [])
                    if item["source_agent_id"] == agent["agent_id"]
                ],
                "incoming_trust": [
                    item
                    for item in report.get("trust_relationships", [])
                    if item["target_agent_id"] == agent["agent_id"]
                ],
                "summary": report.get("summary", {}),
            }
    return None


def reputation_diagnostics(records: list[Any]) -> dict[str, Any]:
    report = build_agent_reputation(records)
    summary = report["summary"]
    return {
        "name": "Agent Reputation",
        "status": "OK",
        "severity": "INFO",
        "detail": {
            "agents_scored": summary["agent_count"],
            "average_agent_score": summary["average_agent_score"],
            "trust_relationships": summary["trust_relationship_count"],
            "scored_events": summary["scored_event_count"],
        },
    }


def _observe_agent_event(
    stats: AgentStats, record: OpenMeshEventRecord, timestamp: str
) -> None:
    event_id = record.event_id
    event_type = record.event_type
    payload = record.payload_json or {}
    metrics = record.metrics_json or {}
    stats.event_count += 1
    if not stats.first_seen:
        stats.first_seen = timestamp
    stats.last_seen = timestamp
    _dedupe(stats.event_ids, event_id)
    _dedupe(stats.trace_ids, getattr(record, "trace_id", None))
    _dedupe(stats.session_ids, getattr(record, "session_id", None))

    if event_type.endswith(SUCCESS_EVENT_SUFFIXES):
        stats.success_events += 1
    if event_type.endswith(FAILURE_EVENT_SUFFIXES) or record.severity == "error":
        stats.failure_events += 1

    if event_type == "workflow.started":
        _dedupe(stats.workflow_started_traces, _trace_key(record))
    elif event_type == "workflow.completed":
        _dedupe(stats.workflow_completed_traces, _trace_key(record))
    elif event_type == "workflow.failed":
        _dedupe(stats.workflow_failed_traces, _trace_key(record))

    if event_type in {"tool.call.completed", "tool.completed"}:
        stats.tool_successes += 1
    elif event_type in {"tool.call.failed", "tool.failed"}:
        stats.tool_failures += 1

    if event_type == "agent.handoff.started":
        stats.handoffs_started += 1
    elif event_type == "agent.handoff.completed":
        stats.handoffs_completed += 1
        if payload.get("relationship_type") == "reviews":
            stats.reviews_completed += 1
    elif event_type == "agent.handoff.failed":
        stats.handoffs_failed += 1

    if event_type == "agent.message.sent":
        stats.messages_sent += 1
    elif event_type == "agent.message.received":
        stats.messages_received += 1

    latency = _number(metrics.get("latency_ms") or payload.get("latency_ms"))
    duration = _number(metrics.get("duration_ms") or payload.get("duration_ms"))
    if latency is not None:
        stats.latency_ms.append(latency)
    elif duration is not None:
        stats.latency_ms.append(duration)

    for key in ("input_tokens", "output_tokens", "tokens", "total_tokens"):
        value = _number(metrics.get(key) or payload.get(key))
        if value is not None:
            stats.total_tokens += value
    cost = _number(metrics.get("cost_usd") or payload.get("cost_usd"))
    if cost is not None:
        stats.total_cost_usd += cost


def _observe_trust(
    trusts: dict[tuple[str, str], TrustStats],
    record: OpenMeshEventRecord,
    source: dict[str, Any],
    target: dict[str, Any],
    timestamp: str,
) -> None:
    if record.event_type not in {
        "agent.handoff.started",
        "agent.handoff.completed",
        "agent.handoff.failed",
        "agent.message.sent",
    }:
        return
    key = (source["node_id"], target["node_id"])
    stats = trusts.setdefault(key, TrustStats(source=source, target=target))
    if not stats.first_seen:
        stats.first_seen = timestamp
    stats.last_seen = timestamp
    _dedupe(stats.evidence_event_ids, record.event_id)
    _dedupe(stats.trace_ids, getattr(record, "trace_id", None))
    _dedupe(stats.session_ids, getattr(record, "session_id", None))

    if record.event_type == "agent.handoff.started":
        stats.started_handoffs += 1
    elif record.event_type == "agent.handoff.completed":
        stats.completed_handoffs += 1
        if (record.payload_json or {}).get("relationship_type") == "reviews":
            stats.reviews += 1
    elif record.event_type == "agent.handoff.failed":
        stats.failed_handoffs += 1
    elif record.event_type == "agent.message.sent":
        stats.messages += 1


def _score_agent(stats: AgentStats) -> dict[str, Any]:
    success_rate = _ratio_score(stats.success_events, stats.failure_events)
    workflows_started = len(stats.workflow_started_traces)
    workflows_completed = len(stats.workflow_completed_traces)
    workflows_failed = len(stats.workflow_failed_traces)
    workflow_completion = _ratio_from_counts(
        workflows_completed,
        max(
            workflows_started,
            workflows_completed + workflows_failed,
        ),
    )
    tool_reliability = _ratio_score(stats.tool_successes, stats.tool_failures)
    handoff_quality = _handoff_quality(stats)
    latency_score, average_latency_ms = _latency_score(stats.latency_ms)
    cost_efficiency = _cost_efficiency_score(stats)
    agent_score = round(
        success_rate * 0.25
        + workflow_completion * 0.20
        + tool_reliability * 0.20
        + handoff_quality * 0.15
        + latency_score * 0.10
        + cost_efficiency * 0.10,
        2,
    )
    return {
        "agent_id": stats.node["node_id"],
        "agent_name": stats.node.get("name") or stats.node["node_id"],
        "agent_score": agent_score,
        "status": _reputation_status(agent_score),
        "first_seen": stats.first_seen,
        "last_seen": stats.last_seen,
        "event_count": stats.event_count,
        "trace_count": len(stats.trace_ids),
        "session_count": len(stats.session_ids),
        "metrics": {
            "success_rate": success_rate,
            "workflow_completion_rate": workflow_completion,
            "tool_reliability": tool_reliability,
            "handoff_quality": handoff_quality,
            "response_latency": latency_score,
            "response_latency_score": latency_score,
            "average_latency_ms": average_latency_ms,
            "latency_samples": len(stats.latency_ms),
            "cost_efficiency": cost_efficiency,
            "success_events": stats.success_events,
            "failure_events": stats.failure_events,
            "workflows_started": workflows_started,
            "workflows_completed": workflows_completed,
            "workflows_failed": workflows_failed,
            "tool_successes": stats.tool_successes,
            "tool_failures": stats.tool_failures,
            "handoffs_started": stats.handoffs_started,
            "handoffs_completed": stats.handoffs_completed,
            "handoffs_failed": stats.handoffs_failed,
            "reviews_completed": stats.reviews_completed,
            "messages_sent": stats.messages_sent,
            "messages_received": stats.messages_received,
            "total_tokens": round(stats.total_tokens, 2),
            "total_cost_usd": round(stats.total_cost_usd, 6),
        },
        "provenance": {
            "event_ids": stats.event_ids,
            "trace_ids": stats.trace_ids,
            "session_ids": stats.session_ids,
            "first_seen": stats.first_seen,
            "last_seen": stats.last_seen,
        },
    }


def _score_trust(
    stats: TrustStats, rankings_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    attempts = max(
        stats.started_handoffs,
        stats.completed_handoffs + stats.failed_handoffs,
    )
    handoff_quality = stats.completed_handoffs / attempts if attempts else 0
    trust_score = min(
        100,
        max(
            0,
            stats.completed_handoffs * 12
            + stats.messages * 2
            + stats.reviews * 15
            - stats.failed_handoffs * 20
            + handoff_quality * 30,
        ),
    )
    source_score = rankings_by_id.get(stats.source["node_id"], {}).get("agent_score")
    target_score = rankings_by_id.get(stats.target["node_id"], {}).get("agent_score")
    return {
        "source_agent_id": stats.source["node_id"],
        "source_agent_name": stats.source.get("name") or stats.source["node_id"],
        "target_agent_id": stats.target["node_id"],
        "target_agent_name": stats.target.get("name") or stats.target["node_id"],
        "source": stats.source,
        "target": stats.target,
        "relationship_type": "trusts",
        "trust_score": round(trust_score, 2),
        "source_agent_score": source_score,
        "target_agent_score": target_score,
        "started_handoffs": stats.started_handoffs,
        "completed_handoffs": stats.completed_handoffs,
        "failed_handoffs": stats.failed_handoffs,
        "reviews": stats.reviews,
        "messages": stats.messages,
        "evidence_event_ids": stats.evidence_event_ids,
        "trace_ids": stats.trace_ids,
        "session_ids": stats.session_ids,
        "first_seen": stats.first_seen,
        "last_seen": stats.last_seen,
    }


def _trust_has_positive_signal(stats: TrustStats) -> bool:
    return stats.completed_handoffs > 0 or stats.messages > 0 or stats.reviews > 0


def _agent(node: dict[str, Any] | None) -> dict[str, Any] | None:
    if not node or node.get("node_type") != "agent" or not node.get("node_id"):
        return None
    return node


def _unique_agents(nodes: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if node:
            unique.setdefault(node["node_id"], node)
    return list(unique.values())


def _timestamp(record: OpenMeshEventRecord) -> str:
    return record.timestamp.isoformat() + "Z"


def _trace_key(record: OpenMeshEventRecord) -> str:
    return getattr(record, "trace_id", None) or record.event_id


def _ratio_score(successes: int, failures: int, *, neutral: float = 70.0) -> float:
    return _ratio_from_counts(successes, successes + failures, neutral=neutral)


def _ratio_from_counts(successes: int, total: int, *, neutral: float = 70.0) -> float:
    if total <= 0:
        return neutral
    return round(max(0, min(100, successes / total * 100)), 2)


def _handoff_quality(stats: AgentStats) -> float:
    attempts = max(
        stats.handoffs_started,
        stats.handoffs_completed + stats.handoffs_failed,
    )
    if attempts <= 0:
        return 80.0 if stats.messages_sent or stats.messages_received else 70.0
    return round(max(0, min(100, stats.handoffs_completed / attempts * 100)), 2)


def _latency_score(samples: list[float]) -> tuple[float, float | None]:
    if not samples:
        return 75.0, None
    average = mean(samples)
    if average <= 250:
        score = 100.0
    elif average >= 5000:
        score = 40.0
    else:
        score = 100 - ((average - 250) / 4750) * 60
    return round(max(40, min(100, score)), 2), round(average, 2)


def _cost_efficiency_score(stats: AgentStats) -> float:
    if stats.total_tokens <= 0 and stats.total_cost_usd <= 0:
        return 75.0
    token_per_event = stats.total_tokens / max(1, stats.event_count)
    token_score = 100 - min(60, max(0, (token_per_event - 500) / 7500 * 60))
    if stats.total_cost_usd <= 0:
        return round(max(40, min(100, token_score)), 2)
    cost_per_event = stats.total_cost_usd / max(1, stats.event_count)
    cost_score = 100 - min(60, max(0, (cost_per_event - 0.001) / 0.049 * 60))
    return round(max(40, min(100, (token_score + cost_score) / 2)), 2)


def _reputation_status(score: float) -> str:
    if score >= 90:
        return "elite"
    if score >= 80:
        return "trusted"
    if score >= 65:
        return "steady"
    if score >= 50:
        return "watchlist"
    return "risky"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[Any], value: Any) -> None:
    if value and value not in values:
        values.append(value)


def _last(values: list[Any] | None) -> Any:
    return values[-1] if values else None


def _agent_node_with_score(node: dict[str, Any], score: dict[str, Any]) -> OpenMeshNode:
    metadata = dict(node.get("metadata") or {})
    metadata["agent_score"] = score.get("agent_score")
    metadata["reputation_status"] = score.get("status")
    return {
        "node_id": node["node_id"],
        "node_type": "agent",
        "name": node.get("name") or node["node_id"],
        "runtime": node.get("runtime") or "openmesh.reputation",
        "metadata": metadata,
    }


def _existing_trust_evidence(
    records: Iterable[OpenMeshEventRecord],
) -> dict[tuple[str, str], set[str]]:
    existing: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in records:
        if record.event_type not in REPUTATION_EVENT_TYPES:
            continue
        source = _agent(record.source_json)
        target = _agent(record.target_json)
        if not source or not target:
            continue
        payload = record.payload_json or {}
        evidence = payload.get("evidence_event_ids") or []
        if isinstance(evidence, list):
            existing[(source["node_id"], target["node_id"])].update(
                item for item in evidence if isinstance(item, str)
            )
    return existing
