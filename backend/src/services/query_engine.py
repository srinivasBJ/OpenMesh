from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..db.openmesh_sessions import list_openmesh_sessions, session_to_dict
from ..db.openmesh_snapshots import list_openmesh_snapshots, snapshot_record_to_detail
from .discovery import build_discovery
from .ecosystem_snapshot import compare_snapshot_payloads
from .graph_state import reduce_graph_state
from .openmesh_queries import trace_summary
from .timeline import build_timeline


QUERY_CATEGORIES = (
    "Agents",
    "Tools",
    "Workflows",
    "Services",
    "Processes",
    "Capabilities",
    "MCP Servers",
    "Relationships",
    "Traces",
    "Sessions",
    "Snapshots",
)

SAVED_QUERIES: list[dict[str, str]] = [
    {
        "category": "Agents",
        "name": "Agents using web_search",
        "query": "agents using web_search",
    },
    {
        "category": "Workflows",
        "name": "Workflows using search",
        "query": "workflows using search",
    },
    {
        "category": "Relationships",
        "name": "Relationships created today",
        "query": "relationships created since 2026-06-03T00:00:00Z",
    },
    {
        "category": "Snapshots",
        "name": "Nodes added between latest snapshots",
        "query": "nodes added between snapshots",
    },
    {
        "category": "Traces",
        "name": "Traces involving OpenMesh CLI",
        "query": "traces involving OpenMesh CLI",
    },
    {
        "category": "Capabilities",
        "name": "Capabilities exposed by Search MCP",
        "query": "capabilities exposed by Search MCP",
    },
]


@dataclass(frozen=True)
class ParsedQuery:
    intent: str
    category: str
    parameters: dict[str, Any]


