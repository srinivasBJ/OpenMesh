from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from statistics import mean
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..failures import classify_failure
from ..services.openmesh_collector import collector
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event


GENOME_EVENT_TYPES = {"agent.genome.resembles"}
DERIVED_EVENT_PREFIXES = ("agent.reputation.", "agent.genome.")
SIMILARITY_THRESHOLD = 35.0


@dataclass
class AgentGenomeStats:
    node: dict[str, Any]
    event_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    event_ids: list[str] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)
    session_ids: list[str] = field(default_factory=list)
    models: Counter[str] = field(default_factory=Counter)
    tools: Counter[str] = field(default_factory=Counter)
    mcp_servers: Counter[str] = field(default_factory=Counter)
    context_sizes: list[float] = field(default_factory=list)
    latency_ms: list[float] = field(default_factory=list)
    cost_usd: list[float] = field(default_factory=list)
    tokens: list[float] = field(default_factory=list)
    outgoing_handoffs: Counter[str] = field(default_factory=Counter)
    incoming_handoffs: Counter[str] = field(default_factory=Counter)
    handoff_started: int = 0
    handoff_completed: int = 0
    handoff_failed: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    failure_patterns: Counter[str] = field(default_factory=Counter)


async def get_agent_genomes(
    db: AsyncSession, *, limit: int = 5000, persist: bool = False
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    report = build_agent_genomes(records)
    if persist:
        await detect_and_persist_genome(db, records=records, report=report)
        records = await list_openmesh_events(db, limit=limit)
        report = build_agent_genomes(records)
    return report


async def get_agent_genome(
    db: AsyncSession,
    agent_ref: str,
    *,
    limit: int = 5000,
    persist: bool = False,
) -> dict[str, Any] | None:
    report = await get_agent_genomes(db, limit=limit, persist=persist)
    return inspect_agent_genome(report, agent_ref)


async def get_agent_comparison(
    db: AsyncSession,
    agent_a: str,
    agent_b: str,
    *,
    limit: int = 5000,
    persist: bool = False,
) -> dict[str, Any] | None:
    report = await get_agent_genomes(db, limit=limit, persist=persist)
    return compare_agent_genomes(report, agent_a, agent_b)


async def detect_and_persist_genome(
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
        report = build_agent_genomes(records)

    existing = _existing_similarity_evidence(records)
    created: list[dict[str, Any]] = []
    genomes_by_id = {item["agent_id"]: item for item in report.get("genomes", [])}
    for similarity in report.get("similarities", []):
        if similarity["similarity_score"] < SIMILARITY_THRESHOLD:
            continue
        key = (similarity["source_agent_id"], similarity["target_agent_id"])
        evidence = set(similarity.get("evidence_event_ids", []))
        new_evidence = evidence - existing.get(key, set())
        if not new_evidence:
            continue

        source_genome = genomes_by_id[similarity["source_agent_id"]]
        target_genome = genomes_by_id[similarity["target_agent_id"]]
        event = make_openmesh_event(
            "agent.genome.resembles",
            _agent_node_with_genome(source_genome),
            {
                "relationship_type": "resembles",
                "similarity_score": similarity["similarity_score"],
                "shared_models": similarity["shared_models"],
                "shared_tools": similarity["shared_tools"],
                "shared_mcp_servers": similarity["shared_mcp_servers"],
                "shared_failure_patterns": similarity["shared_failure_patterns"],
                "evidence_event_ids": sorted(new_evidence),
                "genome_version": "0.1",
            },
            target=_agent_node_with_genome(target_genome),
            metrics={"similarity_score": similarity["similarity_score"]},
            severity="info",
            trace_id=_last(similarity.get("trace_ids")),
            session_id=_last(similarity.get("session_ids")),
            links=[
                {"event_id": event_id, "relationship": "genome_similarity_evidence"}
                for event_id in sorted(new_evidence)[:25]
            ],
        )
        created.append(await collector.accept(db, event, broadcast=broadcast))
    return {"created": len(created), "events": created}


def build_agent_genomes(records: Iterable[OpenMeshEventRecord]) -> dict[str, Any]:
    record_list = sorted(list(records), key=lambda record: record.timestamp)
    stats_by_agent: dict[str, AgentGenomeStats] = {}
    observed_events = 0

    for record in record_list:
        if _is_derived_event(record):
            continue
        observed_events += 1
        source_agent = _agent(record.source_json)
        target_agent = _agent(record.target_json)
        agents = _unique_agents([source_agent, target_agent])
        if not agents:
            continue

        for agent in agents:
            stats = stats_by_agent.setdefault(
                agent["node_id"], AgentGenomeStats(node=agent)
            )
            _observe_agent(stats, record, agent["node_id"])

    genomes = [_genome_from_stats(stats) for stats in stats_by_agent.values()]
    genomes.sort(key=lambda item: item["agent_name"])
    similarities = _similarities(genomes)
    return {
        "genomes": genomes,
        "similarities": similarities,
        "summary": {
            "agent_count": len(genomes),
            "observed_event_count": observed_events,
            "similarity_relationship_count": len(
                [
                    item
                    for item in similarities
                    if item["similarity_score"] >= SIMILARITY_THRESHOLD
                ]
            ),
            "genome_version": "0.1",
        },
    }


def inspect_agent_genome(
    report: dict[str, Any], agent_ref: str
) -> dict[str, Any] | None:
    genome = _find_genome(report, agent_ref)
    if not genome:
        return None
    return {
        "genome": genome,
        "resembles": _related_similarities(report, genome),
        "summary": report.get("summary", {}),
    }


def compare_agent_genomes(
    report: dict[str, Any], agent_a: str, agent_b: str
) -> dict[str, Any] | None:
    first = _find_genome(report, agent_a)
    second = _find_genome(report, agent_b)
    if not first or not second:
        return None
    comparison = _compare_pair(first, second)
    return {
        "agent_a": first,
        "agent_b": second,
        "comparison": comparison,
    }


def genome_diagnostics(records: list[Any]) -> dict[str, Any]:
    report = build_agent_genomes(records)
    summary = report["summary"]
    return {
        "name": "Agent Genome",
        "status": "OK",
        "severity": "INFO",
        "detail": {
            "agents_profiled": summary["agent_count"],
            "similarity_relationships": summary["similarity_relationship_count"],
            "observed_events": summary["observed_event_count"],
            "genome_version": summary["genome_version"],
        },
    }


def _observe_agent(
    stats: AgentGenomeStats, record: OpenMeshEventRecord, agent_id: str
) -> None:
    timestamp = record.timestamp.isoformat() + "Z"
    event_type = record.event_type
    payload = record.payload_json or {}
    metrics = record.metrics_json or {}
    stats.event_count += 1
    if not stats.first_seen:
        stats.first_seen = timestamp
    stats.last_seen = timestamp
    _dedupe(stats.event_ids, record.event_id)
    _dedupe(stats.trace_ids, getattr(record, "trace_id", None))
    _dedupe(stats.session_ids, getattr(record, "session_id", None))

    for name in _model_names(record):
        stats.models[name] += 1
    for name in _tool_names(record):
        stats.tools[name] += 1
    for name in _mcp_names(record):
        stats.mcp_servers[name] += 1

    context_size = _context_size(payload, metrics)
    if context_size is not None:
        stats.context_sizes.append(context_size)
    latency = _number(metrics.get("latency_ms") or payload.get("latency_ms"))
    duration = _number(metrics.get("duration_ms") or payload.get("duration_ms"))
    if latency is not None:
        stats.latency_ms.append(latency)
    elif duration is not None:
        stats.latency_ms.append(duration)
    cost = _number(metrics.get("cost_usd") or payload.get("cost_usd"))
    if cost is not None:
        stats.cost_usd.append(cost)
    for key in ("input_tokens", "output_tokens", "tokens", "total_tokens"):
        token_value = _number(metrics.get(key) or payload.get(key))
        if token_value is not None:
            stats.tokens.append(token_value)

    source_agent = _agent(record.source_json)
    target_agent = _agent(record.target_json)
    if event_type.startswith("agent.handoff."):
        if source_agent and source_agent["node_id"] == agent_id:
            stats.handoff_started += int(event_type == "agent.handoff.started")
            stats.handoff_completed += int(event_type == "agent.handoff.completed")
            stats.handoff_failed += int(event_type == "agent.handoff.failed")
            if target_agent:
                stats.outgoing_handoffs[
                    target_agent.get("name") or target_agent["node_id"]
                ] += 1
        if target_agent and target_agent["node_id"] == agent_id and source_agent:
            stats.incoming_handoffs[
                source_agent.get("name") or source_agent["node_id"]
            ] += 1

    if (
        event_type == "agent.message.sent"
        and source_agent
        and source_agent["node_id"] == agent_id
    ):
        stats.messages_sent += 1
    if (
        event_type == "agent.message.received"
        and source_agent
        and source_agent["node_id"] == agent_id
    ):
        stats.messages_received += 1

    if record.severity == "error" or event_type.endswith(".failed"):
        classification = classify_failure(
            event_type, payload, record.source_json, record.target_json
        )
        stats.failure_patterns[classification["category"]] += 1
    elif event_type == "failure.detected" and payload.get("category"):
        stats.failure_patterns[str(payload["category"])] += 1


def _genome_from_stats(stats: AgentGenomeStats) -> dict[str, Any]:
    preferred_models = _top_counter(stats.models)
    preferred_tools = _top_counter(stats.tools)
    preferred_mcp_servers = _top_counter(stats.mcp_servers)
    failure_patterns = _top_counter(stats.failure_patterns)
    handoff_attempts = max(
        stats.handoff_started, stats.handoff_completed + stats.handoff_failed
    )
    average_context_size = _average(stats.context_sizes)
    average_latency_ms = _average(stats.latency_ms)
    p95_latency_ms = _percentile(stats.latency_ms, 0.95)
    total_cost = round(sum(stats.cost_usd), 6)
    total_tokens = round(sum(stats.tokens), 2)
    genome = {
        "agent_id": stats.node["node_id"],
        "agent_name": stats.node.get("name") or stats.node["node_id"],
        "genome_version": "0.1",
        "first_seen": stats.first_seen,
        "last_seen": stats.last_seen,
        "event_count": stats.event_count,
        "preferred_models": preferred_models,
        "preferred_tools": preferred_tools,
        "preferred_mcp_servers": preferred_mcp_servers,
        "average_context_size": average_context_size,
        "handoff_patterns": {
            "started": stats.handoff_started,
            "completed": stats.handoff_completed,
            "failed": stats.handoff_failed,
            "completion_rate": _ratio(stats.handoff_completed, handoff_attempts),
            "top_outgoing": _top_counter(stats.outgoing_handoffs),
            "top_incoming": _top_counter(stats.incoming_handoffs),
            "messages_sent": stats.messages_sent,
            "messages_received": stats.messages_received,
        },
        "failure_patterns": failure_patterns,
        "cost_profile": {
            "total_cost_usd": total_cost,
            "average_cost_usd": round(total_cost / max(1, stats.event_count), 6),
            "total_tokens": total_tokens,
            "average_tokens": round(total_tokens / max(1, stats.event_count), 2),
        },
        "latency_profile": {
            "average_latency_ms": average_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "samples": len(stats.latency_ms),
        },
        "provenance": {
            "event_ids": stats.event_ids,
            "trace_ids": stats.trace_ids,
            "session_ids": stats.session_ids,
            "first_seen": stats.first_seen,
            "last_seen": stats.last_seen,
        },
    }
    genome["genome_signature"] = _genome_signature(genome)
    return genome


def _similarities(genomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs = []
    for index, source in enumerate(genomes):
        for target in genomes[index + 1 :]:
            forward = _compare_pair(source, target)
            reverse = _compare_pair(target, source)
            pairs.extend([forward, reverse])
    pairs.sort(key=lambda item: (-item["similarity_score"], item["source_agent_name"]))
    return pairs


def _compare_pair(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    source_models = _names(source["preferred_models"])
    target_models = _names(target["preferred_models"])
    source_tools = _names(source["preferred_tools"])
    target_tools = _names(target["preferred_tools"])
    source_mcps = _names(source["preferred_mcp_servers"])
    target_mcps = _names(target["preferred_mcp_servers"])
    source_failures = _names(source["failure_patterns"])
    target_failures = _names(target["failure_patterns"])
    source_handoffs = _names(source["handoff_patterns"]["top_outgoing"]) | _names(
        source["handoff_patterns"]["top_incoming"]
    )
    target_handoffs = _names(target["handoff_patterns"]["top_outgoing"]) | _names(
        target["handoff_patterns"]["top_incoming"]
    )
    latency_score = _numeric_similarity(
        source["latency_profile"]["average_latency_ms"],
        target["latency_profile"]["average_latency_ms"],
    )
    cost_score = _numeric_similarity(
        source["cost_profile"]["average_cost_usd"],
        target["cost_profile"]["average_cost_usd"],
    )
    score = round(
        _jaccard(source_tools, target_tools) * 35
        + _jaccard(source_models, target_models) * 20
        + _jaccard(source_mcps, target_mcps) * 15
        + _jaccard(source_failures, target_failures) * 10
        + _jaccard(source_handoffs, target_handoffs) * 10
        + latency_score * 5
        + cost_score * 5,
        2,
    )
    trace_ids = sorted(
        set(source["provenance"]["trace_ids"]) & set(target["provenance"]["trace_ids"])
    )
    session_ids = sorted(
        set(source["provenance"]["session_ids"])
        & set(target["provenance"]["session_ids"])
    )
    evidence_event_ids = sorted(
        set(source["provenance"]["event_ids"]) & set(target["provenance"]["event_ids"])
    )
    if not evidence_event_ids:
        evidence_event_ids = sorted(
            set(source["provenance"]["event_ids"][:10])
            | set(target["provenance"]["event_ids"][:10])
        )
    return {
        "source_agent_id": source["agent_id"],
        "source_agent_name": source["agent_name"],
        "target_agent_id": target["agent_id"],
        "target_agent_name": target["agent_name"],
        "relationship_type": "resembles",
        "similarity_score": score,
        "shared_models": sorted(source_models & target_models),
        "shared_tools": sorted(source_tools & target_tools),
        "shared_mcp_servers": sorted(source_mcps & target_mcps),
        "shared_failure_patterns": sorted(source_failures & target_failures),
        "shared_handoff_patterns": sorted(source_handoffs & target_handoffs),
        "latency_similarity": round(latency_score * 100, 2),
        "cost_similarity": round(cost_score * 100, 2),
        "evidence_event_ids": evidence_event_ids,
        "trace_ids": trace_ids,
        "session_ids": session_ids,
    }


def _model_names(record: OpenMeshEventRecord) -> set[str]:
    names = set()
    for node in (record.source_json, record.target_json):
        if node and node.get("node_type") == "model":
            names.add(str(node.get("name") or node.get("node_id")))
    payload = record.payload_json or {}
    metrics = record.metrics_json or {}
    for key in ("model", "model_name"):
        value = payload.get(key) or metrics.get(key)
        if value:
            names.add(str(value))
    return names


def _tool_names(record: OpenMeshEventRecord) -> set[str]:
    names = set()
    for node in (record.source_json, record.target_json):
        if node and node.get("node_type") == "tool":
            names.add(str(node.get("name") or node.get("node_id")))
    payload = record.payload_json or {}
    for key in ("tool", "tool_name", "name"):
        value = payload.get(key)
        if value and "tool" in record.event_type:
            names.add(str(value))
    return names


def _mcp_names(record: OpenMeshEventRecord) -> set[str]:
    names = set()
    for node in (record.source_json, record.target_json):
        if node and node.get("node_type") == "mcp_server":
            names.add(str(node.get("name") or node.get("node_id")))
    payload = record.payload_json or {}
    for key in ("mcp_server", "server", "server_name"):
        value = payload.get(key)
        if value and ("mcp" in record.event_type or "tool" in record.event_type):
            names.add(str(value))
    return names


def _context_size(payload: dict[str, Any], metrics: dict[str, Any]) -> float | None:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    metric_usage = (
        metrics.get("usage") if isinstance(metrics.get("usage"), dict) else {}
    )
    for source in (metrics, payload, usage, metric_usage):
        for key in ("context_tokens", "prompt_tokens", "input_tokens", "max_tokens"):
            value = _number(source.get(key))
            if value is not None:
                return value
    return None


def _find_genome(report: dict[str, Any], agent_ref: str) -> dict[str, Any] | None:
    normalized = agent_ref.lower()
    partial_matches = []
    for genome in report.get("genomes", []):
        candidates = {
            str(genome.get("agent_id", "")).lower(),
            str(genome.get("agent_name", "")).lower(),
        }
        if normalized in candidates:
            return genome
        if any(normalized in candidate for candidate in candidates):
            partial_matches.append(genome)
    if len(partial_matches) == 1:
        return partial_matches[0]
    return None


def _related_similarities(
    report: dict[str, Any], genome: dict[str, Any]
) -> list[dict[str, Any]]:
    related: dict[str, dict[str, Any]] = {}
    agent_id = genome["agent_id"]
    for item in report.get("similarities", []):
        if item["source_agent_id"] == agent_id:
            other_id = item["target_agent_id"]
        elif item["target_agent_id"] == agent_id:
            other_id = item["source_agent_id"]
        else:
            continue
        existing = related.get(other_id)
        if not existing or item["similarity_score"] > existing["similarity_score"]:
            related[other_id] = item
    return sorted(
        related.values(),
        key=lambda item: (
            -item["similarity_score"],
            item["target_agent_name"]
            if item["source_agent_id"] == agent_id
            else item["source_agent_name"],
        ),
    )


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


def _is_derived_event(record: OpenMeshEventRecord) -> bool:
    return record.event_type in GENOME_EVENT_TYPES or record.event_type.startswith(
        DERIVED_EVENT_PREFIXES
    )


def _top_counter(counter: Counter[str], limit: int = 5) -> list[dict[str, Any]]:
    total = sum(counter.values())
    return [
        {
            "name": name,
            "count": count,
            "share": round(count / total * 100, 2) if total else 0,
        }
        for name, count in counter.most_common(limit)
    ]


def _average(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 2)


def _ratio(success: int, total: int) -> float:
    return round(success / total * 100, 2) if total else 0


def _names(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["name"]) for row in rows if row.get("name")}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.5
    union = left | right
    return len(left & right) / len(union) if union else 0


def _numeric_similarity(left: float | None, right: float | None) -> float:
    if left is None or right is None:
        return 0.5
    high = max(abs(left), abs(right), 1.0)
    return max(0, 1 - abs(left - right) / high)


def _genome_signature(genome: dict[str, Any]) -> str:
    parts = [
        genome["agent_id"],
        ",".join(sorted(_names(genome["preferred_models"]))),
        ",".join(sorted(_names(genome["preferred_tools"]))),
        ",".join(sorted(_names(genome["preferred_mcp_servers"]))),
        ",".join(sorted(_names(genome["failure_patterns"]))),
    ]
    return sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _agent_node_with_genome(genome: dict[str, Any]) -> OpenMeshNode:
    return {
        "node_id": genome["agent_id"],
        "node_type": "agent",
        "name": genome["agent_name"],
        "runtime": "openmesh.genome",
        "metadata": {
            "genome_signature": genome["genome_signature"],
            "genome_version": genome["genome_version"],
        },
    }


def _existing_similarity_evidence(
    records: Iterable[OpenMeshEventRecord],
) -> dict[tuple[str, str], set[str]]:
    existing: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in records:
        if record.event_type not in GENOME_EVENT_TYPES:
            continue
        source = _agent(record.source_json)
        target = _agent(record.target_json)
        if not source or not target:
            continue
        evidence = (record.payload_json or {}).get("evidence_event_ids") or []
        if isinstance(evidence, list):
            existing[(source["node_id"], target["node_id"])].update(
                item for item in evidence if isinstance(item, str)
            )
    return existing


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
