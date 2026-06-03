from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static

from ..db.openmesh_events import list_openmesh_events
from ..db.session import AsyncSessionLocal
from ..services.discovery import get_discovery
from ..services.ecosystem_registry import get_ecosystem_registry
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
)
from ..services.registry_status import build_registry_status
from ..services.trace_semantics import (
    build_event_hierarchy,
    build_span_summary,
    build_span_tree,
    graph_edges_for_trace,
)
from ..services.workflow_registry import get_workflow_registry
from ..sdk.integrations import list_integrations


OPENMESH_LOGO = r"""
   ____                  __  ___          __
  / __ \____  ___  ____ /  |/  /__  _____/ /_
 / / / / __ \/ _ \/ __ `/ /|_/ / _ \/ ___/ __ \
/ /_/ / /_/ /  __/ /_/ / /  / /  __(__  ) / / /
\____/ .___/\___/\__,_/_/  /_/\___/____/_/ /_/
    /_/
"""


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
    ecosystem: dict[str, Any]
    registry_status: dict[str, Any]
    loaded_at: datetime


async def load_snapshot() -> TuiSnapshot:
    async with AsyncSessionLocal() as db:
        registry_records = await list_openmesh_events(db, limit=5000)
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
            workflows=await get_workflow_registry(db, limit=5000),
            ecosystem=await get_ecosystem_registry(db, limit=5000),
            registry_status=build_registry_status(registry_records),
            loaded_at=datetime.utcnow(),
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


def network_edges(snapshot: TuiSnapshot) -> list[dict[str, Any]]:
    nodes, _ = _node_maps(snapshot)
    return sorted(
        snapshot.graph["edges"],
        key=lambda edge: (
            nodes.get(edge["source"], {}).get("name", edge["source"]),
            edge["type"],
            nodes.get(edge["target"], {}).get("name", edge["target"]),
        ),
    )


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
    rows = ["Workflows"]
    for workflow in snapshot.workflows[:12]:
        rows.append(
            f"  {_short(workflow.get('workflow'), 18):<18} "
            f"{_short(workflow.get('framework') or '-', 10):<10}"
        )
        rows.append(f"    source {_short(workflow.get('source') or '-', 24)}")
        rows.append(f"    last {_time(workflow.get('last_seen'))}")
    return rows


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


class Panel(Static):
    pass


