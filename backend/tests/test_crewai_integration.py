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
from src.sdk.integrations.crewai import OpenMeshCrewAI
from src.services.discovery import build_discovery
from src.services.ecosystem_registry import build_ecosystem_registry
from src.services.graph_state import reduce_graph_state


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


class OpenMeshCrewAIIntegrationTests(unittest.TestCase):
    def collect_records(self, action):
        sessions = []

        def session_factory():
            session = FakeAsyncSession()
            sessions.append(session)
            return FakeSessionContext(session)

        with patch("src.sdk.client.AsyncSessionLocal", session_factory):
            action()

        return [session.added[0] for session in sessions if session.added]

    def test_crewai_workflow_tasks_and_tools_emit_openmesh_events(self):
        def action():
            mesh = OpenMeshCrewAI(
                client=OpenMeshClient(session_id="sess_crewai", broadcast=False),
                crew_name="CrewAI Research Crew",
                trace_id="trace_crewai",
                source="examples/crewai_basic.py",
            )
            researcher = mesh.agent(
                id="researcher", name="Research Agent", role="Researcher"
            )
            writer = mesh.agent(id="writer", name="Writing Agent", role="Writer")

            with mesh.workflow():
                with researcher.task("Research vector databases") as task:
                    with task.tool("web_search"):
                        pass
                with writer.task("Write summary"):
                    pass

        records = self.collect_records(action)
        events = [record_to_event(record) for record in records]
        event_types = [event["event_type"] for event in events]

        self.assertIn("workflow.started", event_types)
        self.assertIn("workflow.registered", event_types)
        self.assertIn("agent.registered", event_types)
        self.assertIn("task.started", event_types)
        self.assertIn("task.completed", event_types)
        self.assertIn("tool.call.started", event_types)
        self.assertIn("tool.call.completed", event_types)
        self.assertIn("node.transition", event_types)
        self.assertEqual({event["trace_id"] for event in events}, {"trace_crewai"})

        workflow_started = events[0]
        task_started = [
            event for event in events if event["event_type"] == "task.started"
        ][0]
        tool_started = [
            event for event in events if event["event_type"] == "tool.call.started"
        ][0]
        transition = [
            event for event in events if event["event_type"] == "node.transition"
        ][0]

        self.assertEqual(task_started["parent_span_id"], workflow_started["span_id"])
        self.assertEqual(tool_started["parent_span_id"], task_started["span_id"])
        self.assertEqual(transition["links"][0]["relationship"], "follows_from")

    def test_crewai_activity_populates_graph_discovery_and_ecosystem(self):
        def action():
            mesh = OpenMeshCrewAI(
                client=OpenMeshClient(session_id="sess_crewai", broadcast=False),
                crew_name="CrewAI Research Crew",
                trace_id="trace_crewai",
                source="examples/crewai_basic.py",
            )
            researcher = mesh.agent(
                id="researcher", name="Research Agent", role="Researcher"
            )

            with mesh.workflow():
                with researcher.task("Research vector databases") as task:
                    with task.tool("web_search"):
                        pass

        records = self.collect_records(action)
        graph = reduce_graph_state(records)
        discovery = build_discovery(records)
        ecosystem = build_ecosystem_registry(records)

        edge_types = {edge["type"] for edge in graph["edges"]}
        node_types = {node["type"] for node in graph["nodes"]}
        framework_names = {entry["name"] for entry in discovery["frameworks"]}
        workflow_names = {entry["name"] for entry in discovery["workflows"]}
        tool_names = {entry["name"] for entry in discovery["tools"]}
        ecosystem_workflows = {
            entry["name"] for entry in ecosystem["entities"]["workflows"]
        }

        self.assertIn("runs", edge_types)
        self.assertIn("uses", edge_types)
        self.assertIn("agent", node_types)
        self.assertIn("workflow", node_types)
        self.assertIn("tool", node_types)
        self.assertIn("CrewAI", framework_names)
        self.assertIn("CrewAI Research Crew", workflow_names)
        self.assertIn("web_search", tool_names)
        self.assertIn("CrewAI Research Crew", ecosystem_workflows)
        self.assertTrue(
            all(edge["validation_status"] == "valid" for edge in graph["edges"])
        )

    def test_crewai_task_failure_emits_failed_events(self):
        class ExpectedError(RuntimeError):
            pass

        def action():
            mesh = OpenMeshCrewAI(
                client=OpenMeshClient(session_id="sess_crewai", broadcast=False),
                crew_name="CrewAI Failure Crew",
                trace_id="trace_crewai_failure",
            )
            researcher = mesh.agent(
                id="researcher", name="Research Agent", role="Researcher"
            )
            with self.assertRaises(ExpectedError):
                with mesh.workflow():
                    with researcher.task("Broken task"):
                        raise ExpectedError("task broke")

        records = self.collect_records(action)
        events = [record_to_event(record) for record in records]
        task_failed = [
            event for event in events if event["event_type"] == "task.failed"
        ][0]
        workflow_failed = [
            event for event in events if event["event_type"] == "workflow.failed"
        ][0]

        self.assertEqual(task_failed["severity"], "error")
        self.assertEqual(task_failed["payload"]["error_type"], "ExpectedError")
        self.assertEqual(workflow_failed["severity"], "error")


if __name__ == "__main__":
    unittest.main()
