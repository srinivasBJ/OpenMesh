from __future__ import annotations

from collections import deque
from typing import Any


VALID_DIRECTIONS = {"incoming", "outgoing", "both"}


def select_graph_node(graph: dict[str, Any], node_ref: str) -> dict[str, Any] | None:
    node = _find_node(graph, node_ref)
    if not node:
        return None
    nodes = _nodes_by_id(graph)
    incoming = [
        _relationship_summary(edge, nodes, selected_node_id=node["id"])
        for edge in graph.get("edges", [])
        if edge.get("target") == node["id"]
    ]
    outgoing = [
        _relationship_summary(edge, nodes, selected_node_id=node["id"])
        for edge in graph.get("edges", [])
        if edge.get("source") == node["id"]
    ]
    return {
        "node": node,
        "node_id": node["id"],
        "name": node.get("name"),
        "node_type": node.get("type"),
        "incoming_relationships": sorted(
            incoming,
            key=lambda item: (
                str(item.get("relationship_type") or ""),
                str(item.get("node_name") or ""),
            ),
        ),
        "outgoing_relationships": sorted(
            outgoing,
            key=lambda item: (
                str(item.get("relationship_type") or ""),
                str(item.get("node_name") or ""),
            ),
        ),
        "navigation_targets": sorted(
            incoming + outgoing,
            key=lambda item: (
                str(item.get("node_type") or ""),
                str(item.get("node_name") or ""),
                str(item.get("node_id") or ""),
            ),
        ),
    }


def traverse_graph_relationships(
    graph: dict[str, Any],
    node_ref: str,
    *,
    direction: str = "both",
    relationship_type: str | None = None,
    node_type: str | None = None,
    limit: int = 100,
) -> dict[str, Any] | None:
    direction = _normalize_direction(direction)
    node = _find_node(graph, node_ref)
    if not node:
        return None
    nodes = _nodes_by_id(graph)
    relationships = [
        _relationship_summary(edge, nodes, selected_node_id=node["id"])
        for edge in graph.get("edges", [])
        if _edge_matches(
            edge,
            node["id"],
            direction=direction,
            relationship_type=relationship_type,
            node_type=node_type,
            nodes=nodes,
        )
    ][: max(limit, 0)]
    return {
        "root": _node_summary(node),
        "direction": direction,
        "relationship_type": relationship_type,
        "node_type": node_type,
        "relationship_count": len(relationships),
        "relationships": relationships,
    }


def expand_graph_neighborhood(
    graph: dict[str, Any],
    node_ref: str,
    *,
    depth: int = 1,
    direction: str = "both",
    relationship_type: str | None = None,
    node_type: str | None = None,
    limit: int = 200,
) -> dict[str, Any] | None:
    direction = _normalize_direction(direction)
    depth = max(0, min(depth, 4))
    limit = max(limit, 0)
    root = _find_node(graph, node_ref)
    if not root:
        return None
    nodes = _nodes_by_id(graph)
    edges_by_node = _edges_by_node(graph)
    visited_nodes = {root["id"]}
    included_edges: dict[str, dict[str, Any]] = {}
    frontier: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    queue = deque([(root["id"], 0, [root["id"]], [])])

    while queue and len(visited_nodes) <= limit:
        node_id, current_depth, path_nodes, path_edges = queue.popleft()
        if current_depth == depth:
            if node_id != root["id"]:
                frontier.append(_node_summary(nodes[node_id]))
            continue
        for edge in edges_by_node.get(node_id, []):
            if not _edge_allowed_for_direction(edge, node_id, direction):
                continue
            if relationship_type and edge.get("type") != relationship_type:
                continue
            neighbor_id = (
                edge["target"] if edge["source"] == node_id else edge["source"]
            )
            neighbor = nodes.get(neighbor_id)
            if not neighbor:
                continue
            if node_type and neighbor.get("type") != node_type:
                continue
            included_edges[edge["id"]] = edge
            next_path_nodes = [*path_nodes, neighbor_id]
            next_path_edges = [*path_edges, edge["id"]]
            paths.append(
                {
                    "from": node_id,
                    "to": neighbor_id,
                    "depth": current_depth + 1,
                    "relationship_type": edge.get("type"),
                    "edge_id": edge.get("id"),
                    "path_node_ids": next_path_nodes,
                    "path_edge_ids": next_path_edges,
                }
            )
            if neighbor_id not in visited_nodes:
                visited_nodes.add(neighbor_id)
                queue.append(
                    (neighbor_id, current_depth + 1, next_path_nodes, next_path_edges)
                )

    neighborhood_nodes = [
        nodes[node_id]
        for node_id in sorted(
            visited_nodes, key=lambda item: (nodes[item].get("type", ""), item)
        )
    ]
    neighborhood_edges = sorted(
        included_edges.values(), key=lambda item: (item.get("type", ""), item["id"])
    )
    return {
        "root": _node_summary(root),
        "depth": depth,
        "direction": direction,
        "relationship_type": relationship_type,
        "node_type": node_type,
        "nodes": neighborhood_nodes,
        "edges": neighborhood_edges,
        "frontier": frontier,
        "paths": paths[:limit],
        "statistics": {
            "node_count": len(neighborhood_nodes),
            "edge_count": len(neighborhood_edges),
            "frontier_count": len(frontier),
            "path_count": min(len(paths), limit),
        },
    }


