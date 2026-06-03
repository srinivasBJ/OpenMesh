# ruff: noqa: E402
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.db.openmesh_events import create_openmesh_event, record_to_event
from src.db.openmesh_sessions import (
    complete_openmesh_session,
    create_openmesh_session,
    session_to_dict,
)
from src.db.openmesh_snapshots import (
    create_openmesh_snapshot,
    snapshot_record_to_detail,
    snapshot_record_to_summary,
)
from src.api.routes.main import (
    get_openmesh_snapshot_replay as api_get_openmesh_snapshot_replay,
    get_openmesh_trace_replay as api_get_openmesh_trace_replay,
    get_openmesh_workflow_replay as api_get_openmesh_workflow_replay,
    query_openmesh as api_query_openmesh,
    OpenMeshQueryRequest,
)
from src.services.discovery import build_discovery
from src.services.graph_state import reduce_graph_state, validate_graph_state
from src.services.graph_exploration import (
    expand_graph_neighborhood,
    filter_graph,
    graph_statistics,
    search_graph,
    select_graph_node,
    traverse_graph_relationships,
)
from src.services.node_types import (
    NODE_TYPES,
    NodeType,
    node_type_definition,
    node_type_registry,
    node_type_validation_metadata,
    validate_node,
)
from src.services.mcp_discovery import (
    build_mcp_registry,
    mcp_server_node,
    register_mcp_server,
)
from src.services.mcp_config_discovery import (
    ClaudeDesktopConfigProvider,
    CodexConfigProvider,
    MCPConfigEntry,
    build_mcp_config_registry,
    discover_mcp_configs,
    register_mcp_config_entry,
    validate_mcp_config_entries,
)
from src.services.mcp_capabilities import (
    MCPCapabilityEntry,
    build_capability_registry,
    capability_node,
    register_mcp_capability,
    validate_capability_entries,
)
from src.services.ecosystem_registry import (
    build_ecosystem_registry,
    validate_ecosystem_entities,
)
from src.services.federation import (
    build_federation_registry,
    discover_federation_peers,
    query_federation_registry,
)
from src.services.openmesh_doctor import (
    build_capability_diagnostics,
    build_ecosystem_diagnostics,
    build_graph_diagnostics,
    build_mcp_config_diagnostics,
    build_node_diagnostics,
    build_registry_compatibility_diagnostics,
    build_relationship_diagnostics,
    build_trace_diagnostics,
    build_workflow_registry_diagnostics,
)
from src.services.registry_compatibility import (
    NODE_REGISTRY_VERSION,
    RELATIONSHIP_REGISTRY_VERSION,
    compatibility_status,
    registry_versions,
    validate_registry_versions,
)
from src.services.registry_status import build_registry_status
from src.services.openmesh_collector import OpenMeshCollector
from src.services.llm_demo import run_research_demo
from src.services.openmesh_queries import (
    inspect_graph_node,
    inspect_graph_workflow,
    trace_summary,
)
from src.providers.base import LLMResponse, ProviderModel, ProviderStatus
from src.providers.settings import load_provider_settings
from src.services.local_llm_metrics import get_local_llm_metrics
from src.services.ecosystem_snapshot import build_ecosystem_snapshot
from src.services.ecosystem_snapshot import compare_snapshot_payloads
from src.services.evaluation import generate_synthetic_ecosystem, run_evaluation_suite
from src.services.timeline import (
    build_node_timeline,
    build_timeline,
    build_trace_timeline,
    build_workflow_timeline,
)
from src.services.query_engine import parse_query, run_query_on_state
from src.services.replay import build_replay_from_snapshot, build_replay_from_timeline
from src.services.relationship_types import (
    relationship_definition,
    relationship_registry,
    relationship_type_for,
    RELATIONSHIP_TYPES,
    RelationshipType,
    validate_relationship,
)
from src.services.simulation import run_local_simulation
from src.services.trace_semantics import (
    build_event_hierarchy,
    build_span_summary,
    build_span_tree,
    graph_edges_for_trace,
    validate_trace_semantics,
)
from src.services.workflow_registry import (
    WorkflowEntry,
    build_workflow_registry,
    register_workflow,
    validate_workflow_entries,
    workflow_node,
)
from src.shared.openmesh_events import agent_node, make_openmesh_event
from src.cli.openmesh import (
    _print_capabilities,
    _print_ecosystem,
    _print_evaluation,
    _print_federation,
    _print_federation_inspection,
    _print_federation_peers,
    _print_mcp,
    _print_mcp_config,
    _print_plugin_detail,
    _print_plugin_validation,
    _print_plugins,
    _print_snapshot_detail,
    _print_snapshot_diff,
    _print_snapshots,
    _print_query_result,
    _print_replay,
    _print_timeline,
    _print_workflow_inspection,
    _print_workflows,
    _with_db,
)
from src.cli.tui import (
    TuiSnapshot,
    capability_rows,
    edge_detail_rows,
    graph_explorer_rows,
    mcp_config_rows,
    mcp_rows,
    network_edges,
    node_detail_rows,
    query_rows,
    registry_rows,
    replay_rows,
    render_plain,
    ecosystem_rows,
    snapshot_diff_rows,
    snapshot_rows,
    timeline_rows,
    workflow_detail_rows,
    workflow_rows,
)


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


def workflow_test_node() -> dict:
    return {
        "node_id": "workflow:research",
        "node_type": "workflow",
        "name": "Research Workflow",
        "runtime": "langgraph",
        "metadata": {"framework": "LangGraph"},
    }


def tool_test_node() -> dict:
    return {
        "node_id": "tool:web_search",
        "node_type": "tool",
        "name": "Web Search",
        "runtime": "openmesh.sdk",
    }


def mcp_test_node() -> dict:
    return {
        "node_id": "mcp:filesystem",
        "node_type": "mcp_server",
        "name": "Filesystem MCP",
        "runtime": "mcp",
        "metadata": {"transport": "stdio"},
    }


def service_test_node() -> dict:
    return {
        "node_id": "service:claude-code",
        "node_type": "service",
        "name": "Claude Code",
        "runtime": "cli",
    }


def capability_test_node() -> dict:
    return {
        "node_id": "capability:read_file",
        "node_type": "capability",
        "name": "read_file",
        "runtime": "mcp",
    }


