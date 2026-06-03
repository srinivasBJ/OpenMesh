from __future__ import annotations

import asyncio
import gc
import json
import time
import tracemalloc
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable, Iterable

from .ecosystem_snapshot import build_ecosystem_snapshot, compare_snapshot_payloads
from .federation import build_federation_registry
from .graph_state import reduce_graph_state
from .openmesh_collector import OpenMeshCollector
from .openmesh_queries import inspect_graph_node, trace_summary
from .query_engine import run_query_on_state
from .replay import build_replay_from_timeline
from .timeline import build_timeline
from .trace_semantics import (
    build_event_hierarchy,
    build_span_summary,
    build_span_tree,
)


DEFAULT_EVALUATION_SIZES = (100, 1_000, 10_000)
EVALUATION_SCHEMA_VERSION = "0.1"


class EvaluationSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, record: Any) -> None:
        self.added.append(record)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


async def run_evaluation_suite(
    sizes: Iterable[int] = DEFAULT_EVALUATION_SIZES,
    *,
    include_ingestion: bool = True,
) -> dict[str, Any]:
    results = []
    for size in sizes:
        results.append(
            await benchmark_synthetic_ecosystem(
                max(int(size), 1), include_ingestion=include_ingestion
            )
        )
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sizes": [result["node_count"] for result in results],
        "benchmarks": results,
        "notes": [
            "Benchmarks use synthetic in-memory OpenMesh events.",
            "Measurements are for observation/read-model cost only; no optimization is applied.",
            "Federation benchmarks aggregate metadata only and do not contact remote peers.",
        ],
    }


async def benchmark_synthetic_ecosystem(
    node_count: int, *, include_ingestion: bool = True
) -> dict[str, Any]:
    synthetic = generate_synthetic_ecosystem(node_count)
    records = synthetic["records"]
    sessions = synthetic["sessions"]
    metrics: list[dict[str, Any]] = []

    if include_ingestion:
        ingestion_metric, ingestion_detail = await _measure_async(
            "event_ingestion",
            lambda: _ingest_events(synthetic["events"]),
        )
        ingestion_metric["details"] = ingestion_detail
        metrics.append(ingestion_metric)

    trace_metric, trace_detail = _measure(
        "trace_reconstruction",
        lambda: _reconstruct_traces(records),
    )
    trace_metric["details"] = trace_detail
    metrics.append(trace_metric)

    graph_metric, graph = _measure(
        "graph_reduction", lambda: reduce_graph_state(records)
    )
    graph_metric["details"] = {
        "nodes": len(graph.get("nodes", [])),
        "edges": len(graph.get("edges", [])),
        "validation": graph.get("validation", {}).get("status", "UNKNOWN"),
    }
    metrics.append(graph_metric)

    inspection_metric, inspection_detail = _measure(
        "inspection",
        lambda: _inspect_representative_nodes(graph),
    )
    inspection_metric["details"] = inspection_detail
    metrics.append(inspection_metric)

    query_metric, query_detail = _measure(
        "query_engine",
        lambda: _run_query_latency_benchmark(graph, records, sessions),
    )
    query_metric["details"] = query_detail
    metrics.append(query_metric)

    snapshot_metric, snapshot = _measure(
        "snapshot_creation",
        lambda: build_ecosystem_snapshot(records, sessions),
    )
    snapshot_metric["details"] = {
        "nodes": snapshot.get("counts", {}).get("nodes", 0),
        "edges": snapshot.get("counts", {}).get("edges", 0),
        "traces": snapshot.get("counts", {}).get("traces", 0),
        "sessions": snapshot.get("counts", {}).get("sessions", 0),
    }
    metrics.append(snapshot_metric)

    changed_records = _changed_records(records)
    changed_snapshot = build_ecosystem_snapshot(changed_records, sessions)
    diff_metric, diff = _measure(
        "snapshot_diff",
        lambda: compare_snapshot_payloads(snapshot, changed_snapshot),
    )
    diff_metric["details"] = diff.get("summary", {})
    metrics.append(diff_metric)

    timeline_metric, timeline = _measure(
        "timeline_generation",
        lambda: build_timeline(records, sessions, [snapshot, changed_snapshot]),
    )
    timeline_metric["details"] = {
        "timeline_entries": len(timeline.get("timeline", [])),
        "relationship_changes": len(timeline.get("relationship_changes", [])),
        "snapshot_history": len(timeline.get("snapshot_history", [])),
    }
    metrics.append(timeline_metric)

    replay_metric, replay = _measure(
        "replay_generation",
        lambda: build_replay_from_timeline(timeline),
    )
    replay_metric["details"] = {
        "frames": replay.get("state", {}).get("frame_count", 0),
        "visible_frames": replay.get("state", {}).get("visible_frame_count", 0),
    }
    metrics.append(replay_metric)

    federation_metric, federation = _measure(
        "federation_aggregation",
        lambda: build_federation_registry(
            records,
            sessions,
            [snapshot, changed_snapshot],
            peers=_synthetic_federation_peers(node_count),
        ),
    )
    federation_metric["details"] = {
        "peers": len(federation.get("peers", [])),
        "relationships": len(federation.get("relationships", [])),
        "instances": federation.get("snapshot", {})
        .get("counts", {})
        .get("instances", 0),
        "metadata_only": federation.get("policy", {}).get("metadata_only", False),
    }
    metrics.append(federation_metric)

    return {
        "node_count": node_count,
        "event_count": len(records),
        "trace_count": synthetic["trace_count"],
        "session_count": len(sessions),
        "graph_size": {
            "nodes": len(graph.get("nodes", [])),
            "edges": len(graph.get("edges", [])),
        },
        "metrics": metrics,
    }


