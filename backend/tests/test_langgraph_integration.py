import unittest
from unittest.mock import patch

from src.db.openmesh_events import record_to_event
from src.sdk import OpenMeshClient
from src.sdk.integrations.langgraph import OpenMeshLangGraph
from src.sdk.integrations.registry import get_integration, list_integrations


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


class OpenMeshLangGraphIntegrationTests(unittest.TestCase):
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

    def test_wrapped_nodes_emit_lifecycle_and_transition_events(self):
        def action():
            mesh = OpenMeshLangGraph(
                client=OpenMeshClient(session_id="sess_langgraph", broadcast=False),
                graph_name="Basic Flow",
                trace_id="trace_langgraph",
            )

            def node_a(state):
                return {**state, "step": "a"}

            def node_b(state):
                return {**state, "step": "b"}

            wrapped_a = mesh.node("Node A", node_a)
            wrapped_b = mesh.node("Node B", node_b)
            state = wrapped_a({"topic": "observability"})
            wrapped_b(state)

        events = self.collect_events(action)
        event_types = [event["event_type"] for event in events]
        transition = [event for event in events if event["event_type"] == "node.transition"][0]

        self.assertEqual(
            event_types,
            ["workflow.started", "node.started", "node.completed", "node.transition", "node.started", "node.completed"],
        )
        workflow = events[0]
        node_starts = [event for event in events if event["event_type"] == "node.started"]
        self.assertEqual(transition["source"]["name"], "Node A")
        self.assertEqual(transition["target"]["name"], "Node B")
        self.assertEqual(transition["trace_id"], "trace_langgraph")
        self.assertEqual(node_starts[0]["parent_span_id"], workflow["span_id"])
        self.assertEqual(node_starts[1]["parent_span_id"], workflow["span_id"])
        self.assertNotEqual(node_starts[0]["span_id"], node_starts[1]["span_id"])
        self.assertEqual(transition["span_id"], workflow["span_id"])
        self.assertEqual(transition["links"][0]["span_id"], node_starts[0]["span_id"])

    def test_wrapped_node_failure_emits_failed_event(self):
        class ExpectedError(RuntimeError):
            pass

        def action():
            mesh = OpenMeshLangGraph(
                client=OpenMeshClient(session_id="sess_langgraph", broadcast=False),
                graph_name="Basic Flow",
                trace_id="trace_langgraph",
            )

            def broken_node(state):
                raise ExpectedError("node broke")

            with self.assertRaises(ExpectedError):
                mesh.node("Broken Node", broken_node)({})

        events = self.collect_events(action)
        failed = [event for event in events if event["event_type"] == "node.failed"][0]
        workflow = [event for event in events if event["event_type"] == "workflow.started"][0]

        self.assertEqual(failed["severity"], "error")
        self.assertEqual(failed["payload"]["error_type"], "ExpectedError")
        self.assertEqual(failed["parent_span_id"], workflow["span_id"])

    def test_registry_reports_langgraph_and_future_integrations(self):
        integrations = {item["key"]: item for item in list_integrations()}

        self.assertIn("langgraph", integrations)
        self.assertIn("crewai", integrations)
        self.assertIn("autogen", integrations)
        self.assertIn("openhands", integrations)
        self.assertEqual(get_integration("langgraph")["name"], "LangGraph")

    def test_add_edge_emits_transition_for_observable_nodes(self):
        class FakeWorkflow:
            def __init__(self):
                self.edges = []

            def add_edge(self, source, target):
                self.edges.append((source, target))

        def action():
            mesh = OpenMeshLangGraph(
                client=OpenMeshClient(session_id="sess_langgraph", broadcast=False),
                graph_name="Basic Flow",
                trace_id="trace_langgraph",
            )
            workflow = FakeWorkflow()
            mesh.add_edge(workflow, "Node A", "Node B")
            mesh.add_edge(workflow, "__start__", "Node A")

        events = self.collect_events(action)
        transitions = [event for event in events if event["event_type"] == "node.transition"]
        workflow = [event for event in events if event["event_type"] == "workflow.started"][0]

        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["source"]["name"], "Node A")
        self.assertEqual(transitions[0]["target"]["name"], "Node B")
        self.assertEqual(transitions[0]["span_id"], workflow["span_id"])


class OpenMeshAsyncLangGraphIntegrationTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_async_wrapped_nodes_emit_lifecycle_and_transition_events(self):
        async def action():
            mesh = OpenMeshLangGraph(
                client=OpenMeshClient(session_id="sess_langgraph", broadcast=False),
                graph_name="Async Flow",
                trace_id="trace_langgraph_async",
            )

            async def node_a(state):
                return {**state, "step": "a"}

            async def node_b(state):
                return {**state, "step": "b"}

            state = await mesh.node("Node A", node_a)({"topic": "observability"})
            await mesh.node("Node B", node_b)(state)

        events = await self.collect_events(action)
        event_types = [event["event_type"] for event in events]

        self.assertEqual(
            event_types,
            ["workflow.started", "node.started", "node.completed", "node.transition", "node.started", "node.completed"],
        )
        workflow = events[0]
        node_starts = [event for event in events if event["event_type"] == "node.started"]
        self.assertEqual(node_starts[0]["parent_span_id"], workflow["span_id"])
        self.assertNotEqual(node_starts[0]["span_id"], node_starts[1]["span_id"])


if __name__ == "__main__":
    unittest.main()
