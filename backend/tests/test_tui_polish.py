# ruff: noqa: E402
"""Regression tests for the OpenMesh Control Room TUI:
scrolling, focus management, search, help overlay, event stream
behavior, table refresh stability, empty states, and export."""

import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from textual.widgets import DataTable, Input

from src.cli.tui import (
    HelpScreen,
    OpenMeshTui,
    TuiSnapshot,
    event_stream_line,
    export_snapshot_files,
)


def _node(node_id: str, name: str, node_type: str = "agent") -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "name": name,
        "event_count": 2,
        "last_seen": "2026-07-17T10:00:00Z",
        "metadata": {},
        "lifecycle_state": "active",
        "validation_status": "valid",
    }


def _event(event_id: str, event_type: str, source_id: str, source_name: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": "2026-07-17T10:00:00Z",
        "trace_id": "tr-1",
        "session_id": "s-1",
        "source": {"node_id": source_id, "node_type": "agent", "name": source_name},
        "payload": {},
        "severity": "info",
    }


def make_snapshot(*, empty: bool = False) -> TuiSnapshot:
    if empty:
        graph = {"nodes": [], "edges": []}
        traces: list[dict] = []
        events: list[dict] = []
    else:
        graph = {
            "nodes": [
                _node("agent-a", "Alpha"),
                _node("agent-b", "Beta"),
                _node("agent-c", "Gamma"),
                _node("tool-1", "Hammer", "tool"),
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "agent-a",
                    "target": "tool-1",
                    "type": "uses",
                    "lifecycle_state": "active",
                    "observation_count": 3,
                }
            ],
        }
        traces = [
            {
                "trace_id": "tr-1",
                "status": "completed",
                "event_count": 2,
                "started_at": "2026-07-17T10:00:00Z",
                "ended_at": "2026-07-17T10:00:05Z",
            }
        ]
        events = [
            _event("ev-2", "agent.task.completed", "agent-b", "Beta"),
            _event("ev-1", "agent.started", "agent-a", "Alpha"),
        ]
    return TuiSnapshot(
        health={
            "events": len(events),
            "traces": len(traces),
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
        },
        graph=graph,
        traces=traces,
        events=events,
        sessions=[],
        integrations=[],
        discovery={},
        mcp_servers=[],
        mcp_configs=[],
        capabilities=[],
        workflows=[],
        snapshots=[],
        ecosystem={"summary": {}, "entities": {}},
        registry_status={
            "versions": {},
            "compatibility": {"severity": "ok", "errors": [], "warnings": []},
            "node_definitions": [],
            "relationship_definitions": [],
        },
        loaded_at=datetime(2026, 7, 17, 10, 0, 0),
        snapshot_details={},
        timeline={},
    )


def patched_load(snapshot: TuiSnapshot):
    async def _load() -> TuiSnapshot:
        return snapshot

    return patch("src.cli.tui.load_snapshot", _load)


