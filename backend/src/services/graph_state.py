from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from ..db.models import OpenMeshEventRecord


EDGE_TYPES = {
    "process.started": "spawned",
    "process.completed": "executed",
    "process.failed": "executed",
    "tool.call.started": "calls_tool",
    "tool.call.completed": "calls_tool",
    "message.sent": "communicates_with",
    "delegation.created": "delegates_to",
    "node.transition": "transitions_to",
}


def _node_from_json(node: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not node:
        return None
    return {
        "id": node["node_id"],
        "type": node["node_type"],
        "name": node["name"],
        "runtime": node.get("runtime"),
        "metadata": node.get("metadata", {}),
        "event_count": 0,
        "last_seen": None,
    }


def edge_type_for(event_type: str, target_type: Optional[str]) -> Optional[str]:
    if event_type in EDGE_TYPES:
        return EDGE_TYPES[event_type]
    if target_type == "tool":
        return "calls_tool"
    if target_type == "agent":
        return "communicates_with"
    return None


def _edge_type_for(event_type: str, target_type: Optional[str]) -> Optional[str]:
    return edge_type_for(event_type, target_type)


def reduce_graph_state(records: Iterable[OpenMeshEventRecord]) -> Dict[str, list[Dict[str, Any]]]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: Dict[str, Dict[str, Any]] = {}

    for record in records:
        source = _node_from_json(record.source_json)
        target = _node_from_json(record.target_json)

        for node in (source, target):
            if not node:
                continue
            existing = nodes.get(node["id"], node)
            existing["event_count"] = existing.get("event_count", 0) + 1
            existing["last_seen"] = record.timestamp.isoformat() + "Z"
            nodes[node["id"]] = existing

        if source and target:
            edge_type = _edge_type_for(record.event_type, target["type"])
            if edge_type:
                event_id = getattr(record, "event_id", f"{record.event_type}:{record.timestamp.isoformat()}")
                edge_id = f"{source['id']}:{edge_type}:{target['id']}"
                edge = edges.get(edge_id, {
                    "id": edge_id,
                    "source": source["id"],
                    "target": target["id"],
                    "type": edge_type,
                    "event_count": 0,
                    "last_seen": None,
                    "trace_ids": [],
                    "event_ids": [],
                    "last_event_id": None,
                })
                edge["event_count"] += 1
                edge["last_seen"] = record.timestamp.isoformat() + "Z"
                edge["last_event_id"] = event_id
                trace_id = getattr(record, "trace_id", None)
                if trace_id and trace_id not in edge["trace_ids"]:
                    edge["trace_ids"].append(trace_id)
                if event_id not in edge["event_ids"]:
                    edge["event_ids"].append(event_id)
                edges[edge_id] = edge

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
