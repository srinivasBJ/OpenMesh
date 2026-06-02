from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static

from ..db.session import AsyncSessionLocal
from ..services.discovery import get_discovery
from ..services.openmesh_queries import get_events, get_graph, get_health, get_sessions, get_traces
from ..services.trace_semantics import build_event_hierarchy, build_span_summary, graph_edges_for_trace
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
    loaded_at: datetime


async def load_snapshot() -> TuiSnapshot:
    async with AsyncSessionLocal() as db:
        return TuiSnapshot(
            health=await get_health(db),
            graph=await get_graph(db, limit=1000),
            traces=await get_traces(db, limit=1000),
            events=await get_events(db, limit=100),
            sessions=await get_sessions(db, limit=1000),
            integrations=list_integrations(),
            discovery=await get_discovery(db, limit=5000),
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


def _node_maps(snapshot: TuiSnapshot) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
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
            if session["session_id"] == session_id or session["command"] == node["name"]:
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

    hero_types = {"agent", "process", "service"}
    visible = [node for node in nodes.values() if node["type"] in hero_types]
    visible.sort(key=lambda node: (node["type"] != "agent", node["type"], node["name"]))

    lines: list[str] = []
    for node in visible:
        lines.append(node["name"])
        edges = sorted(outgoing.get(node["id"], []), key=lambda edge: (edge["type"], edge["target"]))
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
    lines.append("├─ Traces ─────────────────────────┼─ Event Stream / Registry ───────┤")
    traces = trace_rows(snapshot, limit=8)
    events = event_rows(snapshot, limit=4) + ["", "Discovery"] + discovery_rows(snapshot)
    for index in range(max(len(traces), len(events), 1)):
        left = traces[index] if index < len(traces) else ""
        right = events[index] if index < len(events) else ""
        lines.append(f"│ {_short(left, 34):<34} │ {_short(right, 34):<34} │")
    lines.append("└──────────────────────────────────┴──────────────────────────────────┘")
    return "\n".join(lines)


def agent_process_rows(snapshot: TuiSnapshot) -> list[str]:
    nodes, _ = _node_maps(snapshot)
    trace_counts = _trace_counts_by_node(snapshot)
    visible = [node for node in nodes.values() if node["type"] in {"agent", "process", "service"}]
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
        symbol = "✓" if integration.get("available") or integration.get("active") else "○"
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
        rows.append(f"  {_short(span['span_id'], 18)} e:{span['event_count']}")
    rows.append("")
    rows.append("Relationships")
    relationships = graph_edges_for_trace(events)
    if not relationships:
        rows.append("  none")
    for edge in relationships[:8]:
        rows.append(f"  {_short(edge['source'], 10)} {edge['type']} {_short(edge['target'], 10)}")
    return rows


def _compact_hierarchy(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    rows: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        rows.append(f"{prefix}{branch} {_short(node['event_type'], 22)}")
        rows.extend(_compact_hierarchy(node.get("children", []), prefix + ("   " if index == len(nodes) - 1 else "│  ")))
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

    #network-body, #event-body {
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
        ("enter", "inspect_selected", "Inspect"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.snapshot: TuiSnapshot | None = None
        self.selected_detail = "Enter inspects the focused row. Network stays visible."
        self.lower_right_mode = "events"
        self.selected_trace_id: str | None = None

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
                    yield Static("", id="network-body")
                with Panel("", id="events-panel", classes="panel"):
                    yield Static("EVENT STREAM", id="event-title", classes="panel-title")
                    yield Static("", id="event-body")
        yield Footer()

    async def on_mount(self) -> None:
        agents = self.query_one("#agents-table", DataTable)
        agents.add_columns("name", "type", "status", "events", "last")
        agents.cursor_type = "row"
        traces = self.query_one("#traces-table", DataTable)
        traces.add_columns("trace", "status", "events", "start")
        traces.cursor_type = "row"
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
            "[1 overview] [2 traces] [3 graph] [4 events] [5 integrations] [6 discovery] [q quit][/]"
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
        visible = [node for node in nodes.values() if node["type"] in {"agent", "process", "service"}]
        visible.sort(key=lambda node: (node["type"], node["name"]))
        for node in visible:
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
        self.query_one("#network-body", Static).update("\n".join(network_lines(self.snapshot, limit=60)))

    def _refresh_events(self) -> None:
        assert self.snapshot is not None
        if self.lower_right_mode == "integrations":
            self.query_one("#event-title", Static).update("INTEGRATIONS")
            self.query_one("#event-body", Static).update("\n".join(integration_rows(self.snapshot)))
            return
        if self.lower_right_mode == "discovery":
            self.query_one("#event-title", Static).update("DISCOVERY")
            self.query_one("#event-body", Static).update("\n".join(discovery_rows(self.snapshot)))
            return
        if self.lower_right_mode == "trace" and self.selected_trace_id:
            self.query_one("#event-title", Static).update("TRACE DETAIL")
            self.query_one("#event-body", Static).update("\n".join(trace_detail_rows(self.snapshot, self.selected_trace_id)))
            return
        self.query_one("#event-title", Static).update("EVENT STREAM")
        self.query_one("#event-body", Static).update("\n".join(event_rows(self.snapshot, limit=50)))

    def action_focus_panel(self, panel: str) -> None:
        target = {
            "agents": "#agents-table",
            "traces": "#traces-table",
            "network": "#network-body",
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

    def action_inspect_selected(self) -> None:
        focused = self.focused
        if isinstance(focused, DataTable) and focused.cursor_row >= 0:
            if focused.id == "traces-table" and self.snapshot and focused.cursor_row < len(self.snapshot.traces):
                self.selected_trace_id = self.snapshot.traces[focused.cursor_row]["trace_id"]
                self.lower_right_mode = "trace"
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