class TuiPolishTests(unittest.IsolatedAsyncioTestCase):
    async def test_tables_populate(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                agents = app.query_one("#agents-table", DataTable)
                self.assertEqual(agents.row_count, 3)  # 3 agents, tool excluded
                traces = app.query_one("#traces-table", DataTable)
                self.assertEqual(traces.row_count, 1)
                network = app.query_one("#network-table", DataTable)
                self.assertEqual(network.row_count, 1)

    async def test_empty_states_show_placeholders(self):
        with patched_load(make_snapshot(empty=True)):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                agents = app.query_one("#agents-table", DataTable)
                self.assertEqual(agents.row_count, 1)
                self.assertIn("Waiting for agents", str(agents.get_row_at(0)[0]))
                traces = app.query_one("#traces-table", DataTable)
                self.assertIn("No active traces", str(traces.get_row_at(0)[0]))
                network = app.query_one("#network-table", DataTable)
                self.assertIn("No relationships", str(network.get_row_at(0)[0]))
                self.assertEqual(app.agent_node_rows, [])

    async def test_focus_cycles_with_tab_and_number_keys(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                self.assertEqual(app.focused.id, "agents-table")
                await pilot.press("2")
                self.assertEqual(app.focused.id, "traces-table")
                await pilot.press("tab")
                self.assertIsNotNone(app.focused)
                first = app.focused.id
                await pilot.press("shift+tab")
                self.assertEqual(app.focused.id, "traces-table")
                self.assertNotEqual(first, "traces-table")

    async def test_refresh_preserves_cursor_position(self):
        snapshot = make_snapshot()
        with patched_load(snapshot):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                agents = app.query_one("#agents-table", DataTable)
                await pilot.press("down")
                self.assertEqual(agents.cursor_row, 1)
                await app.refresh_data()
                await pilot.pause()
                self.assertEqual(agents.cursor_row, 1)

    async def test_search_filters_tables_live_and_escape_clears(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                await pilot.press("slash")
                self.assertIsInstance(app.focused, Input)
                await pilot.press("b", "e", "t", "a")
                await pilot.pause()
                self.assertEqual(app.search_query, "beta")
                self.assertEqual(len(app.agent_node_rows), 1)
                self.assertEqual(app.agent_node_rows[0]["name"], "Beta")
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.search_query, "")
                self.assertEqual(len(app.agent_node_rows), 3)
                self.assertFalse(app.query_one("#search-input", Input).display)

    async def test_help_overlay_opens_and_closes(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                await pilot.press("question_mark")
                self.assertIsInstance(app.screen, HelpScreen)
                await pilot.press("escape")
                self.assertNotIsInstance(app.screen, HelpScreen)

    async def test_event_stream_pause_and_resume(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                self.assertFalse(app.stream_paused)
                await pilot.press("z")
                self.assertTrue(app.stream_paused)
                await pilot.press("z")
                self.assertFalse(app.stream_paused)

    async def test_event_stream_scroll_keys_do_not_crash(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                await pilot.press("4")
                self.assertEqual(app.focused.id, "event-log")
                await pilot.press("page_up", "page_down", "home", "end", "j", "k")
                await pilot.pause()

    async def test_enter_inspects_selected_agent(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.lower_right_mode, "node")
                self.assertIsNotNone(app.selected_node_id)
                self.assertTrue(app.query_one("#detail-scroll").display)
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(app.lower_right_mode, "events")
                self.assertFalse(app.query_one("#detail-scroll").display)

    async def test_sort_cycles_on_focused_table(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                await pilot.press("v")
                self.assertEqual(app._sort_index.get("agents-table"), 0)
                names = [node["name"] for node in app.agent_node_rows]
                self.assertEqual(names, sorted(names, key=str.lower))

    async def test_resize_stacks_columns_on_narrow_terminals(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                grid = app.query_one("#grid")
                app._apply_layout(SimpleNamespace(width=80, height=24))
                self.assertEqual(str(grid.styles.layout.name), "vertical")
                app._apply_layout(SimpleNamespace(width=160, height=50))
                self.assertEqual(str(grid.styles.layout.name), "horizontal")

    async def test_detail_views_render(self):
        with patched_load(make_snapshot()):
            app = OpenMeshTui()
            async with app.run_test(size=(140, 44)) as pilot:
                await pilot.pause()
                for key in ("5", "6", "w", "e", "s", "l", "y"):
                    await pilot.press(key)
                    await pilot.pause()
                    self.assertTrue(app.query_one("#detail-scroll").display)
                await pilot.press("escape")
                self.assertEqual(app.lower_right_mode, "events")


class ExportTests(unittest.TestCase):
    def test_export_writes_json_and_csv(self):
        snapshot = make_snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            written = export_snapshot_files(snapshot, Path(tmp) / "out")
            names = sorted(path.name for path in written)
            self.assertEqual(
                names,
                [
                    "events.csv",
                    "events.json",
                    "graph.json",
                    "traces.csv",
                    "traces.json",
                ],
            )
            events = json.loads((Path(tmp) / "out" / "events.json").read_text())
            self.assertEqual(len(events), 2)
            with (Path(tmp) / "out" / "events.csv").open() as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(len(rows), 3)  # header + 2 events
            self.assertEqual(rows[0][0], "timestamp")


class EventStreamLineTests(unittest.TestCase):
    def test_line_contains_type_and_source(self):
        line = event_stream_line(_event("ev-9", "tool.invoked", "agent-a", "Alpha"))
        self.assertIn("tool.invoked", line)
        self.assertIn("Alpha", line)
        self.assertIn("info", line)

    def test_line_handles_missing_fields(self):
        line = event_stream_line({"event_type": "x"})
        self.assertIn("x", line)


if __name__ == "__main__":
    unittest.main()