async def execute_query(
    db: AsyncSession,
    query: str,
    *,
    limit: int = 5000,
    snapshot_limit: int = 100,
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    sessions = await list_openmesh_sessions(db, limit=limit)
    snapshot_records = await list_openmesh_snapshots(db, limit=snapshot_limit)
    snapshots = [snapshot_record_to_detail(record) for record in snapshot_records]
    graph = reduce_graph_state(records)
    return run_query_on_state(
        query,
        graph=graph,
        discovery=build_discovery(records),
        traces=_trace_summaries(records),
        sessions=[session_to_dict(record) for record in sessions],
        snapshots=snapshots,
        timeline=build_timeline(records, sessions, snapshots),
    )


def run_query_on_state(
    query: str,
    *,
    graph: dict[str, Any],
    discovery: dict[str, list[dict[str, Any]]] | None = None,
    traces: list[dict[str, Any]] | None = None,
    sessions: list[dict[str, Any]] | None = None,
    snapshots: list[dict[str, Any]] | None = None,
    timeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_query(query)
    context = {
        "graph": graph,
        "discovery": discovery or {},
        "traces": traces or [],
        "sessions": sessions or [],
        "snapshots": snapshots or [],
        "timeline": timeline or {},
    }
    if parsed is None:
        return _result(
            query=query,
            status="unsupported",
            category="Unknown",
            intent="unsupported",
            source=["query_parser"],
            parameters={},
            results=[],
            errors=[
                {
                    "code": "unsupported_query",
                    "message": "Unsupported OpenMesh query. Use a supported structured query form.",
                }
            ],
        )

    handlers = {
        "agents_using_tool": _agents_using_tool,
        "workflows_using_capability": _workflows_using_capability,
        "relationships_created_since": _relationships_created_since,
        "nodes_added_between_snapshots": _nodes_between_snapshots,
        "nodes_removed_between_snapshots": _nodes_between_snapshots,
        "traces_involving_node": _traces_involving_node,
        "sessions_involving_node": _sessions_involving_node,
        "capabilities_exposed_by_mcp": _capabilities_exposed_by_mcp,
    }
    return handlers[parsed.intent](query, parsed, context)


def parse_query(query: str) -> ParsedQuery | None:
    text = _collapse(query)
    if not text:
        return None

    match = re.fullmatch(r"agents\s+using\s+(.+)", text, re.IGNORECASE)
    if match:
        return ParsedQuery(
            "agents_using_tool", "Agents", {"tool": match.group(1).strip()}
        )

    match = re.fullmatch(r"workflows\s+using\s+(.+)", text, re.IGNORECASE)
    if match:
        return ParsedQuery(
            "workflows_using_capability",
            "Workflows",
            {"capability": match.group(1).strip()},
        )

    match = re.fullmatch(r"relationships\s+created\s+since\s+(.+)", text, re.IGNORECASE)
    if match:
        return ParsedQuery(
            "relationships_created_since",
            "Relationships",
            {"timestamp": match.group(1).strip()},
        )

    match = re.fullmatch(
        r"nodes\s+(added|removed)\s+between\s+snapshots(?:\s+(\S+)\s+(\S+))?",
        text,
        re.IGNORECASE,
    )
    if match:
        direction = match.group(1).lower()
        return ParsedQuery(
            f"nodes_{direction}_between_snapshots",
            "Snapshots",
            {"snapshot_a": match.group(2), "snapshot_b": match.group(3)},
        )

    match = re.fullmatch(r"traces\s+involving\s+(.+)", text, re.IGNORECASE)
    if match:
        return ParsedQuery(
            "traces_involving_node", "Traces", {"node": match.group(1).strip()}
        )

    match = re.fullmatch(r"sessions\s+involving\s+(.+)", text, re.IGNORECASE)
    if match:
        return ParsedQuery(
            "sessions_involving_node", "Sessions", {"node": match.group(1).strip()}
        )

    match = re.fullmatch(r"capabilities\s+exposed\s+by\s+(.+)", text, re.IGNORECASE)
    if match:
        return ParsedQuery(
            "capabilities_exposed_by_mcp",
            "Capabilities",
            {"mcp": match.group(1).strip()},
        )

    return None


def _agents_using_tool(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    graph = context["graph"]
    nodes = _nodes_by_id(graph)
    tool = _find_node(graph, parsed.parameters["tool"], node_types={"tool"})
    if not tool:
        return _not_found(query, parsed, "tool_not_found", "Tool not found.")
    results = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "uses" or edge.get("target") != tool["id"]:
            continue
        agent = nodes.get(edge.get("source"))
        if not agent or agent.get("type") != "agent":
            continue
        results.append(
            {
                "agent_id": agent["id"],
                "agent": agent["name"],
                "tool_id": tool["id"],
                "tool": tool["name"],
                **_relationship_result(edge, nodes),
            }
        )
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph", "provenance"],
        parameters={**parsed.parameters, "tool_id": tool["id"]},
        results=sorted(results, key=lambda item: (item["agent"], item["agent_id"])),
    )


def _workflows_using_capability(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    graph = context["graph"]
    nodes = _nodes_by_id(graph)
    capability = _find_node(
        graph, parsed.parameters["capability"], node_types={"capability", "tool"}
    )
    if not capability:
        return _not_found(
            query, parsed, "capability_not_found", "Capability not found."
        )

    exposing_mcp_ids = {
        edge["source"]
        for edge in graph.get("edges", [])
        if edge.get("type") == "exposes" and edge.get("target") == capability["id"]
    }
    results = []
    for edge in graph.get("edges", []):
        source = nodes.get(edge.get("source"))
        target = nodes.get(edge.get("target"))
        if not source or source.get("type") != "workflow":
            continue
        direct_capability = edge.get("target") == capability["id"] and edge.get(
            "type"
        ) in {
            "uses",
            "connects_to",
        }
        connected_mcp = (
            edge.get("target") in exposing_mcp_ids and edge.get("type") == "connects_to"
        )
        matching_tool = (
            target
            and target.get("type") == "tool"
            and _node_matches(target, capability["name"])
            and edge.get("type") == "uses"
        )
        if not (direct_capability or connected_mcp or matching_tool):
            continue
        results.append(
            {
                "workflow_id": source["id"],
                "workflow": source["name"],
                "capability_id": capability["id"],
                "capability": capability["name"],
                **_relationship_result(edge, nodes),
            }
        )
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph", "capability_registry", "provenance"],
        parameters={**parsed.parameters, "capability_id": capability["id"]},
        results=sorted(
            results, key=lambda item: (item["workflow"], item["workflow_id"])
        ),
    )


def _relationships_created_since(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    graph = context["graph"]
    nodes = _nodes_by_id(graph)
    timestamp = parsed.parameters["timestamp"]
    results = [
        _relationship_result(edge, nodes)
        for edge in graph.get("edges", [])
        if _timestamp_gte(edge.get("first_seen"), timestamp)
    ]
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph", "timeline", "provenance"],
        parameters=parsed.parameters,
        results=sorted(results, key=lambda item: item.get("first_seen") or ""),
    )


def _nodes_between_snapshots(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    snapshots = context["snapshots"]
    snapshot_a, snapshot_b = _select_snapshot_pair(
        snapshots,
        parsed.parameters.get("snapshot_a"),
        parsed.parameters.get("snapshot_b"),
    )
    if not snapshot_a or not snapshot_b:
        return _result(
            query=query,
            status="not_found",
            category=parsed.category,
            intent=parsed.intent,
            source=["snapshot_diff"],
            parameters=parsed.parameters,
            results=[],
            errors=[
                {
                    "code": "snapshot_pair_not_found",
                    "message": "At least two matching snapshots are required.",
                }
            ],
        )
    diff = compare_snapshot_payloads(snapshot_a, snapshot_b)
    direction = (
        "added" if parsed.intent == "nodes_added_between_snapshots" else "removed"
    )
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["snapshot_diff"],
        parameters={
            **parsed.parameters,
            "snapshot_a": snapshot_a.get("snapshot_id"),
            "snapshot_b": snapshot_b.get("snapshot_id"),
        },
        results=diff["nodes"][direction],
        metadata={
            "snapshot_a": diff["snapshot_a"],
            "snapshot_b": diff["snapshot_b"],
            "diff_summary": diff["summary"],
        },
    )


def _traces_involving_node(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    graph = context["graph"]
    node = _find_node(graph, parsed.parameters["node"])
    if not node:
        return _not_found(query, parsed, "node_not_found", "Node not found.")
    trace_ids = _node_trace_ids(graph, node["id"])
    traces_by_id = {trace["trace_id"]: trace for trace in context["traces"]}
    results = [
        {**traces_by_id.get(trace_id, {"trace_id": trace_id}), "node_id": node["id"]}
        for trace_id in trace_ids
    ]
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph", "trace_store", "provenance"],
        parameters={**parsed.parameters, "node_id": node["id"]},
        results=sorted(
            results, key=lambda item: item.get("started_at") or "", reverse=True
        ),
    )


def _sessions_involving_node(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    graph = context["graph"]
    node = _find_node(graph, parsed.parameters["node"])
    if not node:
        return _not_found(query, parsed, "node_not_found", "Node not found.")
    session_ids = _node_session_ids(graph, node["id"])
    sessions_by_id = {session["session_id"]: session for session in context["sessions"]}
    results = [
        {
            **sessions_by_id.get(session_id, {"session_id": session_id}),
            "node_id": node["id"],
        }
        for session_id in session_ids
    ]
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph", "session_store", "provenance"],
        parameters={**parsed.parameters, "node_id": node["id"]},
        results=sorted(
            results, key=lambda item: item.get("started_at") or "", reverse=True
        ),
    )


def _capabilities_exposed_by_mcp(
    query: str, parsed: ParsedQuery, context: dict[str, Any]
) -> dict[str, Any]:
    graph = context["graph"]
    nodes = _nodes_by_id(graph)
    mcp = _find_node(graph, parsed.parameters["mcp"], node_types={"mcp_server"})
    if not mcp:
        return _not_found(query, parsed, "mcp_not_found", "MCP server not found.")
    results = []
    for edge in graph.get("edges", []):
        if edge.get("type") != "exposes" or edge.get("source") != mcp["id"]:
            continue
        capability = nodes.get(edge.get("target"))
        if not capability or capability.get("type") != "capability":
            continue
        results.append(
            {
                "mcp_id": mcp["id"],
                "mcp": mcp["name"],
                "capability_id": capability["id"],
                "capability": capability["name"],
                **_relationship_result(edge, nodes),
            }
        )
    return _result(
        query=query,
        status="ok",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph", "mcp_registry", "capability_registry", "provenance"],
        parameters={**parsed.parameters, "mcp_id": mcp["id"]},
        results=sorted(
            results, key=lambda item: (item["capability"], item["capability_id"])
        ),
    )


def _result(
    *,
    query: str,
    status: str,
    category: str,
    intent: str,
    source: list[str],
    parameters: dict[str, Any],
    results: list[dict[str, Any]],
    errors: list[dict[str, str]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "query": query,
        "normalized_query": _collapse(query),
        "status": status,
        "category": category,
        "intent": intent,
        "parameters": parameters,
        "source": source,
        "count": len(results),
        "results": results,
        "errors": errors or [],
        "metadata": metadata or {},
        "categories": list(QUERY_CATEGORIES),
        "examples": SAVED_QUERIES,
    }


def _not_found(
    query: str, parsed: ParsedQuery, code: str, message: str
) -> dict[str, Any]:
    return _result(
        query=query,
        status="not_found",
        category=parsed.category,
        intent=parsed.intent,
        source=["graph"],
        parameters=parsed.parameters,
        results=[],
        errors=[{"code": code, "message": message}],
    )


def _relationship_result(
    edge: dict[str, Any], nodes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    source = nodes.get(edge.get("source"), {"name": edge.get("source")})
    target = nodes.get(edge.get("target"), {"name": edge.get("target")})
    provenance = edge.get("provenance") or {}
    return {
        "relationship_id": edge.get("id"),
        "relationship_type": edge.get("type") or edge.get("relationship_type"),
        "source_id": edge.get("source"),
        "source": source.get("name"),
        "source_type": source.get("type"),
        "target_id": edge.get("target"),
        "target": target.get("name"),
        "target_type": target.get("type"),
        "event_count": edge.get("event_count", 0),
        "observation_count": edge.get("observation_count", 0),
        "first_seen": edge.get("first_seen"),
        "last_seen": edge.get("last_seen"),
        "trace_ids": provenance.get("trace_ids") or edge.get("trace_ids", []),
        "session_ids": provenance.get("session_ids") or edge.get("session_ids", []),
        "event_ids": provenance.get("event_ids") or edge.get("event_ids", []),
        "provenance": provenance,
    }


def _trace_summaries(records: Iterable[OpenMeshEventRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[OpenMeshEventRecord]] = {}
    for record in records:
        grouped.setdefault(record.trace_id, []).append(record)
    return sorted(
        [
            trace_summary(trace_id, trace_records)
            for trace_id, trace_records in grouped.items()
        ],
        key=lambda item: item.get("started_at") or "",
        reverse=True,
    )


def _nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in graph.get("nodes", [])}


def _find_node(
    graph: dict[str, Any], node_ref: str, *, node_types: set[str] | None = None
) -> dict[str, Any] | None:
    candidates = [
        node
        for node in graph.get("nodes", [])
        if (node_types is None or node.get("type") in node_types)
        and _node_matches(node, node_ref)
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.get("type", ""), item["id"]))[0]


def _node_matches(node: dict[str, Any], value: str) -> bool:
    normalized = _normalize(value)
    aliases = {
        node.get("id"),
        node.get("node_id"),
        node.get("name"),
        str(node.get("id") or "").split(":", 1)[-1],
        str(node.get("name") or "").replace(" ", "-"),
        str(node.get("name") or "").replace(" ", "_"),
    }
    metadata = node.get("metadata") or {}
    for key in ("server", "capability", "workflow", "framework", "endpoint"):
        if metadata.get(key):
            aliases.add(str(metadata[key]))
    return normalized in {_normalize(alias) for alias in aliases if alias}


def _node_trace_ids(graph: dict[str, Any], node_id: str) -> list[str]:
    node = _nodes_by_id(graph).get(node_id, {})
    values = list(
        node.get("provenance", {}).get("trace_ids") or node.get("trace_ids", [])
    )
    for edge in graph.get("edges", []):
        if node_id in {edge.get("source"), edge.get("target")}:
            values.extend(
                edge.get("provenance", {}).get("trace_ids") or edge.get("trace_ids", [])
            )
    return _dedupe(values)


def _node_session_ids(graph: dict[str, Any], node_id: str) -> list[str]:
    node = _nodes_by_id(graph).get(node_id, {})
    values = list(
        node.get("provenance", {}).get("session_ids") or node.get("session_ids", [])
    )
    for edge in graph.get("edges", []):
        if node_id in {edge.get("source"), edge.get("target")}:
            values.extend(
                edge.get("provenance", {}).get("session_ids")
                or edge.get("session_ids", [])
            )
    return _dedupe(values)


def _select_snapshot_pair(
    snapshots: list[dict[str, Any]], snapshot_a: str | None, snapshot_b: str | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if snapshot_a and snapshot_b:
        return _find_snapshot(snapshots, snapshot_a), _find_snapshot(
            snapshots, snapshot_b
        )
    if len(snapshots) < 2:
        return None, None
    latest_two = sorted(
        sorted(snapshots, key=lambda item: item.get("created_at") or "", reverse=True)[
            :2
        ],
        key=lambda item: item.get("created_at") or "",
    )
    return latest_two[0], latest_two[1]


def _find_snapshot(
    snapshots: list[dict[str, Any]], snapshot_id: str
) -> dict[str, Any] | None:
    normalized_ref = _normalize(snapshot_id)
    for snapshot in snapshots:
        candidate = str(snapshot.get("snapshot_id") or "")
        if _normalize(candidate) == normalized_ref or candidate.startswith(snapshot_id):
            return snapshot
    return None


def _timestamp_gte(value: str | None, threshold: str) -> bool:
    if not value:
        return False
    return _timestamp_key(value) >= _timestamp_key(threshold)


def _timestamp_key(value: str) -> str:
    return value.replace("Z", "+00:00")


def _dedupe(values: list[Any]) -> list[Any]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _collapse(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