def generate_synthetic_ecosystem(node_count: int) -> dict[str, Any]:
    nodes = _synthetic_nodes(node_count)
    nodes_by_type: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        nodes_by_type.setdefault(node["node_type"], []).append(node)

    events = []
    base_time = datetime(2026, 6, 3, 0, 0, 0)
    for index, node in enumerate(nodes):
        event_type, source, target = _event_for_node(index, node, nodes_by_type)
        events.append(
            _event(
                index,
                event_type,
                source,
                target,
                timestamp=base_time + timedelta(seconds=index),
                node_count=node_count,
            )
        )
    records = [_record_from_event(event) for event in events]
    sessions = _synthetic_sessions(max(1, node_count // 100))
    return {
        "nodes": nodes,
        "events": events,
        "records": records,
        "sessions": sessions,
        "trace_count": len({event["trace_id"] for event in events}),
    }


def _synthetic_nodes(node_count: int) -> list[dict[str, Any]]:
    node_types = (
        "agent",
        "tool",
        "workflow",
        "process",
        "service",
        "mcp_server",
        "capability",
    )
    nodes = []
    for index in range(node_count):
        node_type = node_types[index % len(node_types)]
        nodes.append(
            {
                "node_id": f"{node_type}:{index}",
                "node_type": node_type,
                "name": f"{_display(node_type)} {index}",
                "runtime": "openmesh.synthetic",
                "metadata": {
                    "framework": "synthetic",
                    "version": "0.1",
                },
            }
        )
    return nodes


def _event_for_node(
    index: int,
    node: dict[str, Any],
    nodes_by_type: dict[str, list[dict[str, Any]]],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    node_type = node["node_type"]
    if node_type == "agent":
        return "tool.call.started", node, _pick(nodes_by_type, "tool", index)
    if node_type == "tool":
        return "tool.connected", node, _pick(nodes_by_type, "mcp_server", index)
    if node_type == "workflow":
        return "tool.call.completed", node, _pick(nodes_by_type, "tool", index)
    if node_type == "process":
        return "process.started", _pick(nodes_by_type, "service", index), node
    if node_type == "service":
        return "mcp.config.discovered", node, _pick(nodes_by_type, "mcp_server", index)
    if node_type == "mcp_server":
        return (
            "mcp.capability.discovered",
            node,
            _pick(nodes_by_type, "capability", index),
        )
    return "mcp.capability.discovered", _pick(nodes_by_type, "mcp_server", index), node


def _event(
    index: int,
    event_type: str,
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    timestamp: datetime,
    node_count: int,
) -> dict[str, Any]:
    trace_mod = max(1, node_count // 10)
    session_mod = max(1, node_count // 100)
    event_id = f"evt_bench_{node_count}_{index}"
    return {
        "spec_version": "0.1",
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": timestamp.isoformat() + "Z",
        "trace_id": f"trace_bench_{index % trace_mod}",
        "session_id": f"sess_bench_{index % session_mod}",
        "span_id": f"span_bench_{index}",
        "parent_span_id": f"span_bench_{index - 1}" if index % 5 else None,
        "parent_event_id": f"evt_bench_{node_count}_{index - 1}" if index % 5 else None,
        "root_event_id": event_id
        if index % 5 == 0
        else f"evt_bench_{node_count}_{index - index % 5}",
        "source": source,
        "target": target,
        "payload": {
            "synthetic": True,
            "benchmark_node_count": node_count,
            "benchmark_index": index,
        },
        "metrics": {"tokens": index % 4096},
        "links": [],
        "severity": "info",
    }


def _record_from_event(event: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        event_id=event["event_id"],
        event_type=event["event_type"],
        timestamp=datetime.fromisoformat(
            event["timestamp"].replace("Z", "+00:00")
        ).replace(tzinfo=None),
        trace_id=event["trace_id"],
        session_id=event["session_id"],
        span_id=event.get("span_id"),
        parent_span_id=event.get("parent_span_id"),
        parent_event_id=event.get("parent_event_id"),
        root_event_id=event.get("root_event_id"),
        source_json=event["source"],
        target_json=event.get("target"),
        payload_json=event.get("payload", {}),
        metrics_json=event.get("metrics", {}),
        links_json=event.get("links", []),
        severity=event.get("severity", "info"),
    )


def _synthetic_sessions(session_count: int) -> list[SimpleNamespace]:
    base_time = datetime(2026, 6, 3, 0, 0, 0)
    return [
        SimpleNamespace(
            session_id=f"sess_bench_{index}",
            command=f"synthetic-agent-cluster-{index}",
            started_at=base_time + timedelta(minutes=index),
            ended_at=base_time + timedelta(minutes=index, seconds=30),
            status="completed",
            exit_code=0,
        )
        for index in range(session_count)
    ]


async def _ingest_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    collector = OpenMeshCollector()
    session = EvaluationSession()
    for event in events:
        await collector.accept(session, event, broadcast=False)
    return {
        "events": len(events),
        "records_added": len(session.added),
        "commits": session.commits,
        "rollbacks": session.rollbacks,
    }


def _reconstruct_traces(records: list[Any]) -> dict[str, Any]:
    grouped: dict[str, list[Any]] = {}
    for record in records:
        grouped.setdefault(record.trace_id, []).append(record)

    reconstructed = 0
    span_count = 0
    hierarchy_count = 0
    for trace_id, trace_records in grouped.items():
        ordered = sorted(trace_records, key=lambda item: item.timestamp)
        trace_summary(trace_id, ordered)
        events = [_event_from_record(record) for record in ordered]
        hierarchy_count += len(build_event_hierarchy(events))
        span_count += len(build_span_summary(events))
        build_span_tree(events)
        reconstructed += 1
    return {
        "traces": reconstructed,
        "spans": span_count,
        "hierarchy_roots": hierarchy_count,
    }


def _inspect_representative_nodes(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    if not nodes:
        return {"inspections": 0, "found": 0}
    step = max(1, len(nodes) // 10)
    candidates = nodes[::step][:10]
    found = 0
    for node in candidates:
        if inspect_graph_node(graph, node["id"]):
            found += 1
    return {"inspections": len(candidates), "found": found}


def _run_query_latency_benchmark(
    graph: dict[str, Any], records: list[Any], sessions: list[Any]
) -> dict[str, Any]:
    traces = [
        trace_summary(trace_id, trace_records)
        for trace_id, trace_records in _group_by_trace(records).items()
    ]
    session_payloads = [
        {
            "session_id": session.session_id,
            "command": session.command,
            "started_at": session.started_at.isoformat() + "Z",
            "ended_at": session.ended_at.isoformat() + "Z"
            if session.ended_at
            else None,
            "status": session.status,
            "exit_code": session.exit_code,
        }
        for session in sessions
    ]
    queries = [
        "agents using Tool 1",
        "relationships created since 2026-06-03T00:00:00Z",
        "traces involving Agent 0",
        "sessions involving synthetic-agent-cluster-0",
    ]
    latencies = []
    for query in queries:
        start = time.perf_counter()
        result = run_query_on_state(
            query,
            graph=graph,
            traces=traces,
            sessions=session_payloads,
            snapshots=[],
            timeline={},
        )
        latencies.append(
            {
                "query": query,
                "elapsed_ms": _round_ms(time.perf_counter() - start),
                "status": result.get("status"),
                "count": result.get("count", 0),
            }
        )
    return {
        "queries": len(queries),
        "latencies": latencies,
        "max_latency_ms": max(item["elapsed_ms"] for item in latencies),
    }


def _changed_records(records: list[Any]) -> list[Any]:
    if not records:
        return records
    return records + [
        _record_from_event(
            _event(
                len(records),
                "message.sent",
                {
                    "node_id": "agent:changed",
                    "node_type": "agent",
                    "name": "Changed Agent",
                    "runtime": "openmesh.synthetic",
                    "metadata": {"framework": "synthetic"},
                },
                {
                    "node_id": "agent:0",
                    "node_type": "agent",
                    "name": "Agent 0",
                    "runtime": "openmesh.synthetic",
                    "metadata": {"framework": "synthetic"},
                },
                timestamp=datetime(2026, 6, 3, 23, 59, 59),
                node_count=len(records),
            )
        )
    ]


def _synthetic_federation_peers(node_count: int) -> list[dict[str, Any]]:
    peer_count = max(1, min(10, node_count // 1_000 or 1))
    return [
        {
            "instance_id": f"synthetic-peer-{index}",
            "name": f"Synthetic Peer {index}",
            "organization": "benchmark",
            "cluster": f"cluster-{index % 3}",
            "endpoint": f"https://peer-{index}.example/openmesh",
        }
        for index in range(peer_count)
    ]


def _measure(name: str, operation: Callable[[], Any]) -> tuple[dict[str, Any], Any]:
    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    result = operation()
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return _metric(name, elapsed, peak), result


async def _measure_async(
    name: str, operation: Callable[[], Any]
) -> tuple[dict[str, Any], Any]:
    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    result = await operation()
    elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return _metric(name, elapsed, peak), result


def _metric(name: str, elapsed_seconds: float, peak_bytes: int) -> dict[str, Any]:
    return {
        "name": name,
        "elapsed_ms": _round_ms(elapsed_seconds),
        "peak_memory_bytes": peak_bytes,
        "peak_memory_mb": round(peak_bytes / 1024 / 1024, 3),
        "details": {},
    }


def _group_by_trace(records: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for record in records:
        grouped.setdefault(record.trace_id, []).append(record)
    return grouped


def _event_from_record(record: Any) -> dict[str, Any]:
    event = {
        "spec_version": "0.1",
        "event_id": record.event_id,
        "event_type": record.event_type,
        "timestamp": record.timestamp.isoformat() + "Z",
        "trace_id": record.trace_id,
        "session_id": record.session_id,
        "span_id": getattr(record, "span_id", None),
        "parent_span_id": getattr(record, "parent_span_id", None),
        "parent_event_id": getattr(record, "parent_event_id", None),
        "root_event_id": getattr(record, "root_event_id", None) or record.event_id,
        "source": record.source_json,
        "payload": record.payload_json or {},
        "metrics": record.metrics_json or {},
        "links": getattr(record, "links_json", None) or [],
        "severity": record.severity,
    }
    if record.target_json:
        event["target"] = record.target_json
    return event


def _pick(
    nodes_by_type: dict[str, list[dict[str, Any]]], node_type: str, index: int
) -> dict[str, Any]:
    nodes = nodes_by_type.get(node_type) or next(iter(nodes_by_type.values()))
    return nodes[index % len(nodes)]


def _display(node_type: str) -> str:
    return node_type.replace("_", " ").title()


def _round_ms(elapsed_seconds: float) -> float:
    return round(elapsed_seconds * 1000, 3)


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def run_evaluation_suite_sync(
    sizes: Iterable[int] = DEFAULT_EVALUATION_SIZES,
    *,
    include_ingestion: bool = True,
) -> dict[str, Any]:
    return asyncio.run(run_evaluation_suite(sizes, include_ingestion=include_ingestion))
