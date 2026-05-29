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
from ..services.openmesh_queries import get_events, get_graph, get_health, get_sessions, get_traces


@dataclass
class TuiSnapshot:
    health: dict[str, Any]
    graph: dict[str, list[dict[str, Any]]]
    traces: list[dict[str, Any]]
    events: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    loaded_at: datetime


async def load_snapshot() -> TuiSnapshot:
    async with AsyncSessionLocal() as db:
        return TuiSnapshot(
            health=await get_health(db),
            graph=await get_graph(db, limit=1000),
            traces=await get_traces(db, limit=1000),
            events=await get_events(db, limit=100),
            sessions=await get_sessions(db, limit=1000),
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
        "OPENMESH",
        f"Events {health['events']}  Traces {health['traces']}  Nodes {health['nodes']}  "
        f"Edges {health['edges']}  Sessions {len(snapshot.sessions)}",
        "",
        "┌─ Agents / Processes ─────────────┬─ Network ───────────────────────┐",
    ]
    nodes = agent_process_rows(snapshot)
    network = network_lines(snapshot, limit=10)
    for index in range(max(len(nodes), len(network), 1)):
        left = nodes[index] if index < len(nodes) else ""
        right = network[index] if index < len(network) else ""
        lines.append(f"│ {_short(left, 34):<34} │ {_short(right, 34):<34} │")
    lines.append("├─ Traces ─────────────────────────┼─ Event Stream ──────────────────┤")
    traces = trace_rows(snapshot, limit=8)
    events = event_rows(snapshot, limit=8)
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
            f"{_node_status(node, snapshot.sessions):<9} "
            f"e:{node.get('event_count', 0):<3} "
            f"t:{trace_counts.get(node['id'], 0):<2} "
            f"{_time(node.get('last_seen'))}"
        )
    return rows


def trace_rows(snapshot: TuiSnapshot, limit: int = 50) -> list[str]:
    if not snapshot.traces:
        return ["No traces yet"]
    return [
        f"{_short(trace['trace_id'], 15):<15} {trace['status']:<9} "
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


class Panel(Static):
    pass


class OpenMeshTui(App):
    CSS = """
    Screen {
        background: #090807;
        color: #c9b8a0;
    }

    #topbar {
        height: 3;
        background: #15110d;
        color: #c96f2d;
        text-style: bold;
        padding: 0 1;
        border-bottom: solid #5b321d;
    }

    #grid {
        height: 1fr;
    }

    .column {
        width: 1fr;
    }

    .panel {
        height: 1fr;
        border: solid #4a3428;
        background: #100d0a;
        padding: 0 1;
    }

    .panel:focus {
        border: solid #c96f2d;
    }

    #network-panel {
        border: solid #9b5127;
    }

    DataTable {
        background: #100d0a;
        color: #c9b8a0;
        height: 1fr;
    }

    DataTable > .datatable--header {
        color: #d7823a;
        text-style: bold;
    }

    DataTable > .datatable--cursor {
        background: #5b321d;
        color: #f2d2aa;
    }

    #network-body, #event-body {
        height: 1fr;
        color: #c9b8a0;
    }

    Footer {
        background: #15110d;
        color: #9d8d78;
    }
    """

    BINDINGS = [
        ("1", "focus_panel('agents')", "Overview"),
        ("2", "focus_panel('traces')", "Traces"),
        ("3", "focus_panel('network')", "Graph"),
        ("4", "focus_panel('events')", "Events"),
        ("enter", "inspect_selected", "Inspect"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.snapshot: TuiSnapshot | None = None
        self.selected_detail = "Enter inspects the focused row. Network stays visible."

    def compose(self) -> ComposeResult:
        yield Static("OPENMESH  ::  terminal network operations  ::  loading", id="topbar")
        with Horizontal(id="grid"):
            with Vertical(classes="column"):
                with Panel("Agents / Processes", id="agents-panel", classes="panel"):
                    yield DataTable(id="agents-table")
                with Panel("Traces", id="traces-panel", classes="panel"):
                    yield DataTable(id="traces-table")
            with Vertical(classes="column"):
                with Panel("Network", id="network-panel", classes="panel"):
                    yield Static("", id="network-body")
                with Panel("Event Stream", id="events-panel", classes="panel"):
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
            f"OPENMESH  events:{health['events']} traces:{health['traces']} "
            f"nodes:{health['nodes']} edges:{health['edges']} sessions:{len(self.snapshot.sessions)}  "
            "[1 overview] [2 traces] [3 graph] [4 events] [q quit]"
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
                _node_status(node, self.snapshot.sessions),
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
                trace["status"],
                str(trace["event_count"]),
                _time(trace["started_at"]),
                key=trace["trace_id"],
            )

    def _refresh_network(self) -> None:
        assert self.snapshot is not None
        self.query_one("#network-body", Static).update("\n".join(network_lines(self.snapshot, limit=60)))

    def _refresh_events(self) -> None:
        assert self.snapshot is not None
        self.query_one("#event-body", Static).update("\n".join(event_rows(self.snapshot, limit=50)))

    def action_focus_panel(self, panel: str) -> None:
        target = {
            "agents": "#agents-table",
            "traces": "#traces-table",
            "network": "#network-body",
            "events": "#event-body",
        }[panel]
        self.query_one(target, Widget).focus()

    def action_inspect_selected(self) -> None:
        focused = self.focused
        if isinstance(focused, DataTable) and focused.cursor_row >= 0:
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
