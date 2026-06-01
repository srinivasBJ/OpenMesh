import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from src.db.openmesh_events import create_openmesh_event, record_to_event
from src.db.openmesh_sessions import complete_openmesh_session, create_openmesh_session, session_to_dict
from src.services.graph_state import reduce_graph_state
from src.services.openmesh_collector import OpenMeshCollector
from src.services.openmesh_queries import trace_summary
from src.shared.openmesh_events import agent_node, make_openmesh_event
from src.cli.tui import TuiSnapshot, render_plain


CLI_NODE = {
    "node_id": "openmesh.cli",
    "node_type": "service",
    "name": "OpenMesh CLI",
    "runtime": "python.argparse",
}


def process_node(session_id: str, command: str) -> dict:
    return {
        "node_id": f"process:{session_id}",
        "node_type": "process",
        "name": command,
        "runtime": "subprocess",
    }


def command_node(command: str) -> dict:
    return {
        "node_id": "command:python",
        "node_type": "command",
        "name": command,
        "runtime": "shell",
    }


class FakeAsyncSession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.flushed = 0
        self.refreshed = []

    def add(self, record):
        self.added.append(record)

    async def flush(self):
        self.flushed += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, record):
        self.refreshed.append(record)


class FakeSessionStore(FakeAsyncSession):
    def __init__(self):
        super().__init__()
        self.sessions = {}

    def add(self, record):
        super().add(record)
        if hasattr(record, "session_id"):
            self.sessions[record.session_id] = record


