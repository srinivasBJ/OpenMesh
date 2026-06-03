# ruff: noqa: E402
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.db.openmesh_events import record_to_event
from src.sdk import OpenMeshClient
from src.sdk.integrations.autogen import OpenMeshAutoGen
from src.sdk.integrations.claude_code import OpenMeshClaudeCode
from src.sdk.integrations.opencode import OpenMeshOpenCode
from src.sdk.integrations.openhands import OpenMeshOpenHands
from src.services.discovery import build_discovery
from src.services.ecosystem_snapshot import (
    build_ecosystem_snapshot,
    compare_snapshot_payloads,
)
from src.services.graph_state import reduce_graph_state
from src.services.openmesh_queries import inspect_graph_node, trace_summary
from src.services.query_engine import run_query_on_state
from src.services.replay import build_replay_from_timeline
from src.services.timeline import build_timeline


class FakeAsyncSession:
    def __init__(self):
        self.added = []

    def add(self, record):
        self.added.append(record)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class OpenMeshIntegrationWaveTests(unittest.TestCase):
    def collect_records(self, action):
        sessions = []

        def session_factory():
            session = FakeAsyncSession()
            sessions.append(session)
            return FakeSessionContext(session)

        with patch("src.sdk.client.AsyncSessionLocal", session_factory):
            action()

        return [session.added[0] for session in sessions if session.added]

    def test_autogen_integration_emits_protocol_graph_and_trace_events(self):
        def action():
            mesh = OpenMeshAutoGen(
                client=OpenMeshClient(session_id="sess_autogen", broadcast=False),
                workflow_name="AutoGen Research Chat",
                trace_id="trace_autogen",
            )
            user = mesh.user_proxy(id="autogen-user", name="User Proxy")
            assistant = mesh.assistant(id="autogen-assistant", name="Assistant")
            reviewer = mesh.assistant(id="autogen-reviewer", name="Reviewer")
            with mesh.workflow():
                mesh.observe_message(user, assistant, content="Research OpenMesh.")
                with assistant.task("Research graph provenance") as task:
                    with task.tool("web_search"):
                        pass
                mesh.observe_message(assistant, reviewer, content={"status": "done"})
                with reviewer.task("Review summary"):
                    pass

        records = self.collect_records(action)
        events = [record_to_event(record) for record in records]
        graph = reduce_graph_state(records)
        discovery = build_discovery(records)

        self.assertIn("AutoGen", {item["name"] for item in discovery["frameworks"]})
        self.assertIn("message.sent", {event["event_type"] for event in events})
        self.assertIn("tool.call.completed", {event["event_type"] for event in events})
        self.assertEqual({event["trace_id"] for event in events}, {"trace_autogen"})
        self.assertIn("communicates_with", {edge["type"] for edge in graph["edges"]})
        self.assertIn("uses", {edge["type"] for edge in graph["edges"]})
        self.assertTrue(
            all(edge["validation_status"] == "valid" for edge in graph["edges"])
        )

    def test_coding_agent_integrations_emit_command_and_file_relationships(self):
        def action():
            openhands = OpenMeshOpenHands(
                client=OpenMeshClient(session_id="sess_openhands", broadcast=False),
                workflow_name="OpenHands Coding Session",
                trace_id="trace_openhands",
            )
            hand = openhands.coding_agent()
            with openhands.workflow():
                with hand.task("Fix tests") as task:
                    with task.tool("terminal"):
                        openhands.observe_command("pytest", agent=hand)
                openhands.observe_file("backend/src/app.py", agent=hand)

            claude = OpenMeshClaudeCode(
                client=OpenMeshClient(session_id="sess_claude", broadcast=False),
                workflow_name="Claude Code Session",
                trace_id="trace_claude",
            )
            claude.observe_hook_event(
                {
                    "prompt": "Patch graph output",
                    "tool_name": "Edit",
                    "command": "ruff check .",
                    "file_path": "backend/src/cli/openmesh.py",
                    "exit_code": 0,
                }
            )

            opencode = OpenMeshOpenCode(
                client=OpenMeshClient(session_id="sess_opencode", broadcast=False),
                workflow_name="OpenCode Session",
                trace_id="trace_opencode",
            )
            opencode.observe_event(
                {
                    "prompt": "Add benchmark tests",
                    "tool": "patch",
                    "command": "python -m unittest",
                    "path": "backend/tests/test_openmesh_core.py",
                    "exit_code": 0,
                }
            )

        records = self.collect_records(action)
        graph = reduce_graph_state(records)
        discovery = build_discovery(records)
        edge_types = {edge["type"] for edge in graph["edges"]}
        framework_names = {item["name"] for item in discovery["frameworks"]}

        self.assertIn("OpenHands", framework_names)
        self.assertIn("Claude Code", framework_names)
        self.assertIn("OpenCode", framework_names)
        self.assertIn("spawns", edge_types)
        self.assertIn("executes", edge_types)
        self.assertIn("modifies", edge_types)
        self.assertIn("uses", edge_types)
        self.assertTrue(
            all(edge["validation_status"] == "valid" for edge in graph["edges"])
        )

    def test_integration_generated_data_feeds_inspection_history_and_query_views(self):
        def action():
            mesh = OpenMeshAutoGen(
                client=OpenMeshClient(session_id="sess_wave", broadcast=False),
                workflow_name="Integration Wave Workflow",
                trace_id="trace_wave",
            )
            user = mesh.user_proxy(id="wave-user", name="Wave User")
            assistant = mesh.assistant(id="wave-agent", name="Wave Agent")
            with mesh.workflow():
                mesh.observe_message(user, assistant, content="Use search.")
                with assistant.task("Search ecosystem") as task:
                    with task.tool("search"):
                        pass

        records = self.collect_records(action)
        graph = reduce_graph_state(records)
        discovery = build_discovery(records)
        snapshot_a = build_ecosystem_snapshot(records[:-1], [])
        snapshot_b = build_ecosystem_snapshot(records, [])
        diff = compare_snapshot_payloads(snapshot_a, snapshot_b)
        timeline = build_timeline(records, [], [snapshot_a, snapshot_b])
        replay = build_replay_from_timeline(timeline)
        traces = [
            trace_summary(
                "trace_wave",
                [record for record in records if record.trace_id == "trace_wave"],
            )
        ]
        query = run_query_on_state(
            "agents using search",
            graph=graph,
            discovery=discovery,
            traces=traces,
            sessions=[],
            snapshots=[snapshot_a, snapshot_b],
            timeline=timeline,
        )

        self.assertIsNotNone(inspect_graph_node(graph, "wave-agent"))
        self.assertGreater(snapshot_b["counts"]["relationships"], 0)
        self.assertGreaterEqual(diff["summary"]["relationships_changed"], 0)
        self.assertGreater(timeline["summary"]["events"], 0)
        self.assertGreater(replay["state"]["frame_count"], 0)
        self.assertEqual(query["status"], "ok")
        self.assertGreaterEqual(query["count"], 1)


if __name__ == "__main__":
    unittest.main()