def filter_graph(
    graph: dict[str, Any],
    *,
    node_types: set[str] | None = None,
    relationship_types: set[str] | None = None,
    query: str | None = None,
    lifecycle_state: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    nodes = _nodes_by_id(graph)
    query_text = _normalize_text(query)
    selected_nodes = {
        node_id
        for node_id, node in nodes.items()
        if _node_passes_filter(
            node,
            node_types=node_types,
            query=query_text,
            lifecycle_state=lifecycle_state,
        )
    }
    selected_edges = []
    for edge in graph.get("edges", []):
        if relationship_types and edge.get("type") not in relationship_types:
            continue
        if lifecycle_state and edge.get("lifecycle_state") != lifecycle_state:
            continue
        edge_matches_query = query_text and _edge_matches_query(edge, nodes, query_text)
        touches_selected_node = (
            edge["source"] in selected_nodes or edge["target"] in selected_nodes
        )
        if query_text and not (edge_matches_query or touches_selected_node):
            continue
        if not query_text and not touches_selected_node:
            continue
        selected_edges.append(edge)
        selected_nodes.add(edge["source"])
        selected_nodes.add(edge["target"])
        if len(selected_edges) >= limit:
            break

    filtered_nodes = [
        nodes[node_id]
        for node_id in sorted(
            selected_nodes, key=lambda item: (nodes[item].get("type", ""), item)
        )
    ][:limit]
    return {
        "nodes": filtered_nodes,
        "edges": selected_edges,
        "filters": {
            "node_types": sorted(node_types or []),
            "relationship_types": sorted(relationship_types or []),
            "query": query,
            "lifecycle_state": lifecycle_state,
            "limit": limit,
        },
        "statistics": {
            "node_count": len(filtered_nodes),
            "edge_count": len(selected_edges),
            "node_types": _count_by(filtered_nodes, "type"),
            "relationship_types": _count_by(selected_edges, "type"),
        },
    }


def search_graph(
    graph: dict[str, Any],
    query: str,
    *,
    node_type: str | None = None,
    relationship_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    query_text = _normalize_text(query)
    nodes = _nodes_by_id(graph)
    if not query_text:
        return {
            "query": query,
            "nodes": [],
            "relationships": [],
            "count": 0,
        }
    node_matches = [
        _node_summary(node)
        for node in nodes.values()
        if (not node_type or node.get("type") == node_type)
        and _node_matches_query(node, query_text)
    ][:limit]
    edge_matches = [
        _relationship_summary(edge, nodes)
        for edge in graph.get("edges", [])
        if (not relationship_type or edge.get("type") == relationship_type)
        and _edge_matches_query(edge, nodes, query_text)
    ][:limit]
    return {
        "query": query,
        "node_type": node_type,
        "relationship_type": relationship_type,
        "nodes": node_matches,
        "relationships": edge_matches,
        "count": len(node_matches) + len(edge_matches),
    }


def explore_graph_node(
    graph: dict[str, Any],
    node_ref: str,
    *,
    depth: int = 1,
    direction: str = "both",
    relationship_type: str | None = None,
    node_type: str | None = None,
    query: str | None = None,
    limit: int = 200,
) -> dict[str, Any] | None:
    selection = select_graph_node(graph, node_ref)
    if not selection:
        return None
    traversal = traverse_graph_relationships(
        graph,
        selection["node_id"],
        direction=direction,
        relationship_type=relationship_type,
        node_type=node_type,
        limit=limit,
    )
    neighborhood = expand_graph_neighborhood(
        graph,
        selection["node_id"],
        depth=depth,
        direction=direction,
        relationship_type=relationship_type,
        node_type=node_type,
        limit=limit,
    )
    search = search_graph(
        graph,
        query or str(selection.get("name") or selection["node_id"]),
        node_type=node_type,
        relationship_type=relationship_type,
        limit=min(limit, 50),
    )
    return {
        "selection": selection,
        "traversal": traversal,
        "neighborhood": neighborhood,
        "search": search,
        "filters": {
            "depth": depth,
            "direction": _normalize_direction(direction),
            "relationship_type": relationship_type,
            "node_type": node_type,
            "query": query,
            "limit": limit,
        },
    }


def graph_statistics(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": _count_by(nodes, "type"),
        "relationship_types": _count_by(edges, "type"),
        "lifecycle_states": _count_by(edges, "lifecycle_state"),
        "validation_statuses": _count_by(edges, "validation_status"),
    }


def _nodes_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in graph.get("nodes", [])}


def _edges_by_node(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    edges: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges", []):
        edges.setdefault(edge["source"], []).append(edge)
        edges.setdefault(edge["target"], []).append(edge)
    return edges


def _find_node(graph: dict[str, Any], node_ref: str) -> dict[str, Any] | None:
    normalized_ref = _normalize_ref(node_ref)
    candidates = []
    for node in graph.get("nodes", []):
        node_id = str(node.get("id", ""))
        name = str(node.get("name", ""))
        aliases = {
            node_id,
            name,
            node_id.split(":", 1)[-1],
            name.replace(" ", "-"),
            name.replace(" ", "_"),
        }
        if node_ref in aliases or normalized_ref in {
            _normalize_ref(alias) for alias in aliases
        }:
            candidates.append(node)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item.get("type", ""), item["id"]))[0]