class OpenMeshCoreTests(unittest.IsolatedAsyncioTestCase):
    def make_event(self, event_type="message.sent"):
        return make_openmesh_event(
            event_type,
            agent_node("agent-a", "Research Agent", "researcher"),
            {"message": "hello"},
            target=agent_node("agent-b", "Coding Agent", "engineer"),
            session_id="sess_test",
            trace_id="trace_test",
        )

    async def test_collector_accept_persists_valid_event(self):
        db = FakeAsyncSession()
        collector = OpenMeshCollector()
        event = self.make_event()

        accepted = await collector.accept(db, event, broadcast=False)

        self.assertEqual(accepted["event_id"], event["event_id"])
        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.rollbacks, 0)

    async def test_collector_rejects_invalid_payload(self):
        collector = OpenMeshCollector()
        event = self.make_event()
        event["payload"] = "bad"

        with self.assertRaises(HTTPException) as err:
            await collector.accept(FakeAsyncSession(), event, broadcast=False)

        self.assertEqual(err.exception.status_code, 422)
        self.assertIn("payload", err.exception.detail)

    async def test_event_persistence_round_trip(self):
        db = FakeAsyncSession()
        event = self.make_event("process.stdout")

        record = await create_openmesh_event(db, event)
        restored = record_to_event(record)

        self.assertEqual(record.event_id, event["event_id"])
        self.assertEqual(restored["event_type"], "process.stdout")
        self.assertEqual(restored["trace_id"], "trace_test")
        self.assertEqual(restored["source"]["name"], "Research Agent")

    def test_trace_reconstruction_groups_agents_and_status(self):
        event_a = self.make_event("process.started")
        event_b = self.make_event("process.completed")
        records = [
            SimpleNamespace(
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None),
                trace_id=event["trace_id"],
                session_id=event["session_id"],
                source_json=event["source"],
                target_json=event.get("target"),
                payload_json=event["payload"],
                metrics_json=event["metrics"],
                severity=event["severity"],
            )
            for event in (event_a, event_b)
        ]

        summary = trace_summary("trace_test", records)

        self.assertEqual(summary["trace_id"], "trace_test")
        self.assertEqual(summary["event_count"], 2)
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["agents"], ["Coding Agent", "Research Agent"])

    def test_graph_reduction_process_edges(self):
        started = self.make_event("process.started")
        started["source"] = CLI_NODE
        started["target"] = process_node("sess_test", "python hello.py")
        completed = self.make_event("process.completed")
        completed["source"] = started["target"]
        completed["target"] = command_node("python hello.py")
        records = [
            SimpleNamespace(
                event_type=event["event_type"],
                timestamp=datetime.utcnow(),
                source_json=event["source"],
                target_json=event["target"],
            )
            for event in (started, completed)
        ]

        graph = reduce_graph_state(records)

        edge_types = {edge["type"] for edge in graph["edges"]}
        node_types = {node["type"] for node in graph["nodes"]}
        self.assertIn("spawned", edge_types)
        self.assertIn("executed", edge_types)
        self.assertIn("process", node_types)

    def test_graph_reduction_langgraph_transition_edges(self):
        event = self.make_event("node.transition")
        event["source"] = {
            "node_id": "langgraph:basic:Node A",
            "node_type": "service",
            "name": "Node A",
            "runtime": "langgraph",
        }
        event["target"] = {
            "node_id": "langgraph:basic:Node B",
            "node_type": "service",
            "name": "Node B",
            "runtime": "langgraph",
        }
        records = [
            SimpleNamespace(
                event_type=event["event_type"],
                timestamp=datetime.utcnow(),
                source_json=event["source"],
                target_json=event["target"],
            )
        ]

        graph = reduce_graph_state(records)

        self.assertEqual(graph["edges"][0]["type"], "transitions_to")
        self.assertEqual(graph["nodes"][0]["runtime"], "langgraph")

    async def test_session_creation_and_completion(self):
        db = FakeSessionStore()
        started = datetime.utcnow()
        session = await create_openmesh_session(
            db,
            session_id="sess_test",
            command="python hello.py",
            started_at=started,
        )

        with patch("src.db.openmesh_sessions.get_openmesh_session", return_value=session):
            completed = await complete_openmesh_session(
                db,
                session_id=session.session_id,
                ended_at=datetime.utcnow(),
                status="completed",
                exit_code=0,
            )

        self.assertEqual(session_to_dict(completed)["status"], "completed")
        self.assertEqual(session_to_dict(completed)["exit_code"], 0)

    async def test_process_lifecycle_event_uses_collector_shape(self):
        db = FakeAsyncSession()
        collector = OpenMeshCollector()
        event = make_openmesh_event(
            "process.started",
            CLI_NODE,
            {"command": "python hello.py"},
            target=process_node("sess_test", "python hello.py"),
            severity="info",
            session_id="sess_test",
            trace_id="trace_test",
        )
        await collector.accept(db, event, broadcast=False)

        self.assertEqual(event["event_type"], "process.started")
        self.assertEqual(event["session_id"], "sess_test")
        self.assertEqual(event["trace_id"], "trace_test")
        self.assertEqual(len(db.added), 1)

    def test_tui_plain_render_keeps_network_visible(self):
        snapshot = TuiSnapshot(
            health={"events": 1, "traces": 1, "nodes": 2, "edges": 1},
            graph={
                "nodes": [
                    {"id": "agent-a", "type": "agent", "name": "Research Agent", "event_count": 1, "last_seen": "2026-05-29T10:00:00Z"},
                    {"id": "agent-b", "type": "agent", "name": "Coding Agent", "event_count": 1, "last_seen": "2026-05-29T10:00:00Z"},
                ],
                "edges": [
                    {"id": "edge-1", "source": "agent-a", "target": "agent-b", "type": "communicates_with", "event_count": 1, "last_seen": "2026-05-29T10:00:00Z"}
                ],
            },
            traces=[{"trace_id": "trace_test", "status": "completed", "event_count": 1, "started_at": "2026-05-29T10:00:00Z"}],
            events=[{
                "event_id": "evt_test",
                "event_type": "message.sent",
                "timestamp": "2026-05-29T10:00:00Z",
                "trace_id": "trace_test",
                "session_id": "sess_test",
                "source": {"node_id": "agent-a", "node_type": "agent", "name": "Research Agent"},
                "target": {"node_id": "agent-b", "node_type": "agent", "name": "Coding Agent"},
                "payload": {},
            }],
            sessions=[],
            loaded_at=datetime.utcnow(),
        )

        output = render_plain(snapshot)

        self.assertIn("Agents / Processes", output)
        self.assertIn("Network", output)
        self.assertIn("communicates_with", output)


if __name__ == "__main__":
    unittest.main()
