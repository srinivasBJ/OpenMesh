from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.coordinate import Coordinate
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Input, RichLog, Static

from ..db.openmesh_events import list_openmesh_events
from ..db.session import AsyncSessionLocal
from ..services.discovery import get_discovery
from ..services.ecosystem_registry import get_ecosystem_registry
from ..services.ecosystem_snapshot import (
    compare_snapshot_payloads,
    inspect_ecosystem_snapshot,
    list_ecosystem_snapshots,
)
from ..services.graph_exploration import (
    explore_graph_node,
    filter_graph,
    graph_statistics,
    search_graph,
)
from ..services.mcp_capabilities import get_capability_registry
from ..services.mcp_config_discovery import get_mcp_config_registry
from ..services.mcp_discovery import get_mcp_registry
from ..services.openmesh_queries import (
    get_events,
    get_graph,
    get_health,
    get_sessions,
    get_traces,
    inspect_graph_node,
    inspect_graph_workflow,
    list_workflows,
)
from ..services.query_engine import SAVED_QUERIES, run_query_on_state
from ..services.replay import build_replay_from_timeline
from ..services.registry_status import build_registry_status
from ..services.timeline import get_timeline
from ..services.trace_semantics import (
    build_event_hierarchy,
    build_span_summary,
    build_span_tree,
    graph_edges_for_trace,
)
from ..sdk.integrations import list_integrations


OPENMESH_LOGO = r"""
   ____                  __  ___          __
  / __ \____  ___  ____ /  |/  /__  _____/ /_
 / / / / __ \/ _ \/ __ `/ /|_/ / _ \/ ___/ __ \
/ /_/ / /_/ /  __/ /_/ / /  / /  __(__  ) / / /
\____/ .___/\___/\__,_/_/  /_/\___/____/_/ /_/
    /_/
"""

GRAPH_FILTERS = [
    ("all", None, None),
    ("agents", {"agent"}, None),
    ("tools", {"tool"}, None),
    ("workflows", {"workflow"}, None),
    ("mcp", {"mcp_server"}, None),
    ("uses", None, {"uses"}),
    ("connects", None, {"connects_to"}),
]


@dataclass
class TuiSnapshot:
    health: dict[str, Any]
    graph: dict[str, list[dict[str, Any]]]
    traces: list[dict[str, Any]]
    events: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    integrations: list[dict[str, Any]]
    discovery: dict[str, list[dict[str, Any]]]
    mcp_servers: list[dict[str, Any]]
    mcp_configs: list[dict[str, Any]]
    capabilities: list[dict[str, Any]]
    workflows: list[dict[str, Any]]
    snapshots: list[dict[str, Any]]
    ecosystem: dict[str, Any]
    registry_status: dict[str, Any]
    loaded_at: datetime
    snapshot_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    timeline: dict[str, Any] = field(default_factory=dict)


async def load_snapshot() -> TuiSnapshot:
    async with AsyncSessionLocal() as db:
        registry_records = await list_openmesh_events(db, limit=5000)
        snapshots = await list_ecosystem_snapshots(db, limit=100)
        snapshot_details: dict[str, dict[str, Any]] = {}
        for snapshot in snapshots[:5]:
            snapshot_id = snapshot.get("snapshot_id")
            if not snapshot_id:
                continue
            detail = await inspect_ecosystem_snapshot(db, snapshot_id)
            if detail:
                snapshot_details[snapshot_id] = detail
        return TuiSnapshot(
            health=await get_health(db),
            graph=await get_graph(db, limit=1000),
            traces=await get_traces(db, limit=1000),
            events=await get_events(db, limit=100),
            sessions=await get_sessions(db, limit=1000),
            integrations=list_integrations(),
            discovery=await get_discovery(db, limit=5000),
            mcp_servers=await get_mcp_registry(db, limit=5000),
            mcp_configs=await get_mcp_config_registry(db, limit=5000),
            capabilities=await get_capability_registry(db, limit=5000),
            workflows=await list_workflows(db, limit=5000),
            snapshots=snapshots,
            ecosystem=await get_ecosystem_registry(db, limit=5000),
            registry_status=build_registry_status(registry_records),
            loaded_at=datetime.utcnow(),
            snapshot_details=snapshot_details,
            timeline=await get_timeline(db, limit=5000),
        )


def _time(value: str | None) -> str:
    if not value:
        return "--:--:--"
    return value.split("T", 1)[-1].replace("Z", "")[:8]


def _short(value: str | None, width: int) -> str:
    if value is None:
        return "-"
    if value == "":
        return ""
    return value if len(value) <= width else value[: width - 1] + "…"


