import unittest
from unittest.mock import patch

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
        task_events = [event for event in events if event["event_type"].startswith("task.")]

        self.assertEqual([event["event_type"] for event in task_events], ["task.started", "task.completed"])
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
        tool_events = [event for event in events if event["event_type"].startswith("tool.call.")]

        self.assertEqual([event["event_type"] for event in tool_events], ["tool.call.started", "tool.call.completed"])
        self.assertEqual(tool_events[0]["target"]["node_type"], "tool")
        self.assertEqual(tool_events[0]["target"]["name"], "web_search")
        self.assertEqual(tool_events[0]["trace_id"], tool_events[1]["trace_id"])


if __name__ == "__main__":
    unittest.main()
