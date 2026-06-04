from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from shlex import join as shell_join
from typing import Any, Callable
from uuid import uuid4

from ..db.session import AsyncSessionLocal, init_db
from ..db.openmesh_events import list_openmesh_events
from ..db.openmesh_sessions import complete_openmesh_session, create_openmesh_session
from ..providers import discover_local_providers, list_local_models, verify_providers
from ..runtimes import discover_runtimes
from ..services.openmesh_collector import collector
from ..services.discovery import get_discovery
from ..services.ecosystem_registry import get_ecosystem_registry
from ..services.ecosystem_snapshot import (
    create_ecosystem_snapshot,
    diff_ecosystem_snapshots,
    inspect_ecosystem_snapshot,
    list_ecosystem_snapshots,
)
from ..services.evaluation import (
    DEFAULT_EVALUATION_SIZES,
    report_to_json,
    run_evaluation_suite,
)
from ..failures import get_failure_registry, get_failure_report, inspect_failure
from ..genome import get_agent_comparison, get_agent_genome
from ..reputation import get_agent_reputation, get_agent_score
from ..services.federation import (
    get_federation_peers,
    get_federation_registry,
    inspect_federation_node,
)
from ..services.distributed_nodes import (
    DISTRIBUTED_NODE_TYPES,
    get_distributed_node_registry,
    get_node_status,
    register_distributed_node,
)
from ..services.graph_exploration import (
    explore_graph_node,
    filter_graph,
    graph_statistics,
    search_graph,
)
from ..services.llm_demo import event_types_for_cli, run_research_demo
from ..services.mcp_config_discovery import (
    get_mcp_config_registry,
    register_discovered_mcp_configs,
)
from ..services.mcp_capabilities import get_capability_registry
from ..services.mcp_discovery import get_mcp_registry
from ..services.mcp_tool_observability import (
    get_resource_registry,
    get_tool_registry,
    register_discovered_mcp_ecosystem,
)
from ..services.openmesh_doctor import run_doctor
from ..services.openmesh_queries import (
    get_events,
    get_graph,
    get_health,
    get_trace,
    get_traces,
    inspect_node,
    inspect_workflow,
    list_workflows,
)
from ..services.plugins import get_plugin, list_plugins, load_plugin
from ..services.query_engine import SAVED_QUERIES, execute_query
from ..services.replay import (
    get_replay,
    get_snapshot_replay,
    get_trace_replay,
    get_workflow_replay,
)
from ..services.runtime_observability import observe_runtime
from ..services.simulation import run_local_simulation
from ..services.timeline import (
    get_node_timeline,
    get_timeline,
    get_trace_timeline,
    get_workflow_timeline,
)
from ..services.registry_status import build_registry_status
from ..providers.base import ProviderConfigurationError
from ..shared.openmesh_events import make_openmesh_event
from ..sdk.integrations import list_integrations
from ..workflows import run_multi_agent_demo
from .tui import run_tui


CLI_NODE = {
    "node_id": "openmesh.cli",
    "node_type": "service",
    "name": "OpenMesh CLI",
    "runtime": "python.argparse",
}


def _node_name(node: dict[str, Any] | None) -> str:
    if not node:
        return "None"
    return node.get("name") or node.get("node_id") or "Unknown"


def _short(value: Any, width: int) -> str:
    if value is None:
        return "-"
    text = str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


def _print_health(status: dict[str, Any]) -> None:
    print("OpenMesh Status")
    print()
    print(f"Collector: {status['collector']}")
    print(f"Database: {status['database']}")
    print()
    print(f"Events: {status['events']}")
    print(f"Traces: {status['traces']}")
    print()
    print(f"Nodes: {status['nodes']}")
    print(f"Edges: {status['edges']}")


def _print_events(events: list[dict[str, Any]]) -> None:
    if not events:
        print("No OpenMesh events found.")
        return
    for event in events:
        print(event["timestamp"])
        print(event["event_type"])
        print(f"{_node_name(event.get('source'))} -> {_node_name(event.get('target'))}")
        print()


def _print_traces(traces: list[dict[str, Any]]) -> None:
    if not traces:
        print("No OpenMesh traces found.")
        return
    print(f"{'trace_id':<40} {'events':>6} {'status':<10} started_at")
    for trace in traces:
        print(
            f"{trace['trace_id']:<40} "
            f"{trace['event_count']:>6} "
            f"{trace['status']:<10} "
            f"{trace['started_at']}"
        )


def _print_trace_detail(trace: dict[str, Any]) -> None:
    print(f"Trace {trace['trace_id']}")
    print(f"Status: {trace['status']}")
    print(f"Events: {trace['event_count']}")
    print()
    print("Hierarchy")
    for line in _hierarchy_lines(trace.get("hierarchy", [])):
        print(line)
    print()
    print("Spans")
    for span in trace.get("spans", []):
        parent = span.get("parent_span_id") or "-"
        duration = span.get("duration_ms")
        duration_text = f"{duration}ms" if duration is not None else "-"
        print(
            f"- {span['span_id']} parent:{parent} status:{span.get('status', 'unknown')} "
            f"events:{span['event_count']} duration:{duration_text}"
        )
        for link in span.get("links", []):
            linked = (
                link.get("trace_id")
                or link.get("span_id")
                or link.get("event_id")
                or link.get("url")
            )
            relationship = link.get("relationship") or "linked"
            print(f"  link:{relationship} -> {linked}")
    span_tree = trace.get("span_tree") or []
    if span_tree:
        print()
        print("Span Tree")
        for line in _span_tree_lines(span_tree):
            print(line)
    print()
    print("Graph Relationships")
    relationships = trace.get("relationships", [])
    if not relationships:
        print("- none")
    for edge in relationships:
        print(
            f"- {edge['source']} --{edge['type']}--> {edge['target']} event:{edge['event_id']}"
        )
    print()
    validation = trace.get("validation", {})
    print(f"Validation: {validation.get('status', 'UNKNOWN')}")