def _node_maps(
    snapshot: TuiSnapshot,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    nodes = {node["id"]: node for node in snapshot.graph["nodes"]}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in snapshot.graph["edges"]:
        outgoing[edge["source"]].append(edge)
    return nodes, outgoing


def _trace_counts_by_node(snapshot: TuiSnapshot) -> dict[str, int]:
    traces_by_node: dict[str, set[str]] = defaultdict(set)
    for event in snapshot.events:
        trace_id = event.get("trace_id")
        if not trace_id:
            continue
        for node_key in ("source", "target"):
            node = event.get(node_key)
            if node:
                traces_by_node[node["node_id"]].add(trace_id)
    return {node_id: len(trace_ids) for node_id, trace_ids in traces_by_node.items()}


def _node_status(node: dict[str, Any], sessions: list[dict[str, Any]]) -> str:
    if node["type"] == "service":
        return "online"
    if node["type"] == "agent":
        return "active"
    if node["type"] == "process":
        session_id = (node.get("metadata") or {}).get("session_id")
        for session in sessions:
            if (
                session["session_id"] == session_id
                or session["command"] == node["name"]
            ):
                return session["status"]
        return "observed"
    return "observed"


def _status_label(status: str) -> str:
    normalized = status.lower()
    if normalized in {"active", "running", "online"}:
        return f"● {status}"
    if normalized in {"failed", "error"}:
        return f"✖ {status}"
    return f"○ {status}"


def network_lines(snapshot: TuiSnapshot, limit: int = 80) -> list[str]:
    nodes, outgoing = _node_maps(snapshot)
    if not nodes:
        return ["No network data yet."]

    hero_types = {"agent", "process", "service", "workflow"}
    visible = [node for node in nodes.values() if node["type"] in hero_types]
    visible.sort(key=lambda node: (node["type"] != "agent", node["type"], node["name"]))

    lines: list[str] = []
    for node in visible:
        lines.append(node["name"])
        edges = sorted(
            outgoing.get(node["id"], []),
            key=lambda edge: (edge["type"], edge["target"]),
        )
        if not edges:
            lines.append("└─ no relationships")
        else:
            for index, edge in enumerate(edges):
                branch = "└─" if index == len(edges) - 1 else "├─"
                target = nodes.get(edge["target"], {"name": edge["target"]})
                lines.append(f"{branch} {edge['type']} → {target['name']}")
        lines.append("")
        if len(lines) >= limit:
            break
    return lines[:limit]


def network_edges(
    snapshot: TuiSnapshot,
    *,
    focus_node_id: str | None = None,
    depth: int = 1,
    direction: str = "both",
    node_types: set[str] | None = None,
    relationship_types: set[str] | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    nodes, _ = _node_maps(snapshot)
    node_type = _single_filter(node_types)
    relationship_type = _single_filter(relationship_types)
    if focus_node_id:
        exploration = explore_graph_node(
            snapshot.graph,
            focus_node_id,
            depth=depth,
            direction=direction,
            node_type=node_type,
            relationship_type=relationship_type,
            query=query,
        )
        neighborhood = (exploration or {}).get("neighborhood") or {}
        graph = {
            "nodes": neighborhood.get("nodes", []),
            "edges": neighborhood.get("edges", []),
        }
    elif node_types or relationship_types or query:
        graph = filter_graph(
            snapshot.graph,
            node_types=node_types,
            relationship_types=relationship_types,
            query=query,
        )
    else:
        graph = snapshot.graph
    return sorted(
        graph["edges"],
        key=lambda edge: (
            nodes.get(edge["source"], {}).get("name", edge["source"]),
            edge["type"],
            nodes.get(edge["target"], {}).get("name", edge["target"]),
        ),
    )


def _single_filter(values: set[str] | None) -> str | None:
    if not values or len(values) != 1:
        return None
    return next(iter(values))


def graph_explorer_rows(
    snapshot: TuiSnapshot,
    *,
    focus_node_id: str | None,
    depth: int,
    query: str | None,
) -> list[str]:
    statistics = graph_statistics(snapshot.graph)
    rows = [
        "Graph Explorer",
        f"nodes {statistics['node_count']} relationships {statistics['edge_count']}",
        f"node types {_format_count_map(statistics['node_types'])}",
        f"relationship types {_format_count_map(statistics['relationship_types'])}",
        "p expand  c collapse  o all graph  k search selected",
    ]
    if query:
        search = search_graph(snapshot.graph, query, limit=6)
        rows.extend(["", f"Search: {_short(query, 42)}"])
        if not search.get("nodes") and not search.get("relationships"):
            rows.append("  no matches")
        for node in search.get("nodes", [])[:4]:
            rows.append(
                f"  node {_short(node.get('node_type'), 10)}:"
                f"{_short(node.get('name'), 26)}"
            )
        for relationship in search.get("relationships", [])[:4]:
            rows.append(
                f"  rel {_short(relationship.get('source_name'), 14)} "
                f"{relationship.get('relationship_type')} "
                f"{_short(relationship.get('target_name'), 14)}"
            )
    if not focus_node_id:
        rows.extend(["", "Focus", "  select a node and press Enter or f"])
        return rows
    exploration = explore_graph_node(snapshot.graph, focus_node_id, depth=depth)
    if not exploration:
        rows.extend(["", f"Focus node not found: {focus_node_id}"])
        return rows
    selection = exploration["selection"]
    neighborhood = exploration.get("neighborhood") or {}
    neighborhood_stats = neighborhood.get("statistics", {})
    rows.extend(
        [
            "",
            f"Focus: {_short(selection.get('name'), 34)}",
            f"type: {selection.get('node_type')}  depth:{depth}",
            (
                "neighborhood "
                f"{neighborhood_stats.get('node_count', 0)} nodes / "
                f"{neighborhood_stats.get('edge_count', 0)} relationships"
            ),
            "",
            "Traversal targets",
        ]
    )
    targets = selection.get("navigation_targets", [])
    if not targets:
        rows.append("  none")
    for target in targets[:8]:
        arrow = "->" if target.get("direction") == "outgoing" else "<-"
        rows.append(
            f"  {arrow} {target.get('relationship_type')} "
            f"{_short(target.get('node_type'), 10)}:"
            f"{_short(target.get('node_name'), 22)}"
        )
    return rows


def _format_count_map(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return _short(", ".join(f"{name}:{count}" for name, count in counts.items()), 54)


def render_plain(snapshot: TuiSnapshot) -> str:
    health = snapshot.health
    lines = [
        OPENMESH_LOGO.strip("\n"),
        "OPENMESH CONTROL ROOM",
        f"Events {health['events']}  Traces {health['traces']}  Nodes {health['nodes']}  "
        f"Edges {health['edges']}  Sessions {len(snapshot.sessions)}  "
        f"Registry {sum(len(values) for values in snapshot.discovery.values())}",
        "",
        "┌─ Agents / Processes ─────────────┬─ Network ───────────────────────┐",
    ]
    nodes = agent_process_rows(snapshot)
    network = network_lines(snapshot, limit=10)
    for index in range(max(len(nodes), len(network), 1)):
        left = nodes[index] if index < len(nodes) else ""
        right = network[index] if index < len(network) else ""
        lines.append(f"│ {_short(left, 34):<34} │ {_short(right, 34):<34} │")
    lines.append(
        "├─ Traces ─────────────────────────┼─ Event Stream / Registry ───────┤"
    )
    traces = trace_rows(snapshot, limit=8)
    events = (
        event_rows(snapshot, limit=4) + ["", "Discovery"] + discovery_rows(snapshot)
    )
    for index in range(max(len(traces), len(events), 1)):
        left = traces[index] if index < len(traces) else ""
        right = events[index] if index < len(events) else ""
        lines.append(f"│ {_short(left, 34):<34} │ {_short(right, 34):<34} │")
    lines.append(
        "└──────────────────────────────────┴──────────────────────────────────┘"
    )
    return "\n".join(lines)


def agent_process_rows(snapshot: TuiSnapshot) -> list[str]:
    nodes, _ = _node_maps(snapshot)
    trace_counts = _trace_counts_by_node(snapshot)
    visible = [
        node
        for node in nodes.values()
        if node["type"] in {"agent", "process", "service"}
    ]
    visible.sort(key=lambda node: (node["type"], node["name"]))
    if not visible:
        return ["No agents/processes yet"]
    rows = []
    for node in visible:
        rows.append(
            f"{_short(node['name'], 17):<17} "
            f"{_status_label(_node_status(node, snapshot.sessions)):<11} "
            f"e:{node.get('event_count', 0):<3} "
            f"t:{trace_counts.get(node['id'], 0):<2} "
            f"{_time(node.get('last_seen'))}"
        )
    return rows


def trace_rows(snapshot: TuiSnapshot, limit: int = 50) -> list[str]:
    if not snapshot.traces:
        return ["No traces yet"]
    return [
        f"{_short(trace['trace_id'], 15):<15} {_status_label(trace['status']):<11} "
        f"{trace['event_count']:>3} {_time(trace['started_at'])}"
        for trace in snapshot.traces[:limit]
    ]


def event_rows(snapshot: TuiSnapshot, limit: int = 50) -> list[str]:
    if not snapshot.events:
        return ["No events yet"]
    return [
        f"{_time(event.get('timestamp'))} {_short(event['event_type'], 19)}"
        for event in snapshot.events[:limit]
    ]


def integration_rows(snapshot: TuiSnapshot) -> list[str]:
    if not snapshot.integrations:
        return ["No integrations registered"]
    rows = []
    for integration in snapshot.integrations:
        symbol = (
            "✓" if integration.get("available") or integration.get("active") else "○"
        )
        version = integration.get("version") or "-"
        planned = " planned" if integration.get("status") == "planned" else ""
        rows.append(
            f"{symbol} {_short(str(integration['name']), 14):<14} "
            f"{_short(str(integration['status_label']), 11):<11} "
            f"v:{version}{planned}"
        )
    return rows


def discovery_rows(snapshot: TuiSnapshot) -> list[str]:
    rows: list[str] = []
    sections = [
        ("Frameworks", "frameworks"),
        ("Agents", "agents"),
        ("Tools", "tools"),
        ("Capabilities", "capabilities"),
        ("Workflows", "workflows"),
        ("Processes", "processes"),
        ("Services", "services"),
    ]
    for label, key in sections:
        rows.append(label)
        entries = snapshot.discovery.get(key, [])
        if not entries:
            rows.append("  none observed")
        for entry in entries[:6]:
            rows.append(
                f"  {_short(str(entry['name']), 18):<18} "
                f"{_short(str(entry['status']), 10):<10} "
                f"e:{entry['event_count']} r:{entry['relationship_count']}"
            )
        rows.append("")
    return rows


def registry_rows(snapshot: TuiSnapshot) -> list[str]:
    registry = snapshot.registry_status
    compatibility = registry["compatibility"]
    rows = ["Versions"]
    for name, version in registry["versions"].items():
        rows.append(f"  {_short(name, 20):<20} {version}")
    rows.extend(["", f"Compatibility: {compatibility['severity']}"])
    issues = compatibility.get("errors", []) + compatibility.get("warnings", [])
    if not issues:
        rows.append("  no compatibility issues")
    for issue in issues[:6]:
        rows.append(f"  {_short(issue.get('code'), 24)}")
        rows.append(f"    {_short(issue.get('message'), 34)}")
    rows.extend(["", "Deprecated Definitions"])
    deprecated = [
        item
        for item in registry["node_definitions"] + registry["relationship_definitions"]
        if item.get("deprecated_in")
    ]
    if not deprecated:
        rows.append("  none")
    for item in deprecated[:6]:
        rows.append(f"  {_short(item['type'], 18)} since {item['deprecated_in']}")
    return rows


def mcp_rows(snapshot: TuiSnapshot) -> list[str]:
    if not snapshot.mcp_servers:
        return ["No MCP servers discovered"]
    rows = ["MCP Servers"]
    for server in snapshot.mcp_servers[:12]:
        rows.append(
            f"  {_short(server.get('server'), 18):<18} "
            f"{_short(server.get('version') or '-', 8):<8} "
            f"{_short(server.get('transport') or '-', 10):<10}"
        )
        rows.append(f"    {_short(server.get('endpoint'), 34)}")
        rows.append(f"    last {_time(server.get('last_seen'))}")
    return rows


def mcp_config_rows(snapshot: TuiSnapshot) -> list[str]:
    if not snapshot.mcp_configs:
        return ["No MCP config sources discovered"]
    rows = ["MCP Config Sources"]
    for config in snapshot.mcp_configs[:12]:
        rows.append(
            f"  {_short(config.get('source'), 14):<14} "
            f"{_short(config.get('server'), 16):<16} "
            f"{_short(config.get('transport') or '-', 8):<8}"
        )
        rows.append(f"    {_short(config.get('config_path'), 34)}")
    return rows


def capability_rows(snapshot: TuiSnapshot) -> list[str]:
    if not snapshot.capabilities:
        return ["No MCP capabilities discovered"]
    rows = ["MCP Capabilities"]
    for capability in snapshot.capabilities[:12]:
        rows.append(
            f"  {_short(capability.get('server'), 14):<14} "
            f"{_short(capability.get('capability'), 16):<16} "
            f"{_short(capability.get('category') or '-', 10):<10}"
        )
        if capability.get("description"):
            rows.append(f"    {_short(capability.get('description'), 34)}")
    return rows


def workflow_rows(snapshot: TuiSnapshot) -> list[str]:
    if not snapshot.workflows:
        return ["No workflows discovered"]
    rows = ["Workflows", "Select a workflow in Agents / Processes and press Enter."]
    for workflow in snapshot.workflows[:12]:
        rows.append(
            f"  {_short(workflow.get('workflow'), 18):<18} "
            f"{_short(workflow.get('workflow_type') or workflow.get('framework') or '-', 10):<10} "
            f"{_short(workflow.get('status') or 'observed', 10)}"
        )
        rows.append(f"    id {_short(workflow.get('workflow_id'), 32)}")
        rows.append(f"    start {_time(workflow.get('started_at'))}")
    return rows


def snapshot_rows(snapshot: TuiSnapshot) -> list[str]:
    if not snapshot.snapshots:
        return ["No ecosystem snapshots saved", "Run: openmesh snapshot create"]
    rows = ["Snapshots", "Press d for diff. In diff view, a/b cycle selection."]
    for item in snapshot.snapshots[:12]:
        counts = item.get("counts", {})
        rows.append(f"  {_short(item.get('snapshot_id'), 34)}")
        rows.append(f"    created {_time(item.get('created_at'))}")
        rows.append(
            "    "
            f"nodes {counts.get('nodes', 0)}  "
            f"edges {counts.get('edges', 0)}  "
            f"traces {counts.get('traces', 0)}  "
            f"sessions {counts.get('sessions', 0)}"
        )
    latest = snapshot.snapshots[0]
    graph_stats = latest.get("graph_statistics", {})
    ecosystem_stats = latest.get("ecosystem_statistics", {})
    rows.extend(
        [
            "",
            "Latest Snapshot",
            f"  graph nodes {graph_stats.get('node_count', 0)}",
            f"  graph edges {graph_stats.get('edge_count', 0)}",
            f"  ecosystem entities {ecosystem_stats.get('entity_count', 0)}",
            f"  ecosystem relationships {ecosystem_stats.get('relationship_count', 0)}",
        ]
    )
    return rows


def snapshot_diff_rows(
    snapshot: TuiSnapshot, a_index: int = 1, b_index: int = 0
) -> list[str]:
    detail_ids = [
        item.get("snapshot_id")
        for item in snapshot.snapshots[:5]
        if item.get("snapshot_id") in snapshot.snapshot_details
    ]
    if len(detail_ids) < 2:
        return [
            "Snapshot Diff",
            "Need at least two saved snapshots.",
            "Run: openmesh snapshot create",
        ]
    snapshot_a = detail_ids[a_index % len(detail_ids)]
    snapshot_b = detail_ids[b_index % len(detail_ids)]
    if snapshot_a == snapshot_b:
        snapshot_b = detail_ids[(b_index + 1) % len(detail_ids)]
    diff = compare_snapshot_payloads(
        snapshot.snapshot_details[snapshot_a], snapshot.snapshot_details[snapshot_b]
    )
    summary = diff["summary"]
    rows = [
        "Snapshot Diff",
        f"A {_short(snapshot_a, 32)}",
        f"B {_short(snapshot_b, 32)}",
        "Press a/b to cycle selections.",
        "",
        f"Nodes +{summary['nodes_added']} -{summary['nodes_removed']} ~{summary['nodes_changed']}",
        f"Relationships +{summary['relationships_added']} -{summary['relationships_removed']} ~{summary['relationships_changed']}",
        f"Workflows +{summary['workflows_added']} -{summary['workflows_removed']}",
        f"MCP +{summary['mcp_servers_added']} -{summary['mcp_servers_removed']}",
        f"Capabilities +{summary['capabilities_added']} -{summary['capabilities_removed']}",
        f"Traces Δ{summary['trace_count_delta']:+}",
        f"Sessions Δ{summary['session_count_delta']:+}",
        f"Graph nodes Δ{summary['graph_node_delta']:+}",
        f"Graph edges Δ{summary['graph_edge_delta']:+}",
        "",
        "Recent Relationship Changes",
    ]
    changed_relationships = (
        diff["relationships"]["added"]
        + diff["relationships"]["removed"]
        + diff["relationships"]["changed"]
    )
    if not changed_relationships:
        rows.append("  none")
    for item in changed_relationships[:6]:
        if "changed_fields" in item:
            after = item.get("after", {})
            rows.append(
                f"  ~ {_short(_diff_row_title(after), 32)} "
                f"{_short(','.join(item['changed_fields']), 18)}"
            )
        else:
            rows.append(f"  - {_short(_diff_row_title(item), 48)}")
    return rows


def timeline_rows(snapshot: TuiSnapshot) -> list[str]:
    timeline = snapshot.timeline or {}
    if not timeline:
        return ["No historical timeline loaded"]
    summary = timeline.get("summary", {})
    rows = [
        "Timeline",
        f"first {_time(timeline.get('first_appearance'))}",
        f"last  {_time(timeline.get('last_appearance'))}",
        (
            "events "
            f"{summary.get('events', 0)}  "
            f"relationships {summary.get('relationship_changes', 0)}  "
            f"snapshots {summary.get('snapshots', 0)}"
        ),
        "",
        "Evolution",
    ]
    for item in timeline.get("timeline", [])[-14:]:
        rows.append(
            f"  {_time(item.get('timestamp'))} {_short(_timeline_label(item), 42)}"
        )
    if not timeline.get("timeline"):
        rows.append("  none")
    rows.extend(["", "Snapshot History"])
    snapshots = timeline.get("snapshot_history", [])
    if not snapshots:
        rows.append("  none")
    for item in snapshots[-5:]:
        counts = item.get("counts", {})
        rows.append(
            f"  {_time(item.get('created_at'))} "
            f"{_short(item.get('snapshot_id'), 24)} "
            f"n:{counts.get('nodes', 0)} e:{counts.get('edges', 0)}"
        )
    return rows


def _timeline_label(item: dict[str, Any]) -> str:
    kind = item.get("kind") or item.get("event_type") or "item"
    if item.get("source") and item.get("target"):
        return (
            f"{kind} {item.get('source')} -> {item.get('target')} "
            f"{item.get('relationship_type') or ''}".strip()
        )
    if item.get("snapshot_id"):
        return f"{kind} {item['snapshot_id']}"
    if item.get("session_id"):
        return f"{kind} {item['session_id']}"
    if item.get("event_type"):
        return f"{kind} {item['event_type']}"
    return f"{kind} {item.get('name') or item.get('id') or ''}".strip()


def replay_rows(replay: dict[str, Any]) -> list[str]:
    state = replay.get("state", {})
    summary = replay.get("summary", {})
    rows = [
        "Replay",
        f"control {state.get('control')}  status {state.get('status')}",
        f"position {state.get('position')} / {max(state.get('frame_count', 0) - 1, 0)}",
        (
            "frames "
            f"{summary.get('frames', 0)}  "
            f"nodes {summary.get('nodes', 0)}  "
            f"relationships {summary.get('relationships', 0)}"
        ),
        "space start/pause  n step  m previous  x stop",
        "",
        "Current",
    ]
    current = state.get("current_frame")
    rows.append(f"  {_replay_label(current)}" if current else "  none")
    rows.extend(["", "Playback"])
    visible = replay.get("visible_frames", [])
    if not visible:
        rows.append("  none")
    for frame in visible[-12:]:
        rows.append(f"  {_replay_label(frame)}")
    return rows


def query_rows(snapshot: TuiSnapshot, query_index: int = 0) -> list[str]:
    if not SAVED_QUERIES:
        return ["No saved queries available"]
    saved = SAVED_QUERIES[query_index % len(SAVED_QUERIES)]
    snapshot_payloads = [
        snapshot.snapshot_details[item["snapshot_id"]]
        for item in snapshot.snapshots
        if item.get("snapshot_id") in snapshot.snapshot_details
    ]
    result = run_query_on_state(
        saved["query"],
        graph=snapshot.graph,
        discovery=snapshot.discovery,
        traces=snapshot.traces,
        sessions=snapshot.sessions,
        snapshots=snapshot_payloads,
        timeline=snapshot.timeline,
    )
    rows = [
        "Query",
        f"{saved['category']} / {saved['name']}",
        _short(saved["query"], 62),
        f"status {result.get('status')}  count {result.get('count', 0)}",
        "u next saved query",
        "",
        "Results",
    ]
    errors = result.get("errors", [])
    if errors:
        rows.append(f"  {errors[0].get('code')}: {errors[0].get('message')}")
    results = result.get("results", [])
    if not results and not errors:
        rows.append("  none")
    for item in results[:12]:
        rows.append(f"  {_query_label(item)}")
    rows.extend(["", "Sources"])
    rows.append(f"  {', '.join(result.get('source', [])) or '-'}")
    return rows


def _query_label(item: dict[str, Any]) -> str:
    if item.get("relationship_type"):
        return _short(
            f"{item.get('source')} {item.get('relationship_type')} {item.get('target')}",
            62,
        )
    if item.get("trace_id"):
        return _short(
            f"{item.get('trace_id')} {item.get('status', '-')} e:{item.get('event_count', 0)}",
            62,
        )
    if item.get("session_id"):
        return _short(
            f"{item.get('session_id')} {item.get('status', '-')} {item.get('command', '')}",
            62,
        )
    for key in ("agent", "workflow", "capability", "name", "id"):
        if item.get(key):
            return _short(str(item[key]), 62)
    return _short(str(item), 62)


def _replay_label(frame: dict[str, Any] | None) -> str:
    if not frame:
        return "none"
    return (
        f"[{frame.get('frame_index', '-')}] "
        f"{_time(frame.get('timestamp'))} "
        f"{_short(frame.get('action'), 22)} "
        f"{_short(frame.get('description'), 32)}"
    )


def _diff_row_title(item: dict[str, Any]) -> str:
    if item.get("source") and item.get("target") and item.get("type"):
        return f"{item['source']} {item['type']} {item['target']}"
    for key in ("name", "workflow", "server", "capability", "id"):
        if item.get(key):
            return str(item[key])
    return "unknown"


def ecosystem_rows(snapshot: TuiSnapshot) -> list[str]:
    ecosystem = snapshot.ecosystem
    summary = ecosystem.get("summary", {})
    rows = [
        "Ecosystem",
        f"  entities {summary.get('entity_count', 0)} relationships {summary.get('relationship_count', 0)}",
        "",
    ]
    labels = [
        ("Agents", "agents"),
        ("Tools", "tools"),
        ("Processes", "processes"),
        ("Workflows", "workflows"),
        ("MCP Servers", "mcp_servers"),
        ("MCP Configs", "mcp_configs"),
        ("Capabilities", "capabilities"),
    ]
    entities_by_group = ecosystem.get("entities", {})
    for label, key in labels:
        rows.append(label)
        entities = entities_by_group.get(key, [])
        if not entities:
            rows.append("  none observed")
        for entity in entities[:5]:
            rows.append(
                f"  {_short(entity.get('name'), 17):<17} "
                f"{_short(entity.get('status'), 8):<8} "
                f"e:{entity.get('event_count', 0)} r:{entity.get('relationship_count', 0)}"
            )
        rows.append("")
    return rows


def trace_detail_rows(snapshot: TuiSnapshot, trace_id: str) -> list[str]:
    events = sorted(
        [event for event in snapshot.events if event.get("trace_id") == trace_id],
        key=lambda event: event["timestamp"],
    )
    if not events:
        return [f"Trace {trace_id}", "No loaded events for trace"]
    rows = [f"Trace {_short(trace_id, 24)}", "Hierarchy"]
    rows.extend(_compact_hierarchy(build_event_hierarchy(events)))
    rows.append("")
    rows.append("Spans")
    for span in build_span_summary(events)[:8]:
        rows.append(
            f"  {_short(span['span_id'], 14)} "
            f"{_short(span.get('status'), 9):<9} "
            f"e:{span['event_count']} c:{len(span.get('child_span_ids', []))}"
        )
    span_tree = build_span_tree(events)
    if span_tree:
        rows.append("")
        rows.append("Span Tree")
        rows.extend(_compact_span_tree(span_tree)[:8])
    rows.append("")
    rows.append("Relationships")
    relationships = graph_edges_for_trace(events)
    if not relationships:
        rows.append("  none")
    for edge in relationships[:8]:
        rows.append(
            f"  {_short(edge['source'], 10)} {edge['type']} {_short(edge['target'], 10)}"
        )
    return rows


def edge_detail_rows(snapshot: TuiSnapshot, edge_id: str) -> list[str]:
    nodes, _ = _node_maps(snapshot)
    edge = next(
        (item for item in snapshot.graph["edges"] if item["id"] == edge_id), None
    )
    if not edge:
        return [f"Relationship {edge_id}", "No loaded relationship detail"]
    source = nodes.get(edge["source"], {"name": edge["source"]})
    target = nodes.get(edge["target"], {"name": edge["target"]})
    definition = edge.get("relationship_definition") or {}
    provenance = edge.get("provenance") or {}
    trace_ids = provenance.get("trace_ids") or edge.get("trace_ids") or []
    event_ids = provenance.get("event_ids") or edge.get("event_ids") or []
    rows = [
        f"{_short(source['name'], 18)} {edge['type']} {_short(target['name'], 18)}",
        f"validation: {edge.get('validation_status', 'unknown')}",
        f"definition: {_short(definition.get('description'), 46)}",
        f"state: {edge.get('lifecycle_state', 'unknown')}",
        f"observations: {edge.get('observation_count', edge.get('event_count', 0))}",
        f"first_seen: {_time(edge.get('first_seen'))}",
        f"last_seen: {_time(edge.get('last_seen'))}",
        "",
        "Provenance",
        f"traces: {_short(_join_values(trace_ids), 42)}",
        f"events: {_short(_join_values(event_ids), 42)}",
        f"first_event: {_short(provenance.get('first_event_id'), 28)}",
        f"last_event: {_short(provenance.get('last_event_id'), 28)}",
        "",
        "Traversal",
        f"source: {_short(source.get('type'), 10)}:{_short(source['name'], 28)}",
        f"target: {_short(target.get('type'), 10)}:{_short(target['name'], 28)}",
        f"path: {_short(source['name'], 16)} -> {_short(target['name'], 16)}",
        "",
        "Recent observations",
    ]
    observations = provenance.get("observations") or edge.get("observations", [])
    for observation in observations[-5:]:
        rows.append(
            f"  {_time(observation.get('timestamp'))} "
            f"{_short(observation.get('event_type'), 18)} "
            f"{_short(observation.get('event_id'), 18)}"
        )
    return rows


def _join_values(values: list[Any], limit: int = 4) -> str:
    if not values:
        return "-"
    visible = [str(value) for value in values[:limit]]
    if len(values) > limit:
        visible.append(f"+{len(values) - limit}")
    return ", ".join(visible)


def node_detail_rows(snapshot: TuiSnapshot, node_id: str) -> list[str]:
    nodes, outgoing = _node_maps(snapshot)
    inspection = inspect_graph_node(snapshot.graph, node_id)
    if not inspection:
        return [f"Node {node_id}", "No loaded node detail"]
    node = inspection["node"]
    if node.get("type") == "workflow":
        workflow = inspect_graph_workflow(snapshot.graph, node_id)
        if workflow:
            return workflow_detail_rows(workflow)
    definition = node.get("type_definition") or {}
    provenance = inspection.get("provenance", {})
    rows = [
        node["name"],
        f"type: {node['type']} ({definition.get('display_name', 'unknown')})",
        f"definition: {_short(definition.get('description'), 46)}",
        f"category: {node.get('category', 'unknown')}",
        f"validation: {node.get('validation_status', 'unknown')}",
        f"status: {node.get('lifecycle_state', 'unknown')}",
        f"first_seen: {_time(inspection.get('first_seen'))}",
        f"last_seen: {_time(node.get('last_seen'))}",
        f"events: {inspection.get('event_count', 0)}",
        f"relationships: {inspection.get('relationship_count', 0)}",
        f"traces: {_short(_join_values(inspection.get('trace_ids', [])), 42)}",
        f"sessions: {_short(_join_values(inspection.get('session_ids', [])), 42)}",
        "",
        "Metadata",
    ]
    metadata = node.get("metadata") or {}
    if not metadata:
        rows.append("  none")
    for key, value in sorted(metadata.items()):
        rows.append(f"  {key}: {_short(str(value), 34)}")
    rows.extend(["", "Relationships", "Incoming"])
    if not inspection.get("incoming_relationships"):
        rows.append("  none")
    for edge in inspection.get("incoming_relationships", [])[:5]:
        source = nodes.get(edge["source"], {"name": edge["source"]})
        rows.append(
            f"  <- {edge['type']} {_short(source['name'], 24)} "
            f"obs:{edge.get('observation_count', edge.get('event_count', 0))}"
        )
    rows.append("")
    rows.append("Outgoing")
    if not inspection.get("outgoing_relationships"):
        rows.append("  none")
    for edge in outgoing.get(node_id, [])[:5]:
        target = nodes.get(edge["target"], {"name": edge["target"]})
        rows.append(
            f"  -> {edge['type']} {_short(target['name'], 24)} "
            f"obs:{edge.get('observation_count', edge.get('event_count', 0))}"
        )
    exploration = explore_graph_node(snapshot.graph, node_id, depth=1)
    if exploration:
        neighborhood = exploration.get("neighborhood") or {}
        traversal = exploration.get("traversal") or {}
        rows.extend(
            [
                "",
                "Explore",
                f"neighborhood: {neighborhood.get('statistics', {}).get('node_count', 0)} nodes / "
                f"{neighborhood.get('statistics', {}).get('edge_count', 0)} edges",
                "Traversal targets",
            ]
        )
        relationships = traversal.get("relationships", [])
        if not relationships:
            rows.append("  none")
        for relationship in relationships[:8]:
            arrow = "->" if relationship.get("direction") == "outgoing" else "<-"
            rows.append(
                f"  {arrow} {relationship.get('relationship_type')} "
                f"{_short(relationship.get('node_type'), 10)}:"
                f"{_short(relationship.get('node_name'), 22)}"
            )
        rows.append("")
        rows.append("Search")
        search = search_graph(snapshot.graph, node["name"], limit=5)
        matches = search.get("nodes", []) + search.get("relationships", [])
        if not matches:
            rows.append("  none")
        for match in matches[:5]:
            if match.get("relationship_type"):
                rows.append(
                    f"  rel {match.get('relationship_type')} "
                    f"{_short(match.get('source_name'), 14)} -> "
                    f"{_short(match.get('target_name'), 14)}"
                )
            else:
                rows.append(
                    f"  node {_short(match.get('node_type'), 10)}:"
                    f"{_short(match.get('name'), 24)}"
                )
    rows.extend(
        [
            "",
            "Provenance",
            f"events: {_short(_join_values(provenance.get('event_ids', [])), 42)}",
            f"window: {_time(provenance.get('first_seen'))} -> {_time(provenance.get('last_seen'))}",
            f"first_event: {_short(provenance.get('first_event_id'), 28)}",
            f"last_event: {_short(provenance.get('last_event_id'), 28)}",
        ]
    )
    return rows


def workflow_detail_rows(workflow: dict[str, Any]) -> list[str]:
    rows = [
        workflow["workflow"],
        f"id: {_short(workflow.get('workflow_id'), 42)}",
        f"type: {workflow.get('workflow_type') or '-'}",
        f"runtime: {workflow.get('runtime') or '-'}",
        f"status: {workflow.get('status') or 'observed'}",
        f"started: {_time(workflow.get('started_at'))}",
        f"ended: {_time(workflow.get('ended_at'))}",
        f"events: {workflow.get('event_count', 0)} relationships: {workflow.get('relationship_count', 0)}",
        f"traces: {_short(_join_values(workflow.get('trace_ids', [])), 42)}",
        f"sessions: {_short(_join_values(workflow.get('session_ids', [])), 42)}",
        "",
        "Agents",
    ]
    rows.extend(_participant_rows(workflow.get("participating_agents", [])))
    rows.append("")
    rows.append("Tools")
    rows.extend(_participant_rows(workflow.get("participating_tools", [])))
    rows.append("")
    rows.append("MCP Servers")
    rows.extend(_participant_rows(workflow.get("participating_mcp_servers", [])))
    rows.append("")
    rows.append("Services")
    rows.extend(_participant_rows(workflow.get("participating_services", [])))
    provenance = workflow.get("provenance", {})
    rows.extend(
        [
            "",
            "Workflow Provenance",
            f"events: {_short(_join_values(provenance.get('event_ids', [])), 42)}",
            f"window: {_time(provenance.get('first_seen'))} -> {_time(provenance.get('last_seen'))}",
            f"first_event: {_short(provenance.get('first_event_id'), 28)}",
            f"last_event: {_short(provenance.get('last_event_id'), 28)}",
        ]
    )
    return rows


def _participant_rows(participants: list[dict[str, Any]]) -> list[str]:
    if not participants:
        return ["  none"]
    return [
        f"  {_short(item.get('name'), 24)} {item.get('relationship_type')} {item.get('direction')}"
        for item in participants[:8]
    ]


def _compact_hierarchy(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    rows: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        rows.append(f"{prefix}{branch} {_short(node['event_type'], 22)}")
        rows.extend(
            _compact_hierarchy(
                node.get("children", []),
                prefix + ("   " if index == len(nodes) - 1 else "│  "),
            )
        )
    return rows


def _compact_span_tree(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    rows: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        rows.append(
            f"{prefix}{branch} {_short(node['span_id'], 16)} {node.get('status', 'unknown')}"
        )
        rows.extend(
            _compact_span_tree(
                node.get("children", []),
                prefix + ("   " if index == len(nodes) - 1 else "│  "),
            )
        )
    return rows


def _matches_query(query: str, *values: Any) -> bool:
    """Case-insensitive substring match across candidate values."""
    needle = query.strip().lower()
    if not needle:
        return True
    return any(needle in str(value).lower() for value in values if value is not None)


def event_stream_line(event: dict[str, Any]) -> str:
    """One log-viewer line per OpenMesh event."""
    source = (event.get("source") or {}).get("name") or "-"
    target = (event.get("target") or {}).get("name")
    severity = str(event.get("severity") or "info")
    line = (
        f"{_time(event.get('timestamp'))} "
        f"{severity[:4]:<4} "
        f"{_short(event.get('event_type'), 26):<26} "
        f"{_short(source, 20)}"
    )
    if target:
        line += f" -> {_short(target, 20)}"
    return line


def _memory_mb() -> float:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return 0.0
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return usage / divisor


def export_snapshot_files(snapshot: TuiSnapshot, directory: Path) -> list[Path]:
    """Write events/traces/graph to JSON plus CSV tables. Returns written paths."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, payload in (
        ("events.json", snapshot.events),
        ("traces.json", snapshot.traces),
        ("graph.json", snapshot.graph),
    ):
        path = directory / name
        path.write_text(json.dumps(payload, indent=2, default=str), "utf-8")
        written.append(path)

    events_csv = directory / "events.csv"
    with events_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["timestamp", "event_type", "trace_id", "source", "target", "severity"]
        )
        for event in snapshot.events:
            writer.writerow(
                [
                    event.get("timestamp"),
                    event.get("event_type"),
                    event.get("trace_id"),
                    (event.get("source") or {}).get("name"),
                    (event.get("target") or {}).get("name"),
                    event.get("severity"),
                ]
            )
    written.append(events_csv)

    traces_csv = directory / "traces.csv"
    with traces_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trace_id", "status", "event_count", "started_at", "ended_at"])
        for trace in snapshot.traces:
            writer.writerow(
                [
                    trace.get("trace_id"),
                    trace.get("status"),
                    trace.get("event_count"),
                    trace.get("started_at"),
                    trace.get("ended_at"),
                ]
            )
    written.append(traces_csv)
    return written


# Sortable columns per table: (label, cell index, numeric-descending).
TABLE_SORT_COLUMNS: dict[str, list[tuple[str, int, bool]]] = {
    "agents-table": [
        ("name", 0, False),
        ("type", 1, False),
        ("events", 3, True),
        ("last", 4, False),
    ],
    "traces-table": [
        ("trace", 0, False),
        ("status", 1, False),
        ("events", 2, True),
        ("start", 3, False),
    ],
    "network-table": [
        ("source", 0, False),
        ("relationship", 1, False),
        ("target", 2, False),
        ("obs", 4, True),
    ],
}


HELP_TEXT = """\
OPENMESH CONTROL ROOM — KEYBOARD REFERENCE

Navigation
  Tab / Shift+Tab    cycle focus between panels
  1 / 2 / 3 / 4      focus Agents · Traces · Network · Event Stream
  Arrow keys         move row cursor / scroll
  PgUp / PgDn        page through tables and logs
  Home / End         jump to top / bottom
  j / k              scroll detail view & event stream (vim)
  Mouse / touchpad   wheel-scroll any panel, click to focus & select

Inspect
  Enter / click      inspect selected row (trace, node, relationship)
  f                  focus graph on selected node
  p / c              expand / collapse graph depth
  o                  clear graph focus (show all)
  k                  graph-search from selection (tables)
  g                  cycle graph filter (agents, tools, workflows, …)

Views
  5 integrations   6 discovery      7 registry    8 MCP
  9 MCP config     0 capabilities   w workflows   e ecosystem
  s snapshots      d snapshot diff  l timeline    r replay
  y queries        u next query     a / b diff selection

Event Stream
  z                  pause / resume the stream
  Ctrl+L             clear the stream
  Auto-scroll sticks to the bottom; scroll up to hold position,
  press End to resume following.

Replay
  Space              play / pause      n / m   step forward / back
  x                  stop

Search, Sort & Export
  /                  global search (agents, traces, relationships, events)
  v                  cycle sort column on the focused table
  E                  export events / traces / graph to JSON + CSV

General
  ?                  toggle this help
  Esc                close overlay / clear search / back to event stream
  q                  quit
"""


class Panel(Vertical):
    """Titled panel container; highlighted via :focus-within when active."""


class OMDataTable(DataTable):
    """DataTable with the stock scrolling plus vim-style row movement."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]


class DetailScroll(VerticalScroll):
    """Scrollable, focusable body for the lower-right detail modes."""

    BINDINGS = [
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]


class EventLog(RichLog):
    """Focusable event stream log with vim-style scrolling."""

    can_focus = True

    BINDINGS = [
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]


class HelpScreen(ModalScreen[None]):
    """Keyboard reference overlay. Opened with ?, closed with Esc."""

    BINDINGS = [
        Binding("escape", "close_help", "Close"),
        Binding("question_mark", "close_help", "Close", show=False),
        Binding("q", "close_help", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-card"):
            yield Static(HELP_TEXT, id="help-text")

    def action_close_help(self) -> None:
        self.dismiss(None)


class OpenMeshTui(App):
    REFRESH_INTERVAL = 2.0

    CSS = """
    Screen {
        background: #070605;
        color: #b8afa2;
    }

    #topbar {
        height: auto;
        max-height: 10;
        background: #11100e;
        color: #c56b2c;
        text-style: bold;
        padding: 0 2;
        border-bottom: heavy #7a3f20;
    }

    #search-input {
        display: none;
        height: 3;
        margin: 0 1;
        border: heavy #7a3f20;
        background: #0d0c0a;
        color: #e8dcc8;
    }

    #grid {
        height: 1fr;
        padding: 1 1 0 1;
    }

    .column {
        width: 1fr;
        height: 1fr;
    }

    .panel {
        height: 1fr;
        border: solid #3b3731;
        background: #0d0c0a;
        padding: 0 1 1 1;
    }

    .panel:focus-within {
        border: heavy #c56b2c;
    }

    #network-panel {
        border: heavy #9b5127;
        background: #100c09;
    }

    #network-panel:focus-within {
        border: heavy #c56b2c;
    }

    .panel-title {
        height: 1;
        color: #c56b2c;
        text-style: bold;
        background: #17130f;
    }

    DataTable {
        background: #0d0c0a;
        color: #b8afa2;
        height: 1fr;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }

    DataTable > .datatable--header {
        color: #c56b2c;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #6e3a20;
        color: #f1d0ad;
        text-style: bold;
    }

    DataTable > .datatable--hover {
        background: #211a14;
    }

    #event-log {
        height: 1fr;
        background: #0d0c0a;
        color: #b8afa2;
        padding-top: 1;
        scrollbar-size-vertical: 1;
    }

    #detail-scroll {
        height: 1fr;
        scrollbar-size-vertical: 1;
    }

    #event-body {
        height: auto;
        color: #b8afa2;
        padding-top: 1;
    }

    HelpScreen {
        align: center middle;
    }

    #help-card {
        width: 76;
        max-width: 96%;
        max-height: 90%;
        border: heavy #c56b2c;
        background: #11100e;
        padding: 1 2;
    }

    #help-text {
        color: #d8cdba;
    }

    Footer {
        background: #11100e;
        color: #8f9aa0;
        border-top: solid #3b3731;
    }
    """

    BINDINGS = [
        Binding("tab", "focus_next", "Next Panel", show=False, priority=True),
        Binding("shift+tab", "focus_previous", "Prev Panel", show=False, priority=True),
        Binding("escape", "back", "Back", show=False, priority=True),
        Binding("question_mark", "show_help", "Help"),
        Binding("slash", "open_search", "Search"),
        Binding("E", "export_data", "Export"),
        Binding("v", "cycle_sort", "Sort"),
        Binding("z", "toggle_stream_pause", "Pause Stream"),
        Binding("ctrl+l", "clear_stream", "Clear Stream", show=False),
        ("1", "focus_panel('agents')", "Overview"),
        ("2", "focus_panel('traces')", "Traces"),
        ("3", "focus_panel('network')", "Graph"),
        ("4", "focus_panel('events')", "Events"),
        Binding("5", "show_detail('integrations')", "Integrations", show=False),
        Binding("6", "show_detail('discovery')", "Discovery", show=False),
        Binding("7", "show_detail('registry')", "Registry", show=False),
        Binding("8", "show_detail('mcp')", "MCP", show=False),
        Binding("9", "show_detail('mcp_config')", "MCP Config", show=False),
        Binding("0", "show_detail('capabilities')", "Capabilities", show=False),
        Binding("w", "show_detail('workflows')", "Workflows", show=False),
        Binding("e", "show_detail('ecosystem')", "Ecosystem", show=False),
        Binding("s", "show_detail('snapshots')", "Snapshots", show=False),
        Binding("d", "show_detail('snapshot_diff')", "Snapshot Diff", show=False),
        Binding("l", "show_detail('timeline')", "Timeline", show=False),
        Binding("r", "show_replay", "Replay", show=False),
        Binding("y", "show_detail('query')", "Query", show=False),
        Binding("g", "cycle_graph_filter", "Graph Filter", show=False),
        Binding("f", "focus_graph_node", "Focus Node", show=False),
        Binding("p", "expand_graph", "Expand", show=False),
        Binding("c", "collapse_graph", "Collapse", show=False),
        Binding("o", "clear_graph_focus", "All Graph", show=False),
        Binding("k", "search_graph_selection", "Graph Search", show=False),
        Binding("u", "next_query", "Next Query", show=False),
        Binding("space", "toggle_replay", "Play/Pause", show=False),
        Binding("n", "step_replay", "Step", show=False),
        Binding("m", "previous_replay", "Previous", show=False),
        Binding("x", "stop_replay", "Stop", show=False),
        Binding("a", "select_snapshot_a", "Select A", show=False),
        Binding("b", "select_snapshot_b", "Select B", show=False),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.snapshot: TuiSnapshot | None = None
        self.lower_right_mode = "events"
        self.selected_trace_id: str | None = None
        self.selected_edge_id: str | None = None
        self.selected_node_id: str | None = None
        self.snapshot_diff_a_index = 1
        self.snapshot_diff_b_index = 0
        self.replay_control = "start"
        self.replay_position = 0
        self.query_index = 0
        self.network_filter_index = 0
        self.graph_focus_node_id: str | None = None
        self.graph_depth = 1
        self.graph_search_query: str | None = None
        self.search_query = ""
        self.stream_paused = False
        self.agent_node_rows: list[dict[str, Any]] = []
        self.trace_display_rows: list[dict[str, Any]] = []
        self.network_edge_rows: list[dict[str, Any]] = []
        self._row_payloads: dict[str, dict[str, Any]] = {}
        self._fingerprints: dict[str, Any] = {}
        self._sort_index: dict[str, int | None] = {}
        self._seen_event_ids: set[str] = set()
        self._stream_has_content = False
        self._pending_stream_count = 0
        self._events_per_second = 0.0
        self._load_ms = 0
        self._refreshing = False
        self._compact = False

    # ── Layout ────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("", id="topbar")
        yield Input(
            placeholder=(
                "Search agents, traces, relationships, events…"
                "  (Enter to apply, Esc to clear)"
            ),
            id="search-input",
        )
        with Horizontal(id="grid"):
            with Vertical(classes="column"):
                with Panel(id="agents-panel", classes="panel"):
                    yield Static(
                        "AGENTS / PROCESSES", id="agents-title", classes="panel-title"
                    )
                    yield OMDataTable(id="agents-table")
                with Panel(id="traces-panel", classes="panel"):
                    yield Static("TRACES", id="traces-title", classes="panel-title")
                    yield OMDataTable(id="traces-table")
            with Vertical(classes="column"):
                with Panel(id="network-panel", classes="panel"):
                    yield Static("NETWORK", id="network-title", classes="panel-title")
                    yield OMDataTable(id="network-table")
                with Panel(id="events-panel", classes="panel"):
                    yield Static(
                        "EVENT STREAM", id="event-title", classes="panel-title"
                    )
                    yield EventLog(
                        id="event-log",
                        markup=False,
                        highlight=False,
                        wrap=False,
                        max_lines=2000,
                        auto_scroll=False,
                    )
                    with DetailScroll(id="detail-scroll"):
                        yield Static("", id="event-body")
        yield Footer()

    async def on_mount(self) -> None:
        for table_id, columns in (
            ("agents-table", ("name", "type", "status", "events", "last")),
            ("traces-table", ("trace", "status", "events", "start")),
            ("network-table", ("source", "relationship", "target", "state", "obs")),
        ):
            table = self.query_one(f"#{table_id}", DataTable)
            table.add_columns(*columns)
            table.cursor_type = "row"
            table.zebra_stripes = True
        self.query_one("#detail-scroll", DetailScroll).display = False
        self._apply_layout(self.size)
        self.query_one("#agents-table", DataTable).focus()
        await self.refresh_data()
        self.set_interval(self.REFRESH_INTERVAL, self.refresh_data)

    def on_resize(self, event: Any) -> None:
        self._apply_layout(event.size)

    def _apply_layout(self, size: Any) -> None:
        stacked = size.width < 100
        grid = self.query_one("#grid", Horizontal)
        grid.styles.layout = "vertical" if stacked else "horizontal"
        compact = size.height < 28 or size.width < 90
        if compact != self._compact:
            self._compact = compact
            if self.snapshot:
                self._refresh_topbar()

    def on_descendant_focus(self, event: Any) -> None:
        if self.snapshot:
            self._refresh_topbar()

    # ── Data refresh ──────────────────────────────────────────────────────

    async def refresh_data(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            started = perf_counter()
            self.snapshot = await load_snapshot()
            self._load_ms = int((perf_counter() - started) * 1000)
        finally:
            self._refreshing = False
        self._refresh_all()

    def _refresh_all(self) -> None:
        self._refresh_tables()
        self._refresh_event_stream()
        self._refresh_detail()
        self._refresh_topbar()

    def _refresh_tables(self) -> None:
        self._refresh_agents()
        self._refresh_traces()
        self._refresh_network()

    def _refresh_topbar(self) -> None:
        if not self.snapshot:
            return
        health = self.snapshot.health
        graph_filter = GRAPH_FILTERS[self.network_filter_index][0]
        stats = (
            f"events:{health['events']} traces:{health['traces']} "
            f"nodes:{health['nodes']} edges:{health['edges']} "
            f"sessions:{len(self.snapshot.sessions)} "
            f"evt/s:{self._events_per_second:.1f} "
            f"refresh:{self.REFRESH_INTERVAL:.0f}s db:{self._load_ms}ms "
            f"mem:{_memory_mb():.0f}MB"
        )
        state = (
            f"focus:{self._focused_panel_name()} filter:{graph_filter} "
            f"search:{_short(self.search_query or '-', 16)} "
            f"graph:{_short(self._graph_focus_label(), 20)} depth:{self.graph_depth}"
        )
        if self.stream_paused:
            state += "  · stream PAUSED"
        hints = (
            "\\[?] help  \\[/] search  \\[E] export  \\[z] pause  "
            "\\[Tab] panels  \\[q] quit"
        )
        if self._compact:
            text = (
                "[#c56b2c]OPENMESH CONTROL ROOM[/]  "
                f"[#8f9aa0]{stats}\n{state}  {hints}[/]"
            )
        else:
            text = (
                f"[#c56b2c]{OPENMESH_LOGO.strip()}[/]\n"
                f"[#8f9aa0]CONTROL ROOM  {stats}\n{state}  {hints}[/]"
            )
        self.query_one("#topbar", Static).update(text)

    def _focused_panel_name(self) -> str:
        widget_id = getattr(self.focused, "id", None) or ""
        return {
            "agents-table": "agents",
            "traces-table": "traces",
            "network-table": "network",
            "event-log": "events",
            "detail-scroll": "detail",
            "search-input": "search",
        }.get(widget_id, "-")

    # ── Table plumbing: fingerprints, cursor/scroll preservation, sorting ─

    def _sorted_entries(
        self,
        table_id: str,
        entries: list[tuple[Any, tuple[str, ...]]],
    ) -> list[tuple[Any, tuple[str, ...]]]:
        sort_index = self._sort_index.get(table_id)
        if sort_index is None:
            return entries
        _, cell_index, numeric = TABLE_SORT_COLUMNS[table_id][sort_index]

        def sort_key(entry: tuple[Any, tuple[str, ...]]) -> Any:
            value = str(entry[1][cell_index])
            if numeric:
                digits = "".join(char for char in value if char.isdigit())
                return -int(digits) if digits else 0
            return value.lower()

        return sorted(entries, key=sort_key)

    def _sort_suffix(self, table_id: str) -> str:
        sort_index = self._sort_index.get(table_id)
        if sort_index is None:
            return ""
        label, _, numeric = TABLE_SORT_COLUMNS[table_id][sort_index]
        return f"  ↓{label}" if numeric else f"  ↑{label}"

    @staticmethod
    def _cursor_row_key(table: DataTable) -> str | None:
        if not table.row_count:
            return None
        try:
            cell_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0))
        except Exception:
            return None
        value = cell_key.row_key.value
        return str(value) if value is not None else None

    def _update_table(
        self,
        table_id: str,
        rows: list[tuple[tuple[str, ...], str, Any]],
        empty_message: str,
    ) -> None:
        """Rebuild a table only when its content changed, keeping cursor and
        scroll position so periodic refreshes never yank the view around."""
        table = self.query_one(f"#{table_id}", DataTable)
        fingerprint = hash(tuple((cells, key) for cells, key, _ in rows))
        if self._fingerprints.get(table_id) == fingerprint:
            return
        self._fingerprints[table_id] = fingerprint
        previous_key = self._cursor_row_key(table)
        scroll_y = table.scroll_y
        table.clear()
        payloads: dict[str, Any] = {}
        self._row_payloads[table_id] = payloads
        if not rows:
            table.add_row(empty_message, *[""] * (len(table.columns) - 1))
            return
        key_index: dict[str, int] = {}
        for index, (cells, key, payload) in enumerate(rows):
            row_key = key
            while row_key in payloads:
                row_key = f"{key}#{index}"
            payloads[row_key] = payload
            table.add_row(*cells, key=row_key)
            key_index.setdefault(key, index)
        if previous_key is not None and previous_key in key_index:
            table.move_cursor(row=key_index[previous_key], animate=False)
        else:
            table.scroll_to(y=min(scroll_y, table.max_scroll_y), animate=False)

    def _set_panel_title(
        self, title_id: str, base: str, count: int, table_id: str | None = None
    ) -> None:
        suffix = f" ({count})"
        if table_id:
            suffix += self._sort_suffix(table_id)
        if self.search_query:
            suffix += f"  match:{_short(self.search_query, 12)}"
        self.query_one(f"#{title_id}", Static).update(base + suffix)

    # ── Panel refreshes ───────────────────────────────────────────────────

    def _refresh_agents(self) -> None:
        assert self.snapshot is not None
        nodes, _ = _node_maps(self.snapshot)
        trace_counts = _trace_counts_by_node(self.snapshot)
        entries: list[tuple[Any, tuple[str, ...]]] = []
        for node in nodes.values():
            if node["type"] not in {"agent", "process", "service", "workflow"}:
                continue
            status = _node_status(node, self.snapshot.sessions)
            if not _matches_query(
                self.search_query,
                node.get("name"),
                node.get("type"),
                status,
                node.get("id"),
            ):
                continue
            cells = (
                _short(node["name"], 28),
                node["type"],
                _status_label(status),
                str(node.get("event_count", 0)),
                f"{_time(node.get('last_seen'))} / t:{trace_counts.get(node['id'], 0)}",
            )
            entries.append((node, cells))
        entries.sort(key=lambda entry: (entry[0]["type"], entry[0]["name"]))
        entries = self._sorted_entries("agents-table", entries)
        self.agent_node_rows = [node for node, _ in entries]
        rows = [(cells, str(node["id"]), node) for node, cells in entries]
        self._update_table("agents-table", rows, "Waiting for agents…")
        self._set_panel_title(
            "agents-title", "AGENTS / PROCESSES", len(rows), "agents-table"
        )

    def _refresh_traces(self) -> None:
        assert self.snapshot is not None
        entries: list[tuple[Any, tuple[str, ...]]] = []
        for trace in self.snapshot.traces:
            if not _matches_query(
                self.search_query, trace.get("trace_id"), trace.get("status")
            ):
                continue
            cells = (
                _short(trace["trace_id"], 24),
                _status_label(trace["status"]),
                str(trace["event_count"]),
                _time(trace["started_at"]),
            )
            entries.append((trace, cells))
        entries = self._sorted_entries("traces-table", entries)
        self.trace_display_rows = [trace for trace, _ in entries]
        rows = [(cells, str(trace["trace_id"]), trace) for trace, cells in entries]
        self._update_table("traces-table", rows, "No active traces.")
        self._set_panel_title("traces-title", "TRACES", len(rows), "traces-table")

    def _refresh_network(self) -> None:
        assert self.snapshot is not None
        nodes, _ = _node_maps(self.snapshot)
        filter_name, node_types, relationship_types = GRAPH_FILTERS[
            self.network_filter_index
        ]
        title = "NETWORK"
        if self.graph_focus_node_id:
            title = (
                f"NETWORK  focus:{_short(self._graph_focus_label(), 24)} "
                f"depth:{self.graph_depth}"
            )
        elif self.graph_search_query:
            title = f"NETWORK  search:{_short(self.graph_search_query, 28)}"
        elif filter_name != "all":
            title = f"NETWORK  filter:{filter_name}"
        edges = network_edges(
            self.snapshot,
            focus_node_id=self.graph_focus_node_id,
            depth=self.graph_depth,
            node_types=node_types,
            relationship_types=relationship_types,
            query=self.graph_search_query,
        )
        entries: list[tuple[Any, tuple[str, ...]]] = []
        for edge in edges:
            source = nodes.get(edge["source"], {"name": edge["source"]})
            target = nodes.get(edge["target"], {"name": edge["target"]})
            if not _matches_query(
                self.search_query,
                source.get("name"),
                edge.get("type"),
                target.get("name"),
            ):
                continue
            cells = (
                _short(source["name"], 20),
                _short(edge["type"], 18),
                _short(target["name"], 20),
                _short(edge.get("lifecycle_state", "unknown"), 12),
                str(edge.get("observation_count", edge.get("event_count", 0))),
            )
            entries.append((edge, cells))
        entries = self._sorted_entries("network-table", entries)
        self.network_edge_rows = [edge for edge, _ in entries]
        rows = [(cells, str(edge["id"]), edge) for edge, cells in entries]
        self._update_table("network-table", rows, "No relationships yet.")
        suffix = f" ({len(rows)})" + self._sort_suffix("network-table")
        if self.search_query:
            suffix += f"  match:{_short(self.search_query, 12)}"
        self.query_one("#network-title", Static).update(title + suffix)

    # ── Event stream (log viewer) ─────────────────────────────────────────

    def _refresh_event_stream(self) -> None:
        assert self.snapshot is not None
        log = self.query_one("#event-log", EventLog)
        events = list(reversed(self.snapshot.events))  # chronological order
        fresh = [
            event
            for event in events
            if str(event.get("event_id")) not in self._seen_event_ids
        ]
        self._events_per_second = round(len(fresh) / self.REFRESH_INTERVAL, 2)

        if self.search_query:
            matching = [
                event
                for event in events
                if _matches_query(
                    self.search_query,
                    event.get("event_type"),
                    (event.get("source") or {}).get("name"),
                    (event.get("target") or {}).get("name"),
                    event.get("trace_id"),
                )
            ]
            fingerprint = (
                "search",
                self.search_query,
                tuple(str(event.get("event_id")) for event in matching),
            )
            if self._fingerprints.get("event-log") != fingerprint:
                self._fingerprints["event-log"] = fingerprint
                log.clear()
                if matching:
                    for event in matching:
                        log.write(event_stream_line(event))
                else:
                    log.write("No events match the current search.")
                log.scroll_end(animate=False)
            for event in fresh:
                self._seen_event_ids.add(str(event.get("event_id")))
            self._trim_seen_events()
            self._update_event_title(len(matching))
            return

        if self.stream_paused:
            self._pending_stream_count = len(fresh)
            self._update_event_title(None)
            return

        if not fresh and not self._stream_has_content:
            fingerprint = ("empty",)
            if self._fingerprints.get("event-log") != fingerprint:
                self._fingerprints["event-log"] = fingerprint
                log.clear()
                log.write("No events received yet.")
                log.write("Backend connected — listening for OpenMesh events…")
            self._update_event_title(0)
            return

        if fresh:
            if not self._stream_has_content:
                log.clear()
                self._stream_has_content = True
            at_end = log.is_vertical_scroll_end
            for event in fresh:
                log.write(event_stream_line(event))
                self._seen_event_ids.add(str(event.get("event_id")))
            self._trim_seen_events()
            if at_end:
                log.scroll_end(animate=False)
            self._fingerprints["event-log"] = ("stream",)
        self._update_event_title(None)

    def _trim_seen_events(self) -> None:
        if len(self._seen_event_ids) > 5000 and self.snapshot:
            self._seen_event_ids = {
                str(event.get("event_id")) for event in self.snapshot.events
            }

    def _update_event_title(self, count: int | None) -> None:
        if self.lower_right_mode != "events":
            return
        title = "EVENT STREAM"
        if count is not None:
            title += f" ({count})"
        if self.stream_paused:
            title += f"  ⏸ paused +{self._pending_stream_count} new"
        if self.search_query:
            title += f"  match:{_short(self.search_query, 12)}"
        self.query_one("#event-title", Static).update(title)

    def _reset_stream(self) -> None:
        self._seen_event_ids.clear()
        self._stream_has_content = False
        self._pending_stream_count = 0
        self._fingerprints.pop("event-log", None)
        self.query_one("#event-log", EventLog).clear()

    # ── Detail view (lower-right modes) ───────────────────────────────────

    def _detail_content(self) -> tuple[str, list[str]] | None:
        assert self.snapshot is not None
        snapshot = self.snapshot
        mode = self.lower_right_mode
        if mode == "graph":
            return "GRAPH EXPLORER", graph_explorer_rows(
                snapshot,
                focus_node_id=self.graph_focus_node_id,
                depth=self.graph_depth,
                query=self.graph_search_query,
            )
        if mode == "integrations":
            return "INTEGRATIONS", integration_rows(snapshot)
        if mode == "discovery":
            return "DISCOVERY", discovery_rows(snapshot)
        if mode == "registry":
            return "REGISTRY", registry_rows(snapshot)
        if mode == "mcp":
            return "MCP", mcp_rows(snapshot)
        if mode == "mcp_config":
            return "MCP CONFIG", mcp_config_rows(snapshot)
        if mode == "capabilities":
            return "CAPABILITIES", capability_rows(snapshot)
        if mode == "workflows":
            return "WORKFLOWS", workflow_rows(snapshot)
        if mode == "ecosystem":
            return "ECOSYSTEM", ecosystem_rows(snapshot)
        if mode == "snapshots":
            return "SNAPSHOTS", snapshot_rows(snapshot)
        if mode == "snapshot_diff":
            return "SNAPSHOT DIFF", snapshot_diff_rows(
                snapshot, self.snapshot_diff_a_index, self.snapshot_diff_b_index
            )
        if mode == "timeline":
            return "TIMELINE", timeline_rows(snapshot)
        if mode == "replay":
            replay = build_replay_from_timeline(
                snapshot.timeline,
                control=self.replay_control,
                position=self.replay_position,
            )
            position = replay.get("state", {}).get("position")
            if isinstance(position, int) and position >= 0:
                self.replay_position = position
            return "REPLAY", replay_rows(replay)
        if mode == "query":
            return "QUERY", query_rows(snapshot, self.query_index)
        if mode == "trace" and self.selected_trace_id:
            return "TRACE DETAIL", trace_detail_rows(snapshot, self.selected_trace_id)
        if mode == "edge" and self.selected_edge_id:
            return "RELATIONSHIP DETAIL", edge_detail_rows(
                snapshot, self.selected_edge_id
            )
        if mode == "node" and self.selected_node_id:
            return "NODE DETAIL", node_detail_rows(snapshot, self.selected_node_id)
        return None

    def _refresh_detail(self) -> None:
        if self.snapshot is None:
            return
        log = self.query_one("#event-log", EventLog)
        detail = self.query_one("#detail-scroll", DetailScroll)
        content = self._detail_content()
        if content is None:
            self.lower_right_mode = "events"
            log.display = True
            detail.display = False
            self._update_event_title(None)
            return
        title, rows = content
        log.display = False
        detail.display = True
        self.query_one("#event-title", Static).update(f"{title}  (Esc back)")
        self.query_one("#event-body", Static).update("\n".join(rows))

    # ── Selection helpers ─────────────────────────────────────────────────

    def _graph_focus_label(self) -> str:
        if not self.snapshot or not self.graph_focus_node_id:
            return "all"
        nodes, _ = _node_maps(self.snapshot)
        node = nodes.get(self.graph_focus_node_id)
        if not node:
            return self.graph_focus_node_id
        return node.get("name") or self.graph_focus_node_id

    def _selected_node_id_from_focus(self) -> str | None:
        if not self.snapshot:
            return self.selected_node_id
        focused = self.focused
        if isinstance(focused, DataTable) and focused.cursor_row >= 0:
            if focused.id == "agents-table" and focused.cursor_row < len(
                self.agent_node_rows
            ):
                return self.agent_node_rows[focused.cursor_row]["id"]
            if focused.id == "network-table" and focused.cursor_row < len(
                self.network_edge_rows
            ):
                return self.network_edge_rows[focused.cursor_row]["target"]
        return self.selected_node_id

    def _selected_graph_search_query(self) -> str | None:
        if not self.snapshot:
            return None
        nodes, _ = _node_maps(self.snapshot)
        focused = self.focused
        if isinstance(focused, DataTable) and focused.cursor_row >= 0:
            if focused.id == "agents-table" and focused.cursor_row < len(
                self.agent_node_rows
            ):
                return str(self.agent_node_rows[focused.cursor_row].get("name") or "")
            if focused.id == "network-table" and focused.cursor_row < len(
                self.network_edge_rows
            ):
                edge = self.network_edge_rows[focused.cursor_row]
                target = nodes.get(edge["target"], {})
                return str(target.get("name") or edge.get("type") or "")
            if focused.id == "traces-table" and focused.cursor_row < len(
                self.trace_display_rows
            ):
                return str(self.trace_display_rows[focused.cursor_row].get("trace_id"))
        if self.selected_node_id:
            node = nodes.get(self.selected_node_id)
            return str((node or {}).get("name") or self.selected_node_id)
        return None

    # ── Row selection (Enter / click) ─────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table_id = event.data_table.id or ""
        key = event.row_key.value
        payload = (
            self._row_payloads.get(table_id, {}).get(str(key))
            if key is not None
            else None
        )
        if payload is None:
            return
        if table_id == "traces-table":
            self.selected_trace_id = payload["trace_id"]
            self.action_show_detail("trace")
        elif table_id == "network-table":
            self.selected_edge_id = payload["id"]
            self.action_show_detail("edge")
        elif table_id == "agents-table":
            self.selected_node_id = payload["id"]
            self.graph_focus_node_id = payload["id"]
            self.graph_search_query = None
            self._refresh_network()
            self.action_show_detail("node")

    def action_inspect_selected(self) -> None:
        focused = self.focused
        if isinstance(focused, DataTable):
            return  # DataTable's own Enter emits RowSelected, handled above
        self.notify("Select a row in a table (1/2/3), then press Enter.", timeout=3)

    # ── Panel focus & detail actions ──────────────────────────────────────

    def action_focus_panel(self, panel: str) -> None:
        if panel == "events":
            self.lower_right_mode = "events"
            self._refresh_detail()
            if self.snapshot:
                self._refresh_event_stream()
            self.query_one("#event-log", EventLog).focus()
            return
        if panel == "network":
            self.lower_right_mode = "graph"
            self._refresh_detail()
            self.query_one("#network-table", DataTable).focus()
            return
        target = {"agents": "#agents-table", "traces": "#traces-table"}[panel]
        self.query_one(target, DataTable).focus()

    def action_show_detail(self, mode: str) -> None:
        self.lower_right_mode = mode
        self._refresh_detail()
        self.query_one("#detail-scroll", DetailScroll).focus()

    def action_show_replay(self) -> None:
        self.replay_control = "start"
        self.action_show_detail("replay")

    def action_toggle_replay(self) -> None:
        if self.lower_right_mode != "replay":
            return
        self.replay_control = "pause" if self.replay_control == "start" else "start"
        self._refresh_detail()

    def action_step_replay(self) -> None:
        if self.lower_right_mode != "replay":
            return
        self.replay_control = "step"
        self._refresh_detail()

    def action_previous_replay(self) -> None:
        if self.lower_right_mode != "replay":
            return
        self.replay_control = "previous"
        self._refresh_detail()

    def action_stop_replay(self) -> None:
        if self.lower_right_mode != "replay":
            return
        self.replay_control = "stop"
        self.replay_position = 0
        self._refresh_detail()

    def action_next_query(self) -> None:
        if self.lower_right_mode != "query":
            return
        self.query_index = (self.query_index + 1) % max(len(SAVED_QUERIES), 1)
        self._refresh_detail()

    # ── Graph actions ─────────────────────────────────────────────────────

    def action_cycle_graph_filter(self) -> None:
        self.network_filter_index = (self.network_filter_index + 1) % len(GRAPH_FILTERS)
        self.lower_right_mode = "graph"
        self._refresh_network()
        self._refresh_detail()
        self._refresh_topbar()
        self.query_one("#network-table", DataTable).focus()

    def action_focus_graph_node(self) -> None:
        node_id = self._selected_node_id_from_focus()
        if not node_id:
            self.notify("Select an agent/process row first.", timeout=3)
            return
        self.graph_focus_node_id = node_id
        self.selected_node_id = node_id
        self.graph_search_query = None
        self.lower_right_mode = "node"
        self._refresh_network()
        self._refresh_detail()
        self.query_one("#network-table", DataTable).focus()

    def action_expand_graph(self) -> None:
        if not self.graph_focus_node_id:
            self.graph_focus_node_id = self._selected_node_id_from_focus()
        if not self.graph_focus_node_id:
            self.notify("Select or focus a graph node before expanding.", timeout=3)
            return
        self.graph_depth = min(self.graph_depth + 1, 4)
        self.lower_right_mode = "graph"
        self._refresh_network()
        self._refresh_detail()
        self.query_one("#network-table", DataTable).focus()

    def action_collapse_graph(self) -> None:
        self.graph_depth = max(self.graph_depth - 1, 1)
        self.lower_right_mode = "graph"
        self._refresh_network()
        self._refresh_detail()
        self.query_one("#network-table", DataTable).focus()

    def action_clear_graph_focus(self) -> None:
        self.graph_focus_node_id = None
        self.graph_search_query = None
        self.graph_depth = 1
        self.lower_right_mode = "graph"
        self._refresh_network()
        self._refresh_detail()
        self.query_one("#network-table", DataTable).focus()

    def action_search_graph_selection(self) -> None:
        query = self._selected_graph_search_query()
        if not query:
            self.notify("Select a node or relationship to search from.", timeout=3)
            return
        self.graph_focus_node_id = None
        self.graph_search_query = query
        self.lower_right_mode = "graph"
        self._refresh_network()
        self._refresh_detail()
        self.query_one("#network-table", DataTable).focus()

    def action_select_snapshot_a(self) -> None:
        if self.snapshot and len(self.snapshot.snapshots) > 1:
            visible = len(self.snapshot.snapshots[:5])
            self.snapshot_diff_a_index = (self.snapshot_diff_a_index + 1) % visible
            if self.snapshot_diff_a_index == self.snapshot_diff_b_index:
                self.snapshot_diff_a_index = (self.snapshot_diff_a_index + 1) % visible
        self.action_show_detail("snapshot_diff")

    def action_select_snapshot_b(self) -> None:
        if self.snapshot and len(self.snapshot.snapshots) > 1:
            visible = len(self.snapshot.snapshots[:5])
            self.snapshot_diff_b_index = (self.snapshot_diff_b_index + 1) % visible
            if self.snapshot_diff_b_index == self.snapshot_diff_a_index:
                self.snapshot_diff_b_index = (self.snapshot_diff_b_index + 1) % visible
        self.action_show_detail("snapshot_diff")

    # ── Search ────────────────────────────────────────────────────────────

    def action_open_search(self) -> None:
        search = self.query_one("#search-input", Input)
        search.display = True
        search.focus()

    def _apply_search(self, query: str) -> None:
        query = query.strip()
        if query == self.search_query:
            return
        self.search_query = query
        self._reset_stream()
        for table_id in TABLE_SORT_COLUMNS:
            self._fingerprints.pop(table_id, None)
        if self.snapshot:
            self._refresh_all()

    def _close_search(self, *, clear: bool) -> None:
        search = self.query_one("#search-input", Input)
        if clear and (search.value or self.search_query):
            search.value = ""
            self._apply_search("")
        refocus = search.has_focus
        search.display = False
        if refocus:
            self.query_one("#agents-table", DataTable).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._apply_search(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._apply_search(event.value)
            self.query_one("#search-input", Input).display = False
            self.query_one("#agents-table", DataTable).focus()

    # ── Event stream controls ─────────────────────────────────────────────

    def action_toggle_stream_pause(self) -> None:
        self.stream_paused = not self.stream_paused
        if not self.stream_paused:
            self._pending_stream_count = 0
        if self.snapshot:
            self._refresh_event_stream()
            self._refresh_topbar()

    def action_clear_stream(self) -> None:
        self.query_one("#event-log", EventLog).clear()
        self._stream_has_content = True  # keep the placeholder from reappearing
        if self.snapshot:
            for event in self.snapshot.events:
                self._seen_event_ids.add(str(event.get("event_id")))
        self._pending_stream_count = 0
        self.notify("Event stream cleared.", timeout=2)

    # ── Help / export / navigation ────────────────────────────────────────

    def action_show_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            return
        self.push_screen(HelpScreen())

    def action_export_data(self) -> None:
        if not self.snapshot:
            self.notify("No data loaded yet.", timeout=3)
            return
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        directory = Path.cwd() / f"openmesh-export-{stamp}"
        try:
            written = export_snapshot_files(self.snapshot, directory)
        except OSError as error:
            self.notify(f"Export failed: {error}", severity="error", timeout=5)
            return
        self.notify(f"Exported {len(written)} files to {directory.name}/", timeout=5)

    def action_cycle_sort(self) -> None:
        table_id = getattr(self.focused, "id", None)
        if table_id not in TABLE_SORT_COLUMNS:
            self.notify("Focus a table (1/2/3) to sort it.", timeout=3)
            return
        options = TABLE_SORT_COLUMNS[table_id]
        current = self._sort_index.get(table_id)
        if current is None:
            self._sort_index[table_id] = 0
        elif current + 1 >= len(options):
            self._sort_index[table_id] = None
        else:
            self._sort_index[table_id] = current + 1
        self._fingerprints.pop(table_id, None)
        self._refresh_tables()

    def action_back(self) -> None:
        if isinstance(self.screen, HelpScreen):
            self.pop_screen()
            return
        search = self.query_one("#search-input", Input)
        if search.has_focus or search.display:
            self._close_search(clear=True)
            return
        if self.lower_right_mode != "events":
            self.lower_right_mode = "events"
            self._refresh_detail()
            if self.snapshot:
                self._refresh_event_stream()




async def run_tui(*, once: bool = False) -> int:
    if once:
        snapshot = await load_snapshot()
        print(render_plain(snapshot))
        return 0
    app = OpenMeshTui()
    await app.run_async()
    return 0