class OpenMeshTui(App):
    CSS = """
    Screen {
        background: #070605;
        color: #b8afa2;
    }

    #topbar {
        height: 8;
        background: #11100e;
        color: #c56b2c;
        text-style: bold;
        padding: 0 2;
        border-bottom: heavy #7a3f20;
    }

    #logo-line {
        color: #c56b2c;
    }

    #status-line {
        color: #8f9aa0;
        text-style: none;
    }

    #grid {
        height: 1fr;
        padding: 1 1 0 1;
    }

    .column {
        width: 1fr;
    }

    .panel {
        height: 1fr;
        border: solid #3b3731;
        background: #0d0c0a;
        padding: 0 1 1 1;
    }

    .panel:focus {
        border: heavy #c56b2c;
    }

    #network-panel {
        border: heavy #9b5127;
        background: #100c09;
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

    #network-table, #event-body {
        height: 1fr;
        color: #b8afa2;
        padding-top: 1;
    }

    Footer {
        background: #11100e;
        color: #8f9aa0;
        border-top: solid #3b3731;
    }
    """

    BINDINGS = [
        ("1", "focus_panel('agents')", "Overview"),
        ("2", "focus_panel('traces')", "Traces"),
        ("3", "focus_panel('network')", "Graph"),
        ("4", "focus_panel('events')", "Events"),
        ("5", "show_integrations", "Integrations"),
        ("6", "show_discovery", "Discovery"),
        ("7", "show_registry", "Registry"),
        ("8", "show_mcp", "MCP"),
        ("9", "show_mcp_config", "MCP Config"),
        ("0", "show_capabilities", "Capabilities"),
        ("w", "show_workflows", "Workflows"),
        ("e", "show_ecosystem", "Ecosystem"),
        ("enter", "inspect_selected", "Inspect"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.snapshot: TuiSnapshot | None = None
        self.selected_detail = "Enter inspects the focused row. Network stays visible."
        self.lower_right_mode = "events"
        self.selected_trace_id: str | None = None
        self.selected_edge_id: str | None = None
        self.selected_node_id: str | None = None
        self.agent_node_rows: list[dict[str, Any]] = []
        self.network_edge_rows: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("", id="topbar")
        with Horizontal(id="grid"):
            with Vertical(classes="column"):
                with Panel("", id="agents-panel", classes="panel"):
                    yield Static("AGENTS / PROCESSES", classes="panel-title")
                    yield DataTable(id="agents-table")
                with Panel("", id="traces-panel", classes="panel"):
                    yield Static("TRACES", classes="panel-title")
                    yield DataTable(id="traces-table")
            with Vertical(classes="column"):
                with Panel("", id="network-panel", classes="panel"):
                    yield Static("NETWORK", classes="panel-title")
                    yield DataTable(id="network-table")
                with Panel("", id="events-panel", classes="panel"):
                    yield Static(
                        "EVENT STREAM", id="event-title", classes="panel-title"
                    )
                    yield Static("", id="event-body")
        yield Footer()

    async def on_mount(self) -> None:
        agents = self.query_one("#agents-table", DataTable)
        agents.add_columns("name", "type", "status", "events", "last")
        agents.cursor_type = "row"
        traces = self.query_one("#traces-table", DataTable)
        traces.add_columns("trace", "status", "events", "start")
        traces.cursor_type = "row"
        network = self.query_one("#network-table", DataTable)
        network.add_columns("source", "relationship", "target", "state", "obs")
        network.cursor_type = "row"
        self.query_one("#agents-table", DataTable).focus()
        await self.refresh_data()
        self.set_interval(2.0, self.refresh_data)

    async def refresh_data(self) -> None:
        self.snapshot = await load_snapshot()
        health = self.snapshot.health
        self.query_one("#topbar", Static).update(
            f"[#c56b2c]{OPENMESH_LOGO.strip()}[/]\n"
            f"[#8f9aa0]CONTROL ROOM  events:{health['events']} traces:{health['traces']} "
            f"nodes:{health['nodes']} edges:{health['edges']} sessions:{len(self.snapshot.sessions)}  "
            "observability for agent frameworks  "
            "[1 overview] [2 traces] [3 graph] [4 events] [5 integrations] [6 discovery] [7 registry] [8 mcp] [9 mcp config] [0 capabilities] [w workflows] [e ecosystem] [q quit][/]"
        )
        self._refresh_agents()
        self._refresh_traces()
        self._refresh_network()
        self._refresh_events()

    def _refresh_agents(self) -> None:
        assert self.snapshot is not None
        table = self.query_one("#agents-table", DataTable)
        table.clear()
        nodes, _ = _node_maps(self.snapshot)
        trace_counts = _trace_counts_by_node(self.snapshot)
        self.agent_node_rows = [
            node
            for node in nodes.values()
            if node["type"] in {"agent", "process", "service"}
        ]
        self.agent_node_rows.sort(key=lambda node: (node["type"], node["name"]))
        for node in self.agent_node_rows:
            table.add_row(
                _short(node["name"], 28),
                node["type"],
                _status_label(_node_status(node, self.snapshot.sessions)),
                str(node.get("event_count", 0)),
                f"{_time(node.get('last_seen'))} / t:{trace_counts.get(node['id'], 0)}",
                key=node["id"],
            )

    def _refresh_traces(self) -> None:
        assert self.snapshot is not None
        table = self.query_one("#traces-table", DataTable)
        table.clear()
        for trace in self.snapshot.traces:
            table.add_row(
                _short(trace["trace_id"], 24),
                _status_label(trace["status"]),
                str(trace["event_count"]),
                _time(trace["started_at"]),
                key=trace["trace_id"],
            )

    def _refresh_network(self) -> None:
        assert self.snapshot is not None
        table = self.query_one("#network-table", DataTable)
        table.clear()
        nodes, _ = _node_maps(self.snapshot)
        self.network_edge_rows = network_edges(self.snapshot)
        for edge in self.network_edge_rows:
            source = nodes.get(edge["source"], {"name": edge["source"]})
            target = nodes.get(edge["target"], {"name": edge["target"]})
            table.add_row(
                _short(source["name"], 20),
                edge["type"],
                _short(target["name"], 20),
                edge.get("lifecycle_state", "unknown"),
                str(edge.get("observation_count", edge.get("event_count", 0))),
                key=edge["id"],
            )

    def _refresh_events(self) -> None:
        assert self.snapshot is not None
        if self.lower_right_mode == "integrations":
            self.query_one("#event-title", Static).update("INTEGRATIONS")
            self.query_one("#event-body", Static).update(
                "\n".join(integration_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "discovery":
            self.query_one("#event-title", Static).update("DISCOVERY")
            self.query_one("#event-body", Static).update(
                "\n".join(discovery_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "registry":
            self.query_one("#event-title", Static).update("REGISTRY")
            self.query_one("#event-body", Static).update(
                "\n".join(registry_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "mcp":
            self.query_one("#event-title", Static).update("MCP")
            self.query_one("#event-body", Static).update(
                "\n".join(mcp_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "mcp_config":
            self.query_one("#event-title", Static).update("MCP CONFIG")
            self.query_one("#event-body", Static).update(
                "\n".join(mcp_config_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "capabilities":
            self.query_one("#event-title", Static).update("CAPABILITIES")
            self.query_one("#event-body", Static).update(
                "\n".join(capability_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "workflows":
            self.query_one("#event-title", Static).update("WORKFLOWS")
            self.query_one("#event-body", Static).update(
                "\n".join(workflow_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "ecosystem":
            self.query_one("#event-title", Static).update("ECOSYSTEM")
            self.query_one("#event-body", Static).update(
                "\n".join(ecosystem_rows(self.snapshot))
            )
            return
        if self.lower_right_mode == "trace" and self.selected_trace_id:
            self.query_one("#event-title", Static).update("TRACE DETAIL")
            self.query_one("#event-body", Static).update(
                "\n".join(trace_detail_rows(self.snapshot, self.selected_trace_id))
            )
            return
        if self.lower_right_mode == "edge" and self.selected_edge_id:
            self.query_one("#event-title", Static).update("RELATIONSHIP DETAIL")
            self.query_one("#event-body", Static).update(
                "\n".join(edge_detail_rows(self.snapshot, self.selected_edge_id))
            )
            return
        if self.lower_right_mode == "node" and self.selected_node_id:
            self.query_one("#event-title", Static).update("NODE DETAIL")
            self.query_one("#event-body", Static).update(
                "\n".join(node_detail_rows(self.snapshot, self.selected_node_id))
            )
            return
        self.query_one("#event-title", Static).update("EVENT STREAM")
        self.query_one("#event-body", Static).update(
            "\n".join(event_rows(self.snapshot, limit=50))
        )

    def action_focus_panel(self, panel: str) -> None:
        target = {
            "agents": "#agents-table",
            "traces": "#traces-table",
            "network": "#network-table",
            "events": "#event-body",
        }[panel]
        if panel == "events":
            self.lower_right_mode = "events"
            self._refresh_events()
        self.query_one(target, Widget).focus()

    def action_show_integrations(self) -> None:
        self.lower_right_mode = "integrations"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_discovery(self) -> None:
        self.lower_right_mode = "discovery"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_registry(self) -> None:
        self.lower_right_mode = "registry"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_mcp(self) -> None:
        self.lower_right_mode = "mcp"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_mcp_config(self) -> None:
        self.lower_right_mode = "mcp_config"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_capabilities(self) -> None:
        self.lower_right_mode = "capabilities"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_workflows(self) -> None:
        self.lower_right_mode = "workflows"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_show_ecosystem(self) -> None:
        self.lower_right_mode = "ecosystem"
        self._refresh_events()
        self.query_one("#event-body", Widget).focus()

    def action_inspect_selected(self) -> None:
        focused = self.focused
        if isinstance(focused, DataTable) and focused.cursor_row >= 0:
            if (
                focused.id == "traces-table"
                and self.snapshot
                and focused.cursor_row < len(self.snapshot.traces)
            ):
                self.selected_trace_id = self.snapshot.traces[focused.cursor_row][
                    "trace_id"
                ]
                self.lower_right_mode = "trace"
                self._refresh_events()
                self.query_one("#event-body", Widget).focus()
                return
            if focused.id == "network-table" and focused.cursor_row < len(
                self.network_edge_rows
            ):
                self.selected_edge_id = self.network_edge_rows[focused.cursor_row]["id"]
                self.lower_right_mode = "edge"
                self._refresh_events()
                self.query_one("#event-body", Widget).focus()
                return
            if focused.id == "agents-table" and focused.cursor_row < len(
                self.agent_node_rows
            ):
                self.selected_node_id = self.agent_node_rows[focused.cursor_row]["id"]
                self.lower_right_mode = "node"
                self._refresh_events()
                self.query_one("#event-body", Widget).focus()
                return
            row = focused.get_row_at(focused.cursor_row)
            self.notify(" | ".join(str(cell) for cell in row), timeout=4)
        else:
            self.notify(self.selected_detail, timeout=4)


async def run_tui(*, once: bool = False) -> int:
    if once:
        snapshot = await load_snapshot()
        print(render_plain(snapshot))
        return 0
    app = OpenMeshTui()
    await app.run_async()
    return 0