def _relationship_summary(
    edge: dict[str, Any],
    nodes: dict[str, dict[str, Any]],
    *,
    selected_node_id: str | None = None,
) -> dict[str, Any]:
    source = nodes.get(edge["source"], {"id": edge["source"], "name": edge["source"]})
    target = nodes.get(edge["target"], {"id": edge["target"], "name": edge["target"]})
    other = target
    direction = "outgoing"
    if selected_node_id == edge.get("target"):
        other = source
        direction = "incoming"
    elif selected_node_id is None:
        other = target
        direction = "outgoing"
    provenance = edge.get("provenance") or {}
    return {
        "edge_id": edge.get("id"),
        "relationship_type": edge.get("type"),
        "direction": direction,
        "source_id": edge.get("source"),
        "source_name": source.get("name"),
        "source_type": source.get("type"),
        "target_id": edge.get("target"),
        "target_name": target.get("name"),
        "target_type": target.get("type"),
        "node_id": other.get("id"),
        "node_name": other.get("name"),
        "node_type": other.get("type"),
        "lifecycle_state": edge.get("lifecycle_state"),
        "observation_count": edge.get("observation_count", edge.get("event_count", 0)),
        "provenance": {
            "event_ids": provenance.get("event_ids", []),
            "trace_ids": provenance.get("trace_ids", []),
            "first_seen": provenance.get("first_seen") or edge.get("first_seen"),
            "last_seen": provenance.get("last_seen") or edge.get("last_seen"),
        },
    }


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node.get("id"),
        "name": node.get("name"),
        "node_type": node.get("type"),
        "category": node.get("category"),
        "lifecycle_state": node.get("lifecycle_state"),
        "event_count": node.get("event_count", 0),
        "relationship_count": node.get("relationship_count"),
        "first_seen": node.get("first_seen"),
        "last_seen": node.get("last_seen"),
    }


def _node_passes_filter(
    node: dict[str, Any],
    *,
    node_types: set[str] | None,
    query: str | None,
    lifecycle_state: str | None,
) -> bool:
    if node_types and node.get("type") not in node_types:
        return False
    if lifecycle_state and node.get("lifecycle_state") != lifecycle_state:
        return False
    if query and not _node_matches_query(node, query):
        return False
    return True


def _edge_matches(
    edge: dict[str, Any],
    node_id: str,
    *,
    direction: str,
    relationship_type: str | None,
    node_type: str | None,
    nodes: dict[str, dict[str, Any]],
) -> bool:
    if relationship_type and edge.get("type") != relationship_type:
        return False
    if not _edge_allowed_for_direction(edge, node_id, direction):
        return False
    neighbor_id = edge["target"] if edge["source"] == node_id else edge["source"]
    neighbor = nodes.get(neighbor_id)
    if node_type and (not neighbor or neighbor.get("type") != node_type):
        return False
    return True


def _edge_allowed_for_direction(
    edge: dict[str, Any], node_id: str, direction: str
) -> bool:
    return (
        (
            direction == "both"
            and (edge.get("source") == node_id or edge.get("target") == node_id)
        )
        or (direction == "outgoing" and edge.get("source") == node_id)
        or (direction == "incoming" and edge.get("target") == node_id)
    )


def _node_matches_query(node: dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        [
            str(node.get("id", "")),
            str(node.get("name", "")),
            str(node.get("type", "")),
            str(node.get("runtime", "")),
            " ".join(str(value) for value in (node.get("metadata") or {}).values()),
        ]
    )
    return query in _normalize_text(haystack)


def _edge_matches_query(
    edge: dict[str, Any], nodes: dict[str, dict[str, Any]], query: str
) -> bool:
    source = nodes.get(edge["source"], {})
    target = nodes.get(edge["target"], {})
    provenance = edge.get("provenance") or {}
    haystack = " ".join(
        [
            str(edge.get("id", "")),
            str(edge.get("type", "")),
            str(source.get("name", "")),
            str(source.get("type", "")),
            str(target.get("name", "")),
            str(target.get("type", "")),
            " ".join(str(value) for value in provenance.get("trace_ids", [])),
            " ".join(str(value) for value in provenance.get("event_ids", [])),
        ]
    )
    return query in _normalize_text(haystack)


def _normalize_direction(direction: str) -> str:
    return direction if direction in VALID_DIRECTIONS else "both"


def _normalize_ref(value: str) -> str:
    return value.strip().lower().replace(" ", "-").replace("_", "-")


def _normalize_text(value: str | None) -> str:
    return str(value or "").strip().lower()


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
