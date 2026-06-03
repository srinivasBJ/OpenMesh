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


class FakeAsyncSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushed = 0

    def add(self, record):
        self.added.append(record)

    async def flush(self):
        self.flushed += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class OpenMeshSdkTests(unittest.TestCase):
    def collect_events(self, action):
        sessions = []

        def session_factory():
            session = FakeAsyncSession()
            sessions.append(session)
            return FakeSessionContext(session)

        with patch("src.sdk.client.AsyncSessionLocal", session_factory):
            action()

        records = [session.added[0] for session in sessions if session.added]
        return [record_to_event(record) for record in records]

    def test_agent_registration_emits_openmesh_event(self):
        def action():
            client = OpenMeshClient(session_id="sess_sdk", broadcast=False)
            client.agent(id="research-agent", name="Research Agent", role="researcher")

        events = self.collect_events(action)

        self.assertEqual(events[0]["event_type"], "agent.registered")
        self.assertEqual(events[0]["source"]["node_type"], "agent")
        self.assertEqual(events[0]["source"]["runtime"], "openmesh.sdk.python")
        self.assertEqual(events[0]["session_id"], "sess_sdk")

    def test_task_context_emits_started_and_completed_on_same_trace(self):
        def action():
            client = OpenMeshClient(session_id="sess_sdk", broadcast=False)
            agent = client.agent(id="research-agent", name="Research Agent")
            with agent.task("Research vector databases"):
                pass

        events = self.collect_events(action)
        task_events = [
            event for event in events if event["event_type"].startswith("task.")
        ]

        self.assertEqual(
            [event["event_type"] for event in task_events],
            ["task.started", "task.completed"],
        )
        self.assertEqual(task_events[0]["trace_id"], task_events[1]["trace_id"])

    def test_task_context_emits_failed_and_reraises(self):
        class ExpectedError(RuntimeError):
            pass

        def action():
            client = OpenMeshClient(session_id="sess_sdk", broadcast=False)
            agent = client.agent(id="research-agent", name="Research Agent")
            with self.assertRaises(ExpectedError):
                with agent.task("Research vector databases"):
                    raise ExpectedError("tooling failed")

        events = self.collect_events(action)
        failed = [event for event in events if event["event_type"] == "task.failed"][0]

        self.assertEqual(failed["severity"], "error")
        self.assertEqual(failed["payload"]["error_type"], "ExpectedError")

    def test_tool_context_emits_tool_relationship_events(self):
        def action():
            client = OpenMeshClient(session_id="sess_sdk", broadcast=False)
            agent = client.agent(id="research-agent", name="Research Agent")
            with agent.task("Research vector databases"):
                with agent.tool("web_search"):
                    pass

        events = self.collect_events(action)
        tool_events = [
            event for event in events if event["event_type"].startswith("tool.call.")
        ]

        self.assertEqual(
            [event["event_type"] for event in tool_events],
            ["tool.call.started", "tool.call.completed"],
        )
        self.assertEqual(tool_events[0]["target"]["node_type"], "tool")
        self.assertEqual(tool_events[0]["target"]["name"], "web_search")
        self.assertEqual(tool_events[0]["trace_id"], tool_events[1]["trace_id"])

    def test_agent_emit_accepts_links(self):
        def action():
            client = OpenMeshClient(session_id="sess_sdk", broadcast=False)
            agent = client.agent(id="research-agent", name="Research Agent")
            agent.emit(
                "message.sent",
                {"message": "linked"},
                links=[{"trace_id": "trace_external", "relationship": "follows_from"}],
            )

        events = self.collect_events(action)
        linked = [event for event in events if event["event_type"] == "message.sent"][0]

        self.assertEqual(linked["links"][0]["trace_id"], "trace_external")

    def test_standalone_tool_completion_shares_started_root(self):
        def action():
            client = OpenMeshClient(session_id="sess_sdk", broadcast=False)
            agent = client.agent(id="research-agent", name="Research Agent")
            with agent.tool("web_search"):
                pass

        events = self.collect_events(action)
        tool_events = [
            event for event in events if event["event_type"].startswith("tool.call.")
        ]

        self.assertEqual(
            tool_events[0]["root_event_id"], tool_events[1]["root_event_id"]
        )
        self.assertEqual(tool_events[0]["span_id"], tool_events[1]["span_id"])


class OpenMeshAsyncSdkTests(unittest.IsolatedAsyncioTestCase):
    async def collect_events(self, action):
        sessions = []

        def session_factory():
            session = FakeAsyncSession()
            sessions.append(session)
            return FakeSessionContext(session)

        with patch("src.sdk.client.AsyncSessionLocal", session_factory):
            await action()

        records = [session.added[0] for session in sessions if session.added]
        return [record_to_event(record) for record in records]

    async def test_async_task_and_tool_emit_on_existing_event_loop(self):
        async def action():
            client = OpenMeshClient(session_id="sess_async_sdk", broadcast=False)
            agent = client.agent(id="async-research-agent", name="Async Research Agent")
            async with agent.task("Research vector databases"):
                async with agent.tool("web_search"):
                    await agent.emit_async(
                        "message.sent", {"message": "async summary ready"}
                    )

        events = await self.collect_events(action)
        event_types = [event["event_type"] for event in events]
        trace_ids = {event["trace_id"] for event in events}

        self.assertEqual(
            event_types,
            [
                "agent.registered",
                "task.started",
                "tool.call.started",
                "message.sent",
                "tool.call.completed",
                "task.completed",
            ],
        )
        self.assertEqual(len(trace_ids), 1)
        self.assertEqual(events[0]["session_id"], "sess_async_sdk")

    async def test_async_tool_failure_emits_failed_and_reraises(self):
        class ExpectedError(RuntimeError):
            pass

        async def action():
            client = OpenMeshClient(session_id="sess_async_sdk", broadcast=False)
            agent = client.agent(id="async-research-agent", name="Async Research Agent")
            with self.assertRaises(ExpectedError):
                async with agent.task("Research vector databases"):
                    async with agent.tool("web_search"):
                        raise ExpectedError("search failed")

        events = await self.collect_events(action)
        event_types = [event["event_type"] for event in events]
        tool_failed = [
            event for event in events if event["event_type"] == "tool.call.failed"
        ][0]
        task_failed = [
            event for event in events if event["event_type"] == "task.failed"
        ][0]

        self.assertIn("tool.call.failed", event_types)
        self.assertIn("task.failed", event_types)
        self.assertEqual(tool_failed["severity"], "error")
        self.assertEqual(task_failed["payload"]["error_type"], "ExpectedError")


if __name__ == "__main__":
    unittest.main()