def _hierarchy_lines(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        source = _node_name(node.get("source"))
        target = _node_name(node.get("target")) if node.get("target") else None
        target_text = f" -> {target}" if target else ""
        lines.append(f"{prefix}{branch} {node['event_type']} [{source}{target_text}]")
        child_prefix = prefix + ("   " if index == len(nodes) - 1 else "│  ")
        lines.extend(_hierarchy_lines(node.get("children", []), child_prefix))
    return lines


def _span_tree_lines(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        lines.append(
            f"{prefix}{branch} {node['span_id']} "
            f"{node.get('status', 'unknown')} e:{node.get('event_count', 0)}"
        )
        child_prefix = prefix + ("   " if index == len(nodes) - 1 else "│  ")
        lines.extend(_span_tree_lines(node.get("children", []), child_prefix))
    return lines


def _print_graph(graph: dict[str, Any], *, details: bool = False) -> None:
    nodes = {node["id"]: node for node in graph["nodes"]}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph["edges"]:
        outgoing[edge["source"]].append(edge)

    if not nodes:
        print("No OpenMesh graph nodes found.")
        return

    for node_id, node in sorted(nodes.items(), key=lambda item: item[1]["name"]):
        print(node["name"])
        relationships = sorted(
            outgoing.get(node_id, []), key=lambda edge: (edge["type"], edge["target"])
        )
        if not relationships:
            print("└─ no relationships")
            print()
            continue
        for index, edge in enumerate(relationships):
            branch = "└─" if index == len(relationships) - 1 else "├─"
            target = nodes.get(edge["target"], {"name": edge["target"]})
            print(f"{branch} {edge['type']} -> {target['name']}")
            if details:
                definition = edge.get("relationship_definition") or {}
                print(f"   relationship: {edge.get('relationship_type', edge['type'])}")
                print(f"   validation: {edge.get('validation_status', 'unknown')}")
                if definition.get("description"):
                    print(f"   definition: {definition['description']}")
                print(
                    f"   observations: {edge.get('observation_count', edge.get('event_count', 0))}"
                )
                print(f"   lifecycle: {edge.get('lifecycle_state', 'unknown')}")
                print(f"   first_seen: {edge.get('first_seen')}")
                print(f"   last_seen: {edge.get('last_seen')}")
                provenance = edge.get("provenance") or {}
                trace_ids = provenance.get("trace_ids") or edge.get("trace_ids") or []
                event_ids = provenance.get("event_ids") or edge.get("event_ids") or []
                print(f"   provenance.trace_ids: {_join_short(trace_ids)}")
                print(f"   provenance.event_ids: {_join_short(event_ids)}")
                print(
                    "   provenance.window: "
                    f"{provenance.get('first_seen') or edge.get('first_seen')} -> "
                    f"{provenance.get('last_seen') or edge.get('last_seen')}"
                )
                observations = provenance.get("observations") or edge.get(
                    "observations", []
                )
                if observations:
                    latest = observations[-1]
                    print(
                        "   latest_evidence: "
                        f"{latest.get('event_type')} "
                        f"{latest.get('event_id')} "
                        f"trace:{latest.get('trace_id')}"
                    )
        print()

    if details:
        validation = graph.get("validation", {})
        print(f"Validation: {validation.get('status', 'UNKNOWN')}")
        missing = validation.get("missing_provenance") or []
        invalid = validation.get("invalid_relationships") or []
        invalid_types = validation.get("invalid_relationship_types") or []
        invalid_sources = validation.get("invalid_source_types") or []
        invalid_targets = validation.get("invalid_target_types") or []
        broken = validation.get("broken_references") or []
        if missing or invalid or broken:
            print(f"missing_provenance: {len(missing)}")
            print(f"invalid_relationships: {len(invalid)}")
            print(f"invalid_relationship_types: {len(invalid_types)}")
            print(f"invalid_source_types: {len(invalid_sources)}")
            print(f"invalid_target_types: {len(invalid_targets)}")
            print(f"broken_references: {len(broken)}")


def _print_graph_statistics(graph: dict[str, Any]) -> None:
    statistics = graph_statistics(graph)
    print("Graph Statistics")
    print(
        f"nodes: {statistics['node_count']}  relationships: {statistics['edge_count']}"
    )
    print(f"node_types: {_format_counts(statistics['node_types'])}")
    print(f"relationship_types: {_format_counts(statistics['relationship_types'])}")
    if statistics.get("lifecycle_states"):
        print(f"lifecycle: {_format_counts(statistics['lifecycle_states'])}")
    if statistics.get("validation_statuses"):
        print(f"validation: {_format_counts(statistics['validation_statuses'])}")
    print()


def _print_graph_search(result: dict[str, Any]) -> None:
    print(f"OpenMesh Graph Search: {result['query']}")
    print(f"matches: {result['count']}")
    print()
    print("Nodes")
    if not result.get("nodes"):
        print("  none")
    for node in result.get("nodes", []):
        print(
            f"  {node.get('name')} "
            f"({node.get('node_type')}) id:{node.get('node_id')} "
            f"events:{node.get('event_count', 0)}"
        )
    print()
    print("Relationships")
    if not result.get("relationships"):
        print("  none")
    for relationship in result.get("relationships", []):
        provenance = relationship.get("provenance") or {}
        print(
            f"  {relationship.get('source_name')} "
            f"--{relationship.get('relationship_type')}--> "
            f"{relationship.get('target_name')} "
            f"obs:{relationship.get('observation_count', 0)}"
        )
        print(f"    traces: {_join_short(provenance.get('trace_ids', []), limit=3)}")
        print(f"    events: {_join_short(provenance.get('event_ids', []), limit=3)}")


def _print_graph_exploration(
    exploration: dict[str, Any], *, details: bool = False
) -> None:
    selection = exploration["selection"]
    node = selection["node"]
    filters = exploration.get("filters", {})
    neighborhood = exploration.get("neighborhood") or {}
    traversal = exploration.get("traversal") or {}
    statistics = neighborhood.get("statistics", {})

    print("OpenMesh Graph Explorer")
    print()
    print(f"Focus: {node.get('name')} ({node.get('type')})")
    print(f"node_id: {node.get('id')}")
    print(
        "depth: "
        f"{filters.get('depth')}  direction: {filters.get('direction')}  "
        f"node_type: {filters.get('node_type') or '-'}  "
        f"relationship: {filters.get('relationship_type') or '-'}"
    )
    print(
        "neighborhood: "
        f"{statistics.get('node_count', 0)} nodes / "
        f"{statistics.get('edge_count', 0)} relationships / "
        f"{statistics.get('frontier_count', 0)} frontier"
    )
    print()
    relationship_count = len(selection.get("incoming_relationships", [])) + len(
        selection.get("outgoing_relationships", [])
    )
    _print_graph_node_summary(node, relationship_count=relationship_count)
    print()
    print("Relationships")
    relationships = traversal.get("relationships", [])
    if not relationships:
        print("  none")
    for relationship in relationships[:20]:
        arrow = "->" if relationship.get("direction") == "outgoing" else "<-"
        print(
            f"  {arrow} {relationship.get('relationship_type')} "
            f"{relationship.get('node_name')} ({relationship.get('node_type')}) "
            f"obs:{relationship.get('observation_count', 0)}"
        )
        if details:
            provenance = relationship.get("provenance") or {}
            print(
                "     "
                f"traces:{_join_short(provenance.get('trace_ids', []), limit=3)} "
                f"events:{_join_short(provenance.get('event_ids', []), limit=3)} "
                f"last:{provenance.get('last_seen') or '-'}"
            )
    print()
    print("Neighborhood")
    neighborhood_graph = {
        "nodes": neighborhood.get("nodes", []),
        "edges": neighborhood.get("edges", []),
        "validation": {},
    }
    _print_graph(neighborhood_graph, details=details)


def _print_graph_node_summary(
    node: dict[str, Any], *, relationship_count: int | None = None
) -> None:
    provenance = node.get("provenance") or {}
    print("Inspector")
    print(f"  type: {node.get('type')}")
    print(f"  status: {node.get('lifecycle_state', 'unknown')}")
    print(f"  validation: {node.get('validation_status', 'unknown')}")
    print(f"  first_seen: {node.get('first_seen') or '-'}")
    print(f"  last_seen: {node.get('last_seen') or '-'}")
    print(f"  event_count: {node.get('event_count', 0)}")
    print(
        "  relationship_count: "
        f"{relationship_count if relationship_count is not None else node.get('relationship_count', 0)}"
    )
    print(f"  traces: {_join_short(provenance.get('trace_ids', []), limit=5)}")
    print(f"  sessions: {_join_short(provenance.get('session_ids', []), limit=5)}")


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{name}:{count}" for name, count in counts.items())


def _option_set(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    parsed = {
        item.strip()
        for value in values
        for item in str(value).split(",")
        if item.strip()
    }
    return parsed or None


def _single_option(values: set[str] | None) -> str | None:
    if not values or len(values) != 1:
        return None
    return next(iter(values))


def _join_short(values: list[str], limit: int = 3) -> str:
    if not values:
        return "-"
    visible = [str(value) for value in values[:limit]]
    if len(values) > limit:
        visible.append(f"...+{len(values) - limit}")
    return ", ".join(visible)


def _print_nodes(graph: dict[str, Any]) -> None:
    nodes = sorted(
        graph.get("nodes", []), key=lambda node: (node["type"], node["name"])
    )
    if not nodes:
        print("No OpenMesh graph nodes found.")
        return
    print(
        f"{'name':<30} {'type':<14} {'status':<10} {'validation':<10} {'events':>6} last_seen"
    )
    for node in nodes:
        print(
            f"{_short(node['name'], 30):<30} "
            f"{node['type']:<14} "
            f"{node.get('lifecycle_state', 'unknown'):<10} "
            f"{node.get('validation_status', 'unknown'):<10} "
            f"{node.get('event_count', 0):>6} "
            f"{node.get('last_seen') or '-'}"
        )


def _print_failures(registry: dict[str, Any]) -> None:
    failures = registry.get("failures", [])
    summary = registry.get("summary", {})
    print("OpenMesh Failures")
    print()
    print(
        f"failures: {summary.get('failure_count', 0)}  "
        f"active: {summary.get('active_failures', 0)}  "
        f"resolved: {summary.get('resolved_failures', 0)}  "
        f"rate: {summary.get('failure_rate', 0)}%"
    )
    print()
    if not failures:
        print("No failures detected.")
        return
    print(
        f"{'failure_id':<48} {'category':<20} {'status':<10} {'source_event':<24} trace"
    )
    for failure in failures:
        print(
            f"{str(failure.get('failure_id') or '-'):<48} "
            f"{_short(failure.get('category'), 20):<20} "
            f"{_short(failure.get('status'), 10):<10} "
            f"{_short(failure.get('source_event_type'), 24):<24} "
            f"{failure.get('trace_id') or '-'}"
        )


def _print_failure_detail(detail: dict[str, Any]) -> None:
    failure = detail["failure"]
    taxonomy = detail.get("taxonomy", {})
    print(f"OpenMesh Failure: {failure['failure_id']}")
    print()
    print(f"category: {failure.get('category')}")
    print(f"description: {taxonomy.get('description') or '-'}")
    print(f"status: {failure.get('status')}")
    print(f"confidence: {failure.get('confidence')}")
    print(
        f"source_event: {failure.get('source_event_type')} {failure.get('source_event_id')}"
    )
    print(f"trace_id: {failure.get('trace_id') or '-'}")
    print(f"session_id: {failure.get('session_id') or '-'}")
    print(f"detected_at: {failure.get('timestamp')}")
    print(f"resolved_at: {failure.get('resolved_at') or '-'}")
    if failure.get("error"):
        print(f"error: {failure.get('error')}")
    if failure.get("error_type"):
        print(f"error_type: {failure.get('error_type')}")
    print()
    print("Root Cause")
    cause = failure.get("upstream_cause") or {}
    cause_node = cause.get("node") or {}
    print(f"  reason: {cause.get('reason') or '-'}")
    print(f"  event: {cause.get('event_type') or '-'} {cause.get('event_id') or '-'}")
    print(f"  node: {cause_node.get('name') or cause_node.get('node_id') or '-'}")
    print()
    print("Downstream Impact")
    impact = failure.get("downstream_impact") or {}
    print(f"  downstream_events: {impact.get('downstream_event_count', 0)}")
    print(f"  downstream_failures: {impact.get('downstream_failure_count', 0)}")
    impacted = impact.get("impacted_nodes", [])
    print(
        f"  impacted_nodes: {_join_short([node.get('name') or node.get('node_id') for node in impacted], limit=5)}"
    )
    print()
    print("Affected Agents")
    for agent in failure.get("affected_agents", [])[:10]:
        print(f"  - {agent.get('name') or agent.get('node_id')}")
    if not failure.get("affected_agents"):
        print("  none")
    print()
    print("Affected Workflows")
    for workflow in failure.get("affected_workflows", [])[:10]:
        print(f"  - {workflow.get('name') or workflow.get('node_id')}")
    if not failure.get("affected_workflows"):
        print("  none")


def _print_failure_report(report: dict[str, Any]) -> None:
    summary = report.get("summary", {})
    print("OpenMesh Failure Report")
    print()
    print(f"failures: {summary.get('failure_count', 0)}")
    print(f"active: {summary.get('active_failures', 0)}")
    print(f"resolved: {summary.get('resolved_failures', 0)}")
    print(f"failure_rate: {summary.get('failure_rate', 0)}%")
    print(f"mttr_seconds: {summary.get('mttr_seconds') or '-'}")
    print()
    _print_failure_counter(
        "Most Common Failures", report.get("most_common_failures", [])
    )
    _print_failure_counter("Failing Agents", report.get("failing_agents", []))
    _print_failure_counter("Failing Tools", report.get("failing_tools", []))
    _print_failure_counter("Affected Workflows", report.get("affected_workflows", []))


def _print_failure_counter(title: str, rows: list[dict[str, Any]]) -> None:
    print(title)
    if not rows:
        print("  none")
        print()
        return
    for row in rows[:10]:
        print(f"  - {row.get('name')}: {row.get('count')}")
    print()


def _print_rankings(report: dict[str, Any]) -> None:
    summary = report.get("summary", {})
    rankings = report.get("rankings", [])
    print("OpenMesh Agent Rankings")
    print()
    print(
        f"agents: {summary.get('agent_count', 0)}  "
        f"avg_score: {summary.get('average_agent_score', 0)}  "
        f"trust_edges: {summary.get('trust_relationship_count', 0)}"
    )
    print()
    if not rankings:
        print("No agent reputation data found.")
        return
    print(
        f"{'score':>6} {'status':<10} {'success':>7} {'workflow':>8} "
        f"{'tool':>7} {'handoff':>8} agent"
    )
    for agent in rankings:
        metrics = agent.get("metrics", {})
        print(
            f"{agent.get('agent_score', 0):>6.1f} "
            f"{_short(agent.get('status'), 10):<10} "
            f"{metrics.get('success_rate', 0):>6.1f}% "
            f"{metrics.get('workflow_completion_rate', 0):>7.1f}% "
            f"{metrics.get('tool_reliability', 0):>6.1f}% "
            f"{metrics.get('handoff_quality', 0):>7.1f}% "
            f"{agent.get('agent_name')} ({agent.get('agent_id')})"
        )


def _print_agent_score(detail: dict[str, Any]) -> None:
    agent = detail["agent"]
    metrics = agent.get("metrics", {})
    print(f"OpenMesh Agent Score: {agent['agent_name']}")
    print()
    print(f"agent_id: {agent['agent_id']}")
    print(f"agent_score: {agent.get('agent_score', 0)}")
    print(f"status: {agent.get('status')}")
    print(f"first_seen: {agent.get('first_seen') or '-'}")
    print(f"last_seen: {agent.get('last_seen') or '-'}")
    print(f"event_count: {agent.get('event_count', 0)}")
    print(f"trace_count: {agent.get('trace_count', 0)}")
    print(f"session_count: {agent.get('session_count', 0)}")
    print()
    print("Metrics")
    for key in (
        "success_rate",
        "workflow_completion_rate",
        "tool_reliability",
        "handoff_quality",
        "response_latency_score",
        "cost_efficiency",
    ):
        print(f"  {key}: {metrics.get(key, 0)}")
    print(f"  average_latency_ms: {metrics.get('average_latency_ms') or '-'}")
    print(f"  total_tokens: {metrics.get('total_tokens', 0)}")
    print(f"  total_cost_usd: {metrics.get('total_cost_usd', 0)}")
    print()
    print("Outgoing Trust")
    _print_trust_rows(detail.get("outgoing_trust", []))
    print()
    print("Incoming Trust")
    _print_trust_rows(detail.get("incoming_trust", []))


def _print_trust_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("  none")
        return
    for row in rows[:10]:
        print(
            f"  {row.get('source_agent_name')} -> {row.get('target_agent_name')} "
            f"trust={row.get('trust_score')} evidence={len(row.get('evidence_event_ids', []))}"
        )


def _print_agent_genome(detail: dict[str, Any]) -> None:
    genome = detail["genome"]
    print(f"OpenMesh Agent Genome: {genome['agent_name']}")
    print()
    print(f"agent_id: {genome['agent_id']}")
    print(f"genome_signature: {genome.get('genome_signature')}")
    print(f"genome_version: {genome.get('genome_version')}")
    print(f"first_seen: {genome.get('first_seen') or '-'}")
    print(f"last_seen: {genome.get('last_seen') or '-'}")
    print(f"event_count: {genome.get('event_count', 0)}")
    print(f"average_context_size: {genome.get('average_context_size') or '-'}")
    print()
    _print_genome_rows("Preferred Models", genome.get("preferred_models", []))
    _print_genome_rows("Preferred Tools", genome.get("preferred_tools", []))
    _print_genome_rows("Preferred MCP Servers", genome.get("preferred_mcp_servers", []))
    _print_genome_rows("Failure Patterns", genome.get("failure_patterns", []))
    print("Handoff Patterns")
    handoffs = genome.get("handoff_patterns", {})
    print(f"  started: {handoffs.get('started', 0)}")
    print(f"  completed: {handoffs.get('completed', 0)}")
    print(f"  failed: {handoffs.get('failed', 0)}")
    print(f"  completion_rate: {handoffs.get('completion_rate', 0)}%")
    _print_genome_rows("  top_outgoing", handoffs.get("top_outgoing", []))
    _print_genome_rows("  top_incoming", handoffs.get("top_incoming", []))
    print("Cost Profile")
    cost = genome.get("cost_profile", {})
    print(f"  total_cost_usd: {cost.get('total_cost_usd', 0)}")
    print(f"  average_cost_usd: {cost.get('average_cost_usd', 0)}")
    print(f"  total_tokens: {cost.get('total_tokens', 0)}")
    print(f"  average_tokens: {cost.get('average_tokens', 0)}")
    print("Latency Profile")
    latency = genome.get("latency_profile", {})
    print(f"  average_latency_ms: {latency.get('average_latency_ms') or '-'}")
    print(f"  p95_latency_ms: {latency.get('p95_latency_ms') or '-'}")
    print(f"  samples: {latency.get('samples', 0)}")
    print()
    print("Similar Agents")
    resembles = sorted(
        detail.get("resembles", []),
        key=lambda item: -item.get("similarity_score", 0),
    )
    if not resembles:
        print("  none")
    for row in resembles[:10]:
        other = (
            row.get("target_agent_name")
            if row.get("source_agent_id") == genome["agent_id"]
            else row.get("source_agent_name")
        )
        print(
            f"  {other}: {row.get('similarity_score')} "
            f"tools={_join_short(row.get('shared_tools', []), limit=3)}"
        )


def _print_genome_comparison(detail: dict[str, Any]) -> None:
    first = detail["agent_a"]
    second = detail["agent_b"]
    comparison = detail["comparison"]
    print("OpenMesh Agent Genome Compare")
    print()
    print(f"{first['agent_name']} ({first['agent_id']})")
    print(f"{second['agent_name']} ({second['agent_id']})")
    print()
    print(f"similarity_score: {comparison.get('similarity_score')}")
    print(f"relationship: {comparison.get('relationship_type')}")
    print(f"shared_models: {_join_short(comparison.get('shared_models', []), limit=8)}")
    print(f"shared_tools: {_join_short(comparison.get('shared_tools', []), limit=8)}")
    print(
        f"shared_mcp_servers: {_join_short(comparison.get('shared_mcp_servers', []), limit=8)}"
    )
    print(
        f"shared_failures: {_join_short(comparison.get('shared_failure_patterns', []), limit=8)}"
    )
    print(
        f"latency_similarity: {comparison.get('latency_similarity')}  "
        f"cost_similarity: {comparison.get('cost_similarity')}"
    )
    print(
        f"evidence_events: {_join_short(comparison.get('evidence_event_ids', []), limit=5)}"
    )


def _print_genome_rows(title: str, rows: list[dict[str, Any]]) -> None:
    print(title)
    if not rows:
        print("  none")
        return
    for row in rows[:5]:
        print(f"  - {row.get('name')}: {row.get('count')} ({row.get('share')}%)")


def _print_node_inspection(inspection: dict[str, Any]) -> None:
    node = inspection["node"]
    provenance = inspection.get("provenance", {})
    print(node["name"])
    print()
    print(f"node_id: {inspection['node_id']}")
    print(f"type: {inspection['node_type']}")
    print(f"status: {node.get('lifecycle_state', 'unknown')}")
    print(f"validation: {inspection.get('validation', {}).get('status', 'unknown')}")
    print(f"first_seen: {inspection.get('first_seen') or '-'}")
    print(f"last_seen: {inspection.get('last_seen') or '-'}")
    print(f"event_count: {inspection.get('event_count', 0)}")
    print(f"relationship_count: {inspection.get('relationship_count', 0)}")
    print()
    print("Traces")
    print(f"  {_join_short(inspection.get('trace_ids', []), limit=5)}")
    print("Sessions")
    print(f"  {_join_short(inspection.get('session_ids', []), limit=5)}")
    print()
    print("Incoming Relationships")
    _print_inspection_relationships(inspection.get("incoming_relationships", []))
    print()
    print("Outgoing Relationships")
    _print_inspection_relationships(inspection.get("outgoing_relationships", []))
    print()
    print("Provenance")
    print(f"  events: {_join_short(provenance.get('event_ids', []), limit=5)}")
    print(
        f"  window: {provenance.get('first_seen') or '-'} -> {provenance.get('last_seen') or '-'}"
    )
    print(f"  first_event: {provenance.get('first_event_id') or '-'}")
    print(f"  last_event: {provenance.get('last_event_id') or '-'}")
    print(f"  relationship_events: {provenance.get('relationship_event_count', 0)}")
    observations = provenance.get("observations", [])
    if observations:
        print("  recent_observations:")
        for observation in observations[-5:]:
            print(
                "    "
                f"{observation.get('timestamp')} "
                f"{observation.get('event_type')} "
                f"{observation.get('event_id')} "
                f"role:{observation.get('role', '-')}"
            )


def _print_inspection_relationships(edges: list[dict[str, Any]]) -> None:
    if not edges:
        print("  none")
        return
    for edge in sorted(edges, key=lambda item: (item["type"], item["id"]))[:20]:
        provenance = edge.get("provenance") or {}
        print(
            f"  {edge['type']} {edge['source']} -> {edge['target']} "
            f"obs:{edge.get('observation_count', edge.get('event_count', 0))} "
            f"state:{edge.get('lifecycle_state', 'unknown')}"
        )
        print(f"    traces: {_join_short(provenance.get('trace_ids', []), limit=3)}")
        print(f"    events: {_join_short(provenance.get('event_ids', []), limit=3)}")


def _print_registry(registry: dict[str, Any]) -> None:
    compatibility = registry["compatibility"]
    print("OpenMesh Registry")
    print()
    print("Versions")
    for name, version in registry["versions"].items():
        print(f"- {name}: {version}")
    print()
    print(f"Compatibility: {compatibility['severity']}")
    for warning in compatibility.get("warnings", []):
        print(f"WARNING: {warning['message']}")
    for error in compatibility.get("errors", []):
        print(f"ERROR: {error['message']}")
    if not compatibility.get("warnings") and not compatibility.get("errors"):
        print("No compatibility issues detected.")
    print()
    print("Node Definitions")
    for definition in registry["node_definitions"]:
        marker = _definition_marker(definition)
        print(
            f"{marker} {definition['type']:<16} {definition['display_name']} ({definition['category']})"
        )
    print()
    print("Relationship Definitions")
    for definition in registry["relationship_definitions"]:
        marker = _definition_marker(definition)
        print(f"{marker} {definition['type']:<20} {definition['description']}")


def _definition_marker(definition: dict[str, Any]) -> str:
    if definition.get("removed_in"):
        return "✖"
    if definition.get("deprecated_in"):
        return "!"
    return "✓"


def _print_doctor(report: dict[str, Any]) -> None:
    print("OpenMesh Doctor")
    print()
    for check in report["checks"]:
        severity = check.get("severity", check["status"])
        print(f"{check['name']}: {severity}")
        detail = check.get("detail")
        if isinstance(detail, dict):
            for key, value in detail.items():
                if isinstance(value, list):
                    print(f"  {key}: {len(value)}")
                    for item in value[:5]:
                        print(f"    - {item}")
                    if len(value) > 5:
                        print(f"    ... {len(value) - 5} more")
                else:
                    print(f"  {key}: {value}")
        elif detail:
            print(f"  {detail}")
    print()
    print(f"Overall: {report['status']}")


def _integration_symbol(integration: dict[str, Any]) -> str:
    if integration.get("active") or integration.get("available"):
        return "✓"
    return "○"


def _print_integrations(integrations: list[dict[str, Any]]) -> None:
    print("Installed Integrations")
    print()
    for integration in integrations:
        version = integration.get("version") or "-"
        suffix = ""
        if integration.get("status") == "planned":
            suffix = " (planned)"
        print(
            f"{_integration_symbol(integration)} {integration['name']}{suffix} "
            f"- {integration['status_label']} - version: {version}"
        )


def _print_plugins(plugins: list[dict[str, Any]]) -> None:
    print("OpenMesh Plugins")
    print()
    if not plugins:
        print("No OpenMesh plugins discovered.")
        return
    print(f"{'plugin':<18} {'kind':<12} {'status':<14} {'version':<10} module")
    for plugin in plugins:
        print(
            f"{plugin['plugin_id']:<18} "
            f"{plugin.get('kind', '-'):<12} "
            f"{plugin.get('status_label', '-'):<14} "
            f"{plugin.get('version', '-'):<10} "
            f"{plugin.get('module', '-')}"
        )


def _print_plugin_detail(plugin: dict[str, Any]) -> None:
    print(f"OpenMesh Plugin: {plugin['name']}")
    print()
    print(f"plugin_id: {plugin['plugin_id']}")
    print(f"kind: {plugin.get('kind')}")
    print(f"status: {plugin.get('status')}")
    print(f"status_label: {plugin.get('status_label')}")
    print(f"version: {plugin.get('version')}")
    print(f"plugin_api_version: {plugin.get('plugin_api_version')}")
    print(f"registry_version: {plugin.get('registry_version')}")
    print(f"supported_plugin_api_version: {plugin.get('supported_plugin_api_version')}")
    print(f"module: {plugin.get('module')}")
    print(f"entrypoint: {plugin.get('entrypoint') or '-'}")
    print(f"package: {plugin.get('package') or '-'}")
    print(f"package_version: {plugin.get('package_version') or '-'}")
    print(f"available: {plugin.get('available')}")
    print(f"active: {plugin.get('active')}")
    if plugin.get("description"):
        print(f"description: {plugin['description']}")
    print()
    print("Capabilities")
    capabilities = plugin.get("capabilities") or []
    if not capabilities:
        print("  none")
    for capability in capabilities:
        print(f"  - {capability}")
    validation = plugin.get("validation") or {}
    print()
    print(f"Validation: {validation.get('status', 'unknown')}")
    for error in validation.get("errors", []):
        print(f"  ERROR {error.get('code')}: {error.get('message')}")
    for warning in validation.get("warnings", []):
        print(f"  WARNING {warning.get('code')}: {warning.get('message')}")
    try:
        loaded = load_plugin(plugin["plugin_id"])
    except Exception as exc:
        print(f"loadable: no ({exc})")
    else:
        entrypoint = loaded.entrypoint
        print(f"loadable: yes ({getattr(entrypoint, '__name__', 'module')})")


def _print_plugin_validation(plugin: dict[str, Any]) -> None:
    validation = plugin.get("validation") or {}
    print(f"OpenMesh Plugin Validation: {plugin['plugin_id']}")
    print()
    print(f"status: {validation.get('status', 'unknown')}")
    print(f"registry_version: {validation.get('registry_version')}")
    print(
        "supported_plugin_api_version: "
        f"{validation.get('supported_plugin_api_version')}"
    )
    errors = validation.get("errors", [])
    warnings = validation.get("warnings", [])
    if not errors and not warnings:
        print("No validation issues found.")
        return
    for error in errors:
        print(f"ERROR {error.get('code')}: {error.get('message')}")
    for warning in warnings:
        print(f"WARNING {warning.get('code')}: {warning.get('message')}")


def _print_discovery(discovery: dict[str, list[dict[str, Any]]]) -> None:
    sections = [
        ("Frameworks", "frameworks"),
        ("Agents", "agents"),
        ("Tools", "tools"),
        ("Capabilities", "capabilities"),
        ("Resources", "resources"),
        ("Workflows", "workflows"),
        ("Processes", "processes"),
        ("Services", "services"),
    ]
    for title, key in sections:
        print(title)
        print()
        entries = discovery.get(key, [])
        if not entries:
            print("  none observed")
        for entry in entries:
            marker = "✓" if key == "frameworks" else "-"
            detail = f"{entry['status']} · events:{entry['event_count']} · relationships:{entry['relationship_count']}"
            print(f"{marker} {entry['name']} ({detail})")
        print()


def _print_mcp(servers: list[dict[str, Any]]) -> None:
    print("MCP Servers")
    print()
    if not servers:
        print("No MCP servers discovered.")
        return
    print(f"{'server':<28} {'version':<12} {'transport':<12} last_seen")
    for server in servers:
        print(
            f"{_short(server.get('server'), 28):<28} "
            f"{_short(server.get('version') or '-', 12):<12} "
            f"{_short(server.get('transport') or '-', 12):<12} "
            f"{server.get('last_seen') or '-'}"
        )


def _print_mcp_discovery(result: dict[str, Any]) -> None:
    print("MCP Discovery")
    print()
    servers = result.get("servers", [])
    if not servers:
        print("No MCP servers discovered.")
    for server in servers:
        print(str(server.get("server") or server.get("name")))
    tools = result.get("tools", [])
    if tools:
        print()
        print("Tools")
        for tool in tools:
            print(f"- {tool.get('server')} / {tool.get('tool')}")
    resources = result.get("resources", [])
    if resources:
        print()
        print("Resources")
        for resource in resources:
            print(
                f"- {resource.get('server')} / {resource.get('resource')} "
                f"({resource.get('resource_type')})"
            )
    issues = result.get("issues", [])
    if issues:
        print()
        print("Issues")
        for issue in issues:
            print(
                f"- {issue.get('source')} {issue.get('config_path')}: "
                f"{issue.get('code')} ({issue.get('message')})"
            )


def _print_tools(tools: list[dict[str, Any]]) -> None:
    print("OpenMesh Tools")
    print()
    if not tools:
        print("No tools discovered.")
        return
    print(f"{'server':<24} {'tool':<28} {'category':<14} calls")
    for tool in tools:
        print(
            f"{_short(tool.get('server') or '-', 24):<24} "
            f"{_short(tool.get('tool') or tool.get('name'), 28):<28} "
            f"{_short(tool.get('category') or '-', 14):<14} "
            f"{tool.get('relationship_count', 0)}"
        )


def _print_resources(resources: list[dict[str, Any]]) -> None:
    print("OpenMesh Resources")
    print()
    if not resources:
        print("No resources discovered.")
        return
    print(f"{'type':<18} {'resource':<28} {'server':<24} locator")
    for resource in resources:
        print(
            f"{_short(resource.get('resource_type') or '-', 18):<18} "
            f"{_short(resource.get('resource') or resource.get('name'), 28):<28} "
            f"{_short(resource.get('server') or '-', 24):<24} "
            f"{resource.get('locator') or '-'}"
        )


def _print_mcp_config(
    configs: list[dict[str, Any]], *, issues: list[dict[str, Any]] | None = None
) -> None:
    print("MCP Configuration Sources")
    print()
    issues = issues or []
    if issues:
        print("Issues")
        for issue in issues:
            print(
                f"- {issue['source']} {issue['config_path']}: {issue['code']} ({issue['message']})"
            )
        print()
    if not configs:
        print("No MCP configuration entries discovered.")
        return
    print(f"{'source':<18} {'server':<24} {'transport':<12} path")
    for config in configs:
        print(
            f"{_short(config.get('source'), 18):<18} "
            f"{_short(config.get('server'), 24):<24} "
            f"{_short(config.get('transport') or '-', 12):<12} "
            f"{config.get('config_path') or '-'}"
        )


def _print_capabilities(capabilities: list[dict[str, Any]]) -> None:
    print("MCP Capabilities")
    print()
    if not capabilities:
        print("No MCP capabilities discovered.")
        return
    print(f"{'server':<24} {'capability':<28} {'category':<14} version")
    for capability in capabilities:
        print(
            f"{_short(capability.get('server'), 24):<24} "
            f"{_short(capability.get('capability'), 28):<28} "
            f"{_short(capability.get('category') or '-', 14):<14} "
            f"{capability.get('version') or '-'}"
        )


def _print_workflows(workflows: list[dict[str, Any]]) -> None:
    print("Workflows")
    print()
    if not workflows:
        print("No workflows discovered.")
        return
    print(f"{'workflow_id':<34} {'workflow':<24} {'type':<14} {'status':<12} started")
    for workflow in workflows:
        print(
            f"{_short(workflow.get('workflow_id') or workflow.get('id'), 34):<34} "
            f"{_short(workflow.get('workflow') or workflow.get('name'), 24):<24} "
            f"{_short(workflow.get('workflow_type') or workflow.get('framework') or '-', 14):<14} "
            f"{_short(workflow.get('status') or 'observed', 12):<12} "
            f"{workflow.get('started_at') or workflow.get('last_seen') or '-'}"
        )


def _print_workflow_inspection(workflow: dict[str, Any]) -> None:
    print(workflow["workflow"])
    print()
    print(f"workflow_id: {workflow['workflow_id']}")
    print(f"workflow_type: {workflow.get('workflow_type') or '-'}")
    print(f"runtime: {workflow.get('runtime') or '-'}")
    print(f"status: {workflow.get('status') or 'observed'}")
    print(f"started_at: {workflow.get('started_at') or '-'}")
    print(f"ended_at: {workflow.get('ended_at') or '-'}")
    print(f"event_count: {workflow.get('event_count', 0)}")
    print(f"relationship_count: {workflow.get('relationship_count', 0)}")
    print()
    print("Participating Agents")
    _print_participants(workflow.get("participating_agents", []))
    print()
    print("Participating Tools")
    _print_participants(workflow.get("participating_tools", []))
    print()
    print("Participating MCP Servers")
    _print_participants(workflow.get("participating_mcp_servers", []))
    print()
    print("Participating Services")
    _print_participants(workflow.get("participating_services", []))
    print()
    print("Traces")
    print(f"  {_join_short(workflow.get('trace_ids', []), limit=5)}")
    print("Sessions")
    print(f"  {_join_short(workflow.get('session_ids', []), limit=5)}")
    provenance = workflow.get("provenance", {})
    print()
    print("Workflow Provenance")
    print(f"  events: {_join_short(provenance.get('event_ids', []), limit=5)}")
    print(
        f"  window: {provenance.get('first_seen') or '-'} -> {provenance.get('last_seen') or '-'}"
    )
    print(f"  first_event: {provenance.get('first_event_id') or '-'}")
    print(f"  last_event: {provenance.get('last_event_id') or '-'}")


def _print_participants(participants: list[dict[str, Any]]) -> None:
    if not participants:
        print("  none")
        return
    for participant in participants:
        print(
            f"  {participant['name']} "
            f"({participant['type']}, {participant['relationship_type']}, "
            f"{participant['direction']}, events:{participant.get('event_count', 0)})"
        )


def _print_ecosystem(ecosystem: dict[str, Any]) -> None:
    print("OpenMesh Ecosystem")
    print()
    summary = ecosystem.get("summary", {})
    print(f"Entities: {summary.get('entity_count', 0)}")
    print(f"Relationships: {summary.get('relationship_count', 0)}")
    print()
    labels = [
        ("Agents", "agents"),
        ("Tools", "tools"),
        ("Processes", "processes"),
        ("Resources", "resources"),
        ("Workflows", "workflows"),
        ("MCP Servers", "mcp_servers"),
        ("MCP Configs", "mcp_configs"),
        ("Capabilities", "capabilities"),
    ]
    for title, key in labels:
        print(title)
        entities = ecosystem.get("entities", {}).get(key, [])
        if not entities:
            print("  none observed")
        for entity in entities:
            print(
                f"  {_short(entity.get('name'), 28):<28} "
                f"{_short(entity.get('status'), 10):<10} "
                f"e:{entity.get('event_count', 0):<3} "
                f"r:{entity.get('relationship_count', 0):<3} "
                f"{entity.get('last_seen') or '-'}"
            )
        print()


def _print_snapshot_created(snapshot: dict[str, Any]) -> None:
    print("OpenMesh Snapshot Created")
    print()
    _print_snapshot_summary(snapshot)


def _print_snapshots(snapshots: list[dict[str, Any]]) -> None:
    print("OpenMesh Snapshots")
    print()
    if not snapshots:
        print("No snapshots found.")
        return
    print(f"{'snapshot_id':<38} {'created_at':<28} nodes edges traces sessions")
    for snapshot in snapshots:
        counts = snapshot.get("counts", {})
        print(
            f"{_short(snapshot.get('snapshot_id'), 38):<38} "
            f"{_short(snapshot.get('created_at'), 28):<28} "
            f"{counts.get('nodes', 0):>5} "
            f"{counts.get('edges', 0):>5} "
            f"{counts.get('traces', 0):>6} "
            f"{counts.get('sessions', 0):>8}"
        )


def _print_snapshot_detail(snapshot: dict[str, Any]) -> None:
    print("OpenMesh Snapshot")
    print()
    _print_snapshot_summary(snapshot)
    contents = snapshot.get("contents", {})
    print()
    print("Contents")
    for label, key in [
        ("Agents", "agents"),
        ("Tools", "tools"),
        ("Workflows", "workflows"),
        ("Processes", "processes"),
        ("Services", "services"),
        ("MCP Servers", "mcp_servers"),
        ("Capabilities", "capabilities"),
        ("Relationships", "relationships"),
        ("Traces", "traces"),
        ("Sessions", "sessions"),
    ]:
        print(f"  {label}: {len(contents.get(key, []))}")
    graph_stats = snapshot.get("graph_statistics", {})
    ecosystem_stats = snapshot.get("ecosystem_statistics", {})
    print()
    print("Graph Statistics")
    print(f"  node_count: {graph_stats.get('node_count', 0)}")
    print(f"  edge_count: {graph_stats.get('edge_count', 0)}")
    print(f"  node_types: {graph_stats.get('node_types', {})}")
    print(f"  relationship_types: {graph_stats.get('relationship_types', {})}")
    print(f"  validation: {graph_stats.get('validation_status', 'UNKNOWN')}")
    print()
    print("Ecosystem Statistics")
    print(f"  entity_count: {ecosystem_stats.get('entity_count', 0)}")
    print(f"  relationship_count: {ecosystem_stats.get('relationship_count', 0)}")
    print(f"  groups: {ecosystem_stats.get('groups', {})}")
    print(f"  validation: {ecosystem_stats.get('validation_status', 'UNKNOWN')}")


def _print_snapshot_summary(snapshot: dict[str, Any]) -> None:
    counts = snapshot.get("counts", {})
    print(f"snapshot_id: {snapshot.get('snapshot_id')}")
    print(f"created_at: {snapshot.get('created_at')}")
    print(f"schema_version: {snapshot.get('schema_version', '-')}")
    print()
    print("Counts")
    for key in [
        "agents",
        "tools",
        "workflows",
        "processes",
        "services",
        "mcp_servers",
        "capabilities",
        "nodes",
        "edges",
        "traces",
        "sessions",
        "events",
    ]:
        print(f"  {key}: {counts.get(key, 0)}")


def _print_snapshot_diff(diff: dict[str, Any]) -> None:
    snapshot_a = diff["snapshot_a"]
    snapshot_b = diff["snapshot_b"]
    summary = diff["summary"]
    print("OpenMesh Snapshot Diff")
    print()
    print(
        f"{snapshot_a.get('snapshot_id')} ({snapshot_a.get('created_at')}) "
        f"-> {snapshot_b.get('snapshot_id')} ({snapshot_b.get('created_at')})"
    )
    print()
    print("Summary")
    for key in [
        "nodes_added",
        "nodes_removed",
        "nodes_changed",
        "relationships_added",
        "relationships_removed",
        "relationships_changed",
        "workflows_added",
        "workflows_removed",
        "mcp_servers_added",
        "mcp_servers_removed",
        "capabilities_added",
        "capabilities_removed",
        "trace_count_delta",
        "session_count_delta",
        "graph_node_delta",
        "graph_edge_delta",
    ]:
        print(f"  {key}: {summary.get(key, 0)}")
    print()
    _print_diff_items("Nodes Added", diff["nodes"].get("added", []))
    _print_diff_items("Nodes Removed", diff["nodes"].get("removed", []))
    _print_changed_items("Nodes Changed", diff["nodes"].get("changed", []))
    _print_diff_items("Relationships Added", diff["relationships"].get("added", []))
    _print_diff_items("Relationships Removed", diff["relationships"].get("removed", []))
    _print_changed_items(
        "Relationships Changed", diff["relationships"].get("changed", [])
    )
    _print_diff_items("Workflows Added", diff["workflows"].get("added", []))
    _print_diff_items("Workflows Removed", diff["workflows"].get("removed", []))
    _print_diff_items("MCP Servers Added", diff["mcp_servers"].get("added", []))
    _print_diff_items("MCP Servers Removed", diff["mcp_servers"].get("removed", []))
    _print_diff_items("Capabilities Added", diff["capabilities"].get("added", []))
    _print_diff_items("Capabilities Removed", diff["capabilities"].get("removed", []))
    print("Graph Statistics Delta")
    for key, value in diff.get("graph_statistics_delta", {}).items():
        if isinstance(value, dict) and {"before", "after", "delta"} <= set(value):
            print(
                f"  {key}: {value['before']} -> {value['after']} ({value['delta']:+})"
            )
        elif isinstance(value, dict):
            print(f"  {key}:")
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, dict) and "delta" in nested_value:
                    print(
                        f"    {nested_key}: {nested_value['before']} -> "
                        f"{nested_value['after']} ({nested_value['delta']:+})"
                    )
                else:
                    print(f"    {nested_key}: {nested_value}")
        else:
            print(f"  {key}: {value}")


def _print_diff_items(title: str, items: list[dict[str, Any]]) -> None:
    print(title)
    if not items:
        print("  none")
        print()
        return
    for item in items[:20]:
        print(f"  - {_diff_item_title(item)}")
        provenance = item.get("provenance") or {}
        if provenance:
            print(
                f"    traces: {_join_short(provenance.get('trace_ids', []), limit=3)}"
            )
            print(
                f"    events: {_join_short(provenance.get('event_ids', []), limit=3)}"
            )
    if len(items) > 20:
        print(f"  ... {len(items) - 20} more")
    print()


def _print_changed_items(title: str, items: list[dict[str, Any]]) -> None:
    print(title)
    if not items:
        print("  none")
        print()
        return
    for item in items[:20]:
        print(f"  - {_diff_item_title(item)}")
        print(f"    changed: {', '.join(item.get('changed_fields', []))}")
        after = item.get("after", {})
        provenance = after.get("provenance") or {}
        if provenance:
            print(
                f"    traces: {_join_short(provenance.get('trace_ids', []), limit=3)}"
            )
            print(
                f"    events: {_join_short(provenance.get('event_ids', []), limit=3)}"
            )
    if len(items) > 20:
        print(f"  ... {len(items) - 20} more")
    print()


def _diff_item_title(item: dict[str, Any]) -> str:
    source = item.get("source")
    target = item.get("target")
    relationship = item.get("type") or item.get("relationship_type")
    if source and target and relationship:
        return f"{source} {relationship} {target}"
    for key in ("name", "workflow", "server", "capability", "id", "workflow_id"):
        if item.get(key):
            return str(item[key])
    return str(item)


def _print_timeline(timeline: dict[str, Any]) -> None:
    subject = timeline.get("subject", {})
    scope = timeline.get("scope", "ecosystem")
    print(f"OpenMesh {scope.title()} Timeline")
    print()
    print(f"subject: {_timeline_subject(subject)}")
    print(f"first_appearance: {timeline.get('first_appearance') or '-'}")
    print(f"last_appearance: {timeline.get('last_appearance') or '-'}")
    print()
    print("Summary")
    for key, value in timeline.get("summary", {}).items():
        print(f"  {key}: {value}")
    print()
    _print_timeline_section(
        "Relationship Changes", timeline.get("relationship_changes", [])
    )
    _print_timeline_section("Workflow Changes", timeline.get("workflow_changes", []))
    _print_timeline_section(
        "Capability Changes", timeline.get("capability_changes", [])
    )
    _print_timeline_section("MCP Changes", timeline.get("mcp_changes", []))
    _print_timeline_section("Session History", timeline.get("session_history", []))
    _print_timeline_section("Snapshot History", timeline.get("snapshot_history", []))
    _print_timeline_section("Timeline", timeline.get("timeline", []), limit=25)


def _print_timeline_section(
    title: str, items: list[dict[str, Any]], *, limit: int = 12
) -> None:
    print(title)
    if not items:
        print("  none")
        print()
        return
    for item in items[:limit]:
        print(f"  - {_timeline_item(item)}")
    if len(items) > limit:
        print(f"  ... {len(items) - limit} more")
    print()


def _timeline_subject(subject: dict[str, Any]) -> str:
    for key in ("workflow", "name", "trace_id", "snapshot_id", "id", "node_id"):
        if subject.get(key):
            return str(subject[key])
    return str(subject.get("type") or "ecosystem")


def _timeline_item(item: dict[str, Any]) -> str:
    timestamp = (
        item.get("timestamp") or item.get("started_at") or item.get("created_at") or "-"
    )
    kind = item.get("kind") or item.get("event_type") or item.get("status") or "item"
    if item.get("event_id") and item.get("event_type"):
        return (
            f"{timestamp} {kind} {item.get('event_type')} "
            f"{item.get('source') or '-'} -> {item.get('target') or '-'}"
        )
    if item.get("source") and item.get("target"):
        return (
            f"{timestamp} {kind} "
            f"{item.get('source')} -> {item.get('target')} "
            f"{item.get('relationship_type') or ''}".strip()
        )
    if item.get("snapshot_id"):
        counts = item.get("counts", {})
        return (
            f"{timestamp} {kind} {item['snapshot_id']} "
            f"nodes:{counts.get('nodes', 0)} edges:{counts.get('edges', 0)}"
        )
    if item.get("session_id"):
        return (
            f"{timestamp} {kind} {item['session_id']} {_short(item.get('command'), 36)}"
        )
    return f"{timestamp} {kind} {_timeline_subject(item)}"


def _print_replay(replay: dict[str, Any]) -> None:
    subject = replay.get("subject", {})
    state = replay.get("state", {})
    summary = replay.get("summary", {})
    print(f"OpenMesh {str(replay.get('scope', 'ecosystem')).title()} Replay")
    print()
    print(f"subject: {_timeline_subject(subject)}")
    print(f"control: {state.get('control')} ({state.get('status')})")
    print(
        f"position: {state.get('position')} / {max(state.get('frame_count', 0) - 1, 0)}"
    )
    if state.get("speed") is not None:
        print(f"speed: {state.get('speed')}x")
    if state.get("jump_event_id") or state.get("jump_timestamp"):
        print(
            "jump: "
            f"event={state.get('jump_event_id') or '-'} "
            f"timestamp={state.get('jump_timestamp') or '-'}"
        )
    print()
    print("Controls")
    for control in replay.get("controls", []):
        print(f"  {control['name']}: {control['description']}")
    print()
    print("Summary")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print()
    current = state.get("current_frame")
    print("Current Frame")
    if current:
        print(f"  {_replay_frame(current)}")
    else:
        print("  none")
    print()
    print("Visible Frames")
    visible = replay.get("visible_frames", [])
    if not visible:
        print("  none")
    for frame in visible[-20:]:
        print(f"  - {_replay_frame(frame)}")
    if len(visible) > 20:
        print(f"  ... {len(visible) - 20} earlier")


def _replay_frame(frame: dict[str, Any]) -> str:
    timestamp = frame.get("timestamp") or "-"
    index = frame.get("frame_index", "-")
    action = frame.get("action") or "frame"
    description = frame.get("description") or "-"
    return f"[{index}] {timestamp} {action} {description}"


def _print_federation(registry: dict[str, Any]) -> None:
    local = registry.get("local_node", {})
    snapshot = registry.get("snapshot", {})
    counts = snapshot.get("counts", {})
    replay = registry.get("replay", {})
    replay_state = replay.get("state", {})
    policy = registry.get("policy", {})
    print("OpenMesh Federation")
    print()
    print(f"schema_version: {registry.get('schema_version')}")
    print(f"protocol_version: {registry.get('protocol_version')}")
    print(f"local_node: {local.get('name')} ({local.get('id')})")
    print(f"organization: {local.get('organization')}")
    print(f"cluster: {local.get('cluster')}")
    print()
    print(f"peers: {len(registry.get('peers', []))}")
    print(f"relationships: {len(registry.get('relationships', []))}")
    print(f"snapshot_instances: {counts.get('instances', 0)}")
    print(f"timeline_entries: {len(registry.get('timeline', {}).get('timeline', []))}")
    print(f"replay_frames: {replay_state.get('frame_count', 0)}")
    print()
    print("Policy")
    for key in (
        "metadata_only",
        "remote_execution",
        "remote_control",
        "code_execution",
        "security_analysis",
    ):
        print(f"  {key}: {policy.get(key)}")


def _print_federation_peers(
    peers: list[dict[str, Any]], *, title: str = "OpenMesh Federation Peers"
) -> None:
    print(title)
    print()
    if not peers:
        print("No federation peers configured.")
        return
    print(f"{'peer':<34} {'status':<12} {'org':<16} {'cluster':<16} endpoint")
    for peer in peers:
        print(
            f"{_short(peer.get('id'), 34):<34} "
            f"{_short(peer.get('status'), 12):<12} "
            f"{_short(peer.get('organization'), 16):<16} "
            f"{_short(peer.get('cluster'), 16):<16} "
            f"{peer.get('endpoint') or '-'}"
        )


def _print_federation_inspection(inspection: dict[str, Any]) -> None:
    node = inspection.get("node", {})
    policy = inspection.get("policy", {})
    print(f"OpenMesh Federation Node: {inspection.get('name')}")
    print()
    print(f"node_id: {inspection.get('node_id')}")
    print(f"status: {inspection.get('status')}")
    print(f"organization: {inspection.get('organization')}")
    print(f"cluster: {inspection.get('cluster')}")
    print(f"endpoint: {inspection.get('endpoint') or '-'}")
    print(f"type: {node.get('type') or node.get('node_type')}")
    print()
    print("Capabilities")
    capabilities = inspection.get("capabilities", [])
    if not capabilities:
        print("  none")
    for capability in capabilities:
        print(f"  - {capability}")
    print()
    print("Relationships")
    relationships = inspection.get("relationships", [])
    if not relationships:
        print("  none")
    for relationship in relationships[:20]:
        print(
            f"  {relationship.get('source')} --{relationship.get('type')}--> "
            f"{relationship.get('target')}"
        )
    print()
    print("Snapshot")
    counts = inspection.get("snapshot", {}).get("counts", {})
    for key, value in counts.items():
        print(f"  {key}: {value}")
    print()
    print("Policy")
    for key, value in policy.items():
        print(f"  {key}: {value}")


def _print_node_status(status: dict[str, Any]) -> None:
    local = status.get("local_node", {})
    summary = status.get("summary", {})
    observed = status.get("observed_node")
    print("OpenMesh Node Status")
    print()
    print(f"node_id: {local.get('node_id')}")
    print(f"node_name: {local.get('node_name')}")
    print(f"node_type: {local.get('node_type')}")
    print(f"config_path: {local.get('config_path')}")
    print(f"registered: {'yes' if status.get('registered') else 'no'}")
    if observed:
        print(f"status: {observed.get('status')}")
        print(f"last_seen: {observed.get('last_seen') or '-'}")
        print(f"uptime_seconds: {observed.get('uptime_seconds', 0)}")
    print()
    print("Registry")
    print(f"  active_nodes: {summary.get('active_nodes', 0)}")
    print(f"  hosted_agents: {summary.get('hosted_agents', 0)}")
    print(f"  hosted_runtimes: {summary.get('hosted_runtimes', 0)}")
    print(f"  hosted_mcp_servers: {summary.get('hosted_mcp_servers', 0)}")


def _print_distributed_node_registry(registry: dict[str, Any]) -> None:
    nodes = registry.get("nodes", [])
    summary = registry.get("summary", {})
    print("OpenMesh Nodes")
    print()
    print(
        f"nodes: {summary.get('node_count', 0)}  "
        f"active: {summary.get('active_nodes', 0)}  "
        f"host relationships: {summary.get('host_relationships', 0)}"
    )
    print()
    if not nodes:
        print("No distributed OpenMesh nodes observed.")
        return
    print(
        f"{'node':<28} {'type':<12} {'status':<10} "
        f"{'agents':>6} {'runtime':>7} {'mcp':>5} last_seen"
    )
    for node in nodes:
        hosted = node.get("hosted_counts", {})
        print(
            f"{_short(node.get('node_name'), 28):<28} "
            f"{_short(node.get('node_type'), 12):<12} "
            f"{_short(node.get('status'), 10):<10} "
            f"{hosted.get('agents', 0):>6} "
            f"{hosted.get('runtimes', 0):>7} "
            f"{hosted.get('mcp_servers', 0):>5} "
            f"{node.get('last_seen') or '-'}"
        )


def _print_node_registration(result: dict[str, Any]) -> None:
    node = result.get("node", {})
    print("OpenMesh Node Registered")
    print()
    print(f"node_id: {node.get('node_id')}")
    print(f"node_name: {node.get('node_name')}")
    print(f"node_type: {node.get('node_type')}")
    print(f"events: {len(result.get('events', []))}")


def _print_evaluation(report: dict[str, Any]) -> None:
    print("OpenMesh Evaluation")
    print()
    print(f"schema_version: {report.get('schema_version')}")
    print(f"generated_at: {report.get('generated_at')}")
    print(f"sizes: {', '.join(str(size) for size in report.get('sizes', []))}")
    print()
    for benchmark in report.get("benchmarks", []):
        graph_size = benchmark.get("graph_size", {})
        print(
            f"Synthetic ecosystem: {benchmark.get('node_count')} nodes, "
            f"{benchmark.get('event_count')} events, "
            f"{benchmark.get('trace_count')} traces, "
            f"graph {graph_size.get('nodes', 0)} nodes / {graph_size.get('edges', 0)} edges"
        )
        print(f"{'metric':<24} {'time_ms':>12} {'peak_mb':>10} details")
        for metric in benchmark.get("metrics", []):
            print(
                f"{metric.get('name', '-'):<24} "
                f"{metric.get('elapsed_ms', 0):>12.3f} "
                f"{metric.get('peak_memory_mb', 0):>10.3f} "
                f"{_short(metric.get('details', {}), 72)}"
            )
        print()
    notes = report.get("notes", [])
    if notes:
        print("Notes")
        for note in notes:
            print(f"  - {note}")


def _print_simulation_summary(summary: dict[str, Any]) -> None:
    print("OpenMesh Simulation Created")
    print()
    print(f"run_id: {summary['run_id']}")
    print(f"session_id: {summary['session_id']}")
    print(f"started_at: {summary['started_at']}")
    print(f"ended_at: {summary['ended_at']}")
    print()
    print("Generated")
    for key in (
        "agents",
        "guilds",
        "events",
        "tool_calls",
        "workflows",
        "distributed_nodes",
        "host_relationships",
        "runtimes",
        "mcp_servers",
        "messages",
        "posts",
        "wiki_articles",
        "traces",
    ):
        print(f"  {key}: {summary.get(key, 0)}")
    print()
    print("Try next")
    print("  openmesh discover")
    print("  openmesh graph --details")
    print("  openmesh ecosystem")
    print("  openmesh timeline")


def _print_saved_queries() -> None:
    print("OpenMesh Saved Queries")
    print()
    for query in SAVED_QUERIES:
        print(f"{query['category']}: {query['name']}")
        print(f"  openmesh query {query['query']}")


def _print_query_result(result: dict[str, Any]) -> None:
    print("OpenMesh Query")
    print()
    print(f"query: {result.get('query')}")
    print(f"status: {result.get('status')}")
    print(f"category: {result.get('category')}")
    print(f"intent: {result.get('intent')}")
    print(f"source: {', '.join(result.get('source', []))}")
    print(f"count: {result.get('count', 0)}")
    if result.get("metadata"):
        print()
        print("Metadata")
        for key, value in result["metadata"].items():
            print(f"  {key}: {_short(value, 120)}")
    if result.get("errors"):
        print()
        print("Errors")
        for error in result["errors"]:
            print(f"  {error.get('code')}: {error.get('message')}")
    print()
    print("Results")
    results = result.get("results", [])
    if not results:
        print("  none")
        return
    for item in results[:50]:
        print(f"  - {_query_result_line(item)}")
    if len(results) > 50:
        print(f"  ... {len(results) - 50} more")


def _query_result_line(item: dict[str, Any]) -> str:
    if item.get("relationship_type"):
        return (
            f"{item.get('source')} --{item.get('relationship_type')}--> "
            f"{item.get('target')} events:{item.get('event_count', 0)}"
        )
    if item.get("trace_id"):
        return (
            f"{item.get('trace_id')} status:{item.get('status', '-')} "
            f"events:{item.get('event_count', 0)}"
        )
    if item.get("session_id"):
        return (
            f"{item.get('session_id')} status:{item.get('status', '-')} "
            f"{_short(item.get('command'), 48)}"
        )
    if item.get("capability"):
        return f"{item.get('mcp') or item.get('server') or '-'} exposes {item['capability']}"
    if item.get("workflow"):
        return f"{item['workflow']} ({item.get('workflow_id') or item.get('id')})"
    if item.get("agent"):
        return f"{item['agent']} ({item.get('agent_id')})"
    return _short(item.get("name") or item.get("id") or item, 120)


def _print_provider_statuses(statuses: list[Any]) -> None:
    print("OpenMesh LLM Providers")
    print()
    for status in statuses:
        if status.connected:
            marker = "✓"
        elif status.configured:
            marker = "✗"
        else:
            marker = "○"
        print(f"{marker} {status.name} {status.message}")


def _print_provider_discovery(statuses: list[Any]) -> None:
    print("Local LLM Providers")
    print()
    for status in statuses:
        marker = "✓" if status.connected else "✗"
        endpoint = status.endpoint or status.message
        print(f"{status.name:<11} {marker} {endpoint}")


def _print_models(models: list[Any]) -> None:
    if not models:
        print("No local models discovered.")
        print("Start Ollama, LM Studio, or vLLM and rerun: openmesh models list")
        return
    print("Local Models")
    print()
    for model in models:
        print(f"{model.model:<32} {model.provider_name}  {model.endpoint or '-'}")


def _print_runtime_discovery(statuses: list[Any]) -> None:
    print("OpenMesh Agent Runtimes")
    print()
    for status in statuses:
        marker = "✓" if status.available else "✗"
        detail = status.executable or status.path or status.message
        print(f"{status.name:<12} {marker} {detail}")


def _print_research_demo_result(result: dict[str, Any]) -> None:
    print("OpenMesh Research Demo")
    print()
    print(f"Provider: {result['provider']}")
    print(f"Model: {result['model']}")
    print(f"Trace: {result['trace_id']}")
    print(f"Session: {result['session_id']}")
    if result.get("latency_ms") is not None:
        print(f"Latency: {result['latency_ms']}ms")
    if result.get("tokens_per_second") is not None:
        print(f"Tokens/sec: {result['tokens_per_second']}")
    print()
    print("Events")
    for event_type in event_types_for_cli(result):
        print(f"- {event_type}")
    print()
    print("Response")
    print(_short(result.get("response", ""), 1000))


def _print_multi_agent_demo_result(result: dict[str, Any]) -> None:
    print("OpenMesh Multi-Agent Demo")
    print()
    print(f"Workflow: {result['workflow']}")
    print(f"Workflow ID: {result['workflow_id']}")
    print(f"Trace: {result['trace_id']}")
    print(f"Session: {result['session_id']}")
    print(f"Agents: {', '.join(result.get('agents', []))}")
    print(f"Handoffs: {result.get('handoffs', 0)}")
    print(f"Messages: {result.get('messages', 0)}")
    print(f"Events: {len(result.get('events', []))}")
    print()
    print("Workflow Graph")
    for source, target in zip(result.get("agents", []), result.get("agents", [])[1:]):
        print(f"{source} -> {target}")
    if result.get("agents"):
        print(f"{result['agents'][-1]} -> {result['agents'][0]}")
    print()
    print("Next")
    print(f"openmesh workflow inspect {result['workflow_id']}")
    print(f"openmesh workflow replay {result['workflow_id']}")


def _print_runtime_observation(result: dict[str, Any]) -> None:
    runtime = result["runtime"]
    print("OpenMesh Runtime Observation")
    print()
    print(f"Runtime: {runtime['name']}")
    print(f"Status: {runtime['status']}")
    if runtime.get("executable"):
        print(f"Executable: {runtime['executable']}")
    if runtime.get("path"):
        print(f"Path: {runtime['path']}")
    print(f"Trace: {result['trace_id']}")
    print(f"Session: {result['session_id']}")
    print()
    print("Events")
    for event in result["events"]:
        print(f"- {event['event_type']}")


def _utc_now() -> datetime:
    return datetime.utcnow()


def _process_node(session_id: str, command: str) -> dict[str, Any]:
    return {
        "node_id": f"process:{session_id}",
        "node_type": "process",
        "name": command,
        "runtime": "subprocess",
        "metadata": {"session_id": session_id},
    }


def _command_node(command: str) -> dict[str, Any]:
    executable = command.split(" ", 1)[0] if command else "command"
    return {
        "node_id": f"command:{executable}",
        "node_type": "command",
        "name": command,
        "runtime": "shell",
    }


async def _emit_process_event(
    db,
    event_type: str,
    *,
    session_id: str,
    trace_id: str,
    source: dict[str, Any],
    payload: dict[str, Any],
    target: dict[str, Any] | None = None,
    severity: str = "info",
    span_id: str | None = None,
    parent_span_id: str | None = None,
    parent_event_id: str | None = None,
    root_event_id: str | None = None,
) -> dict[str, Any]:
    event = make_openmesh_event(
        event_type,
        source,
        payload,
        target=target,
        severity=severity,
        session_id=session_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        parent_event_id=parent_event_id,
        root_event_id=root_event_id,
    )
    await collector.accept(db, event)
    return event


async def _stream_output(
    db,
    stream: asyncio.StreamReader,
    *,
    event_type: str,
    session_id: str,
    trace_id: str,
    process: dict[str, Any],
    command: str,
    severity: str,
    emit_lock: asyncio.Lock,
    span_id: str,
    parent_event_id: str,
    root_event_id: str,
) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode(errors="replace").rstrip("\n")
        print(text)
        async with emit_lock:
            await _emit_process_event(
                db,
                event_type,
                session_id=session_id,
                trace_id=trace_id,
                source=process,
                payload={"command": command, "line": text},
                severity=severity,
                span_id=span_id,
                parent_event_id=parent_event_id,
                root_event_id=root_event_id,
            )


async def _with_db(handler: Callable[..., Any], *args: Any) -> int:
    try:
        await init_db(announce=False)
        async with AsyncSessionLocal() as db:
            result = await handler(db, *args)
            return result if isinstance(result, int) else 0
    except Exception as exc:
        print("OpenMesh CLI error")
        print()
        print(f"Database: ERROR ({exc.__class__.__name__})")
        if str(exc):
            print(str(exc))
        return 1


async def _health(args: argparse.Namespace) -> int:
    async def run(db):
        status = await get_health(db)
        _print_health(status)

    return await _with_db(run)


async def _events(args: argparse.Namespace) -> int:
    async def run(db):
        events = await get_events(db, limit=args.limit)
        _print_events(events)

    return await _with_db(run)


async def _traces(args: argparse.Namespace) -> int:
    async def run(db):
        traces = await get_traces(db, limit=args.limit)
        _print_traces(traces[: args.limit])

    return await _with_db(run)


async def _trace(args: argparse.Namespace) -> int:
    async def run(db):
        trace = await get_trace(db, args.trace_id)
        if not trace:
            print(f"Trace not found: {args.trace_id}")
            return 1
        _print_trace_detail(trace)

    return await _with_db(run)


async def _graph(args: argparse.Namespace) -> int:
    async def run(db):
        graph = await get_graph(db, limit=args.limit)
        node_types = _option_set(args.node_type)
        relationship_types = _option_set(args.relationship_type)
        node_type = _single_option(node_types)
        relationship_type = _single_option(relationship_types)

        if args.focus:
            exploration = explore_graph_node(
                graph,
                args.focus,
                depth=args.depth,
                direction=args.direction,
                relationship_type=relationship_type,
                node_type=node_type,
                query=args.search,
                limit=args.limit,
            )
            if not exploration:
                print(f"OpenMesh graph node not found: {args.focus}")
                return 1
            _print_graph_exploration(exploration, details=args.details)
            return 0

        if args.search:
            result = search_graph(
                graph,
                args.search,
                node_type=node_type,
                relationship_type=relationship_type,
                limit=args.limit,
            )
            _print_graph_search(result)
            return 0

        if node_types or relationship_types or args.lifecycle_state:
            graph = filter_graph(
                graph,
                node_types=node_types,
                relationship_types=relationship_types,
                lifecycle_state=args.lifecycle_state,
                limit=args.limit,
            )
        if args.stats:
            _print_graph_statistics(graph)
        _print_graph(graph, details=args.details)
        return 0

    return await _with_db(run)


async def _nodes(args: argparse.Namespace) -> int:
    async def run(db):
        graph = await get_graph(db)
        _print_nodes(graph)

    return await _with_db(run)


async def _inspect(args: argparse.Namespace) -> int:
    async def run(db):
        inspection = await inspect_node(db, args.node_id)
        if not inspection:
            print(f"OpenMesh node not found: {args.node_id}")
            return 1
        _print_node_inspection(inspection)
        return 0

    return await _with_db(run)


async def _registry(args: argparse.Namespace) -> int:
    async def run(db):
        records = await list_openmesh_events(db, limit=args.limit)
        registry = build_registry_status(records)
        _print_registry(registry)
        return 1 if registry["compatibility"]["severity"] == "ERROR" else 0

    return await _with_db(run)


async def _snapshot_create(args: argparse.Namespace) -> int:
    async def run(db):
        snapshot = await create_ecosystem_snapshot(db, limit=args.limit)
        _print_snapshot_created(snapshot)
        return 0

    return await _with_db(run)


async def _snapshot_list(args: argparse.Namespace) -> int:
    async def run(db):
        snapshots = await list_ecosystem_snapshots(db, limit=args.limit)
        _print_snapshots(snapshots)
        return 0

    return await _with_db(run)


async def _snapshot_inspect(args: argparse.Namespace) -> int:
    async def run(db):
        snapshot = await inspect_ecosystem_snapshot(db, args.snapshot_id)
        if not snapshot:
            print(f"OpenMesh snapshot not found: {args.snapshot_id}")
            return 1
        _print_snapshot_detail(snapshot)
        return 0

    return await _with_db(run)


async def _snapshot_diff(args: argparse.Namespace) -> int:
    async def run(db):
        diff = await diff_ecosystem_snapshots(db, args.snapshot_a, args.snapshot_b)
        if not diff:
            print(
                "OpenMesh snapshot diff failed: "
                f"{args.snapshot_a} or {args.snapshot_b} was not found"
            )
            return 1
        _print_snapshot_diff(diff)
        return 0

    return await _with_db(run)


async def _timeline(args: argparse.Namespace) -> int:
    async def run(db):
        timeline = await get_timeline(db, limit=args.limit)
        _print_timeline(timeline)
        return 0

    return await _with_db(run)


async def _timeline_node(args: argparse.Namespace) -> int:
    async def run(db):
        timeline = await get_node_timeline(db, args.node_id, limit=args.limit)
        if not timeline:
            print(f"OpenMesh node timeline not found: {args.node_id}")
            return 1
        _print_timeline(timeline)
        return 0

    return await _with_db(run)


async def _timeline_workflow(args: argparse.Namespace) -> int:
    async def run(db):
        timeline = await get_workflow_timeline(db, args.workflow_id, limit=args.limit)
        if not timeline:
            print(f"OpenMesh workflow timeline not found: {args.workflow_id}")
            return 1
        _print_timeline(timeline)
        return 0

    return await _with_db(run)


async def _timeline_trace(args: argparse.Namespace) -> int:
    async def run(db):
        timeline = await get_trace_timeline(db, args.trace_id, limit=args.limit)
        if not timeline:
            print(f"OpenMesh trace timeline not found: {args.trace_id}")
            return 1
        _print_timeline(timeline)
        return 0

    return await _with_db(run)


async def _replay(args: argparse.Namespace) -> int:
    async def run(db):
        replay = await get_replay(
            db,
            control=args.control,
            position=args.position,
            timestamp=args.timestamp,
            event_id=args.event_id,
            speed=args.speed,
            limit=args.limit,
        )
        _print_replay(replay)
        return 0

    return await _with_db(run)


async def _replay_snapshot(args: argparse.Namespace) -> int:
    async def run(db):
        replay = await get_snapshot_replay(
            db,
            args.snapshot_id,
            control=args.control,
            position=args.position,
            timestamp=args.timestamp,
            event_id=args.event_id,
            speed=args.speed,
        )
        if not replay:
            print(f"OpenMesh snapshot replay not found: {args.snapshot_id}")
            return 1
        _print_replay(replay)
        return 0

    return await _with_db(run)


async def _replay_trace(args: argparse.Namespace) -> int:
    async def run(db):
        replay = await get_trace_replay(
            db,
            args.trace_id,
            control=args.control,
            position=args.position,
            timestamp=args.timestamp,
            event_id=args.event_id,
            speed=args.speed,
            limit=args.limit,
        )
        if not replay:
            print(f"OpenMesh trace replay not found: {args.trace_id}")
            return 1
        _print_replay(replay)
        return 0

    return await _with_db(run)


async def _replay_workflow(args: argparse.Namespace) -> int:
    async def run(db):
        replay = await get_workflow_replay(
            db,
            args.workflow_id,
            control=args.control,
            position=args.position,
            timestamp=args.timestamp,
            event_id=args.event_id,
            speed=args.speed,
            limit=args.limit,
        )
        if not replay:
            print(f"OpenMesh workflow replay not found: {args.workflow_id}")
            return 1
        _print_replay(replay)
        return 0

    return await _with_db(run)


async def _query(args: argparse.Namespace) -> int:
    query_parts = args.query or []
    if query_parts and query_parts[0] == "--":
        query_parts = query_parts[1:]
    query_text = " ".join(query_parts).strip()
    if args.saved or not query_text:
        _print_saved_queries()
        return 0

    async def run(db):
        result = await execute_query(db, query_text, limit=args.limit)
        _print_query_result(result)
        return 1 if result.get("status") == "unsupported" else 0

    return await _with_db(run)


async def _doctor(args: argparse.Namespace) -> int:
    async def run(db):
        report = await run_doctor(db)
        _print_doctor(report)
        return 1 if report["status"] == "ERROR" else 0

    return await _with_db(run)


async def _failures(args: argparse.Namespace) -> int:
    async def run(db):
        registry = await get_failure_registry(db, limit=args.limit, persist=True)
        _print_failures(registry)
        return 0

    return await _with_db(run)


async def _failure_inspect(args: argparse.Namespace) -> int:
    async def run(db):
        await get_failure_registry(db, limit=args.limit, persist=True)
        records = await list_openmesh_events(db, limit=args.limit)
        detail = inspect_failure(records, args.failure_id)
        if not detail:
            print(f"OpenMesh failure not found: {args.failure_id}")
            return 1
        _print_failure_detail(detail)
        return 0

    return await _with_db(run)


async def _failure_report(args: argparse.Namespace) -> int:
    async def run(db):
        report = await get_failure_report(db, limit=args.limit, persist=True)
        _print_failure_report(report)
        return 0

    return await _with_db(run)


async def _rankings(args: argparse.Namespace) -> int:
    async def run(db):
        report = await get_agent_reputation(db, limit=args.limit, persist=True)
        _print_rankings(report)
        return 0

    return await _with_db(run)


async def _agent_score(args: argparse.Namespace) -> int:
    async def run(db):
        detail = await get_agent_score(
            db, args.agent_id, limit=args.limit, persist=True
        )
        if not detail:
            print(f"OpenMesh agent reputation not found: {args.agent_id}")
            return 1
        _print_agent_score(detail)
        return 0

    return await _with_db(run)


async def _genome(args: argparse.Namespace) -> int:
    async def run(db):
        detail = await get_agent_genome(db, args.agent, limit=args.limit, persist=True)
        if not detail:
            print(f"OpenMesh agent genome not found: {args.agent}")
            return 1
        _print_agent_genome(detail)
        return 0

    return await _with_db(run)


async def _compare(args: argparse.Namespace) -> int:
    async def run(db):
        detail = await get_agent_comparison(
            db, args.agent_a, args.agent_b, limit=args.limit, persist=True
        )
        if not detail:
            print(
                f"OpenMesh agent genome comparison not found: {args.agent_a} {args.agent_b}"
            )
            return 1
        _print_genome_comparison(detail)
        return 0

    return await _with_db(run)


async def _integrations(args: argparse.Namespace) -> int:
    _print_integrations(list_integrations())
    return 0


async def _providers(args: argparse.Namespace) -> int:
    return await _providers_verify(args)


async def _providers_verify(args: argparse.Namespace) -> int:
    statuses = await verify_providers()
    _print_provider_statuses(statuses)
    configured_failures = [
        status
        for status in statuses
        if status.configured and not status.connected and not status.local
    ]
    strict = getattr(args, "strict", False)
    strict_failures = (
        [status for status in statuses if not status.connected] if strict else []
    )
    if configured_failures or (strict and strict_failures):
        return 1
    return 0


async def _providers_discover(args: argparse.Namespace) -> int:
    statuses = await discover_local_providers()
    _print_provider_discovery(statuses)
    return 0


async def _models(args: argparse.Namespace) -> int:
    return await _models_list(args)


async def _models_list(args: argparse.Namespace) -> int:
    models = await list_local_models()
    _print_models(models)
    return 0


async def _runtimes(args: argparse.Namespace) -> int:
    return await _runtimes_discover(args)


async def _runtimes_discover(args: argparse.Namespace) -> int:
    _print_runtime_discovery(discover_runtimes())
    return 0


async def _plugins(args: argparse.Namespace) -> int:
    _print_plugins(list_plugins())
    return 0


async def _plugins_list(args: argparse.Namespace) -> int:
    _print_plugins(list_plugins())
    return 0


async def _plugins_inspect(args: argparse.Namespace) -> int:
    plugin = get_plugin(args.plugin_id)
    if not plugin:
        print(f"OpenMesh plugin not found: {args.plugin_id}")
        return 1
    _print_plugin_detail(plugin)
    return 0


async def _plugins_validate(args: argparse.Namespace) -> int:
    plugin = get_plugin(args.plugin_id)
    if not plugin:
        print(f"OpenMesh plugin not found: {args.plugin_id}")
        return 1
    _print_plugin_validation(plugin)
    validation = plugin.get("validation") or {}
    return 1 if validation.get("status") == "invalid" else 0


async def _federation(args: argparse.Namespace) -> int:
    async def run(db):
        registry = await get_federation_registry(db, limit=args.limit)
        _print_federation(registry)
        return 0

    return await _with_db(run)


async def _federation_list(args: argparse.Namespace) -> int:
    async def run(db):
        registry = await get_federation_registry(db, limit=args.limit)
        _print_federation_peers(
            [registry.get("local_node", {}), *registry.get("peers", [])],
            title="OpenMesh Federation Nodes",
        )
        return 0

    return await _with_db(run)


async def _federation_peers(args: argparse.Namespace) -> int:
    async def run(db):
        peers = await get_federation_peers(db, limit=args.limit)
        _print_federation_peers(peers)
        return 0

    return await _with_db(run)


async def _federation_inspect(args: argparse.Namespace) -> int:
    async def run(db):
        inspection = await inspect_federation_node(db, args.node_id, limit=args.limit)
        if not inspection:
            print(f"OpenMesh federation node not found: {args.node_id}")
            return 1
        _print_federation_inspection(inspection)
        return 0

    return await _with_db(run)


async def _node_status(args: argparse.Namespace) -> int:
    async def run(db):
        status = await get_node_status(db, limit=args.limit)
        _print_node_status(status)
        return 0

    return await _with_db(run)


async def _node_register(args: argparse.Namespace) -> int:
    async def run(db):
        result = await register_distributed_node(
            db,
            node_id=args.node_id,
            node_name=args.name,
            node_type=args.type,
            broadcast=False,
        )
        _print_node_registration(result)
        return 0

    return await _with_db(run)


async def _node_list(args: argparse.Namespace) -> int:
    async def run(db):
        registry = await get_distributed_node_registry(db, limit=args.limit)
        _print_distributed_node_registry(registry)
        return 0

    return await _with_db(run)


async def _evaluate(args: argparse.Namespace) -> int:
    report = await run_evaluation_suite(
        args.sizes,
        include_ingestion=not args.skip_ingestion,
    )
    if args.json:
        print(report_to_json(report))
    else:
        _print_evaluation(report)
    return 0


async def _simulate(args: argparse.Namespace) -> int:
    if args.agents < 2:
        print("openmesh simulate requires at least 2 agents.")
        return 2
    if args.nodes < 0:
        print("openmesh simulate requires --nodes to be >= 0.")
        return 2
    if args.events < args.agents + args.nodes:
        print("openmesh simulate requires --events to be >= --agents + --nodes.")
        return 2

    async def run(db):
        summary = await run_local_simulation(
            db,
            agent_count=args.agents,
            event_count=args.events,
            node_count=args.nodes,
            seed=args.seed,
            broadcast=False,
        )
        _print_simulation_summary(summary)
        return 0

    return await _with_db(run)


async def _run_demo_research(args: argparse.Namespace) -> int:
    async def run(db):
        try:
            result = await run_research_demo(
                db,
                query=args.query,
                provider_id=args.provider,
                model=args.model,
                max_tokens=args.max_tokens,
                broadcast=False,
            )
        except ProviderConfigurationError as exc:
            print("OpenMesh research demo is not configured")
            print()
            print(str(exc))
            return 2
        except RuntimeError as exc:
            print("OpenMesh research demo failed")
            print()
            print(str(exc))
            return 1
        _print_research_demo_result(result)
        return 0

    return await _with_db(run)


async def _run_demo_multi_agent(args: argparse.Namespace) -> int:
    async def run(db):
        result = await run_multi_agent_demo(
            db,
            agents=args.agents,
            handoffs=args.handoffs,
            messages=args.messages,
            broadcast=False,
        )
        _print_multi_agent_demo_result(result)
        return 0

    return await _with_db(run)


async def _observe(args: argparse.Namespace) -> int:
    async def run(db):
        try:
            result = await observe_runtime(
                db,
                args.runtime,
                broadcast=False,
            )
        except ValueError as exc:
            print("OpenMesh runtime is unknown")
            print()
            print(str(exc))
            return 2
        except RuntimeError as exc:
            print("OpenMesh runtime is unavailable")
            print()
            print(str(exc))
            return 1
        _print_runtime_observation(result)
        return 0

    return await _with_db(run)


async def _discover(args: argparse.Namespace) -> int:
    async def run(db):
        discovery = await get_discovery(db, limit=args.limit)
        _print_discovery(discovery)

    return await _with_db(run)


async def _mcp(args: argparse.Namespace) -> int:
    async def run(db):
        servers = await get_mcp_registry(db, limit=args.limit)
        _print_mcp(servers)

    return await _with_db(run)


async def _mcp_discover(args: argparse.Namespace) -> int:
    async def run(db):
        result = await register_discovered_mcp_ecosystem(
            db,
            paths_by_source=_paths_by_source(args.path),
            broadcast=False,
        )
        _print_mcp_discovery(result)
        return 1 if result.get("issues") else 0

    return await _with_db(run)


async def _mcp_config(args: argparse.Namespace) -> int:
    async def run(db):
        if args.scan:
            result = await register_discovered_mcp_configs(
                db,
                paths_by_source=_paths_by_source(args.path),
                broadcast=False,
            )
            _print_mcp_config(result["entries"], issues=result["issues"])
            return 1 if result["issues"] else 0
        configs = await get_mcp_config_registry(db, limit=args.limit)
        _print_mcp_config(configs)

    return await _with_db(run)


async def _capabilities(args: argparse.Namespace) -> int:
    async def run(db):
        capabilities = await get_capability_registry(db, limit=args.limit)
        _print_capabilities(capabilities)

    return await _with_db(run)


async def _tools(args: argparse.Namespace) -> int:
    async def run(db):
        tools = await get_tool_registry(db, limit=args.limit)
        _print_tools(tools)

    return await _with_db(run)


async def _resources(args: argparse.Namespace) -> int:
    async def run(db):
        resources = await get_resource_registry(db, limit=args.limit)
        _print_resources(resources)

    return await _with_db(run)


async def _workflows(args: argparse.Namespace) -> int:
    async def run(db):
        workflows = await list_workflows(db, limit=args.limit)
        _print_workflows(workflows)

    return await _with_db(run)


async def _workflow_list(args: argparse.Namespace) -> int:
    async def run(db):
        workflows = await list_workflows(db, limit=args.limit)
        _print_workflows(workflows)

    return await _with_db(run)


async def _workflow_inspect(args: argparse.Namespace) -> int:
    async def run(db):
        workflow = await inspect_workflow(db, args.workflow_id, limit=args.limit)
        if not workflow:
            print(f"OpenMesh workflow not found: {args.workflow_id}")
            return 1
        _print_workflow_inspection(workflow)
        return 0

    return await _with_db(run)


async def _ecosystem(args: argparse.Namespace) -> int:
    async def run(db):
        ecosystem = await get_ecosystem_registry(db, limit=args.limit)
        _print_ecosystem(ecosystem)

    return await _with_db(run)


def _paths_by_source(raw_paths: list[str] | None) -> dict[str, list[Path]]:
    paths: dict[str, list[Path]] = {}
    for raw in raw_paths or []:
        if "=" not in raw:
            raise ValueError("--path must use SOURCE=/path/to/config")
        source, path = raw.split("=", 1)
        paths.setdefault(source, []).append(Path(path).expanduser())
    return paths


async def _run_command(args: argparse.Namespace) -> int:
    command_parts = args.command
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        print("Usage: openmesh run -- <command>")
        return 2

    command = shell_join(command_parts)
    session_id = f"sess_{uuid4().hex}"
    trace_id = f"trace_{uuid4().hex}"
    span_id = f"span_{uuid4().hex}"
    process = _process_node(session_id, command)
    command_target = _command_node(command)

    async def run(db) -> int:
        started_at = _utc_now()
        await create_openmesh_session(
            db, session_id=session_id, command=command, started_at=started_at
        )
        started_event = await _emit_process_event(
            db,
            "process.started",
            session_id=session_id,
            trace_id=trace_id,
            source=CLI_NODE,
            target=process,
            payload={
                "command": command,
                "argv": command_parts,
                "started_at": started_at.isoformat() + "Z",
            },
            span_id=span_id,
        )
        root_event_id = started_event["root_event_id"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *command_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            ended_at = _utc_now()
            await _emit_process_event(
                db,
                "process.failed",
                session_id=session_id,
                trace_id=trace_id,
                source=process,
                target=command_target,
                payload={
                    "command": command,
                    "error": str(exc),
                    "started_at": started_at.isoformat() + "Z",
                    "ended_at": ended_at.isoformat() + "Z",
                },
                severity="error",
                span_id=span_id,
                parent_event_id=started_event["event_id"],
                root_event_id=root_event_id,
            )
            await complete_openmesh_session(
                db,
                session_id=session_id,
                ended_at=ended_at,
                status="failed",
                exit_code=None,
            )
            raise
        assert proc.stdout is not None
        assert proc.stderr is not None
        emit_lock = asyncio.Lock()
        await asyncio.gather(
            _stream_output(
                db,
                proc.stdout,
                event_type="process.stdout",
                session_id=session_id,
                trace_id=trace_id,
                process=process,
                command=command,
                severity="info",
                emit_lock=emit_lock,
                span_id=span_id,
                parent_event_id=started_event["event_id"],
                root_event_id=root_event_id,
            ),
            _stream_output(
                db,
                proc.stderr,
                event_type="process.stderr",
                session_id=session_id,
                trace_id=trace_id,
                process=process,
                command=command,
                severity="warning",
                emit_lock=emit_lock,
                span_id=span_id,
                parent_event_id=started_event["event_id"],
                root_event_id=root_event_id,
            ),
        )
        exit_code = await proc.wait()
        ended_at = _utc_now()
        status = "completed" if exit_code == 0 else "failed"
        event_type = "process.completed" if exit_code == 0 else "process.failed"
        await _emit_process_event(
            db,
            event_type,
            session_id=session_id,
            trace_id=trace_id,
            source=process,
            target=command_target,
            payload={
                "command": command,
                "exit_code": exit_code,
                "started_at": started_at.isoformat() + "Z",
                "ended_at": ended_at.isoformat() + "Z",
            },
            severity="info" if exit_code == 0 else "error",
            span_id=span_id,
            parent_event_id=started_event["event_id"],
            root_event_id=root_event_id,
        )
        await complete_openmesh_session(
            db,
            session_id=session_id,
            ended_at=ended_at,
            status=status,
            exit_code=exit_code,
        )
        print()
        print(f"OpenMesh session: {session_id}")
        print(f"OpenMesh trace: {trace_id}")
        print(f"Exit code: {exit_code}")
        return exit_code

    return await _with_db(run)


async def _tui(args: argparse.Namespace) -> int:
    try:
        return await run_tui(once=args.once)
    except Exception as exc:
        print("OpenMesh TUI error")
        print()
        print(f"{exc.__class__.__name__}: {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmesh", description="Inspect persisted OpenMesh events."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="Show collector and storage status.")
    health.set_defaults(func=_health)

    events = subparsers.add_parser("events", help="Show latest OpenMesh events.")
    events.add_argument("--limit", type=int, default=10, help="Maximum events to show.")
    events.set_defaults(func=_events)

    traces = subparsers.add_parser("traces", help="Show OpenMesh traces.")
    traces.add_argument("--limit", type=int, default=20, help="Maximum traces to show.")
    traces.set_defaults(func=_traces)

    trace = subparsers.add_parser("trace", help="Inspect one OpenMesh trace.")
    trace.add_argument("trace_id", help="Trace id to inspect.")
    trace.set_defaults(func=_trace)

    graph = subparsers.add_parser("graph", help="Show OpenMesh graph relationships.")
    graph.add_argument(
        "--details",
        action="store_true",
        help="Show edge provenance and lifecycle metadata.",
    )
    graph.add_argument(
        "--focus",
        help="Center graph exploration on a node id, name, or alias.",
    )
    graph.add_argument(
        "--depth",
        type=int,
        default=1,
        help="Neighborhood depth for --focus exploration.",
    )
    graph.add_argument(
        "--direction",
        choices=["incoming", "outgoing", "both"],
        default="both",
        help="Relationship direction for focused exploration.",
    )
    graph.add_argument(
        "--node-type",
        action="append",
        help="Filter by node type. Repeat or use comma-separated values.",
    )
    graph.add_argument(
        "--relationship-type",
        action="append",
        help="Filter by relationship type. Repeat or use comma-separated values.",
    )
    graph.add_argument(
        "--search",
        help="Search nodes and relationships by id, name, type, trace, or event.",
    )
    graph.add_argument(
        "--lifecycle-state",
        help="Filter relationships by lifecycle state.",
    )
    graph.add_argument(
        "--stats",
        action="store_true",
        help="Show graph statistics before graph output.",
    )
    graph.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum graph records to load.",
    )
    graph.set_defaults(func=_graph)

    nodes = subparsers.add_parser("nodes", help="Show governed OpenMesh graph nodes.")
    nodes.set_defaults(func=_nodes)

    inspect = subparsers.add_parser("inspect", help="Inspect one OpenMesh graph node.")
    inspect.add_argument(
        "node_id", help="Node id, node name, or normalized node alias."
    )
    inspect.set_defaults(func=_inspect)

    registry = subparsers.add_parser(
        "registry", help="Show OpenMesh registry versions and compatibility."
    )
    registry.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to validate compatibility from.",
    )
    registry.set_defaults(func=_registry)

    snapshot = subparsers.add_parser(
        "snapshot", help="Create and inspect OpenMesh ecosystem snapshots."
    )
    snapshot_subparsers = snapshot.add_subparsers(
        dest="snapshot_command", required=True
    )
    snapshot_create = snapshot_subparsers.add_parser(
        "create", help="Create a point-in-time ecosystem snapshot."
    )
    snapshot_create.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to include in the snapshot.",
    )
    snapshot_create.set_defaults(func=_snapshot_create)
    snapshot_list = snapshot_subparsers.add_parser(
        "list", help="List saved ecosystem snapshots."
    )
    snapshot_list.add_argument(
        "--limit", type=int, default=100, help="Maximum snapshots to show."
    )
    snapshot_list.set_defaults(func=_snapshot_list)
    snapshot_inspect = snapshot_subparsers.add_parser(
        "inspect", help="Inspect one saved ecosystem snapshot."
    )
    snapshot_inspect.add_argument("snapshot_id", help="Snapshot id to inspect.")
    snapshot_inspect.set_defaults(func=_snapshot_inspect)
    snapshot_diff = snapshot_subparsers.add_parser(
        "diff", help="Compare two saved ecosystem snapshots."
    )
    snapshot_diff.add_argument("snapshot_a", help="Earlier/base snapshot id.")
    snapshot_diff.add_argument("snapshot_b", help="Later/compare snapshot id.")
    snapshot_diff.set_defaults(func=_snapshot_diff)

    timeline = subparsers.add_parser(
        "timeline", help="Show OpenMesh historical ecosystem evolution."
    )
    timeline.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive timeline from.",
    )
    timeline.set_defaults(func=_timeline)
    timeline_subparsers = timeline.add_subparsers(dest="timeline_command")
    timeline_node = timeline_subparsers.add_parser(
        "node", help="Show historical evolution for one node."
    )
    timeline_node.add_argument(
        "node_id", help="Node id, node name, or normalized node alias."
    )
    timeline_node.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive timeline from.",
    )
    timeline_node.set_defaults(func=_timeline_node)
    timeline_workflow = timeline_subparsers.add_parser(
        "workflow", help="Show historical evolution for one workflow."
    )
    timeline_workflow.add_argument(
        "workflow_id", help="Workflow id, workflow name, or normalized workflow alias."
    )
    timeline_workflow.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive timeline from.",
    )
    timeline_workflow.set_defaults(func=_timeline_workflow)
    timeline_trace = timeline_subparsers.add_parser(
        "trace", help="Show historical evolution for one trace."
    )
    timeline_trace.add_argument("trace_id", help="Trace id to inspect.")
    timeline_trace.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive timeline from.",
    )
    timeline_trace.set_defaults(func=_timeline_trace)

    replay = subparsers.add_parser("replay", help="Replay OpenMesh ecosystem history.")
    _add_replay_options(replay)
    replay.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive replay from.",
    )
    replay.set_defaults(func=_replay)
    replay_subparsers = replay.add_subparsers(dest="replay_command")
    replay_ecosystem = replay_subparsers.add_parser(
        "ecosystem", help="Replay OpenMesh ecosystem history."
    )
    _add_replay_options(replay_ecosystem)
    replay_ecosystem.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive replay from.",
    )
    replay_ecosystem.set_defaults(func=_replay)
    replay_snapshot = replay_subparsers.add_parser(
        "snapshot", help="Replay one saved ecosystem snapshot."
    )
    replay_snapshot.add_argument("snapshot_id", help="Snapshot id to replay.")
    _add_replay_options(replay_snapshot)
    replay_snapshot.set_defaults(func=_replay_snapshot)
    replay_trace = replay_subparsers.add_parser(
        "trace", help="Replay one OpenMesh trace."
    )
    replay_trace.add_argument("trace_id", help="Trace id to replay.")
    _add_replay_options(replay_trace)
    replay_trace.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive replay from.",
    )
    replay_trace.set_defaults(func=_replay_trace)
    replay_workflow = replay_subparsers.add_parser(
        "workflow", help="Replay one OpenMesh workflow."
    )
    replay_workflow.add_argument(
        "workflow_id", help="Workflow id, workflow name, or normalized workflow alias."
    )
    _add_replay_options(replay_workflow)
    replay_workflow.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive replay from.",
    )
    replay_workflow.set_defaults(func=_replay_workflow)

    query = subparsers.add_parser("query", help="Run a structured OpenMesh query.")
    query.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive query answers from.",
    )
    query.add_argument(
        "--saved",
        action="store_true",
        help="List built-in saved query examples.",
    )
    query.add_argument("query", nargs=argparse.REMAINDER, help="Query text.")
    query.set_defaults(func=_query)

    doctor = subparsers.add_parser("doctor", help="Check OpenMesh local configuration.")
    doctor.set_defaults(func=_doctor)

    failures = subparsers.add_parser(
        "failures", help="Detect, classify, and list OpenMesh failures."
    )
    failures.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive failure intelligence from.",
    )
    failures.set_defaults(func=_failures)

    failure = subparsers.add_parser("failure", help="Inspect OpenMesh failures.")
    failure_subparsers = failure.add_subparsers(dest="failure_command", required=True)
    failure_inspect = failure_subparsers.add_parser(
        "inspect", help="Inspect one detected failure."
    )
    failure_inspect.add_argument("failure_id", help="Failure id or source event id.")
    failure_inspect.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive failure intelligence from.",
    )
    failure_inspect.set_defaults(func=_failure_inspect)
    failure_report = failure_subparsers.add_parser(
        "report", help="Show aggregate failure intelligence metrics."
    )
    failure_report.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive failure intelligence from.",
    )
    failure_report.set_defaults(func=_failure_report)

    rankings = subparsers.add_parser(
        "rankings", help="Rank agents by observed OpenMesh reputation."
    )
    rankings.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive reputation from.",
    )
    rankings.set_defaults(func=_rankings)

    agent = subparsers.add_parser("agent", help="Inspect OpenMesh agent reputation.")
    agent_subparsers = agent.add_subparsers(dest="agent_command", required=True)
    agent_score = agent_subparsers.add_parser(
        "score", help="Show one agent reputation score."
    )
    agent_score.add_argument("agent_id", help="Agent id or agent name.")
    agent_score.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive reputation from.",
    )
    agent_score.set_defaults(func=_agent_score)

    genome = subparsers.add_parser(
        "genome", help="Show an agent behavioral genome profile."
    )
    genome.add_argument("agent", help="Agent id or agent name.")
    genome.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive genome from.",
    )
    genome.set_defaults(func=_genome)

    compare = subparsers.add_parser(
        "compare", help="Compare two agent behavioral genomes."
    )
    compare.add_argument("agent_a", help="First agent id or name.")
    compare.add_argument("agent_b", help="Second agent id or name.")
    compare.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive genomes from.",
    )
    compare.set_defaults(func=_compare)

    integrations = subparsers.add_parser(
        "integrations", help="Show OpenMesh framework integration status."
    )
    integrations.set_defaults(func=_integrations)

    providers = subparsers.add_parser(
        "providers", help="Show OpenMesh LLM provider status."
    )
    providers.set_defaults(func=_providers)
    provider_subparsers = providers.add_subparsers(dest="provider_command")
    providers_verify = provider_subparsers.add_parser(
        "verify", help="Verify configured LLM provider connections."
    )
    providers_verify.add_argument(
        "--strict",
        action="store_true",
        help="Fail when any provider is missing an API key.",
    )
    providers_verify.set_defaults(func=_providers_verify)
    providers_discover = provider_subparsers.add_parser(
        "discover", help="Discover local LLM providers on localhost."
    )
    providers_discover.set_defaults(func=_providers_discover)

    models = subparsers.add_parser("models", help="Show locally served LLM models.")
    models.set_defaults(func=_models)
    model_subparsers = models.add_subparsers(dest="model_command")
    models_list = model_subparsers.add_parser(
        "list", help="List models exposed by local LLM providers."
    )
    models_list.set_defaults(func=_models_list)

    runtimes = subparsers.add_parser(
        "runtimes", help="Discover local coding agent runtimes."
    )
    runtimes.set_defaults(func=_runtimes)
    runtime_subparsers = runtimes.add_subparsers(dest="runtime_command")
    runtimes_discover = runtime_subparsers.add_parser(
        "discover", help="Discover Claude Code, Codex CLI, OpenCode, Aider, and Cursor."
    )
    runtimes_discover.set_defaults(func=_runtimes_discover)

    plugins = subparsers.add_parser("plugins", help="Show OpenMesh plugin status.")
    plugins.set_defaults(func=_plugins)
    plugin_subparsers = plugins.add_subparsers(dest="plugin_command")
    plugins_list = plugin_subparsers.add_parser("list", help="List OpenMesh plugins.")
    plugins_list.set_defaults(func=_plugins_list)
    plugins_inspect = plugin_subparsers.add_parser(
        "inspect", help="Inspect one OpenMesh plugin."
    )
    plugins_inspect.add_argument("plugin_id", help="Plugin id to inspect.")
    plugins_inspect.set_defaults(func=_plugins_inspect)
    plugins_validate = plugin_subparsers.add_parser(
        "validate", help="Validate one OpenMesh plugin."
    )
    plugins_validate.add_argument("plugin_id", help="Plugin id to validate.")
    plugins_validate.set_defaults(func=_plugins_validate)

    federation = subparsers.add_parser(
        "federation", help="Show OpenMesh federation metadata."
    )
    federation.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive federation metadata from.",
    )
    federation.set_defaults(func=_federation)
    federation_subparsers = federation.add_subparsers(dest="federation_command")
    federation_list = federation_subparsers.add_parser(
        "list", help="List local and peer federation nodes."
    )
    federation_list.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive federation metadata from.",
    )
    federation_list.set_defaults(func=_federation_list)
    federation_inspect = federation_subparsers.add_parser(
        "inspect", help="Inspect the local or a peer federation node."
    )
    federation_inspect.add_argument(
        "node_id",
        nargs="?",
        default=None,
        help="Federation node id, name, or instance id. Defaults to local node.",
    )
    federation_inspect.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive federation metadata from.",
    )
    federation_inspect.set_defaults(func=_federation_inspect)
    federation_peers = federation_subparsers.add_parser(
        "peers", help="List configured federation peers."
    )
    federation_peers.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive federation metadata from.",
    )
    federation_peers.set_defaults(func=_federation_peers)

    node = subparsers.add_parser(
        "node", help="Manage this OpenMesh installation's distributed node identity."
    )
    node_subparsers = node.add_subparsers(dest="node_command", required=True)
    node_status = node_subparsers.add_parser(
        "status", help="Show local node identity and observed registry status."
    )
    node_status.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive node registry status from.",
    )
    node_status.set_defaults(func=_node_status)
    node_register = node_subparsers.add_parser(
        "register", help="Register this OpenMesh installation in the event graph."
    )
    node_register.add_argument("--node-id", help="Stable node id to register.")
    node_register.add_argument("--name", help="Human-readable node name.")
    node_register.add_argument(
        "--type",
        choices=DISTRIBUTED_NODE_TYPES,
        help="Installation type.",
    )
    node_register.set_defaults(func=_node_register)
    node_list = node_subparsers.add_parser(
        "list", help="List observed distributed OpenMesh nodes."
    )
    node_list.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive distributed node registry from.",
    )
    node_list.set_defaults(func=_node_list)

    evaluate = subparsers.add_parser(
        "evaluate", help="Run synthetic OpenMesh performance benchmarks."
    )
    evaluate.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=list(DEFAULT_EVALUATION_SIZES),
        help="Synthetic ecosystem node counts to benchmark.",
    )
    evaluate.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip collector ingestion benchmarks.",
    )
    evaluate.add_argument(
        "--json",
        action="store_true",
        help="Emit the benchmark report as JSON.",
    )
    evaluate.set_defaults(func=_evaluate)

    simulate = subparsers.add_parser(
        "simulate", help="Generate local OpenMesh demo ecosystem data."
    )
    simulate.add_argument(
        "--agents",
        type=int,
        default=14,
        help="Number of agents to generate.",
    )
    simulate.add_argument(
        "--events",
        type=int,
        default=300,
        help="Number of OpenMesh events to persist.",
    )
    simulate.add_argument(
        "--nodes",
        type=int,
        default=0,
        help="Number of distributed OpenMesh nodes to generate.",
    )
    simulate.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional deterministic random seed.",
    )
    simulate.set_defaults(func=_simulate)

    run_demo = subparsers.add_parser(
        "run-demo", help="Run an OpenMesh real provider demo workflow."
    )
    run_demo_subparsers = run_demo.add_subparsers(dest="demo_command", required=True)
    research_demo = run_demo_subparsers.add_parser(
        "research", help="Run a real LLM research workflow through OpenMesh."
    )
    research_demo.add_argument(
        "--provider",
        choices=(
            "auto",
            "openai",
            "anthropic",
            "openrouter",
            "ollama",
            "lmstudio",
            "vllm",
        ),
        default="auto",
        help="LLM provider to use. Defaults to first configured provider.",
    )
    research_demo.add_argument(
        "--model",
        default=None,
        help="Override the provider model, for example hermes3 or qwen3.",
    )
    research_demo.add_argument(
        "--query",
        default="What should an AI agent observability graph reveal?",
        help="Research question to send to the LLM.",
    )
    research_demo.add_argument(
        "--max-tokens",
        type=int,
        default=500,
        help="Maximum response tokens for the LLM call.",
    )
    research_demo.set_defaults(func=_run_demo_research)
    multi_agent_demo = run_demo_subparsers.add_parser(
        "multi-agent", help="Generate a multi-agent handoff workflow through OpenMesh."
    )
    multi_agent_demo.add_argument(
        "--agents",
        type=int,
        default=5,
        help="Number of agents to include, clamped to 4-6.",
    )
    multi_agent_demo.add_argument(
        "--handoffs",
        type=int,
        default=24,
        help="Number of handoffs to generate. Minimum 20.",
    )
    multi_agent_demo.add_argument(
        "--messages",
        type=int,
        default=60,
        help="Number of message exchanges to generate. Minimum 50.",
    )
    multi_agent_demo.set_defaults(func=_run_demo_multi_agent)

    discover = subparsers.add_parser(
        "discover", help="Show observed OpenMesh ecosystem registry."
    )
    discover.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive discovery from.",
    )
    discover.set_defaults(func=_discover)

    mcp = subparsers.add_parser("mcp", help="Show discovered MCP server metadata.")
    mcp.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive MCP registry from.",
    )
    mcp.set_defaults(func=_mcp)
    mcp_subparsers = mcp.add_subparsers(dest="mcp_command")
    mcp_discover = mcp_subparsers.add_parser(
        "discover", help="Discover and register MCP servers, tools, and resources."
    )
    mcp_discover.add_argument(
        "--path",
        action="append",
        help="Override scan path as SOURCE=/path/to/config. May be repeated.",
    )
    mcp_discover.set_defaults(func=_mcp_discover)

    mcp_config = subparsers.add_parser(
        "mcp-config", help="Show discovered MCP configuration metadata."
    )
    mcp_config.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive MCP config registry from.",
    )
    mcp_config.add_argument(
        "--scan",
        action="store_true",
        help="Passively scan known MCP config files and register metadata.",
    )
    mcp_config.add_argument(
        "--path",
        action="append",
        help="Override scan path as SOURCE=/path/to/config. May be repeated.",
    )
    mcp_config.set_defaults(func=_mcp_config)

    capabilities = subparsers.add_parser(
        "capabilities", help="Show discovered MCP capability metadata."
    )
    capabilities.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive capability registry from.",
    )
    capabilities.set_defaults(func=_capabilities)

    tools = subparsers.add_parser(
        "tools", help="Show discovered OpenMesh tool metadata."
    )
    tools.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive tool registry from.",
    )
    tools.set_defaults(func=_tools)

    resources = subparsers.add_parser(
        "resources", help="Show discovered OpenMesh resource metadata."
    )
    resources.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive resource registry from.",
    )
    resources.set_defaults(func=_resources)

    workflows = subparsers.add_parser(
        "workflows", help="Show discovered workflow metadata."
    )
    workflows.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive workflow registry from.",
    )
    workflows.set_defaults(func=_workflows)

    workflow = subparsers.add_parser("workflow", help="Inspect OpenMesh workflows.")
    workflow_subparsers = workflow.add_subparsers(
        dest="workflow_command", required=True
    )
    workflow_list = workflow_subparsers.add_parser(
        "list", help="List discovered workflows."
    )
    workflow_list.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive workflow registry from.",
    )
    workflow_list.set_defaults(func=_workflow_list)
    workflow_inspect = workflow_subparsers.add_parser(
        "inspect", help="Inspect one workflow."
    )
    workflow_inspect.add_argument(
        "workflow_id", help="Workflow id, workflow name, or normalized workflow alias."
    )
    workflow_inspect.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive workflow inspection from.",
    )
    workflow_inspect.set_defaults(func=_workflow_inspect)
    workflow_replay = workflow_subparsers.add_parser(
        "replay", help="Replay one workflow."
    )
    workflow_replay.add_argument(
        "workflow_id", help="Workflow id, workflow name, or normalized workflow alias."
    )
    _add_replay_options(workflow_replay)
    workflow_replay.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive workflow replay from.",
    )
    workflow_replay.set_defaults(func=_replay_workflow)

    ecosystem = subparsers.add_parser(
        "ecosystem", help="Show unified OpenMesh ecosystem inventory."
    )
    ecosystem.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum events to derive ecosystem registry from.",
    )
    ecosystem.set_defaults(func=_ecosystem)

    tui = subparsers.add_parser("tui", help="Launch the OpenMesh terminal UI.")
    tui.add_argument(
        "--once", action="store_true", help="Render one terminal capture and exit."
    )
    tui.set_defaults(func=_tui)

    observe = subparsers.add_parser(
        "observe", help="Observe a detected local coding agent runtime."
    )
    observe.add_argument(
        "runtime",
        help="Runtime id or alias, for example codex, claude, opencode, aider, cursor.",
    )
    observe.set_defaults(func=_observe)

    run = subparsers.add_parser("run", help="Run and observe a command.")
    run.add_argument(
        "command", nargs=argparse.REMAINDER, help="Command to run after --."
    )
    run.set_defaults(func=_run_command)

    return parser


def _add_replay_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--control",
        choices=("start", "pause", "stop", "step", "previous", "jump"),
        default="start",
        help="Playback control to apply to the derived replay.",
    )
    parser.add_argument(
        "--position",
        type=int,
        default=0,
        help="Frame position to start, pause, stop, or step from.",
    )
    parser.add_argument(
        "--timestamp",
        help="Jump to the latest replay frame at or before this ISO timestamp.",
    )
    parser.add_argument(
        "--event-id",
        help="Jump to the replay frame created by this event id.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier for consumers that animate replay output.",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
