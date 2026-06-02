import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from src.db.openmesh_events import create_openmesh_event, record_to_event
from src.db.openmesh_sessions import complete_openmesh_session, create_openmesh_session, session_to_dict
from src.services.discovery import build_discovery
from src.services.graph_state import reduce_graph_state
from src.services.openmesh_doctor import build_graph_diagnostics, build_trace_diagnostics
from src.services.openmesh_collector import OpenMeshCollector
from src.services.openmesh_queries import trace_summary
from src.services.relationship_types import relationship_registry, relationship_type_for
from src.services.trace_semantics import build_event_hierarchy, build_span_summary, build_span_tree, graph_edges_for_trace, validate_trace_semantics
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


def record_from_event(event: dict, **overrides):
    values = {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "timestamp": datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None),
        "trace_id": event["trace_id"],
        "session_id": event["session_id"],
        "span_id": event.get("span_id"),
        "parent_span_id": event.get("parent_span_id"),
        "parent_event_id": event.get("parent_event_id"),
        "root_event_id": event.get("root_event_id"),
        "source_json": event["source"],
        "target_json": event.get("target"),
        "payload_json": event.get("payload", {}),
        "metrics_json": event.get("metrics", {}),
        "links_json": event.get("links", []),
        "severity": event.get("severity", "info"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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

    async def test_event_persistence_round_trips_links(self):
        db = FakeAsyncSession()
        event = make_openmesh_event(
            "message.sent",
            agent_node("agent-a", "Research Agent", "researcher"),
            {"message": "linked"},
            session_id="sess_test",
            trace_id="trace_test",
            links=[{"trace_id": "trace_parent", "span_id": "span_parent", "relationship": "follows_from"}],
        )

        record = await create_openmesh_event(db, event)
        restored = record_to_event(record)

        self.assertEqual(restored["links"], event["links"])

    async def test_collector_rejects_invalid_links(self):
        collector = OpenMeshCollector()
        event = self.make_event()
        event["links"] = ["bad-link"]

        with self.assertRaises(HTTPException) as err:
            await collector.accept(FakeAsyncSession(), event, broadcast=False)

        self.assertEqual(err.exception.status_code, 422)
        self.assertIn("link", err.exception.detail)

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
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=datetime.utcnow(),
                trace_id=event["trace_id"],
                span_id=event.get("span_id"),
                source_json=event["source"],
                target_json=event["target"],
            )
            for event in (started, completed)
        ]

        graph = reduce_graph_state(records)

        edge_types = {edge["type"] for edge in graph["edges"]}
        node_types = {node["type"] for node in graph["nodes"]}
        self.assertIn("spawns", edge_types)
        self.assertIn("executes", edge_types)
        self.assertIn("process", node_types)
        self.assertEqual(graph["validation"]["status"], "OK")
        self.assertTrue(all(edge["event_id"] for edge in graph["edges"]))
        self.assertTrue(all(edge["trace_id"] == "trace_test" for edge in graph["edges"]))
        self.assertTrue(all(edge["observation_count"] == 1 for edge in graph["edges"]))

    def test_relationship_registry_maps_protocol_events_to_canonical_types(self):
        relationship_types = {item["type"] for item in relationship_registry()}

        self.assertIn("uses", relationship_types)
        self.assertIn("spawns", relationship_types)
        self.assertEqual(relationship_type_for("tool.call.started", source_type="agent", target_type="tool"), "uses")
        self.assertEqual(relationship_type_for("process.started", source_type="service", target_type="process"), "spawns")

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
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=datetime.utcnow(),
                trace_id=event["trace_id"],
                span_id=event.get("span_id"),
                source_json=event["source"],
                target_json=event["target"],
            )
        ]

        graph = reduce_graph_state(records)

        self.assertEqual(graph["edges"][0]["type"], "transitions_to")
        self.assertEqual(graph["edges"][0]["lifecycle_state"], "active")
        self.assertEqual(graph["nodes"][0]["runtime"], "langgraph")
        self.assertIn("relationship_types", graph["metadata"])

    def test_discovery_registry_groups_observed_entities(self):
        tool_event = self.make_event("tool.call.completed")
        tool_event["target"] = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "openmesh.sdk.python",
        }
        framework_event = self.make_event("node.transition")
        framework_event["source"] = {
            "node_id": "langgraph:basic:Node A",
            "node_type": "service",
            "name": "Node A",
            "runtime": "langgraph",
            "metadata": {"framework": "langgraph"},
        }
        framework_event["target"] = {
            "node_id": "langgraph:basic:Node B",
            "node_type": "service",
            "name": "Node B",
            "runtime": "langgraph",
            "metadata": {"framework": "langgraph"},
        }
        process_event = self.make_event("process.started")
        process_event["source"] = CLI_NODE
        process_event["target"] = process_node("sess_test", "python hello.py")
        records = [
            SimpleNamespace(
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None),
                trace_id=event["trace_id"],
                span_id=event.get("span_id"),
                source_json=event["source"],
                target_json=event.get("target"),
                severity=event["severity"],
            )
            for event in (tool_event, framework_event, process_event)
        ]

        discovery = build_discovery(records)

        self.assertEqual(discovery["frameworks"][0]["name"], "LangGraph")
        self.assertEqual(discovery["tools"][0]["name"], "web_search")
        self.assertTrue(any(entry["name"] == "python hello.py" for entry in discovery["processes"]))
        self.assertTrue(any(entry["name"] == "Research Agent" for entry in discovery["agents"]))

    def test_trace_semantics_reconstruct_parent_child_tree_and_provenance(self):
        root = self.make_event("agent.registered")
        root.pop("target", None)
        task = make_openmesh_event(
            "task.started",
            root["source"],
            {"task": "Research"},
            session_id=root["session_id"],
            trace_id=root["trace_id"],
            parent_event_id=root["event_id"],
            root_event_id=root["event_id"],
            parent_span_id=root["span_id"],
        )
        tool = make_openmesh_event(
            "tool.call.started",
            root["source"],
            {"tool": "web_search"},
            target={"node_id": "tool:web_search", "node_type": "tool", "name": "web_search"},
            session_id=root["session_id"],
            trace_id=root["trace_id"],
            parent_event_id=task["event_id"],
            root_event_id=root["event_id"],
            parent_span_id=task["span_id"],
        )
        events = [root, task, tool]

        hierarchy = build_event_hierarchy(events)
        relationships = graph_edges_for_trace(events)
        validation = validate_trace_semantics(events)

        self.assertEqual(hierarchy[0]["children"][0]["event_id"], task["event_id"])
        self.assertEqual(hierarchy[0]["children"][0]["children"][0]["event_id"], tool["event_id"])
        self.assertEqual(relationships[0]["event_id"], tool["event_id"])
        self.assertEqual(relationships[0]["type"], "uses")
        self.assertEqual(validation["status"], "OK")

    def test_span_semantics_build_lifecycle_tree_and_links(self):
        root = self.make_event("task.started")
        linked = make_openmesh_event(
            "tool.call.started",
            root["source"],
            {"tool": "web_search"},
            target={"node_id": "tool:web_search", "node_type": "tool", "name": "web_search"},
            session_id=root["session_id"],
            trace_id=root["trace_id"],
            parent_event_id=root["event_id"],
            root_event_id=root["event_id"],
            parent_span_id=root["span_id"],
            links=[{"trace_id": "trace_external", "relationship": "follows_from"}],
        )
        completed = make_openmesh_event(
            "tool.call.completed",
            root["source"],
            {"tool": "web_search"},
            target={"node_id": "tool:web_search", "node_type": "tool", "name": "web_search"},
            session_id=root["session_id"],
            trace_id=root["trace_id"],
            span_id=linked["span_id"],
            parent_span_id=root["span_id"],
            parent_event_id=linked["event_id"],
            root_event_id=root["event_id"],
        )
        events = [root, linked, completed]

        spans = build_span_summary(events)
        span_tree = build_span_tree(events)
        validation = validate_trace_semantics(events)

        child_span = next(span for span in spans if span["span_id"] == linked["span_id"])
        self.assertEqual(child_span["status"], "completed")
        self.assertEqual(child_span["event_count"], 2)
        self.assertEqual(child_span["links"][0]["trace_id"], "trace_external")
        self.assertEqual(span_tree[0]["children"][0]["span_id"], linked["span_id"])
        self.assertEqual(validation["cross_trace_links"][0]["linked_trace_id"], "trace_external")

    def test_doctor_trace_diagnostics_find_broken_parent_span_and_orphan_span(self):
        root = self.make_event("task.started")
        child = make_openmesh_event(
            "tool.call.started",
            root["source"],
            {"tool": "web_search"},
            target={"node_id": "tool:web_search", "node_type": "tool", "name": "web_search"},
            session_id=root["session_id"],
            trace_id=root["trace_id"],
            parent_span_id="span_missing",
            parent_event_id=root["event_id"],
            root_event_id=root["event_id"],
        )

        diagnostics = build_trace_diagnostics([record_from_event(root), record_from_event(child)])
        trace_check = diagnostics[0]

        self.assertEqual(trace_check["severity"], "ERROR")
        self.assertEqual(len(trace_check["detail"]["broken_parent_span_events"]), 1)
        self.assertEqual(len(trace_check["detail"]["orphan_spans"]), 1)

    def test_doctor_trace_diagnostics_find_missing_and_broken_root_event_ids(self):
        missing = self.make_event("task.started")
        broken = self.make_event("tool.call.started")

        diagnostics = build_trace_diagnostics([
            record_from_event(missing, root_event_id=None),
            record_from_event(broken, root_event_id="evt_missing_root"),
        ])
        detail = diagnostics[0]["detail"]

        self.assertEqual(diagnostics[0]["severity"], "ERROR")
        self.assertEqual(len(detail["missing_root_event_events"]), 1)
        self.assertEqual(len(detail["broken_root_event_events"]), 1)

    def test_doctor_trace_diagnostics_find_malformed_and_invalid_cross_trace_links(self):
        local = self.make_event("message.sent")
        local["links"] = [{"trace_id": "trace_missing", "span_id": "span_missing", "relationship": "follows_from"}]
        malformed = self.make_event("message.sent")
        malformed["links"] = [{"relationship": "empty"}]

        diagnostics = build_trace_diagnostics([record_from_event(local), record_from_event(malformed)])
        detail = diagnostics[0]["detail"]

        self.assertEqual(diagnostics[0]["severity"], "ERROR")
        self.assertEqual(len(detail["malformed_link_events"]), 1)
        self.assertEqual(len(detail["invalid_cross_trace_links"]), 1)

    def test_doctor_trace_diagnostics_count_valid_cross_trace_links(self):
        parent = self.make_event("task.started")
        parent["trace_id"] = "trace_parent"
        child = self.make_event("task.started")
        child["trace_id"] = "trace_child"
        child["links"] = [{
            "trace_id": parent["trace_id"],
            "span_id": parent["span_id"],
            "event_id": parent["event_id"],
            "relationship": "follows_from",
        }]

        diagnostics = build_trace_diagnostics([record_from_event(parent), record_from_event(child)])

        self.assertEqual(diagnostics[0]["severity"], "INFO")
        self.assertEqual(diagnostics[0]["detail"]["valid_cross_trace_links"], 1)

    def test_doctor_workflow_diagnostics_find_incomplete_and_long_running_spans(self):
        workflow = make_openmesh_event(
            "workflow.started",
            {"node_id": "workflow:test", "node_type": "workflow", "name": "Test Workflow"},
            {"workflow": "test"},
            session_id="sess_test",
            trace_id="trace_workflow",
        )
        record = record_from_event(workflow, timestamp=datetime(2026, 1, 1, 0, 0, 0))

        diagnostics = build_trace_diagnostics([record], now=datetime(2026, 1, 1, 2, 0, 0))
        trace_check, workflow_check = diagnostics

        self.assertEqual(trace_check["severity"], "WARNING")
        self.assertEqual(workflow_check["severity"], "WARNING")
        self.assertEqual(len(trace_check["detail"]["long_running_active_spans"]), 1)
        self.assertEqual(len(workflow_check["detail"]["incomplete_workflow_spans"]), 1)

    def test_doctor_graph_diagnostics_find_missing_provenance_invalid_and_stale_edges(self):
        stale = self.make_event("message.sent")
        stale["source"] = agent_node("agent-a", "Research Agent", "researcher")
        stale["target"] = agent_node("agent-b", "Coding Agent", "engineer")
        invalid = self.make_event("node.transition")
        invalid["source"] = agent_node("agent-a", "Research Agent", "researcher")
        invalid["target"] = {"node_id": "tool:web_search", "node_type": "tool", "name": "web_search"}
        missing = self.make_event("message.sent")
        missing["source"] = agent_node("agent-c", "Planning Agent", "planner")
        missing["target"] = agent_node("agent-d", "Review Agent", "reviewer")

        diagnostics = build_graph_diagnostics([
            record_from_event(stale, timestamp=datetime(2026, 1, 1, 0, 0, 0)),
            record_from_event(invalid),
            record_from_event(missing, trace_id=None),
        ])

        detail = diagnostics["detail"]
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertGreaterEqual(len(detail["missing_provenance"]), 1)
        self.assertGreaterEqual(len(detail["invalid_relationships"]), 1)
        self.assertGreaterEqual(len(detail["stale_relationships"]), 1)

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
            integrations=[],
            discovery={"frameworks": [], "agents": [], "tools": [], "processes": [], "services": []},
            loaded_at=datetime.utcnow(),
        )

        output = render_plain(snapshot)

        self.assertIn("Agents / Processes", output)
        self.assertIn("Network", output)
        self.assertIn("communicates_with", output)


if __name__ == "__main__":
    unittest.main()