def record_from_event(event: dict, **overrides):
    values = {
        "event_id": event["event_id"],
        "event_type": event["event_type"],
        "timestamp": datetime.fromisoformat(
            event["timestamp"].replace("Z", "+00:00")
        ).replace(tzinfo=None),
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
    async def test_cli_db_commands_bootstrap_schema_quietly(self):
        calls = []

        class SessionContext:
            async def __aenter__(self):
                calls.append(("session", "enter"))
                return "db"

            async def __aexit__(self, exc_type, exc, traceback):
                calls.append(("session", "exit"))
                return False

        async def fake_init_db(*, announce=True):
            calls.append(("init", announce))

        async def handler(db):
            calls.append(("handler", db))
            return 0

        with (
            patch("src.cli.openmesh.init_db", fake_init_db),
            patch("src.cli.openmesh.AsyncSessionLocal", lambda: SessionContext()),
        ):
            result = await _with_db(handler)

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                ("init", False),
                ("session", "enter"),
                ("handler", "db"),
                ("session", "exit"),
            ],
        )

    def make_event(self, event_type="message.sent"):
        return make_openmesh_event(
            event_type,
            agent_node("agent-a", "Research Agent", "researcher"),
            {"message": "hello"},
            target=agent_node("agent-b", "Coding Agent", "engineer"),
            session_id="sess_test",
            trace_id="trace_test",
        )

    async def test_provider_settings_read_llm_api_keys(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "openai-key",
                "ANTHROPIC_API_KEY": "anthropic-key",
                "OPENROUTER_API_KEY": "openrouter-key",
                "OPENAI_MODEL": "openai-model",
                "ANTHROPIC_MODEL": "anthropic-model",
                "OPENROUTER_MODEL": "openrouter-model",
                "OLLAMA_BASE_URL": "http://localhost:11434",
                "LMSTUDIO_BASE_URL": "http://localhost:1234",
                "VLLM_BASE_URL": "http://localhost:8000",
                "OLLAMA_MODEL": "hermes3",
                "LMSTUDIO_MODEL": "qwen3",
                "VLLM_MODEL": "deepseek-r1",
            },
        ):
            settings = load_provider_settings()

        self.assertEqual(settings.openai_api_key, "openai-key")
        self.assertEqual(settings.anthropic_api_key, "anthropic-key")
        self.assertEqual(settings.openrouter_api_key, "openrouter-key")
        self.assertEqual(settings.openai_model, "openai-model")
        self.assertEqual(settings.anthropic_model, "anthropic-model")
        self.assertEqual(settings.openrouter_model, "openrouter-model")
        self.assertEqual(settings.ollama_base_url, "http://localhost:11434")
        self.assertEqual(settings.lmstudio_base_url, "http://localhost:1234")
        self.assertEqual(settings.vllm_base_url, "http://localhost:8000")
        self.assertEqual(settings.ollama_model, "hermes3")
        self.assertEqual(settings.lmstudio_model, "qwen3")
        self.assertEqual(settings.vllm_model, "deepseek-r1")

    async def test_research_demo_emits_llm_trace_and_graph_events(self):
        class FakeProvider:
            provider_id = "openai"
            display_name = "OpenAI"
            env_var = "OPENAI_API_KEY"
            model = "gpt-test"
            configured = True
            endpoint = ""
            is_local = False

            async def complete(self, **kwargs):
                self.kwargs = kwargs
                return LLMResponse(
                    provider=self.provider_id,
                    model=self.model,
                    content="Finding one\nFinding two\nFinding three",
                    usage={"input_tokens": 10, "output_tokens": 12},
                    latency_ms=25,
                )

        async def fake_complete_session(*args, **kwargs):
            return None

        db = FakeSessionStore()
        provider = FakeProvider()
        with patch(
            "src.services.llm_demo.complete_openmesh_session",
            fake_complete_session,
        ):
            result = await run_research_demo(
                db,
                query="How should OpenMesh observe agent ecosystems?",
                provider=provider,  # type: ignore[arg-type]
            )

        records = [record for record in db.added if hasattr(record, "event_type")]
        event_types = [record.event_type for record in records]
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["model"], "gpt-test")
        self.assertEqual(
            event_types,
            [
                "trace.started",
                "llm.request",
                "llm.response",
                "tool.call.started",
                "tool.call.completed",
                "trace.completed",
            ],
        )
        self.assertEqual({record.trace_id for record in records}, {result["trace_id"]})
        graph = reduce_graph_state(records)
        model_nodes = [node for node in graph["nodes"] if node["type"] == "model"]
        self.assertEqual(len(model_nodes), 1)
        uses_edges = [
            edge
            for edge in graph["edges"]
            if edge["type"] == "uses" and edge["target"] == model_nodes[0]["id"]
        ]
        self.assertTrue(uses_edges)
        self.assertEqual(uses_edges[0]["validation_status"], "valid")
        self.assertIn(result["trace_id"], uses_edges[0]["provenance"]["trace_ids"])

    async def test_research_demo_emits_local_model_served_by_provider(self):
        class FakeLocalProvider:
            provider_id = "ollama"
            display_name = "Ollama"
            env_var = "OLLAMA_BASE_URL"
            model = "hermes3"
            configured = True
            endpoint = "http://localhost:11434"
            is_local = True

            async def complete(self, **kwargs):
                return LLMResponse(
                    provider=self.provider_id,
                    model=self.model,
                    content="Local finding",
                    usage={"eval_count": 20},
                    latency_ms=100,
                    tokens_per_second=200.0,
                )

        async def fake_complete_session(*args, **kwargs):
            return None

        db = FakeSessionStore()
        with patch(
            "src.services.llm_demo.complete_openmesh_session",
            fake_complete_session,
        ):
            result = await run_research_demo(
                db,
                query="Map local model ecosystems",
                provider=FakeLocalProvider(),  # type: ignore[arg-type]
                model="hermes3",
            )

        records = [record for record in db.added if hasattr(record, "event_type")]
        event_types = [record.event_type for record in records]
        self.assertIn("model.loaded", event_types)
        self.assertEqual(result["tokens_per_second"], 200.0)
        graph = reduce_graph_state(records)
        served_by_edges = [edge for edge in graph["edges"] if edge["type"] == "served_by"]
        self.assertEqual(len(served_by_edges), 1)
        self.assertEqual(served_by_edges[0]["validation_status"], "valid")
        self.assertIn(result["trace_id"], served_by_edges[0]["provenance"]["trace_ids"])

    async def test_local_llm_metrics_derives_latency_and_uptime(self):
        provider_statuses = [
            ProviderStatus(
                provider="ollama",
                name="Ollama",
                configured=True,
                connected=True,
                status="connected",
                message="connected",
                endpoint="http://localhost:11434",
                local=True,
            ),
            ProviderStatus(
                provider="vllm",
                name="vLLM",
                configured=True,
                connected=False,
                status="failed",
                message="unavailable",
                endpoint="http://localhost:8000",
                local=True,
            ),
        ]
        local_models = [
            ProviderModel(
                provider="ollama",
                provider_name="Ollama",
                model="hermes3",
                endpoint="http://localhost:11434",
            )
        ]

        async def fake_discover():
            return provider_statuses

        async def fake_models():
            return local_models

        db = FakeAsyncSession()
        event = make_openmesh_event(
            "llm.response",
            {
                "node_id": "agent:local",
                "node_type": "agent",
                "name": "Local Agent",
                "runtime": "test",
            },
            {"provider": "ollama", "model": "hermes3", "local": True},
            target={
                "node_id": "model:ollama:hermes3",
                "node_type": "model",
                "name": "hermes3",
                "runtime": "ollama",
                "metadata": {
                    "provider": "ollama",
                    "endpoint": "http://localhost:11434",
                    "local": True,
                },
            },
            metrics={"latency_ms": 100, "tokens_per_second": 200.0},
        )
        records = [record_from_event(event)]

        async def fake_list_events(*args, **kwargs):
            return records

        with (
            patch("src.services.local_llm_metrics.list_openmesh_events", fake_list_events),
            patch("src.services.local_llm_metrics.discover_local_providers", fake_discover),
            patch("src.services.local_llm_metrics.list_local_models", fake_models),
        ):
            metrics = await get_local_llm_metrics(db)  # type: ignore[arg-type]

        self.assertEqual(metrics["active_model_count"], 1)
        self.assertEqual(metrics["average_latency_ms"], 100)
        self.assertEqual(metrics["average_tokens_per_second"], 200)
        self.assertEqual(metrics["provider_uptime"]["connected"], 1)
        self.assertEqual(metrics["provider_uptime"]["total"], 2)

    def make_exploration_graph(self):
        pairs = [
            (
                "workflow.started",
                agent_node("agent-a", "Research Agent"),
                workflow_test_node(),
            ),
            (
                "tool.call.started",
                agent_node("agent-a", "Research Agent"),
                tool_test_node(),
            ),
            ("tool.connected", tool_test_node(), mcp_test_node()),
            ("tool.call.completed", workflow_test_node(), tool_test_node()),
            ("mcp.config.discovered", service_test_node(), mcp_test_node()),
            ("mcp.capability.discovered", mcp_test_node(), capability_test_node()),
        ]
        records = []
        for index, (event_type, source, target) in enumerate(pairs):
            event = self.make_event(event_type)
            event["source"] = source
            event["target"] = target
            records.append(
                record_from_event(
                    event,
                    timestamp=datetime(2026, 6, 3, 10, index, 0),
                )
            )
        return reduce_graph_state(records)

    def make_snapshot_payload(
        self,
        snapshot_id: str,
        *,
        created_at: str,
        nodes: list[dict],
        relationships: list[dict],
        workflows: list[dict] | None = None,
        mcp_servers: list[dict] | None = None,
        capabilities: list[dict] | None = None,
        traces: list[dict] | None = None,
        sessions: list[dict] | None = None,
    ) -> dict:
        workflows = workflows or []
        mcp_servers = mcp_servers or []
        capabilities = capabilities or []
        traces = traces or []
        sessions = sessions or []
        counts = {
            "events": sum(item.get("event_count", 0) for item in nodes),
            "traces": len(traces),
            "sessions": len(sessions),
            "nodes": len(nodes),
            "edges": len(relationships),
            "relationships": len(relationships),
            "agents": len([item for item in nodes if item.get("type") == "agent"]),
            "tools": len([item for item in nodes if item.get("type") == "tool"]),
            "workflows": len(workflows),
            "processes": len([item for item in nodes if item.get("type") == "process"]),
            "services": len([item for item in nodes if item.get("type") == "service"]),
            "mcp_servers": len(mcp_servers),
            "capabilities": len(capabilities),
        }
        return {
            "snapshot_id": snapshot_id,
            "schema_version": "0.1",
            "created_at": created_at,
            "counts": counts,
            "graph_statistics": {
                "node_count": len(nodes),
                "edge_count": len(relationships),
                "node_types": self._count_by_type(nodes),
                "relationship_types": self._count_by_type(relationships),
                "validation_status": "OK",
            },
            "ecosystem_statistics": {
                "entity_count": len(nodes),
                "relationship_count": len(relationships),
                "groups": {"workflows": len(workflows)},
                "validation_status": "OK",
            },
            "contents": {
                "agents": [item for item in nodes if item.get("type") == "agent"],
                "tools": [item for item in nodes if item.get("type") == "tool"],
                "workflows": workflows,
                "processes": [item for item in nodes if item.get("type") == "process"],
                "services": [item for item in nodes if item.get("type") == "service"],
                "mcp_servers": mcp_servers,
                "mcp_configs": [],
                "capabilities": capabilities,
                "relationships": relationships,
                "graph_provenance": {
                    item["id"]: item.get("provenance", {}) for item in relationships
                },
                "traces": traces,
                "sessions": sessions,
                "graph": {"nodes": nodes, "edges": relationships},
                "discovery": {},
                "ecosystem": {},
                "events": [],
                "registry": {},
            },
        }

    def make_query_context(self) -> dict:
        agent = agent_node("agent-a", "Research Agent", "researcher")
        tool = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "mcp",
        }
        workflow = workflow_node(
            WorkflowEntry(
                workflow="Research Flow",
                framework="LangGraph",
                source="examples/langgraph_basic.py",
            )
        )
        mcp = mcp_server_node(
            name="Search MCP",
            transport="stdio",
            endpoint="stdio://search",
        )
        capability = capability_node(
            MCPCapabilityEntry(
                server="Search MCP",
                capability="search",
                category="web",
            )
        )
        events = [
            make_openmesh_event(
                "tool.call.started",
                agent,
                {"tool": "web_search"},
                target=tool,
                session_id="sess_query",
                trace_id="trace_query_agent",
            ),
            make_openmesh_event(
                "workflow.mcp.connected",
                workflow,
                {"workflow": "Research Flow", "server": "Search MCP"},
                target=mcp,
                session_id="sess_query",
                trace_id="trace_query_workflow",
            ),
            make_openmesh_event(
                "mcp.capability.discovered",
                mcp,
                {"server": "Search MCP", "capability": "search", "category": "web"},
                target=capability,
                session_id="sess_query",
                trace_id="trace_query_workflow",
            ),
        ]
        records = [
            record_from_event(event, timestamp=datetime(2026, 6, 3, 10, index, 0))
            for index, event in enumerate(events)
        ]
        sessions = [
            SimpleNamespace(
                session_id="sess_query",
                command="python query_agent.py",
                started_at=datetime(2026, 6, 3, 10, 0, 0),
                ended_at=datetime(2026, 6, 3, 10, 3, 0),
                status="completed",
                exit_code=0,
            )
        ]
        before = self.make_snapshot_payload(
            "snap_query_before",
            created_at="2026-06-03T09:55:00Z",
            nodes=[{"id": agent["node_id"], "type": "agent", "name": agent["name"]}],
            relationships=[],
            traces=[{"trace_id": "trace_query_agent"}],
            sessions=[{"session_id": "sess_query"}],
        )
        after = self.make_snapshot_payload(
            "snap_query_after",
            created_at="2026-06-03T10:05:00Z",
            nodes=[
                {"id": agent["node_id"], "type": "agent", "name": agent["name"]},
                {"id": tool["node_id"], "type": "tool", "name": tool["name"]},
                {
                    "id": workflow["node_id"],
                    "type": "workflow",
                    "name": workflow["name"],
                },
                {"id": mcp["node_id"], "type": "mcp_server", "name": mcp["name"]},
                {
                    "id": capability["node_id"],
                    "type": "capability",
                    "name": capability["name"],
                },
            ],
            relationships=[
                {
                    "id": f"{agent['node_id']}:uses:{tool['node_id']}",
                    "source": agent["node_id"],
                    "target": tool["node_id"],
                    "type": "uses",
                    "event_count": 1,
                }
            ],
            workflows=[
                {
                    "id": workflow["node_id"],
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                }
            ],
            mcp_servers=[{"id": mcp["node_id"], "server": "Search MCP"}],
            capabilities=[{"server": "Search MCP", "capability": "search"}],
            traces=[
                {"trace_id": "trace_query_agent"},
                {"trace_id": "trace_query_workflow"},
            ],
            sessions=[{"session_id": "sess_query"}],
        )
        grouped: dict[str, list] = {}
        for record in records:
            grouped.setdefault(record.trace_id, []).append(record)
        return {
            "records": records,
            "graph": reduce_graph_state(records),
            "discovery": build_discovery(records),
            "traces": [
                trace_summary(trace_id, trace_records)
                for trace_id, trace_records in grouped.items()
            ],
            "sessions": [session_to_dict(record) for record in sessions],
            "snapshots": [before, after],
        }

    def _count_by_type(self, items: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            item_type = item.get("type") or "unknown"
            counts[item_type] = counts.get(item_type, 0) + 1
        return counts

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
            links=[
                {
                    "trace_id": "trace_parent",
                    "span_id": "span_parent",
                    "relationship": "follows_from",
                }
            ],
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

    async def test_collector_rejects_unknown_node_types_and_invalid_metadata(self):
        collector = OpenMeshCollector()
        unknown = self.make_event()
        unknown["source"] = {
            "node_id": "unknown:a",
            "node_type": "unknown",
            "name": "Unknown A",
        }
        invalid_metadata = self.make_event()
        invalid_metadata["source"]["metadata"] = []

        with self.assertRaises(HTTPException) as unknown_error:
            await collector.accept(FakeAsyncSession(), unknown, broadcast=False)
        with self.assertRaises(HTTPException) as metadata_error:
            await collector.accept(
                FakeAsyncSession(), invalid_metadata, broadcast=False
            )

        self.assertIn("Unknown node type", unknown_error.exception.detail)
        self.assertIn("metadata must be an object", metadata_error.exception.detail)

    def test_trace_reconstruction_groups_agents_and_status(self):
        event_a = self.make_event("process.started")
        event_b = self.make_event("process.completed")
        records = [
            SimpleNamespace(
                event_id=event["event_id"],
                event_type=event["event_type"],
                timestamp=datetime.fromisoformat(
                    event["timestamp"].replace("Z", "+00:00")
                ).replace(tzinfo=None),
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
        self.assertTrue(
            all(edge["trace_id"] == "trace_test" for edge in graph["edges"])
        )
        self.assertTrue(all(edge["observation_count"] == 1 for edge in graph["edges"]))
        self.assertTrue(
            all(edge["validation_status"] == "valid" for edge in graph["edges"])
        )
        self.assertTrue(all(edge["relationship_definition"] for edge in graph["edges"]))

    def test_graph_reduction_exposes_relationship_provenance(self):
        first = self.make_event("process.started")
        first["source"] = CLI_NODE
        first["target"] = process_node("sess_test", "python hello.py")
        second = self.make_event("process.started")
        second["source"] = CLI_NODE
        second["target"] = process_node("sess_test", "python hello.py")
        second["trace_id"] = "trace_followup"
        second["span_id"] = "span_followup"
        records = [
            record_from_event(first, timestamp=datetime(2026, 6, 3, 10, 0, 0)),
            record_from_event(second, timestamp=datetime(2026, 6, 3, 10, 1, 0)),
        ]

        graph = reduce_graph_state(records)
        edge = graph["edges"][0]
        provenance = edge["provenance"]

        self.assertEqual(edge["type"], "spawns")
        self.assertEqual(edge["event_count"], 2)
        self.assertEqual(edge["observation_count"], 2)
        self.assertEqual(provenance["relationship_type"], "spawns")
        self.assertEqual(provenance["source"], "openmesh.cli")
        self.assertEqual(provenance["target"], "process:sess_test")
        self.assertEqual(
            provenance["event_ids"], [first["event_id"], second["event_id"]]
        )
        self.assertEqual(provenance["trace_ids"], ["trace_test", "trace_followup"])
        self.assertEqual(provenance["span_ids"], [first["span_id"], "span_followup"])
        self.assertEqual(provenance["first_seen"], "2026-06-03T10:00:00Z")
        self.assertEqual(provenance["last_seen"], "2026-06-03T10:01:00Z")
        self.assertEqual(len(provenance["observations"]), 2)
        self.assertEqual(
            provenance["observations"][0]["source"]["name"], "OpenMesh CLI"
        )
        self.assertEqual(
            provenance["observations"][1]["target"]["name"], "python hello.py"
        )
        self.assertEqual(graph["validation"]["missing_provenance"], [])

    def test_graph_node_inspection_explains_node_relationships(self):
        started = self.make_event("process.started")
        started["source"] = CLI_NODE
        started["target"] = process_node("sess_test", "python hello.py")
        completed = self.make_event("process.completed")
        completed["source"] = started["target"]
        completed["target"] = command_node("python hello.py")
        graph = reduce_graph_state(
            [
                record_from_event(started, timestamp=datetime(2026, 6, 3, 10, 0, 0)),
                record_from_event(completed, timestamp=datetime(2026, 6, 3, 10, 1, 0)),
            ]
        )

        inspection = inspect_graph_node(graph, "sess_test")

        self.assertIsNotNone(inspection)
        assert inspection is not None
        self.assertEqual(inspection["node_id"], "process:sess_test")
        self.assertEqual(inspection["node_type"], "process")
        self.assertEqual(inspection["first_seen"], "2026-06-03T10:00:00Z")
        self.assertEqual(inspection["last_seen"], "2026-06-03T10:01:00Z")
        self.assertEqual(inspection["event_count"], 2)
        self.assertEqual(inspection["relationship_count"], 2)
        self.assertEqual(len(inspection["incoming_relationships"]), 1)
        self.assertEqual(len(inspection["outgoing_relationships"]), 1)
        self.assertEqual(inspection["trace_ids"], ["trace_test"])
        self.assertEqual(inspection["session_ids"], ["sess_test"])
        self.assertEqual(
            inspection["provenance"]["event_ids"],
            [started["event_id"], completed["event_id"]],
        )
        self.assertEqual(
            inspection["outgoing_relationships"][0]["provenance"]["event_ids"],
            [completed["event_id"]],
        )

    def test_graph_exploration_selects_and_traverses_nodes(self):
        graph = self.make_exploration_graph()

        selection = select_graph_node(graph, "agent-a")
        traversal = traverse_graph_relationships(
            graph,
            "agent-a",
            direction="outgoing",
            relationship_type="uses",
        )

        self.assertIsNotNone(selection)
        assert selection is not None
        self.assertEqual(selection["node_type"], "agent")
        self.assertIn(
            "tool:web_search",
            {target["node_id"] for target in selection["navigation_targets"]},
        )
        self.assertIsNotNone(traversal)
        assert traversal is not None
        self.assertEqual(traversal["relationship_count"], 1)
        self.assertEqual(traversal["relationships"][0]["node_id"], "tool:web_search")
        self.assertEqual(traversal["relationships"][0]["relationship_type"], "uses")

    def test_graph_exploration_both_direction_only_returns_adjacent_edges(self):
        graph = self.make_exploration_graph()

        traversal = traverse_graph_relationships(graph, "agent-a", direction="both")

        self.assertIsNotNone(traversal)
        assert traversal is not None
        node_ids = {
            relationship["node_id"] for relationship in traversal["relationships"]
        }
        self.assertIn("workflow:research", node_ids)
        self.assertIn("tool:web_search", node_ids)
        self.assertNotIn("mcp:filesystem", node_ids)
        self.assertEqual(traversal["relationship_count"], len(node_ids))

    def test_graph_exploration_expands_neighborhood_and_filters_graph(self):
        graph = self.make_exploration_graph()

        neighborhood = expand_graph_neighborhood(graph, "agent-a", depth=2)
        filtered = filter_graph(graph, node_types={"agent"})

        self.assertIsNotNone(neighborhood)
        assert neighborhood is not None
        node_ids = {node["id"] for node in neighborhood["nodes"]}
        self.assertIn("agent-a", node_ids)
        self.assertIn("workflow:research", node_ids)
        self.assertIn("tool:web_search", node_ids)
        self.assertGreaterEqual(neighborhood["statistics"]["edge_count"], 2)
        self.assertEqual(filtered["filters"]["node_types"], ["agent"])
        self.assertIn(
            "tool:web_search",
            {node["id"] for node in filtered["nodes"]},
        )
        self.assertGreaterEqual(filtered["statistics"]["edge_count"], 1)

    def test_graph_search_finds_nodes_and_relationships(self):
        graph = self.make_exploration_graph()

        result = search_graph(graph, "filesystem")

        self.assertGreaterEqual(result["count"], 2)
        self.assertIn(
            "mcp:filesystem",
            {node["node_id"] for node in result["nodes"]},
        )
        self.assertIn(
            "connects_to",
            {edge["relationship_type"] for edge in result["relationships"]},
        )

    def test_graph_statistics_summarizes_exploration_graph(self):
        graph = self.make_exploration_graph()

        statistics = graph_statistics(graph)

        self.assertGreaterEqual(statistics["node_count"], 6)
        self.assertGreaterEqual(statistics["edge_count"], 6)
        self.assertEqual(statistics["node_types"]["agent"], 1)
        self.assertEqual(statistics["relationship_types"]["uses"], 2)
        self.assertGreaterEqual(statistics["validation_statuses"]["valid"], 6)

    def test_relationship_registry_maps_protocol_events_to_canonical_types(self):
        relationship_types = {item["type"] for item in relationship_registry()}

        self.assertIn("uses", relationship_types)
        self.assertIn("spawns", relationship_types)
        self.assertIn("federates_with", relationship_types)
        self.assertIn("collaborates_with", relationship_types)
        self.assertEqual(
            node_type_definition("federation_node")["display_name"],
            "Federation Node",
        )
        self.assertEqual(relationship_definition("uses")["name"], "uses")
        self.assertEqual(
            validate_relationship(
                "federates_with", "federation_node", "federation_node"
            )["status"],
            "valid",
        )
        self.assertEqual(
            relationship_type_for(
                "tool.call.started", source_type="agent", target_type="tool"
            ),
            "uses",
        )
        self.assertEqual(
            relationship_type_for(
                "process.started", source_type="service", target_type="process"
            ),
            "spawns",
        )
        self.assertEqual(
            relationship_type_for(
                "collaboration.created", source_type="agent", target_type="agent"
            ),
            "collaborates_with",
        )

    async def test_local_simulation_persists_protocol_and_legacy_data(self):
        db = FakeAsyncSession()

        summary = await run_local_simulation(
            db, agent_count=10, event_count=120, seed=7, broadcast=False
        )

        records = [record for record in db.added if getattr(record, "event_id", None)]
        legacy_types = {record.__class__.__name__ for record in db.added}
        graph = reduce_graph_state(records)
        discovery = build_discovery(records)
        relationship_types = {edge["relationship_type"] for edge in graph["edges"]}

        self.assertEqual(summary["agents"], 10)
        self.assertEqual(summary["events"], 120)
        self.assertGreaterEqual(summary["tool_calls"], 20)
        self.assertGreaterEqual(summary["traces"], 3)
        self.assertEqual(len(records), 120)
        self.assertIn("Guild", legacy_types)
        self.assertIn("Agent", legacy_types)
        self.assertIn("Post", legacy_types)
        self.assertIn("Message", legacy_types)
        self.assertIn("WikiPage", legacy_types)
        self.assertIn("OpenMeshSessionRecord", legacy_types)
        for expected in (
            "uses",
            "runs",
            "communicates_with",
            "collaborates_with",
            "delegates_to",
            "transitions_to",
            "modifies",
        ):
            self.assertIn(expected, relationship_types)
        self.assertGreaterEqual(len(discovery["agents"]), 10)
        self.assertGreaterEqual(len(discovery["tools"]), 4)
        self.assertGreaterEqual(len(discovery["workflows"]), 3)

    def test_federation_registry_builds_metadata_only_views(self):
        event = self.make_event("message.sent")
        records = [record_from_event(event, timestamp=datetime(2026, 6, 3, 10, 0, 0))]
        registry = build_federation_registry(
            records,
            [],
            [],
            peers=[
                {
                    "instance_id": "remote-a",
                    "name": "Remote A",
                    "organization": "research",
                    "cluster": "agents",
                    "endpoint": "https://remote-a.example/openmesh",
                }
            ],
        )
        peer_query = query_federation_registry(registry, "federation peers")

        self.assertEqual(registry["local_node"]["type"], "federation_node")
        self.assertEqual(registry["peers"][0]["id"], "federation:remote-a")
        self.assertEqual(registry["relationships"][0]["type"], "federates_with")
        self.assertTrue(registry["policy"]["metadata_only"])
        self.assertFalse(registry["policy"]["remote_execution"])
        self.assertEqual(registry["snapshot"]["counts"]["instances"], 2)
        self.assertEqual(registry["timeline"]["scope"], "federation")
        self.assertTrue(registry["replay"]["source"]["metadata_only"])
        self.assertEqual(peer_query["count"], 1)

    def test_federation_discovery_parses_json_and_csv_peers(self):
        json_peers = discover_federation_peers(
            '[{"peer_id":"remote-json","endpoint":"https://remote.example"}]'
        )
        csv_peers = discover_federation_peers(
            "https://one.example, https://two.example"
        )

        self.assertEqual(json_peers[0]["instance_id"], "remote-json")
        self.assertEqual(len(csv_peers), 2)
        self.assertEqual(csv_peers[0]["status"], "configured")

    def test_evaluation_synthetic_ecosystem_builds_graph_inputs(self):
        synthetic = generate_synthetic_ecosystem(14)
        graph = reduce_graph_state(synthetic["records"])

        self.assertEqual(len(synthetic["nodes"]), 14)
        self.assertEqual(len(synthetic["events"]), 14)
        self.assertEqual(synthetic["trace_count"], 1)
        self.assertGreaterEqual(len(graph["nodes"]), 14)
        self.assertGreater(len(graph["edges"]), 0)

    async def test_evaluation_suite_measures_core_operations(self):
        report = await run_evaluation_suite([14], include_ingestion=True)
        benchmark = report["benchmarks"][0]
        metric_names = {metric["name"] for metric in benchmark["metrics"]}

        self.assertEqual(report["schema_version"], "0.1")
        self.assertEqual(benchmark["node_count"], 14)
        self.assertEqual(benchmark["event_count"], 14)
        self.assertIn("event_ingestion", metric_names)
        self.assertIn("trace_reconstruction", metric_names)
        self.assertIn("graph_reduction", metric_names)
        self.assertIn("inspection", metric_names)
        self.assertIn("query_engine", metric_names)
        self.assertIn("snapshot_creation", metric_names)
        self.assertIn("snapshot_diff", metric_names)
        self.assertIn("timeline_generation", metric_names)
        self.assertIn("replay_generation", metric_names)
        self.assertIn("federation_aggregation", metric_names)
        for metric in benchmark["metrics"]:
            self.assertIn("elapsed_ms", metric)
            self.assertIn("peak_memory_bytes", metric)
            self.assertIn("peak_memory_mb", metric)

        query_metric = next(
            metric
            for metric in benchmark["metrics"]
            if metric["name"] == "query_engine"
        )
        self.assertEqual(query_metric["details"]["queries"], 4)
        self.assertGreaterEqual(query_metric["details"]["max_latency_ms"], 0)

    def test_relationship_registry_validates_types_and_pairs(self):
        valid = validate_relationship("uses", "agent", "tool")
        mcp_connection = validate_relationship("connects_to", "agent", "mcp_server")
        mcp_capability = validate_relationship("exposes", "mcp_server", "capability")
        invalid_type = validate_relationship("unknown", "agent", "tool")
        invalid_pair = validate_relationship("uses", "tool", "service")

        self.assertEqual(valid["status"], "valid")
        self.assertEqual(mcp_connection["status"], "valid")
        self.assertEqual(mcp_capability["status"], "valid")
        self.assertEqual(invalid_type["errors"][0]["code"], "invalid_relationship_type")
        self.assertEqual(
            {error["code"] for error in invalid_pair["errors"]},
            {"invalid_source_type", "invalid_target_type"},
        )

    def test_node_type_registry_validates_known_and_unknown_nodes(self):
        valid = validate_node(
            {
                "node_id": "agent:a",
                "node_type": "agent",
                "name": "Agent A",
                "metadata": {"role": "researcher"},
            }
        )
        unknown = validate_node(
            {"node_id": "thing:a", "node_type": "thing", "name": "Thing A"}
        )
        missing = validate_node({"node_type": "agent", "name": ""})
        invalid_metadata = validate_node(
            {
                "node_id": "agent:b",
                "node_type": "agent",
                "name": "Agent B",
                "metadata": [],
            }
        )

        self.assertEqual(node_type_definition("agent")["display_name"], "Agent")
        self.assertIn("mcp_server", {item["type"] for item in node_type_registry()})
        self.assertEqual(
            node_type_validation_metadata()["required_identifiers"],
            ("node_id", "node_type", "name"),
        )
        self.assertEqual(valid["status"], "valid")
        self.assertEqual(unknown["errors"][0]["code"], "unknown_node_type")
        self.assertEqual(missing["errors"][0]["code"], "missing_required_identifiers")
        self.assertEqual(invalid_metadata["errors"][0]["code"], "invalid_node_metadata")

    def test_registry_versions_and_compatibility_rules(self):
        versions = registry_versions()
        supported = validate_registry_versions()
        unsupported = validate_registry_versions(node_registry_version="9.0.0")
        deprecated = compatibility_status(
            deprecated_nodes=[
                {"type": "legacy_agent", "deprecation_message": "Use agent"}
            ]
        )

        self.assertEqual(versions["node_registry"], NODE_REGISTRY_VERSION)
        self.assertEqual(
            versions["relationship_registry"], RELATIONSHIP_REGISTRY_VERSION
        )
        self.assertEqual(supported["status"], "ok")
        self.assertEqual(
            unsupported["errors"][0]["code"], "unsupported_registry_version"
        )
        self.assertEqual(deprecated["severity"], "WARNING")

    def test_registry_validation_reports_deprecated_definitions(self):
        with (
            patch.dict(
                NODE_TYPES,
                {
                    "legacy_agent": NodeType(
                        "legacy_agent",
                        "Legacy Agent",
                        "Deprecated test node.",
                        "agents",
                        (),
                        deprecated_in="0.1.0",
                    )
                },
            ),
            patch.dict(
                RELATIONSHIP_TYPES,
                {
                    "legacy_uses": RelationshipType(
                        "legacy_uses",
                        "legacy uses",
                        "Deprecated test relationship.",
                        ("legacy_agent",),
                        ("tool",),
                        deprecated_in="0.1.0",
                    )
                },
            ),
        ):
            node_validation = validate_node(
                {"node_id": "legacy:a", "node_type": "legacy_agent", "name": "Legacy A"}
            )
            relationship_validation = validate_relationship(
                "legacy_uses", "legacy_agent", "tool"
            )

        self.assertEqual(node_validation["status"], "warning")
        self.assertEqual(node_validation["warnings"][0]["code"], "deprecated_node_type")
        self.assertEqual(relationship_validation["status"], "warning")
        self.assertEqual(
            relationship_validation["warnings"][0]["code"],
            "deprecated_relationship_type",
        )

    def test_registry_compatibility_diagnostics_report_unsupported_versions(self):
        diagnostics = build_registry_compatibility_diagnostics(
            [], node_registry_version="9.0.0"
        )

        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertEqual(
            diagnostics["detail"]["errors"][0]["code"], "unsupported_registry_version"
        )

    def test_registry_status_exposes_versions_definitions_and_rules(self):
        status = build_registry_status([])

        self.assertEqual(status["compatibility"]["severity"], "INFO")
        self.assertIn("node_registry", status["versions"])
        self.assertGreater(len(status["node_definitions"]), 0)
        self.assertGreater(len(status["relationship_definitions"]), 0)
        self.assertIn("additive_changes", status["rules"])

    async def test_mcp_registration_uses_collector_and_metadata_only(self):
        db = FakeAsyncSession()

        event = await register_mcp_server(
            db,
            name="Filesystem MCP",
            transport="stdio",
            endpoint="stdio://filesystem",
            version="1.0.0",
            broadcast=False,
        )

        self.assertEqual(event["event_type"], "mcp.server.discovered")
        self.assertEqual(event["target"]["node_type"], "mcp_server")
        self.assertEqual(event["target"]["metadata"]["transport"], "stdio")
        self.assertEqual(event["target"]["metadata"]["endpoint"], "stdio://filesystem")
        self.assertEqual(len(db.added), 1)

    def test_mcp_registry_graph_and_discovery_are_event_derived(self):
        mcp_node = mcp_server_node(
            name="Filesystem MCP",
            transport="stdio",
            endpoint="stdio://filesystem",
            version="1.0.0",
        )
        event = make_openmesh_event(
            "mcp.server.discovered",
            agent_node("agent-a", "Research Agent", "researcher"),
            {"server": "Filesystem MCP"},
            target=mcp_node,
            session_id="sess_mcp",
            trace_id="trace_mcp",
        )
        record = record_from_event(event)

        registry = build_mcp_registry([record])
        discovery = build_discovery([record])
        graph = reduce_graph_state([record])

        self.assertEqual(registry[0]["server"], "Filesystem MCP")
        self.assertEqual(registry[0]["transport"], "stdio")
        self.assertTrue(
            any(entry["type"] == "mcp_server" for entry in discovery["services"])
        )
        self.assertEqual(graph["edges"][0]["type"], "connects_to")
        self.assertEqual(graph["edges"][0]["validation_status"], "valid")

    def test_mcp_config_providers_parse_json_and_toml_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_path = root / "claude_desktop_config.json"
            codex_path = root / "config.toml"
            claude_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "filesystem": {
                                "command": "mcp-server-filesystem",
                                "version": "1.0.0",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            codex_path.write_text(
                "[mcp.servers.search]\n"
                'transport = "http"\n'
                'endpoint = "http://localhost:8765/mcp"\n',
                encoding="utf-8",
            )

            discovered = discover_mcp_configs(
                providers=(ClaudeDesktopConfigProvider(), CodexConfigProvider()),
                paths_by_source={
                    "Claude Desktop": [claude_path],
                    "Codex": [codex_path],
                },
            )

        self.assertEqual(len(discovered["issues"]), 0)
        self.assertEqual(
            {entry["server"] for entry in discovered["entries"]},
            {"filesystem", "search"},
        )
        self.assertTrue(
            any(entry["transport"] == "stdio" for entry in discovered["entries"])
        )
        self.assertTrue(
            any(entry["transport"] == "http" for entry in discovered["entries"])
        )

    async def test_mcp_config_registration_creates_defines_edge(self):
        db = FakeAsyncSession()
        entry = MCPConfigEntry(
            source="Codex",
            config_path="/tmp/codex/config.toml",
            server="search",
            transport="http",
            endpoint="http://localhost:8765/mcp",
            version="0.2.0",
        )

        event = await register_mcp_config_entry(db, entry, broadcast=False)
        record = record_from_event(event)
        configs = build_mcp_config_registry([record])
        mcp_servers = build_mcp_registry([record])
        graph = reduce_graph_state([record])

        self.assertEqual(event["event_type"], "mcp.config.discovered")
        self.assertEqual(configs[0]["source"], "Codex")
        self.assertEqual(mcp_servers[0]["server"], "search")
        self.assertEqual(graph["edges"][0]["type"], "defines")
        self.assertEqual(graph["edges"][0]["validation_status"], "valid")
        self.assertEqual(len(db.added), 1)

    def test_mcp_config_validation_detects_duplicates_and_missing_metadata(self):
        validation = validate_mcp_config_entries(
            [
                {
                    "source": "Codex",
                    "config_path": "/tmp/a.toml",
                    "server": "search",
                    "transport": "http",
                    "endpoint": "http://localhost:8765/mcp",
                },
                {
                    "source": "Codex",
                    "config_path": "/tmp/b.toml",
                    "server": "search",
                    "transport": "http",
                    "endpoint": "http://localhost:9999/mcp",
                },
                {
                    "source": "OpenHands",
                    "config_path": "/tmp/openhands.toml",
                    "server": "broken",
                },
            ]
        )

        self.assertEqual(len(validation["duplicates"]), 1)
        self.assertEqual(len(validation["missing_required_metadata"]), 1)

    def test_doctor_mcp_config_diagnostics_reports_integrity_issues(self):
        diagnostics = build_mcp_config_diagnostics(
            [],
            discovered={
                "entries": [
                    {
                        "source": "Codex",
                        "config_path": "/tmp/config.toml",
                        "server": "broken",
                    }
                ],
                "issues": [
                    {
                        "source": "Codex",
                        "config_path": "/tmp/bad.toml",
                        "code": "malformed_config",
                        "message": "bad toml",
                    }
                ],
            },
        )

        self.assertEqual(diagnostics["name"], "MCP Configuration Integrity")
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertEqual(len(diagnostics["detail"]["malformed_configs"]), 1)
        self.assertEqual(len(diagnostics["detail"]["missing_required_metadata"]), 1)

    async def test_mcp_capability_registration_uses_collector_and_metadata_only(self):
        db = FakeAsyncSession()
        entry = MCPCapabilityEntry(
            server="Filesystem MCP",
            capability="read_file",
            description="Read file metadata",
            category="filesystem",
            version="1.0.0",
        )

        event = await register_mcp_capability(db, entry, broadcast=False)

        self.assertEqual(event["event_type"], "mcp.capability.discovered")
        self.assertEqual(event["source"]["node_type"], "mcp_server")
        self.assertEqual(event["target"]["node_type"], "capability")
        self.assertEqual(event["target"]["metadata"]["server"], "Filesystem MCP")
        self.assertEqual(event["target"]["metadata"]["category"], "filesystem")
        self.assertEqual(len(db.added), 1)

    def test_mcp_capability_registry_graph_and_discovery_are_event_derived(self):
        source = mcp_server_node(
            name="Filesystem MCP",
            transport="stdio",
            endpoint="stdio://filesystem",
            version="1.0.0",
        )
        target = capability_node(
            MCPCapabilityEntry(
                server="Filesystem MCP",
                capability="read_file",
                description="Read file metadata",
                category="filesystem",
                version="1.0.0",
            )
        )
        event = make_openmesh_event(
            "mcp.capability.discovered",
            source,
            {
                "server": "Filesystem MCP",
                "capability": "read_file",
                "description": "Read file metadata",
                "category": "filesystem",
                "version": "1.0.0",
            },
            target=target,
            session_id="sess_capability",
            trace_id="trace_capability",
        )
        record = record_from_event(event)

        registry = build_capability_registry([record])
        discovery = build_discovery([record])
        graph = reduce_graph_state([record])

        self.assertEqual(registry[0]["server"], "Filesystem MCP")
        self.assertEqual(registry[0]["capability"], "read_file")
        self.assertTrue(
            any(entry["type"] == "capability" for entry in discovery["capabilities"])
        )
        self.assertEqual(graph["edges"][0]["type"], "exposes")
        self.assertEqual(graph["edges"][0]["validation_status"], "valid")

    def test_mcp_capability_validation_detects_duplicates_and_missing_metadata(self):
        validation = validate_capability_entries(
            [
                {
                    "server": "Filesystem MCP",
                    "capability": "read_file",
                    "category": "filesystem",
                    "metadata": {},
                },
                {
                    "server": "Filesystem MCP",
                    "capability": "read_file",
                    "category": "filesystem",
                    "metadata": {},
                },
                {
                    "server": "Search MCP",
                    "capability": "",
                    "metadata": [],
                },
            ]
        )

        self.assertEqual(len(validation["duplicates"]), 1)
        self.assertEqual(len(validation["missing_required_metadata"]), 1)
        self.assertEqual(len(validation["malformed_metadata"]), 1)

    def test_doctor_capability_diagnostics_reports_integrity_issues(self):
        target = capability_node(
            {
                "server": "Search MCP",
                "capability": "broken_search",
                "metadata": {},
            }
        )
        event = make_openmesh_event(
            "mcp.capability.discovered",
            mcp_server_node(
                name="Search MCP",
                transport="http",
                endpoint="http://localhost:8765/mcp",
            ),
            {"server": "Search MCP", "capability": "broken_search"},
            target=target,
        )

        diagnostics = build_capability_diagnostics([record_from_event(event)])

        self.assertEqual(diagnostics["name"], "Capability Integrity")
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertEqual(len(diagnostics["detail"]["missing_required_metadata"]), 1)

    async def test_workflow_registration_uses_collector_and_metadata_only(self):
        db = FakeAsyncSession()
        entry = WorkflowEntry(
            workflow="Research Flow",
            framework="LangGraph",
            version="0.1.0",
            source="examples/langgraph_basic.py",
        )

        event = await register_workflow(
            db,
            entry,
            source=agent_node("agent:research", "Research Agent", "researcher"),
            broadcast=False,
        )

        self.assertEqual(event["event_type"], "workflow.registered")
        self.assertEqual(event["source"]["node_type"], "agent")
        self.assertEqual(event["target"]["node_type"], "workflow")
        self.assertEqual(event["target"]["metadata"]["framework"], "LangGraph")
        self.assertEqual(
            event["target"]["metadata"]["source"], "examples/langgraph_basic.py"
        )
        self.assertEqual(len(db.added), 1)

    def test_workflow_registry_graph_and_discovery_are_event_derived(self):
        agent = agent_node("agent:research", "Research Agent", "researcher")
        workflow = workflow_node(
            WorkflowEntry(
                workflow="Research Flow",
                framework="LangGraph",
                version="0.1.0",
                source="examples/langgraph_basic.py",
            )
        )
        tool = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "mcp",
        }
        mcp = mcp_server_node(
            name="Search MCP", transport="http", endpoint="http://localhost:8765/mcp"
        )
        events = [
            make_openmesh_event(
                "workflow.registered",
                agent,
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "version": "0.1.0",
                    "source": "examples/langgraph_basic.py",
                },
                target=workflow,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.tool.used",
                workflow,
                {"workflow": "Research Flow", "tool": "web_search"},
                target=tool,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.mcp.connected",
                workflow,
                {"workflow": "Research Flow", "server": "Search MCP"},
                target=mcp,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
        ]
        records = [record_from_event(event) for event in events]

        registry = build_workflow_registry(records)
        discovery = build_discovery(records)
        graph = reduce_graph_state(records)
        edge_types = {edge["type"] for edge in graph["edges"]}

        self.assertEqual(registry[0]["workflow"], "Research Flow")
        self.assertEqual(registry[0]["framework"], "LangGraph")
        self.assertTrue(
            any(entry["type"] == "workflow" for entry in discovery["workflows"])
        )
        self.assertEqual(edge_types, {"runs", "uses", "connects_to"})
        self.assertTrue(
            all(edge["validation_status"] == "valid" for edge in graph["edges"])
        )

    def test_workflow_inspection_reports_participants_and_provenance(self):
        agent = agent_node("agent:research", "Research Agent", "researcher")
        workflow = workflow_node(
            WorkflowEntry(
                workflow="Research Flow",
                framework="LangGraph",
                version="0.1.0",
                source="examples/langgraph_basic.py",
            )
        )
        tool = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "mcp",
        }
        mcp = mcp_server_node(
            name="Search MCP", transport="http", endpoint="http://localhost:8765/mcp"
        )
        service = {
            "node_id": "service:vector-db",
            "node_type": "service",
            "name": "Vector DB",
            "runtime": "http",
        }
        events = [
            make_openmesh_event(
                "workflow.started",
                workflow,
                {"workflow": "Research Flow"},
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.registered",
                agent,
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "version": "0.1.0",
                    "source": "examples/langgraph_basic.py",
                },
                target=workflow,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.tool.used",
                workflow,
                {"workflow": "Research Flow", "tool": "web_search"},
                target=tool,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.mcp.connected",
                workflow,
                {"workflow": "Research Flow", "server": "Search MCP"},
                target=mcp,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.service.connected",
                workflow,
                {"workflow": "Research Flow", "service": "Vector DB"},
                target=service,
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
            make_openmesh_event(
                "workflow.completed",
                workflow,
                {"workflow": "Research Flow"},
                session_id="sess_workflow",
                trace_id="trace_workflow",
            ),
        ]
        records = [
            record_from_event(event, timestamp=datetime(2026, 6, 3, 10, index, 0))
            for index, event in enumerate(events)
        ]
        graph = reduce_graph_state(records)

        inspection = inspect_graph_workflow(graph, "research-flow")

        self.assertIsNotNone(inspection)
        assert inspection is not None
        self.assertEqual(inspection["workflow"], "Research Flow")
        self.assertEqual(inspection["workflow_type"], "LangGraph")
        self.assertEqual(inspection["runtime"], "LangGraph")
        self.assertEqual(inspection["status"], "completed")
        self.assertEqual(inspection["started_at"], "2026-06-03T10:00:00Z")
        self.assertEqual(inspection["ended_at"], "2026-06-03T10:05:00Z")
        self.assertEqual(
            [item["name"] for item in inspection["participating_agents"]],
            ["Research Agent"],
        )
        self.assertEqual(
            [item["name"] for item in inspection["participating_tools"]],
            ["web_search"],
        )
        self.assertEqual(
            [item["name"] for item in inspection["participating_mcp_servers"]],
            ["Search MCP"],
        )
        self.assertEqual(
            [item["name"] for item in inspection["participating_services"]],
            ["Vector DB"],
        )
        self.assertEqual(inspection["trace_ids"], ["trace_workflow"])
        self.assertEqual(inspection["session_ids"], ["sess_workflow"])
        self.assertEqual(len(inspection["provenance"]["event_ids"]), 6)

    def test_ecosystem_snapshot_preserves_graph_registry_and_provenance(self):
        agent = agent_node("agent:research", "Research Agent", "researcher")
        workflow = workflow_node(
            WorkflowEntry(
                workflow="Research Flow",
                framework="LangGraph",
                version="0.1.0",
                source="examples/langgraph_basic.py",
            )
        )
        tool = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "mcp",
        }
        events = [
            make_openmesh_event(
                "workflow.registered",
                agent,
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "version": "0.1.0",
                    "source": "examples/langgraph_basic.py",
                },
                target=workflow,
                session_id="sess_snapshot",
                trace_id="trace_snapshot",
            ),
            make_openmesh_event(
                "workflow.tool.used",
                workflow,
                {"workflow": "Research Flow", "tool": "web_search"},
                target=tool,
                session_id="sess_snapshot",
                trace_id="trace_snapshot",
            ),
        ]
        records = [
            record_from_event(event, timestamp=datetime(2026, 6, 3, 10, index, 0))
            for index, event in enumerate(events)
        ]
        sessions = [
            SimpleNamespace(
                session_id="sess_snapshot",
                command="langgraph basic",
                started_at=datetime(2026, 6, 3, 10, 0, 0),
                ended_at=datetime(2026, 6, 3, 10, 1, 0),
                status="completed",
                exit_code=0,
            )
        ]

        snapshot = build_ecosystem_snapshot(records, sessions)

        self.assertTrue(snapshot["snapshot_id"].startswith("snap_"))
        self.assertEqual(snapshot["counts"]["events"], 2)
        self.assertEqual(snapshot["counts"]["traces"], 1)
        self.assertEqual(snapshot["counts"]["sessions"], 1)
        self.assertEqual(snapshot["counts"]["workflows"], 1)
        self.assertEqual(snapshot["counts"]["tools"], 1)
        self.assertEqual(snapshot["counts"]["edges"], 2)
        self.assertEqual(snapshot["graph_statistics"]["edge_count"], 2)
        self.assertEqual(
            snapshot["graph_statistics"]["relationship_types"], {"runs": 1, "uses": 1}
        )
        self.assertEqual(snapshot["ecosystem_statistics"]["groups"]["workflows"], 1)
        self.assertEqual(
            snapshot["contents"]["graph"]["validation"]["missing_provenance"], []
        )
        first_edge = snapshot["contents"]["relationships"][0]
        self.assertIn(first_edge["id"], snapshot["contents"]["graph_provenance"])
        self.assertIn("trace_snapshot", first_edge["provenance"]["trace_ids"])
        self.assertEqual(
            snapshot["contents"]["traces"][0]["trace_id"], "trace_snapshot"
        )
        self.assertEqual(
            snapshot["contents"]["sessions"][0]["session_id"], "sess_snapshot"
        )

    async def test_snapshot_persistence_stores_metadata_and_payload(self):
        db = FakeAsyncSession()
        snapshot = {
            "snapshot_id": "snap_test",
            "schema_version": "0.1",
            "created_at": "2026-06-03T10:00:00Z",
            "counts": {"events": 2, "traces": 1, "sessions": 1, "nodes": 2, "edges": 1},
            "graph_statistics": {"node_count": 2, "edge_count": 1},
            "ecosystem_statistics": {"entity_count": 2, "relationship_count": 1},
            "contents": {"relationships": [{"id": "edge-1"}]},
        }

        record = await create_openmesh_snapshot(db, snapshot)
        summary = snapshot_record_to_summary(record)
        detail = snapshot_record_to_detail(record)

        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.commits, 1)
        self.assertEqual(record.snapshot_id, "snap_test")
        self.assertEqual(record.event_count, 2)
        self.assertEqual(record.edge_count, 1)
        self.assertEqual(summary["counts"]["nodes"], 2)
        self.assertEqual(detail["contents"]["relationships"][0]["id"], "edge-1")

    def test_snapshot_diff_reports_nodes_relationships_and_deltas(self):
        before = self.make_snapshot_payload(
            "snap_before",
            created_at="2026-06-03T10:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "event_count": 1,
                    "trace_ids": ["trace_a"],
                    "last_seen": "2026-06-03T10:00:00Z",
                },
                {
                    "id": "tool:web_search",
                    "type": "tool",
                    "name": "web_search",
                    "event_count": 1,
                    "trace_ids": ["trace_a"],
                    "last_seen": "2026-06-03T10:00:00Z",
                },
            ],
            relationships=[
                {
                    "id": "agent-a:uses:tool:web_search",
                    "source": "agent-a",
                    "target": "tool:web_search",
                    "type": "uses",
                    "event_count": 1,
                    "observation_count": 1,
                    "trace_ids": ["trace_a"],
                    "event_ids": ["evt_a"],
                    "provenance": {
                        "trace_ids": ["trace_a"],
                        "event_ids": ["evt_a"],
                        "first_seen": "2026-06-03T10:00:00Z",
                        "last_seen": "2026-06-03T10:00:00Z",
                    },
                },
                {
                    "id": "agent-a:connects_to:mcp:old",
                    "source": "agent-a",
                    "target": "mcp:old",
                    "type": "connects_to",
                    "event_count": 1,
                    "observation_count": 1,
                    "trace_ids": ["trace_a"],
                    "event_ids": ["evt_old"],
                    "provenance": {
                        "trace_ids": ["trace_a"],
                        "event_ids": ["evt_old"],
                    },
                },
            ],
            workflows=[
                {
                    "id": "workflow:old",
                    "workflow": "Old Flow",
                    "framework": "LangGraph",
                }
            ],
            mcp_servers=[{"id": "mcp:old", "server": "Old MCP"}],
            capabilities=[{"server": "Old MCP", "capability": "old_tool"}],
            traces=[{"trace_id": "trace_a"}],
            sessions=[{"session_id": "sess_a"}],
        )
        after = self.make_snapshot_payload(
            "snap_after",
            created_at="2026-06-03T11:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "event_count": 2,
                    "trace_ids": ["trace_a", "trace_b"],
                    "last_seen": "2026-06-03T11:00:00Z",
                },
                {
                    "id": "process:pytest",
                    "type": "process",
                    "name": "pytest",
                    "event_count": 1,
                    "trace_ids": ["trace_b"],
                    "last_seen": "2026-06-03T11:00:00Z",
                },
            ],
            relationships=[
                {
                    "id": "agent-a:uses:tool:web_search",
                    "source": "agent-a",
                    "target": "tool:web_search",
                    "type": "uses",
                    "event_count": 2,
                    "observation_count": 2,
                    "trace_ids": ["trace_a", "trace_b"],
                    "event_ids": ["evt_a", "evt_b"],
                    "provenance": {
                        "trace_ids": ["trace_a", "trace_b"],
                        "event_ids": ["evt_a", "evt_b"],
                        "first_seen": "2026-06-03T10:00:00Z",
                        "last_seen": "2026-06-03T11:00:00Z",
                    },
                },
                {
                    "id": "agent-a:spawns:process:pytest",
                    "source": "agent-a",
                    "target": "process:pytest",
                    "type": "spawns",
                    "event_count": 1,
                    "observation_count": 1,
                    "trace_ids": ["trace_b"],
                    "event_ids": ["evt_spawn"],
                    "provenance": {
                        "trace_ids": ["trace_b"],
                        "event_ids": ["evt_spawn"],
                    },
                },
            ],
            workflows=[
                {
                    "id": "workflow:new",
                    "workflow": "New Flow",
                    "framework": "CrewAI",
                }
            ],
            mcp_servers=[{"id": "mcp:new", "server": "New MCP"}],
            capabilities=[{"server": "New MCP", "capability": "new_tool"}],
            traces=[{"trace_id": "trace_a"}, {"trace_id": "trace_b"}],
            sessions=[
                {"session_id": "sess_a"},
                {"session_id": "sess_b"},
            ],
        )

        diff = compare_snapshot_payloads(before, after)

        self.assertEqual(diff["summary"]["nodes_added"], 1)
        self.assertEqual(diff["summary"]["nodes_removed"], 1)
        self.assertEqual(diff["summary"]["nodes_changed"], 1)
        self.assertEqual(diff["summary"]["relationships_added"], 1)
        self.assertEqual(diff["summary"]["relationships_removed"], 1)
        self.assertEqual(diff["summary"]["relationships_changed"], 1)
        self.assertEqual(diff["trace_count_delta"], 1)
        self.assertEqual(diff["session_count_delta"], 1)
        self.assertEqual(diff["summary"]["graph_node_delta"], 0)
        self.assertEqual(diff["summary"]["graph_edge_delta"], 0)
        self.assertEqual(diff["workflows"]["added"][0]["workflow"], "New Flow")
        self.assertEqual(diff["workflows"]["removed"][0]["workflow"], "Old Flow")
        self.assertEqual(diff["mcp_servers"]["added"][0]["server"], "New MCP")
        self.assertEqual(diff["capabilities"]["removed"][0]["capability"], "old_tool")

    def test_snapshot_diff_preserves_relationship_provenance(self):
        before = self.make_snapshot_payload(
            "snap_before",
            created_at="2026-06-03T10:00:00Z",
            nodes=[],
            relationships=[
                {
                    "id": "agent-a:uses:tool:web_search",
                    "source": "agent-a",
                    "target": "tool:web_search",
                    "type": "uses",
                    "event_count": 1,
                    "observation_count": 1,
                    "trace_ids": ["trace_a"],
                    "event_ids": ["evt_a"],
                    "provenance": {
                        "trace_ids": ["trace_a"],
                        "event_ids": ["evt_a"],
                    },
                }
            ],
        )
        after = self.make_snapshot_payload(
            "snap_after",
            created_at="2026-06-03T11:00:00Z",
            nodes=[],
            relationships=[
                {
                    "id": "agent-a:uses:tool:web_search",
                    "source": "agent-a",
                    "target": "tool:web_search",
                    "type": "uses",
                    "event_count": 2,
                    "observation_count": 2,
                    "trace_ids": ["trace_a", "trace_b"],
                    "event_ids": ["evt_a", "evt_b"],
                    "provenance": {
                        "trace_ids": ["trace_a", "trace_b"],
                        "event_ids": ["evt_a", "evt_b"],
                        "observations": [
                            {"event_id": "evt_a", "trace_id": "trace_a"},
                            {"event_id": "evt_b", "trace_id": "trace_b"},
                        ],
                    },
                }
            ],
        )

        diff = compare_snapshot_payloads(before, after)
        changed = diff["relationships"]["changed"][0]

        self.assertIn("provenance", changed["changed_fields"])
        self.assertEqual(
            changed["after"]["provenance"]["event_ids"], ["evt_a", "evt_b"]
        )
        self.assertEqual(
            changed["after"]["provenance"]["trace_ids"], ["trace_a", "trace_b"]
        )
        self.assertEqual(len(changed["after"]["provenance"]["observations"]), 2)

    def test_timeline_reconstructs_ecosystem_evolution(self):
        agent = agent_node("agent-a", "Research Agent", "researcher")
        workflow = workflow_node(
            WorkflowEntry(
                workflow="Research Flow",
                framework="LangGraph",
                source="examples/langgraph_basic.py",
            )
        )
        tool = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "mcp",
        }
        mcp = mcp_server_node(
            name="Search MCP",
            transport="stdio",
            endpoint="stdio://search",
        )
        capability = capability_node(
            MCPCapabilityEntry(
                server="Search MCP",
                capability="search",
                category="web",
            )
        )
        events = [
            make_openmesh_event(
                "workflow.registered",
                agent,
                {"workflow": "Research Flow", "framework": "LangGraph"},
                target=workflow,
                session_id="sess_timeline",
                trace_id="trace_timeline",
            ),
            make_openmesh_event(
                "workflow.tool.used",
                workflow,
                {"workflow": "Research Flow", "tool": "web_search"},
                target=tool,
                session_id="sess_timeline",
                trace_id="trace_timeline",
            ),
            make_openmesh_event(
                "mcp.capability.discovered",
                mcp,
                {"server": "Search MCP", "capability": "search", "category": "web"},
                target=capability,
                session_id="sess_timeline",
                trace_id="trace_timeline",
            ),
        ]
        records = [
            record_from_event(event, timestamp=datetime(2026, 6, 3, 10, index, 0))
            for index, event in enumerate(events)
        ]
        sessions = [
            SimpleNamespace(
                session_id="sess_timeline",
                command="langgraph basic",
                started_at=datetime(2026, 6, 3, 10, 0, 0),
                ended_at=datetime(2026, 6, 3, 10, 3, 0),
                status="completed",
                exit_code=0,
            )
        ]
        before = self.make_snapshot_payload(
            "snap_before",
            created_at="2026-06-03T09:55:00Z",
            nodes=[],
            relationships=[],
        )
        after = self.make_snapshot_payload(
            "snap_after",
            created_at="2026-06-03T10:04:00Z",
            nodes=[
                {"id": agent["node_id"], "type": "agent", "name": agent["name"]},
                {
                    "id": workflow["node_id"],
                    "type": "workflow",
                    "name": workflow["name"],
                },
                {"id": tool["node_id"], "type": "tool", "name": tool["name"]},
                {"id": mcp["node_id"], "type": "mcp_server", "name": mcp["name"]},
                {
                    "id": capability["node_id"],
                    "type": "capability",
                    "name": capability["name"],
                },
            ],
            relationships=[
                {
                    "id": f"{agent['node_id']}:runs:{workflow['node_id']}",
                    "source": agent["node_id"],
                    "target": workflow["node_id"],
                    "type": "runs",
                    "provenance": {"trace_ids": ["trace_timeline"]},
                },
                {
                    "id": f"{workflow['node_id']}:uses:{tool['node_id']}",
                    "source": workflow["node_id"],
                    "target": tool["node_id"],
                    "type": "uses",
                    "provenance": {"trace_ids": ["trace_timeline"]},
                },
                {
                    "id": f"{mcp['node_id']}:exposes:{capability['node_id']}",
                    "source": mcp["node_id"],
                    "target": capability["node_id"],
                    "type": "exposes",
                    "provenance": {"trace_ids": ["trace_timeline"]},
                },
            ],
            workflows=[
                {
                    "id": workflow["node_id"],
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                }
            ],
            mcp_servers=[{"id": mcp["node_id"], "server": "Search MCP"}],
            capabilities=[{"server": "Search MCP", "capability": "search"}],
            traces=[{"trace_id": "trace_timeline"}],
            sessions=[{"session_id": "sess_timeline"}],
        )

        timeline = build_timeline(records, sessions, [before, after])

        self.assertEqual(timeline["scope"], "ecosystem")
        self.assertEqual(timeline["first_appearance"], "2026-06-03T09:55:00Z")
        self.assertEqual(timeline["last_appearance"], "2026-06-03T10:04:00Z")
        self.assertGreaterEqual(timeline["summary"]["relationship_changes"], 6)
        self.assertGreaterEqual(timeline["summary"]["workflow_changes"], 2)
        self.assertGreaterEqual(timeline["summary"]["mcp_changes"], 2)
        self.assertGreaterEqual(timeline["summary"]["capability_changes"], 2)
        self.assertEqual(timeline["session_history"][0]["session_id"], "sess_timeline")
        self.assertEqual(len(timeline["snapshot_history"]), 2)

        node_timeline = build_node_timeline(
            records, sessions, [before, after], "agent-a"
        )
        assert node_timeline is not None
        self.assertEqual(node_timeline["scope"], "node")
        self.assertEqual(node_timeline["subject"]["id"], "agent-a")
        self.assertEqual(node_timeline["summary"]["events"], 1)
        self.assertTrue(node_timeline["relationship_changes"])

        workflow_timeline = build_workflow_timeline(
            records, sessions, [before, after], "Research Flow"
        )
        assert workflow_timeline is not None
        self.assertEqual(workflow_timeline["scope"], "workflow")
        self.assertEqual(workflow_timeline["subject"]["workflow"], "Research Flow")
        self.assertTrue(workflow_timeline["relationship_changes"])

        trace_timeline = build_trace_timeline(
            records, sessions, [before, after], "trace_timeline"
        )
        assert trace_timeline is not None
        self.assertEqual(trace_timeline["scope"], "trace")
        self.assertEqual(trace_timeline["subject"]["trace_id"], "trace_timeline")
        self.assertEqual(trace_timeline["summary"]["events"], 3)
        self.assertEqual(
            trace_timeline["session_history"][0]["session_id"], "sess_timeline"
        )

    def test_replay_from_timeline_reconstructs_playback_frames(self):
        timeline = {
            "scope": "ecosystem",
            "subject": {"type": "ecosystem", "id": "openmesh.ecosystem"},
            "summary": {"events": 1},
            "relationship_changes": [
                {
                    "timestamp": "2026-06-03T10:00:00Z",
                    "kind": "relationship.observed",
                    "source": "agent-a",
                    "source_name": "Research Agent",
                    "target": "workflow:research",
                    "target_name": "Research Flow",
                    "relationship_type": "runs",
                    "provenance": {
                        "trace_ids": ["trace_replay"],
                        "event_ids": ["evt_replay"],
                    },
                }
            ],
            "workflow_changes": [
                {
                    "timestamp": "2026-06-03T10:01:00Z",
                    "kind": "workflow.observed",
                    "id": "workflow:research",
                    "name": "Research Flow",
                }
            ],
            "mcp_changes": [
                {
                    "timestamp": "2026-06-03T10:02:00Z",
                    "kind": "mcp_server.observed",
                    "id": "mcp:search",
                    "name": "Search MCP",
                }
            ],
            "capability_changes": [
                {
                    "timestamp": "2026-06-03T10:03:00Z",
                    "kind": "capability.observed",
                    "id": "capability:search",
                    "name": "search",
                }
            ],
            "session_history": [
                {
                    "session_id": "sess_replay",
                    "command": "python agent.py",
                    "started_at": "2026-06-03T10:04:00Z",
                    "ended_at": "2026-06-03T10:05:00Z",
                    "status": "completed",
                    "exit_code": 0,
                }
            ],
            "snapshot_history": [
                {
                    "snapshot_id": "snap_replay",
                    "created_at": "2026-06-03T10:06:00Z",
                    "counts": {"nodes": 2, "edges": 1},
                }
            ],
            "timeline": [
                {
                    "timestamp": "2026-06-03T10:00:30Z",
                    "kind": "event",
                    "event_id": "evt_replay",
                    "event_type": "workflow.registered",
                    "trace_id": "trace_replay",
                    "session_id": "sess_replay",
                    "source": "Research Agent",
                    "target": "Research Flow",
                }
            ],
        }

        replay = build_replay_from_timeline(timeline, control="step", position=0)
        actions = [frame["action"] for frame in replay["frames"]]

        self.assertEqual(replay["state"]["control"], "step")
        self.assertEqual(replay["state"]["position"], 1)
        self.assertIn("node.appeared", actions)
        self.assertIn("relationship.created", actions)
        self.assertIn("workflow.evolved", actions)
        self.assertIn("mcp.evolved", actions)
        self.assertIn("capability.evolved", actions)
        self.assertIn("session.started", actions)
        self.assertIn("snapshot.created", actions)
        self.assertGreaterEqual(replay["summary"]["frames"], 8)

        stopped = build_replay_from_timeline(timeline, control="stop", position=3)
        self.assertEqual(stopped["state"]["status"], "stopped")
        self.assertEqual(stopped["visible_frames"], [])

    def test_replay_from_snapshot_reconstructs_snapshot_state(self):
        snapshot = self.make_snapshot_payload(
            "snap_replay",
            created_at="2026-06-03T10:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "first_seen": "2026-06-03T09:59:00Z",
                    "provenance": {"event_ids": ["evt_agent"]},
                },
                {
                    "id": "tool:web_search",
                    "type": "tool",
                    "name": "web_search",
                    "first_seen": "2026-06-03T09:59:30Z",
                },
            ],
            relationships=[
                {
                    "id": "agent-a:uses:tool:web_search",
                    "source": "agent-a",
                    "target": "tool:web_search",
                    "type": "uses",
                    "first_seen": "2026-06-03T10:00:00Z",
                    "provenance": {
                        "trace_ids": ["trace_snapshot"],
                        "event_ids": ["evt_edge"],
                    },
                }
            ],
            workflows=[
                {
                    "id": "workflow:research",
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                }
            ],
            mcp_servers=[{"id": "mcp:search", "server": "Search MCP"}],
            capabilities=[{"server": "Search MCP", "capability": "search"}],
            sessions=[
                {
                    "session_id": "sess_replay",
                    "command": "python agent.py",
                    "started_at": "2026-06-03T09:58:00Z",
                    "ended_at": "2026-06-03T10:01:00Z",
                    "status": "completed",
                    "exit_code": 0,
                }
            ],
        )

        replay = build_replay_from_snapshot(snapshot, control="start", position=0)
        actions = [frame["action"] for frame in replay["frames"]]

        self.assertEqual(replay["scope"], "snapshot")
        self.assertIn("snapshot.loaded", actions)
        self.assertIn("node.appeared", actions)
        self.assertIn("relationship.created", actions)
        self.assertIn("workflow.evolved", actions)
        self.assertIn("mcp.evolved", actions)
        self.assertIn("capability.evolved", actions)
        self.assertIn("session.started", actions)

    def test_query_parser_supports_structured_queries(self):
        parsed = parse_query("agents using web_search")
        assert parsed is not None
        self.assertEqual(parsed.intent, "agents_using_tool")
        self.assertEqual(parsed.parameters["tool"], "web_search")

        parsed = parse_query("nodes removed between snapshots snap_a snap_b")
        assert parsed is not None
        self.assertEqual(parsed.intent, "nodes_removed_between_snapshots")
        self.assertEqual(parsed.parameters["snapshot_a"], "snap_a")
        self.assertEqual(parsed.parameters["snapshot_b"], "snap_b")

        self.assertIsNone(parse_query("why did this fail"))

    def test_query_engine_answers_graph_and_provenance_questions(self):
        context = self.make_query_context()
        state = {key: value for key, value in context.items() if key != "records"}

        agents = run_query_on_state("agents using web_search", **state)
        workflows = run_query_on_state("workflows using search", **state)
        relationships = run_query_on_state(
            "relationships created since 2026-06-03T10:01:30Z", **state
        )
        capabilities = run_query_on_state("capabilities exposed by Search MCP", **state)

        self.assertEqual(agents["status"], "ok")
        self.assertEqual(agents["results"][0]["agent"], "Research Agent")
        self.assertEqual(agents["results"][0]["relationship_type"], "uses")
        self.assertEqual(workflows["results"][0]["workflow"], "Research Flow")
        self.assertEqual(workflows["results"][0]["capability"], "search")
        self.assertEqual(relationships["count"], 1)
        self.assertEqual(relationships["results"][0]["relationship_type"], "exposes")
        self.assertEqual(capabilities["results"][0]["capability"], "search")

    def test_query_engine_answers_snapshot_trace_and_session_questions(self):
        context = self.make_query_context()
        state = {key: value for key, value in context.items() if key != "records"}

        added = run_query_on_state("nodes added between snapshots", **state)
        removed = run_query_on_state(
            "nodes removed between snapshots snap_query_before snap_query_after",
            **state,
        )
        traces = run_query_on_state("traces involving Research Agent", **state)
        sessions = run_query_on_state("sessions involving Research Agent", **state)

        self.assertEqual(added["status"], "ok")
        self.assertEqual(added["parameters"]["snapshot_a"], "snap_query_before")
        self.assertIn("web_search", {item.get("name") for item in added["results"]})
        self.assertEqual(removed["count"], 0)
        self.assertEqual(traces["results"][0]["trace_id"], "trace_query_agent")
        self.assertEqual(sessions["results"][0]["session_id"], "sess_query")

    def test_query_engine_reports_unsupported_and_not_found_queries(self):
        context = self.make_query_context()
        state = {key: value for key, value in context.items() if key != "records"}

        unsupported = run_query_on_state("show me surprises", **state)
        missing = run_query_on_state("agents using missing_tool", **state)
        no_snapshots = run_query_on_state(
            "nodes added between snapshots",
            graph=context["graph"],
            traces=context["traces"],
            sessions=context["sessions"],
            snapshots=[],
        )

        self.assertEqual(unsupported["status"], "unsupported")
        self.assertEqual(missing["status"], "not_found")
        self.assertEqual(missing["errors"][0]["code"], "tool_not_found")
        self.assertEqual(no_snapshots["status"], "not_found")
        self.assertEqual(no_snapshots["errors"][0]["code"], "snapshot_pair_not_found")

    async def test_replay_api_routes_return_derived_payloads(self):
        async def fake_trace_replay(db, trace_id, **kwargs):
            return {
                "scope": "trace",
                "subject": {"trace_id": trace_id},
                "state": {"control": kwargs["control"]},
            }

        async def fake_workflow_replay(db, workflow_id, **kwargs):
            return {
                "scope": "workflow",
                "subject": {"workflow": workflow_id},
                "state": {"position": kwargs["position"]},
            }

        async def fake_snapshot_replay(db, snapshot_id, **kwargs):
            return {
                "scope": "snapshot",
                "subject": {"snapshot_id": snapshot_id},
                "state": {"control": kwargs["control"]},
            }

        with (
            patch("src.api.routes.main.get_trace_replay", fake_trace_replay),
            patch("src.api.routes.main.get_workflow_replay", fake_workflow_replay),
            patch("src.api.routes.main.get_snapshot_replay", fake_snapshot_replay),
        ):
            trace = await api_get_openmesh_trace_replay(
                "trace_api",
                control="pause",
                position=2,
                limit=100,
                db=FakeAsyncSession(),
            )
            workflow = await api_get_openmesh_workflow_replay(
                "workflow_api",
                control="step",
                position=3,
                limit=100,
                db=FakeAsyncSession(),
            )
            snapshot = await api_get_openmesh_snapshot_replay(
                "snap_api",
                control="start",
                position=0,
                db=FakeAsyncSession(),
            )

        self.assertEqual(trace["subject"]["trace_id"], "trace_api")
        self.assertEqual(trace["state"]["control"], "pause")
        self.assertEqual(workflow["scope"], "workflow")
        self.assertEqual(workflow["state"]["position"], 3)
        self.assertEqual(snapshot["subject"]["snapshot_id"], "snap_api")

    async def test_replay_api_routes_return_404_when_missing(self):
        async def missing_replay(*args, **kwargs):
            return None

        with patch("src.api.routes.main.get_trace_replay", missing_replay):
            with self.assertRaises(HTTPException) as err:
                await api_get_openmesh_trace_replay(
                    "missing_trace", db=FakeAsyncSession()
                )

        self.assertEqual(err.exception.status_code, 404)
        self.assertIn("replay not found", err.exception.detail)

    async def test_query_api_route_returns_query_payload(self):
        async def fake_execute_query(db, query, **kwargs):
            return {
                "query": query,
                "status": "ok",
                "count": 1,
                "results": [{"name": "Research Agent"}],
                "limit": kwargs["limit"],
            }

        with patch("src.api.routes.main.execute_query", fake_execute_query):
            result = await api_query_openmesh(
                OpenMeshQueryRequest(query="agents using web_search", limit=25),
                db=FakeAsyncSession(),
            )

        self.assertEqual(result["query"], "agents using web_search")
        self.assertEqual(result["limit"], 25)
        self.assertEqual(result["count"], 1)

    def test_workflow_validation_detects_duplicates_and_missing_metadata(self):
        validation = validate_workflow_entries(
            [
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "source": "examples/langgraph_basic.py",
                    "metadata": {},
                },
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "source": "examples/other.py",
                    "metadata": {},
                },
                {
                    "workflow": "Broken Flow",
                    "metadata": [],
                },
            ]
        )

        self.assertEqual(len(validation["duplicates"]), 1)
        self.assertEqual(len(validation["missing_required_metadata"]), 1)
        self.assertEqual(len(validation["malformed_metadata"]), 1)

    def test_doctor_workflow_registry_diagnostics_reports_integrity_issues(self):
        event = make_openmesh_event(
            "workflow.registered",
            agent_node("agent:research", "Research Agent", "researcher"),
            {"workflow": "Broken Flow"},
            target=workflow_node({"workflow": "Broken Flow", "metadata": {}}),
        )

        diagnostics = build_workflow_registry_diagnostics([record_from_event(event)])

        self.assertEqual(diagnostics["name"], "Workflow Registry Integrity")
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertEqual(len(diagnostics["detail"]["missing_required_metadata"]), 1)

    def test_ecosystem_registry_unifies_observed_entities(self):
        agent = agent_node("agent:research", "Research Agent", "researcher")
        workflow = workflow_node(
            WorkflowEntry(
                workflow="Research Flow",
                framework="LangGraph",
                version="0.1.0",
                source="examples/langgraph_basic.py",
            )
        )
        tool = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
            "runtime": "mcp",
        }
        mcp = mcp_server_node(
            name="Search MCP", transport="http", endpoint="http://localhost:8765/mcp"
        )
        capability = capability_node(
            MCPCapabilityEntry(
                server="Search MCP",
                capability="web_search",
                description="Search query metadata",
                category="search",
            )
        )
        config_source = {
            "node_id": "mcp_config:codex:config",
            "node_type": "service",
            "name": "Codex MCP Config",
            "runtime": "mcp.config",
            "metadata": {"source": "Codex", "config_path": "/tmp/config.toml"},
        }
        events = [
            make_openmesh_event(
                "workflow.registered",
                agent,
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "source": "examples/langgraph_basic.py",
                },
                target=workflow,
            ),
            make_openmesh_event(
                "workflow.tool.used",
                workflow,
                {"workflow": "Research Flow"},
                target=tool,
            ),
            make_openmesh_event(
                "workflow.mcp.connected",
                workflow,
                {"workflow": "Research Flow"},
                target=mcp,
            ),
            make_openmesh_event(
                "mcp.capability.discovered",
                mcp,
                {
                    "server": "Search MCP",
                    "capability": "web_search",
                    "category": "search",
                },
                target=capability,
            ),
            make_openmesh_event(
                "mcp.config.discovered",
                config_source,
                {
                    "source": "Codex",
                    "config_path": "/tmp/config.toml",
                    "server": "Search MCP",
                    "transport": "http",
                    "endpoint": "http://localhost:8765/mcp",
                },
                target=mcp,
            ),
        ]
        registry = build_ecosystem_registry(
            [record_from_event(event) for event in events]
        )

        self.assertEqual(registry["summary"]["groups"]["agents"], 1)
        self.assertEqual(registry["summary"]["groups"]["tools"], 1)
        self.assertEqual(registry["summary"]["groups"]["workflows"], 1)
        self.assertEqual(registry["summary"]["groups"]["mcp_servers"], 1)
        self.assertEqual(registry["summary"]["groups"]["mcp_configs"], 1)
        self.assertEqual(registry["summary"]["groups"]["capabilities"], 1)
        self.assertEqual(registry["validation"]["status"], "OK")

    def test_ecosystem_validation_detects_duplicates_and_orphans(self):
        validation = validate_ecosystem_entities(
            [
                {
                    "id": "agent:a",
                    "type": "agent",
                    "name": "Agent A",
                    "relationship_count": 0,
                    "metadata": {},
                },
                {
                    "id": "agent:b",
                    "type": "agent",
                    "name": "Agent A",
                    "relationship_count": 1,
                    "metadata": {},
                },
                {
                    "id": "tool:a",
                    "type": "tool",
                    "name": "Tool A",
                    "relationship_count": 0,
                    "metadata": {},
                },
            ]
        )

        self.assertEqual(validation["status"], "ERROR")
        self.assertEqual(len(validation["duplicate_entities"]), 1)
        self.assertEqual(len(validation["orphan_entities"]), 2)
        self.assertEqual(len(validation["missing_relationships"]), 2)

    def test_doctor_ecosystem_diagnostics_reports_integrity_issues(self):
        event = make_openmesh_event(
            "agent.started",
            {"node_id": "agent:solo", "node_type": "agent", "name": "Solo Agent"},
            {"status": "started"},
        )

        diagnostics = build_ecosystem_diagnostics([record_from_event(event)])

        self.assertEqual(diagnostics["name"], "Ecosystem Integrity")
        self.assertEqual(diagnostics["severity"], "WARNING")
        self.assertEqual(len(diagnostics["detail"]["orphan_entities"]), 1)

    def test_graph_validation_distinguishes_relationship_integrity_errors(self):
        nodes = {
            "agent:a": {
                "id": "agent:a",
                "type": "agent",
                "name": "Agent A",
                "category": "agents",
            },
            "tool:a": {
                "id": "tool:a",
                "type": "tool",
                "name": "Tool A",
                "category": "tools",
            },
            "service:a": {
                "id": "service:a",
                "type": "service",
                "name": "Service A",
                "category": "services",
            },
        }
        edge_base = {
            "trace_id": "trace_test",
            "event_id": "evt_test",
            "first_seen": "2026-06-03T00:00:00Z",
            "last_seen": "2026-06-03T00:00:00Z",
        }
        edges = {
            "unknown": {
                "id": "unknown",
                "source": "agent:a",
                "target": "tool:a",
                "type": "unknown",
                **edge_base,
            },
            "bad-source": {
                "id": "bad-source",
                "source": "tool:a",
                "target": "tool:a",
                "type": "uses",
                **edge_base,
            },
            "bad-target": {
                "id": "bad-target",
                "source": "agent:a",
                "target": "service:a",
                "type": "uses",
                **edge_base,
            },
        }

        validation = validate_graph_state(nodes, edges)

        self.assertEqual(len(validation["invalid_relationship_types"]), 1)
        self.assertEqual(len(validation["invalid_source_types"]), 1)
        self.assertEqual(len(validation["invalid_target_types"]), 1)

    def test_graph_validation_detects_unknown_node_types_and_categories(self):
        nodes = {
            "unknown:a": {
                "id": "unknown:a",
                "type": "unknown",
                "name": "Unknown A",
                "category": "unknown",
            },
            "agent:a": {
                "id": "agent:a",
                "type": "agent",
                "name": "Agent A",
                "category": "tools",
            },
        }
        edges = {
            "edge:a": {
                "id": "edge:a",
                "source": "unknown:a",
                "target": "agent:a",
                "type": "communicates_with",
                "trace_id": "trace_test",
                "event_id": "evt_test",
                "first_seen": "2026-06-03T00:00:00Z",
                "last_seen": "2026-06-03T00:00:00Z",
            }
        }

        validation = validate_graph_state(nodes, edges)

        self.assertEqual(len(validation["unknown_node_types"]), 1)
        self.assertEqual(len(validation["invalid_node_categories"]), 1)
        self.assertEqual(len(validation["invalid_relationship_endpoints"]), 1)

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
                timestamp=datetime.fromisoformat(
                    event["timestamp"].replace("Z", "+00:00")
                ).replace(tzinfo=None),
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
        self.assertTrue(
            any(entry["name"] == "python hello.py" for entry in discovery["processes"])
        )
        self.assertTrue(
            any(entry["name"] == "Research Agent" for entry in discovery["agents"])
        )
        self.assertEqual(
            discovery["tools"][0]["type_definition"]["display_name"], "Tool"
        )
        self.assertEqual(discovery["tools"][0]["validation_status"], "valid")

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
            target={
                "node_id": "tool:web_search",
                "node_type": "tool",
                "name": "web_search",
            },
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
        self.assertEqual(
            hierarchy[0]["children"][0]["children"][0]["event_id"], tool["event_id"]
        )
        self.assertEqual(relationships[0]["event_id"], tool["event_id"])
        self.assertEqual(relationships[0]["type"], "uses")
        self.assertEqual(
            relationships[0]["provenance"]["event_ids"], [tool["event_id"]]
        )
        self.assertEqual(
            relationships[0]["provenance"]["trace_ids"], [tool["trace_id"]]
        )
        self.assertEqual(validation["status"], "OK")

    def test_span_semantics_build_lifecycle_tree_and_links(self):
        root = self.make_event("task.started")
        linked = make_openmesh_event(
            "tool.call.started",
            root["source"],
            {"tool": "web_search"},
            target={
                "node_id": "tool:web_search",
                "node_type": "tool",
                "name": "web_search",
            },
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
            target={
                "node_id": "tool:web_search",
                "node_type": "tool",
                "name": "web_search",
            },
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

        child_span = next(
            span for span in spans if span["span_id"] == linked["span_id"]
        )
        self.assertEqual(child_span["status"], "completed")
        self.assertEqual(child_span["event_count"], 2)
        self.assertEqual(child_span["links"][0]["trace_id"], "trace_external")
        self.assertEqual(span_tree[0]["children"][0]["span_id"], linked["span_id"])
        self.assertEqual(
            validation["cross_trace_links"][0]["linked_trace_id"], "trace_external"
        )

    def test_doctor_trace_diagnostics_find_broken_parent_span_and_orphan_span(self):
        root = self.make_event("task.started")
        child = make_openmesh_event(
            "tool.call.started",
            root["source"],
            {"tool": "web_search"},
            target={
                "node_id": "tool:web_search",
                "node_type": "tool",
                "name": "web_search",
            },
            session_id=root["session_id"],
            trace_id=root["trace_id"],
            parent_span_id="span_missing",
            parent_event_id=root["event_id"],
            root_event_id=root["event_id"],
        )

        diagnostics = build_trace_diagnostics(
            [record_from_event(root), record_from_event(child)]
        )
        trace_check = diagnostics[0]

        self.assertEqual(trace_check["severity"], "ERROR")
        self.assertEqual(len(trace_check["detail"]["broken_parent_span_events"]), 1)
        self.assertEqual(len(trace_check["detail"]["orphan_spans"]), 1)

    def test_doctor_trace_diagnostics_find_missing_and_broken_root_event_ids(self):
        missing = self.make_event("task.started")
        broken = self.make_event("tool.call.started")

        diagnostics = build_trace_diagnostics(
            [
                record_from_event(missing, root_event_id=None),
                record_from_event(broken, root_event_id="evt_missing_root"),
            ]
        )
        detail = diagnostics[0]["detail"]

        self.assertEqual(diagnostics[0]["severity"], "ERROR")
        self.assertEqual(len(detail["missing_root_event_events"]), 1)
        self.assertEqual(len(detail["broken_root_event_events"]), 1)

    def test_doctor_trace_diagnostics_find_malformed_and_invalid_cross_trace_links(
        self,
    ):
        local = self.make_event("message.sent")
        local["links"] = [
            {
                "trace_id": "trace_missing",
                "span_id": "span_missing",
                "relationship": "follows_from",
            }
        ]
        malformed = self.make_event("message.sent")
        malformed["links"] = [{"relationship": "empty"}]

        diagnostics = build_trace_diagnostics(
            [record_from_event(local), record_from_event(malformed)]
        )
        detail = diagnostics[0]["detail"]

        self.assertEqual(diagnostics[0]["severity"], "ERROR")
        self.assertEqual(len(detail["malformed_link_events"]), 1)
        self.assertEqual(len(detail["invalid_cross_trace_links"]), 1)

    def test_doctor_trace_diagnostics_count_valid_cross_trace_links(self):
        parent = self.make_event("task.started")
        parent["trace_id"] = "trace_parent"
        child = self.make_event("task.started")
        child["trace_id"] = "trace_child"
        child["links"] = [
            {
                "trace_id": parent["trace_id"],
                "span_id": parent["span_id"],
                "event_id": parent["event_id"],
                "relationship": "follows_from",
            }
        ]

        diagnostics = build_trace_diagnostics(
            [record_from_event(parent), record_from_event(child)]
        )

        self.assertEqual(diagnostics[0]["severity"], "INFO")
        self.assertEqual(diagnostics[0]["detail"]["valid_cross_trace_links"], 1)

    def test_doctor_workflow_diagnostics_find_incomplete_and_long_running_spans(self):
        workflow = make_openmesh_event(
            "workflow.started",
            {
                "node_id": "workflow:test",
                "node_type": "workflow",
                "name": "Test Workflow",
            },
            {"workflow": "test"},
            session_id="sess_test",
            trace_id="trace_workflow",
        )
        record = record_from_event(workflow, timestamp=datetime(2026, 1, 1, 0, 0, 0))

        diagnostics = build_trace_diagnostics(
            [record], now=datetime(2026, 1, 1, 2, 0, 0)
        )
        trace_check, workflow_check = diagnostics

        self.assertEqual(trace_check["severity"], "WARNING")
        self.assertEqual(workflow_check["severity"], "WARNING")
        self.assertEqual(len(trace_check["detail"]["long_running_active_spans"]), 1)
        self.assertEqual(len(workflow_check["detail"]["incomplete_workflow_spans"]), 1)

    def test_doctor_graph_diagnostics_find_missing_provenance_invalid_and_stale_edges(
        self,
    ):
        stale = self.make_event("message.sent")
        stale["source"] = agent_node("agent-a", "Research Agent", "researcher")
        stale["target"] = agent_node("agent-b", "Coding Agent", "engineer")
        invalid = self.make_event("node.transition")
        invalid["source"] = agent_node("agent-a", "Research Agent", "researcher")
        invalid["target"] = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
        }
        missing = self.make_event("message.sent")
        missing["source"] = agent_node("agent-c", "Planning Agent", "planner")
        missing["target"] = agent_node("agent-d", "Review Agent", "reviewer")

        diagnostics = build_graph_diagnostics(
            [
                record_from_event(stale, timestamp=datetime(2026, 1, 1, 0, 0, 0)),
                record_from_event(invalid),
                record_from_event(missing, trace_id=None),
            ]
        )

        detail = diagnostics["detail"]
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertGreaterEqual(len(detail["missing_provenance"]), 1)
        self.assertGreaterEqual(len(detail["invalid_relationships"]), 1)
        self.assertGreaterEqual(len(detail["stale_relationships"]), 1)

    def test_doctor_relationship_diagnostics_find_invalid_source_and_target_types(self):
        invalid = self.make_event("node.transition")
        invalid["source"] = agent_node("agent-a", "Research Agent", "researcher")
        invalid["target"] = {
            "node_id": "tool:web_search",
            "node_type": "tool",
            "name": "web_search",
        }

        diagnostics = build_relationship_diagnostics([record_from_event(invalid)])

        self.assertEqual(diagnostics["name"], "Relationship Integrity")
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertEqual(len(diagnostics["detail"]["invalid_source_types"]), 1)
        self.assertEqual(len(diagnostics["detail"]["invalid_target_types"]), 1)

    def test_doctor_node_diagnostics_find_unknown_node_types(self):
        event = self.make_event("message.sent")
        event["source"] = {
            "node_id": "unknown:a",
            "node_type": "unknown",
            "name": "Unknown A",
        }

        diagnostics = build_node_diagnostics([record_from_event(event)])

        self.assertEqual(diagnostics["name"], "Node Integrity")
        self.assertEqual(diagnostics["severity"], "ERROR")
        self.assertEqual(len(diagnostics["detail"]["unknown_node_types"]), 1)

    async def test_session_creation_and_completion(self):
        db = FakeSessionStore()
        started = datetime.utcnow()
        session = await create_openmesh_session(
            db,
            session_id="sess_test",
            command="python hello.py",
            started_at=started,
        )

        with patch(
            "src.db.openmesh_sessions.get_openmesh_session", return_value=session
        ):
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
                    {
                        "id": "agent-a",
                        "type": "agent",
                        "name": "Research Agent",
                        "event_count": 1,
                        "last_seen": "2026-05-29T10:00:00Z",
                    },
                    {
                        "id": "agent-b",
                        "type": "agent",
                        "name": "Coding Agent",
                        "event_count": 1,
                        "last_seen": "2026-05-29T10:00:00Z",
                    },
                ],
                "edges": [
                    {
                        "id": "edge-1",
                        "source": "agent-a",
                        "target": "agent-b",
                        "type": "communicates_with",
                        "event_count": 1,
                        "last_seen": "2026-05-29T10:00:00Z",
                        "validation_status": "valid",
                        "relationship_definition": {
                            "description": "Agents communicate with each other."
                        },
                    }
                ],
            },
            traces=[
                {
                    "trace_id": "trace_test",
                    "status": "completed",
                    "event_count": 1,
                    "started_at": "2026-05-29T10:00:00Z",
                }
            ],
            events=[
                {
                    "event_id": "evt_test",
                    "event_type": "message.sent",
                    "timestamp": "2026-05-29T10:00:00Z",
                    "trace_id": "trace_test",
                    "session_id": "sess_test",
                    "source": {
                        "node_id": "agent-a",
                        "node_type": "agent",
                        "name": "Research Agent",
                    },
                    "target": {
                        "node_id": "agent-b",
                        "node_type": "agent",
                        "name": "Coding Agent",
                    },
                    "payload": {},
                }
            ],
            sessions=[],
            integrations=[],
            discovery={
                "frameworks": [],
                "agents": [],
                "tools": [],
                "capabilities": [],
                "workflows": [],
                "processes": [],
                "services": [],
            },
            mcp_servers=[],
            mcp_configs=[],
            capabilities=[],
            workflows=[],
            snapshots=[],
            ecosystem={
                "entities": {
                    "agents": [],
                    "tools": [],
                    "processes": [],
                    "workflows": [],
                    "mcp_servers": [],
                    "mcp_configs": [],
                    "capabilities": [],
                },
                "summary": {"entity_count": 0, "relationship_count": 0},
                "validation": {"status": "OK"},
            },
            registry_status=build_registry_status([]),
            loaded_at=datetime.utcnow(),
        )

        output = render_plain(snapshot)

        self.assertIn("Agents / Processes", output)
        self.assertIn("Network", output)
        self.assertIn("communicates_with", output)
        detail = "\n".join(edge_detail_rows(snapshot, "edge-1"))
        self.assertIn("validation: valid", detail)
        self.assertIn("Agents communicate with each other.", detail)
        node_detail = "\n".join(node_detail_rows(snapshot, "agent-a"))
        self.assertIn("type: agent", node_detail)
        self.assertIn("Relationships", node_detail)
        self.assertIn("Explore", node_detail)
        self.assertIn("Traversal targets", node_detail)
        focused_edges = network_edges(snapshot, focus_node_id="agent-a", depth=1)
        self.assertEqual([edge["id"] for edge in focused_edges], ["edge-1"])
        explorer_detail = "\n".join(
            graph_explorer_rows(
                snapshot,
                focus_node_id="agent-a",
                depth=1,
                query="Coding",
            )
        )
        self.assertIn("Graph Explorer", explorer_detail)
        self.assertIn("Focus: Research Agent", explorer_detail)
        self.assertIn("Search: Coding", explorer_detail)
        registry_detail = "\n".join(registry_rows(snapshot))
        self.assertIn("Compatibility: INFO", registry_detail)
        self.assertIn("node_registry", registry_detail)

    def test_tui_mcp_rows_display_discovered_servers(self):
        snapshot = TuiSnapshot(
            health={"events": 1, "traces": 1, "nodes": 1, "edges": 0},
            graph={"nodes": [], "edges": []},
            traces=[],
            events=[],
            sessions=[],
            integrations=[],
            discovery={
                "frameworks": [],
                "agents": [],
                "tools": [],
                "capabilities": [],
                "workflows": [],
                "processes": [],
                "services": [],
            },
            mcp_servers=[
                {
                    "server": "Filesystem MCP",
                    "version": "1.0.0",
                    "transport": "stdio",
                    "endpoint": "stdio://filesystem",
                    "last_seen": "2026-06-03T10:00:00Z",
                }
            ],
            mcp_configs=[
                {
                    "source": "Codex",
                    "server": "search",
                    "transport": "http",
                    "config_path": "/tmp/config.toml",
                }
            ],
            capabilities=[
                {
                    "server": "Filesystem MCP",
                    "capability": "read_file",
                    "category": "filesystem",
                    "description": "Read file metadata",
                }
            ],
            workflows=[
                {
                    "workflow": "Research Flow",
                    "framework": "LangGraph",
                    "source": "examples/langgraph_basic.py",
                    "last_seen": "2026-06-03T10:00:00Z",
                }
            ],
            snapshots=[
                {
                    "snapshot_id": "snap_test",
                    "created_at": "2026-06-03T10:00:00Z",
                    "counts": {
                        "nodes": 2,
                        "edges": 1,
                        "traces": 1,
                        "sessions": 1,
                    },
                    "graph_statistics": {"node_count": 2, "edge_count": 1},
                    "ecosystem_statistics": {
                        "entity_count": 2,
                        "relationship_count": 1,
                    },
                }
            ],
            ecosystem={
                "entities": {
                    "agents": [],
                    "tools": [],
                    "processes": [],
                    "workflows": [
                        {
                            "id": "workflow:research",
                            "type": "workflow",
                            "name": "Research Flow",
                            "status": "active",
                            "event_count": 3,
                            "relationship_count": 2,
                            "last_seen": "2026-06-03T10:00:00Z",
                        }
                    ],
                    "mcp_servers": [
                        {
                            "id": "mcp:filesystem",
                            "type": "mcp_server",
                            "name": "Filesystem MCP",
                            "status": "active",
                            "event_count": 1,
                            "relationship_count": 1,
                            "last_seen": "2026-06-03T10:00:00Z",
                        }
                    ],
                    "mcp_configs": [],
                    "capabilities": [],
                },
                "summary": {"entity_count": 2, "relationship_count": 2},
                "validation": {"status": "OK"},
            },
            registry_status=build_registry_status([]),
            loaded_at=datetime.utcnow(),
        )

        output = "\n".join(mcp_rows(snapshot))

        self.assertIn("Filesystem MCP", output)
        self.assertIn("stdio", output)
        config_output = "\n".join(mcp_config_rows(snapshot))
        self.assertIn("Codex", config_output)
        self.assertIn("search", config_output)
        capability_output = "\n".join(capability_rows(snapshot))
        self.assertIn("read_file", capability_output)
        self.assertIn("filesystem", capability_output)
        workflow_output = "\n".join(workflow_rows(snapshot))
        self.assertIn("Research Flow", workflow_output)
        self.assertIn("LangGraph", workflow_output)
        workflow_detail = "\n".join(
            workflow_detail_rows(
                {
                    "workflow_id": "workflow:langgraph:research-flow",
                    "workflow": "Research Flow",
                    "workflow_type": "LangGraph",
                    "runtime": "LangGraph",
                    "status": "completed",
                    "started_at": "2026-06-03T10:00:00Z",
                    "ended_at": "2026-06-03T10:05:00Z",
                    "event_count": 6,
                    "relationship_count": 4,
                    "participating_agents": [{"name": "Research Agent"}],
                    "participating_tools": [{"name": "web_search"}],
                    "participating_mcp_servers": [{"name": "Search MCP"}],
                    "participating_services": [{"name": "Vector DB"}],
                    "trace_ids": ["trace_workflow"],
                    "session_ids": ["sess_workflow"],
                    "provenance": {"event_ids": ["evt_workflow"]},
                }
            )
        )
        self.assertIn("Workflow Provenance", workflow_detail)
        self.assertIn("Research Agent", workflow_detail)
        ecosystem_output = "\n".join(ecosystem_rows(snapshot))
        self.assertIn("Ecosystem", ecosystem_output)
        self.assertIn("Research Flow", ecosystem_output)
        snapshot_output = "\n".join(snapshot_rows(snapshot))
        self.assertIn("snap_test", snapshot_output)
        self.assertIn("Latest Snapshot", snapshot_output)

    def test_tui_snapshot_diff_rows_display_selected_pair(self):
        before = self.make_snapshot_payload(
            "snap_before",
            created_at="2026-06-03T10:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "event_count": 1,
                }
            ],
            relationships=[],
            traces=[{"trace_id": "trace_a"}],
            sessions=[{"session_id": "sess_a"}],
        )
        after = self.make_snapshot_payload(
            "snap_after",
            created_at="2026-06-03T11:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "event_count": 1,
                },
                {
                    "id": "process:pytest",
                    "type": "process",
                    "name": "pytest",
                    "event_count": 1,
                },
            ],
            relationships=[],
            traces=[{"trace_id": "trace_a"}, {"trace_id": "trace_b"}],
            sessions=[{"session_id": "sess_a"}],
        )
        snapshot = TuiSnapshot(
            health={"events": 2, "traces": 2, "nodes": 2, "edges": 0},
            graph={"nodes": [], "edges": []},
            traces=[],
            events=[],
            sessions=[],
            integrations=[],
            discovery={
                "frameworks": [],
                "agents": [],
                "tools": [],
                "capabilities": [],
                "workflows": [],
                "processes": [],
                "services": [],
            },
            mcp_servers=[],
            mcp_configs=[],
            capabilities=[],
            workflows=[],
            snapshots=[
                {
                    "snapshot_id": after["snapshot_id"],
                    "created_at": after["created_at"],
                    "counts": after["counts"],
                },
                {
                    "snapshot_id": before["snapshot_id"],
                    "created_at": before["created_at"],
                    "counts": before["counts"],
                },
            ],
            ecosystem={
                "entities": {
                    "agents": [],
                    "tools": [],
                    "processes": [],
                    "workflows": [],
                    "mcp_servers": [],
                    "mcp_configs": [],
                    "capabilities": [],
                },
                "summary": {"entity_count": 0, "relationship_count": 0},
                "validation": {"status": "OK"},
            },
            registry_status=build_registry_status([]),
            loaded_at=datetime.utcnow(),
            snapshot_details={
                before["snapshot_id"]: before,
                after["snapshot_id"]: after,
            },
        )

        output = "\n".join(snapshot_diff_rows(snapshot))

        self.assertIn("Snapshot Diff", output)
        self.assertIn("snap_before", output)
        self.assertIn("snap_after", output)
        self.assertIn("Nodes +1 -0 ~0", output)
        self.assertIn("Traces Δ+1", output)

    def test_tui_timeline_rows_display_historical_evolution(self):
        snapshot = TuiSnapshot(
            health={"events": 1, "traces": 1, "nodes": 1, "edges": 0},
            graph={"nodes": [], "edges": []},
            traces=[],
            events=[],
            sessions=[],
            integrations=[],
            discovery={
                "frameworks": [],
                "agents": [],
                "tools": [],
                "capabilities": [],
                "workflows": [],
                "processes": [],
                "services": [],
            },
            mcp_servers=[],
            mcp_configs=[],
            capabilities=[],
            workflows=[],
            snapshots=[],
            ecosystem={
                "entities": {
                    "agents": [],
                    "tools": [],
                    "processes": [],
                    "workflows": [],
                    "mcp_servers": [],
                    "mcp_configs": [],
                    "capabilities": [],
                },
                "summary": {"entity_count": 0, "relationship_count": 0},
                "validation": {"status": "OK"},
            },
            registry_status=build_registry_status([]),
            loaded_at=datetime.utcnow(),
            timeline={
                "first_appearance": "2026-06-03T10:00:00Z",
                "last_appearance": "2026-06-03T10:05:00Z",
                "summary": {
                    "events": 1,
                    "relationship_changes": 1,
                    "snapshots": 1,
                },
                "timeline": [
                    {
                        "timestamp": "2026-06-03T10:00:00Z",
                        "kind": "event",
                        "event_type": "workflow.registered",
                    },
                    {
                        "timestamp": "2026-06-03T10:05:00Z",
                        "kind": "snapshot.created",
                        "snapshot_id": "snap_timeline",
                    },
                ],
                "snapshot_history": [
                    {
                        "snapshot_id": "snap_timeline",
                        "created_at": "2026-06-03T10:05:00Z",
                        "counts": {"nodes": 2, "edges": 1},
                    }
                ],
            },
        )

        output = "\n".join(timeline_rows(snapshot))

        self.assertIn("Timeline", output)
        self.assertIn("workflow.registered", output)
        self.assertIn("snap_timeline", output)

    def test_tui_replay_rows_display_playback_controls(self):
        replay = {
            "state": {
                "control": "start",
                "status": "playing",
                "position": 0,
                "frame_count": 2,
                "current_frame": {
                    "frame_index": 0,
                    "timestamp": "2026-06-03T10:00:00Z",
                    "action": "node.appeared",
                    "description": "Research Agent appeared",
                },
            },
            "summary": {"frames": 2, "nodes": 1, "relationships": 1},
            "visible_frames": [
                {
                    "frame_index": 0,
                    "timestamp": "2026-06-03T10:00:00Z",
                    "action": "node.appeared",
                    "description": "Research Agent appeared",
                },
                {
                    "frame_index": 1,
                    "timestamp": "2026-06-03T10:01:00Z",
                    "action": "relationship.created",
                    "description": "Research Agent runs Research Flow",
                },
            ],
        }

        output = "\n".join(replay_rows(replay))

        self.assertIn("Replay", output)
        self.assertIn("control start", output)
        self.assertIn("space start/pause", output)
        self.assertIn("relationship.created", output)

    def test_tui_query_rows_display_saved_query_results(self):
        context = self.make_query_context()
        before, after = context["snapshots"]
        snapshot = TuiSnapshot(
            health={"events": 3, "traces": 2, "nodes": 5, "edges": 3},
            graph=context["graph"],
            traces=context["traces"],
            events=[],
            sessions=context["sessions"],
            integrations=[],
            discovery=context["discovery"],
            mcp_servers=[],
            mcp_configs=[],
            capabilities=[],
            workflows=[],
            snapshots=[
                {
                    "snapshot_id": after["snapshot_id"],
                    "created_at": after["created_at"],
                    "counts": after["counts"],
                },
                {
                    "snapshot_id": before["snapshot_id"],
                    "created_at": before["created_at"],
                    "counts": before["counts"],
                },
            ],
            ecosystem={
                "entities": {
                    "agents": [],
                    "tools": [],
                    "processes": [],
                    "workflows": [],
                    "mcp_servers": [],
                    "mcp_configs": [],
                    "capabilities": [],
                },
                "summary": {"entity_count": 0, "relationship_count": 0},
                "validation": {"status": "OK"},
            },
            registry_status=build_registry_status([]),
            loaded_at=datetime.utcnow(),
            snapshot_details={
                before["snapshot_id"]: before,
                after["snapshot_id"]: after,
            },
            timeline={},
        )

        output = "\n".join(query_rows(snapshot, query_index=0))

        self.assertIn("Query", output)
        self.assertIn("Agents using web_search", output)
        self.assertIn("Research Agent", output)
        self.assertIn("u next saved query", output)

    def test_cli_mcp_printer_displays_metadata(self):
        with patch("builtins.print") as printer:
            _print_mcp(
                [
                    {
                        "server": "Filesystem MCP",
                        "version": "1.0.0",
                        "transport": "stdio",
                        "last_seen": "2026-06-03T10:00:00Z",
                    }
                ]
            )

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("Filesystem MCP", printed)
        self.assertIn("stdio", printed)

    def test_cli_mcp_config_printer_displays_metadata(self):
        with patch("builtins.print") as printer:
            _print_mcp_config(
                [
                    {
                        "source": "Codex",
                        "server": "search",
                        "transport": "http",
                        "config_path": "/tmp/config.toml",
                    }
                ]
            )

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("Codex", printed)
        self.assertIn("search", printed)

    def test_cli_capability_printer_displays_metadata(self):
        with patch("builtins.print") as printer:
            _print_capabilities(
                [
                    {
                        "server": "Filesystem MCP",
                        "capability": "read_file",
                        "category": "filesystem",
                        "version": "1.0.0",
                    }
                ]
            )

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("Filesystem MCP", printed)
        self.assertIn("read_file", printed)
        self.assertIn("filesystem", printed)

    def test_cli_plugin_printers_display_metadata(self):
        plugin = {
            "plugin_id": "langgraph",
            "name": "LangGraph",
            "kind": "integration",
            "status": "reference",
            "status_label": "Available",
            "version": "0.1.0",
            "plugin_api_version": "1.0",
            "registry_version": "0.1",
            "supported_plugin_api_version": "1.0",
            "module": "src.sdk.integrations.langgraph",
            "entrypoint": "OpenMeshLangGraph",
            "package": "langgraph",
            "package_version": "1.0.0",
            "available": True,
            "active": False,
            "description": "Observe LangGraph workflows.",
            "capabilities": ["node.lifecycle"],
            "validation": {
                "status": "valid",
                "errors": [],
                "warnings": [],
            },
        }
        with patch("builtins.print") as printer:
            _print_plugins([plugin])
            _print_plugin_detail(plugin)
            _print_plugin_validation(plugin)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Plugins", printed)
        self.assertIn("langgraph", printed)
        self.assertIn("OpenMesh Plugin: LangGraph", printed)
        self.assertIn("OpenMesh Plugin Validation: langgraph", printed)
        self.assertIn("node.lifecycle", printed)
        self.assertIn("loadable: yes", printed)

    def test_cli_federation_printers_display_metadata(self):
        registry = build_federation_registry(
            [],
            [],
            [],
            peers=[
                {
                    "instance_id": "remote-a",
                    "name": "Remote A",
                    "organization": "research",
                    "cluster": "agents",
                    "endpoint": "https://remote-a.example/openmesh",
                }
            ],
        )
        inspection = {
            "node": registry["peers"][0],
            "node_id": registry["peers"][0]["id"],
            "name": registry["peers"][0]["name"],
            "status": registry["peers"][0]["status"],
            "organization": registry["peers"][0]["organization"],
            "cluster": registry["peers"][0]["cluster"],
            "endpoint": registry["peers"][0]["endpoint"],
            "capabilities": registry["peers"][0]["capabilities"],
            "relationships": registry["relationships"],
            "snapshot": registry["snapshot"],
            "policy": registry["policy"],
        }
        with patch("builtins.print") as printer:
            _print_federation(registry)
            _print_federation_peers(registry["peers"])
            _print_federation_inspection(inspection)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Federation", printed)
        self.assertIn("OpenMesh Federation Peers", printed)
        self.assertIn("Remote A", printed)
        self.assertIn("metadata_only", printed)

    def test_cli_evaluation_printer_displays_metrics(self):
        report = {
            "schema_version": "0.1",
            "generated_at": "2026-06-03T00:00:00Z",
            "sizes": [14],
            "benchmarks": [
                {
                    "node_count": 14,
                    "event_count": 14,
                    "trace_count": 1,
                    "graph_size": {"nodes": 14, "edges": 7},
                    "metrics": [
                        {
                            "name": "graph_reduction",
                            "elapsed_ms": 1.23,
                            "peak_memory_mb": 0.5,
                            "details": {"nodes": 14, "edges": 7},
                        }
                    ],
                }
            ],
            "notes": ["synthetic test"],
        }
        with patch("builtins.print") as printer:
            _print_evaluation(report)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Evaluation", printed)
        self.assertIn("Synthetic ecosystem: 14 nodes", printed)
        self.assertIn("graph_reduction", printed)
        self.assertIn("synthetic test", printed)

    def test_cli_workflow_printer_displays_metadata(self):
        with patch("builtins.print") as printer:
            _print_workflows(
                [
                    {
                        "workflow_id": "workflow:langgraph:research-flow",
                        "workflow": "Research Flow",
                        "workflow_type": "LangGraph",
                        "status": "completed",
                        "started_at": "2026-06-03T10:00:00Z",
                    }
                ]
            )

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("Research Flow", printed)
        self.assertIn("LangGraph", printed)
        self.assertIn("completed", printed)

    def test_cli_workflow_inspection_printer_displays_participants(self):
        with patch("builtins.print") as printer:
            _print_workflow_inspection(
                {
                    "workflow_id": "workflow:langgraph:research-flow",
                    "workflow": "Research Flow",
                    "workflow_type": "LangGraph",
                    "runtime": "LangGraph",
                    "status": "completed",
                    "started_at": "2026-06-03T10:00:00Z",
                    "ended_at": "2026-06-03T10:05:00Z",
                    "event_count": 6,
                    "relationship_count": 4,
                    "participating_agents": [
                        {
                            "name": "Research Agent",
                            "type": "agent",
                            "relationship_type": "runs",
                            "direction": "incoming",
                            "event_count": 1,
                        }
                    ],
                    "participating_tools": [],
                    "participating_mcp_servers": [],
                    "participating_services": [],
                    "trace_ids": ["trace_workflow"],
                    "session_ids": ["sess_workflow"],
                    "provenance": {
                        "event_ids": ["evt_workflow"],
                        "first_seen": "2026-06-03T10:00:00Z",
                        "last_seen": "2026-06-03T10:05:00Z",
                        "first_event_id": "evt_start",
                        "last_event_id": "evt_end",
                    },
                }
            )

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("Research Flow", printed)
        self.assertIn("Participating Agents", printed)
        self.assertIn("Research Agent", printed)
        self.assertIn("Workflow Provenance", printed)

    def test_cli_snapshot_printers_display_counts_and_statistics(self):
        snapshot = {
            "snapshot_id": "snap_test",
            "schema_version": "0.1",
            "created_at": "2026-06-03T10:00:00Z",
            "counts": {
                "agents": 1,
                "tools": 1,
                "workflows": 1,
                "processes": 0,
                "services": 1,
                "mcp_servers": 1,
                "capabilities": 1,
                "nodes": 6,
                "edges": 4,
                "traces": 2,
                "sessions": 1,
                "events": 8,
            },
            "graph_statistics": {
                "node_count": 6,
                "edge_count": 4,
                "node_types": {"agent": 1},
                "relationship_types": {"uses": 1},
                "validation_status": "OK",
            },
            "ecosystem_statistics": {
                "entity_count": 6,
                "relationship_count": 4,
                "groups": {"agents": 1},
                "validation_status": "OK",
            },
            "contents": {
                "agents": [{}],
                "tools": [{}],
                "workflows": [{}],
                "processes": [],
                "services": [{}],
                "mcp_servers": [{}],
                "capabilities": [{}],
                "relationships": [{}, {}, {}, {}],
                "traces": [{}, {}],
                "sessions": [{}],
            },
        }
        with patch("builtins.print") as printer:
            _print_snapshots([snapshot])
            _print_snapshot_detail(snapshot)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("snap_test", printed)
        self.assertIn("Graph Statistics", printed)
        self.assertIn("Ecosystem Statistics", printed)
        self.assertIn("Relationships: 4", printed)

    def test_cli_snapshot_diff_printer_displays_changes(self):
        before = self.make_snapshot_payload(
            "snap_before",
            created_at="2026-06-03T10:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "event_count": 1,
                }
            ],
            relationships=[],
            traces=[{"trace_id": "trace_a"}],
            sessions=[{"session_id": "sess_a"}],
        )
        after = self.make_snapshot_payload(
            "snap_after",
            created_at="2026-06-03T11:00:00Z",
            nodes=[
                {
                    "id": "agent-a",
                    "type": "agent",
                    "name": "Research Agent",
                    "event_count": 1,
                },
                {
                    "id": "process:pytest",
                    "type": "process",
                    "name": "pytest",
                    "event_count": 1,
                },
            ],
            relationships=[],
            traces=[{"trace_id": "trace_a"}, {"trace_id": "trace_b"}],
            sessions=[{"session_id": "sess_a"}],
        )
        diff = compare_snapshot_payloads(before, after)

        with patch("builtins.print") as printer:
            _print_snapshot_diff(diff)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Snapshot Diff", printed)
        self.assertIn("nodes_added: 1", printed)
        self.assertIn("Nodes Added", printed)
        self.assertIn("pytest", printed)

    def test_cli_timeline_printer_displays_sections(self):
        timeline = {
            "scope": "ecosystem",
            "subject": {"type": "ecosystem", "id": "openmesh.ecosystem"},
            "first_appearance": "2026-06-03T10:00:00Z",
            "last_appearance": "2026-06-03T10:05:00Z",
            "summary": {
                "events": 1,
                "sessions": 1,
                "snapshots": 1,
                "relationship_changes": 1,
            },
            "relationship_changes": [
                {
                    "timestamp": "2026-06-03T10:00:00Z",
                    "kind": "relationship.observed",
                    "source": "agent-a",
                    "target": "workflow:research",
                    "relationship_type": "runs",
                }
            ],
            "workflow_changes": [],
            "capability_changes": [],
            "mcp_changes": [],
            "session_history": [
                {
                    "session_id": "sess_timeline",
                    "command": "langgraph basic",
                    "started_at": "2026-06-03T10:00:00Z",
                    "status": "completed",
                }
            ],
            "snapshot_history": [
                {
                    "snapshot_id": "snap_timeline",
                    "created_at": "2026-06-03T10:05:00Z",
                    "counts": {"nodes": 2, "edges": 1},
                }
            ],
            "timeline": [
                {
                    "timestamp": "2026-06-03T10:00:00Z",
                    "kind": "event",
                    "event_type": "workflow.registered",
                    "event_id": "evt_timeline",
                    "source": "Research Agent",
                    "target": "Research Flow",
                }
            ],
        }

        with patch("builtins.print") as printer:
            _print_timeline(timeline)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Ecosystem Timeline", printed)
        self.assertIn("Relationship Changes", printed)
        self.assertIn("Snapshot History", printed)
        self.assertIn("workflow.registered", printed)

    def test_cli_replay_printer_displays_controls_and_frames(self):
        replay = {
            "scope": "trace",
            "subject": {"trace_id": "trace_replay"},
            "controls": [
                {"name": "start", "description": "Begin playback."},
                {"name": "pause", "description": "Hold playback."},
                {"name": "stop", "description": "Stop playback."},
                {"name": "step", "description": "Advance one frame."},
            ],
            "state": {
                "control": "pause",
                "status": "paused",
                "position": 1,
                "frame_count": 2,
                "current_frame": {
                    "frame_index": 1,
                    "timestamp": "2026-06-03T10:01:00Z",
                    "action": "relationship.created",
                    "description": "Research Agent runs Research Flow",
                },
            },
            "summary": {"frames": 2, "nodes": 1, "relationships": 1},
            "visible_frames": [
                {
                    "frame_index": 0,
                    "timestamp": "2026-06-03T10:00:00Z",
                    "action": "node.appeared",
                    "description": "Research Agent appeared",
                },
                {
                    "frame_index": 1,
                    "timestamp": "2026-06-03T10:01:00Z",
                    "action": "relationship.created",
                    "description": "Research Agent runs Research Flow",
                },
            ],
        }

        with patch("builtins.print") as printer:
            _print_replay(replay)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Trace Replay", printed)
        self.assertIn("control: pause", printed)
        self.assertIn("Controls", printed)
        self.assertIn("relationship.created", printed)

    def test_cli_query_printer_displays_results(self):
        result = {
            "query": "agents using web_search",
            "status": "ok",
            "category": "Agents",
            "intent": "agents_using_tool",
            "source": ["graph", "provenance"],
            "count": 1,
            "metadata": {},
            "errors": [],
            "results": [
                {
                    "agent": "Research Agent",
                    "agent_id": "agent-a",
                    "source": "Research Agent",
                    "target": "web_search",
                    "relationship_type": "uses",
                    "event_count": 2,
                }
            ],
        }

        with patch("builtins.print") as printer:
            _print_query_result(result)

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Query", printed)
        self.assertIn("agents using web_search", printed)
        self.assertIn("Research Agent --uses--> web_search", printed)

    def test_cli_ecosystem_printer_displays_grouped_inventory(self):
        with patch("builtins.print") as printer:
            _print_ecosystem(
                {
                    "entities": {
                        "agents": [
                            {
                                "name": "Research Agent",
                                "status": "active",
                                "event_count": 1,
                                "relationship_count": 1,
                                "last_seen": "2026-06-03T10:00:00Z",
                            }
                        ],
                        "tools": [],
                        "processes": [],
                        "workflows": [
                            {
                                "name": "Research Flow",
                                "status": "active",
                                "event_count": 3,
                                "relationship_count": 2,
                                "last_seen": "2026-06-03T10:00:00Z",
                            }
                        ],
                        "mcp_servers": [],
                        "mcp_configs": [],
                        "capabilities": [],
                    },
                    "summary": {"entity_count": 2, "relationship_count": 2},
                }
            )

        printed = "\n".join(
            str(call.args[0]) for call in printer.call_args_list if call.args
        )
        self.assertIn("OpenMesh Ecosystem", printed)
        self.assertIn("Research Agent", printed)
        self.assertIn("Research Flow", printed)


if __name__ == "__main__":
    unittest.main()
