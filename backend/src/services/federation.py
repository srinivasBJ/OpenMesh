from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord, OpenMeshSessionRecord
from ..db.openmesh_events import list_openmesh_events
from ..db.openmesh_sessions import list_openmesh_sessions
from ..db.openmesh_snapshots import (
    list_openmesh_snapshots,
    snapshot_record_to_detail,
)
from .ecosystem_snapshot import build_ecosystem_snapshot
from .graph_state import reduce_graph_state
from .relationship_types import relationship_definition, validate_relationship
from .replay import build_replay_from_timeline
from .timeline import build_timeline


FEDERATION_SCHEMA_VERSION = "0.1"
FEDERATION_PROTOCOL_VERSION = "openmesh.protocol.v1"
FEDERATION_CAPABILITIES = (
    "metadata.exchange",
    "ecosystem.registry",
    "graph.provenance",
    "snapshot.summary",
    "timeline.summary",
    "replay.summary",
)


async def get_federation_registry(
    db: AsyncSession, *, limit: int = 5000, snapshot_limit: int = 100
) -> dict[str, Any]:
    records, sessions, snapshots = await _load_federation_state(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return build_federation_registry(records, sessions, snapshots)


async def get_federation_peers(
    db: AsyncSession, *, limit: int = 5000, snapshot_limit: int = 100
) -> list[dict[str, Any]]:
    registry = await get_federation_registry(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return registry["peers"]


async def inspect_federation_node(
    db: AsyncSession,
    node_ref: str | None = None,
    *,
    limit: int = 5000,
    snapshot_limit: int = 100,
) -> dict[str, Any] | None:
    registry = await get_federation_registry(
        db, limit=limit, snapshot_limit=snapshot_limit
    )
    return inspect_federation_registry_node(registry, node_ref)


async def _load_federation_state(
    db: AsyncSession, *, limit: int, snapshot_limit: int
) -> tuple[
    list[OpenMeshEventRecord],
    list[OpenMeshSessionRecord],
    list[dict[str, Any]],
]:
    records = await list_openmesh_events(db, limit=limit)
    sessions = await list_openmesh_sessions(db, limit=limit)
    snapshots = [
        snapshot_record_to_detail(record)
        for record in await list_openmesh_snapshots(db, limit=snapshot_limit)
    ]
    return records, sessions, snapshots


def build_federation_registry(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
    *,
    peers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record_list = list(records)
    session_list = list(sessions)
    snapshot_list = list(snapshots)
    local_node = local_federation_node()
    peer_source = discover_federation_peers() if peers is None else peers
    peer_nodes = [federation_peer_node(peer) for peer in peer_source]
    relationships = federation_relationships(local_node, peer_nodes)
    graph = reduce_graph_state(record_list)
    federation_snapshot = build_federation_snapshot(
        record_list,
        session_list,
        snapshot_list,
        local_node=local_node,
        peers=peer_nodes,
        relationships=relationships,
    )
    federation_timeline = build_federation_timeline(
        record_list,
        session_list,
        snapshot_list,
        local_node=local_node,
        peers=peer_nodes,
        relationships=relationships,
    )
    federation_replay = build_federation_replay(federation_timeline)
    return {
        "schema_version": FEDERATION_SCHEMA_VERSION,
        "protocol_version": FEDERATION_PROTOCOL_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "local_node": local_node,
        "peers": peer_nodes,
        "relationships": relationships,
        "graph": federation_graph(local_node, peer_nodes, relationships),
        "discovery": {
            "local": local_node,
            "peers": peer_nodes,
            "peer_count": len(peer_nodes),
            "capabilities": list(FEDERATION_CAPABILITIES),
        },
        "registry": {
            "instances": [local_node, *peer_nodes],
            "relationship_count": len(relationships),
            "local_graph_statistics": {
                "node_count": len(graph.get("nodes", [])),
                "edge_count": len(graph.get("edges", [])),
                "validation_status": graph.get("validation", {}).get(
                    "status", "UNKNOWN"
                ),
            },
        },
        "queries": federation_query_catalog(),
        "snapshot": federation_snapshot,
        "timeline": federation_timeline,
        "replay": federation_replay,
        "policy": federation_policy(),
    }


def local_federation_node() -> dict[str, Any]:
    instance_id = os.getenv("OPENMESH_INSTANCE_ID", "openmesh.local")
    return federation_node_model(
        instance_id=instance_id,
        name=os.getenv("OPENMESH_INSTANCE_NAME", "Local OpenMesh"),
        organization=os.getenv("OPENMESH_ORGANIZATION", "local"),
        cluster=os.getenv("OPENMESH_CLUSTER", "default"),
        endpoint=os.getenv("OPENMESH_FEDERATION_ENDPOINT"),
        status="local",
    )


def discover_federation_peers(raw: str | None = None) -> list[dict[str, Any]]:
    raw_value = raw if raw is not None else os.getenv("OPENMESH_FEDERATION_PEERS", "")
    if not raw_value.strip():
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = [
            {"endpoint": value.strip()}
            for value in raw_value.split(",")
            if value.strip()
        ]
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [
        _normalize_peer_metadata(peer, index)
        for index, peer in enumerate(parsed)
        if isinstance(peer, dict)
    ]


def federation_node_model(
    *,
    instance_id: str,
    name: str,
    organization: str = "unknown",
    cluster: str = "default",
    endpoint: str | None = None,
    status: str = "configured",
    last_seen: str | None = None,
    capabilities: Iterable[str] = FEDERATION_CAPABILITIES,
) -> dict[str, Any]:
    return {
        "id": f"federation:{instance_id}",
        "node_id": f"federation:{instance_id}",
        "node_type": "federation_node",
        "type": "federation_node",
        "name": name,
        "status": status,
        "endpoint": endpoint,
        "organization": organization,
        "cluster": cluster,
        "last_seen": last_seen,
        "capabilities": list(capabilities),
        "metadata": {
            "instance_id": instance_id,
            "organization": organization,
            "cluster": cluster,
            "endpoint": endpoint,
            "protocol_version": FEDERATION_PROTOCOL_VERSION,
            "federation_schema_version": FEDERATION_SCHEMA_VERSION,
        },
    }


def federation_peer_node(peer: dict[str, Any]) -> dict[str, Any]:
    return federation_node_model(
        instance_id=str(peer["instance_id"]),
        name=str(peer.get("name") or peer["instance_id"]),
        organization=str(peer.get("organization") or "unknown"),
        cluster=str(peer.get("cluster") or "default"),
        endpoint=peer.get("endpoint"),
        status=str(peer.get("status") or "configured"),
        last_seen=peer.get("last_seen"),
        capabilities=peer.get("capabilities") or FEDERATION_CAPABILITIES,
    )


def federation_relationships(
    local_node: dict[str, Any], peers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    relationships = []
    timestamp = datetime.utcnow().isoformat() + "Z"
    for peer in peers:
        validation = validate_relationship(
            "federates_with", local_node["type"], peer["type"]
        )
        relationship_id = f"{local_node['id']}:federates_with:{peer['id']}"
        relationships.append(
            {
                "id": relationship_id,
                "source": local_node["id"],
                "target": peer["id"],
                "type": "federates_with",
                "relationship_type": "federates_with",
                "relationship_definition": relationship_definition("federates_with"),
                "validation_status": validation["status"],
                "validation_errors": validation["errors"],
                "validation_warnings": validation["warnings"],
                "event_count": 0,
                "observation_count": 1,
                "first_seen": peer.get("last_seen") or timestamp,
                "last_seen": peer.get("last_seen") or timestamp,
                "lifecycle_state": peer.get("status") or "configured",
                "provenance": {
                    "source": local_node["id"],
                    "target": peer["id"],
                    "relationship_type": "federates_with",
                    "event_ids": [],
                    "trace_ids": [],
                    "session_ids": [],
                    "first_seen": peer.get("last_seen") or timestamp,
                    "last_seen": peer.get("last_seen") or timestamp,
                    "source_evidence": "OPENMESH_FEDERATION_PEERS",
                    "metadata_only": True,
                },
            }
        )
    return relationships


def federation_graph(
    local_node: dict[str, Any],
    peers: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "nodes": [local_node, *peers],
        "edges": relationships,
        "metadata": {
            "schema_version": FEDERATION_SCHEMA_VERSION,
            "protocol_version": FEDERATION_PROTOCOL_VERSION,
            "metadata_only": True,
        },
    }


def build_federation_snapshot(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
    *,
    local_node: dict[str, Any] | None = None,
    peers: list[dict[str, Any]] | None = None,
    relationships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    record_list = list(records)
    session_list = list(sessions)
    local = local_node or local_federation_node()
    peer_nodes = (
        [federation_peer_node(peer) for peer in discover_federation_peers()]
        if peers is None
        else peers
    )
    federation_edges = (
        federation_relationships(local, peer_nodes)
        if relationships is None
        else relationships
    )
    local_snapshot = build_ecosystem_snapshot(record_list, session_list)
    stored_snapshots = list(snapshots)
    return {
        "snapshot_id": f"fed_snap_{uuid4().hex}",
        "schema_version": FEDERATION_SCHEMA_VERSION,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "counts": {
            "instances": 1 + len(peer_nodes),
            "peers": len(peer_nodes),
            "relationships": len(federation_edges),
            "local_nodes": local_snapshot.get("counts", {}).get("nodes", 0),
            "local_edges": local_snapshot.get("counts", {}).get("edges", 0),
            "stored_snapshots": len(stored_snapshots),
        },
        "contents": {
            "local_node": local,
            "peers": peer_nodes,
            "relationships": federation_edges,
            "local_snapshot": local_snapshot,
            "stored_snapshots": stored_snapshots,
        },
        "policy": federation_policy(),
    }


def build_federation_timeline(
    records: Iterable[OpenMeshEventRecord],
    sessions: Iterable[OpenMeshSessionRecord],
    snapshots: Iterable[dict[str, Any]],
    *,
    local_node: dict[str, Any] | None = None,
    peers: list[dict[str, Any]] | None = None,
    relationships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    local = local_node or local_federation_node()
    peer_nodes = (
        [federation_peer_node(peer) for peer in discover_federation_peers()]
        if peers is None
        else peers
    )
    federation_edges = (
        federation_relationships(local, peer_nodes)
        if relationships is None
        else relationships
    )
    snapshot_list = list(snapshots)
    local_timeline = build_timeline(records, sessions, snapshot_list)
    peer_entries = [_peer_timeline_entry(peer) for peer in peer_nodes]
    relationship_changes = [
        {
            "timestamp": edge.get("last_seen"),
            "kind": "relationship.observed",
            "source": edge["source"],
            "target": edge["target"],
            "source_name": local.get("name"),
            "target_name": _peer_name(peer_nodes, edge["target"]),
            "relationship_type": edge["type"],
            "provenance": edge.get("provenance", {}),
        }
        for edge in federation_edges
    ]
    timeline = sorted(
        [*peer_entries, *relationship_changes],
        key=lambda item: item.get("timestamp") or "",
    )
    return {
        "scope": "federation",
        "subject": {
            "type": "federation",
            "id": local["id"],
            "name": local["name"],
        },
        "first_appearance": timeline[0].get("timestamp") if timeline else None,
        "last_appearance": timeline[-1].get("timestamp") if timeline else None,
        "relationship_changes": relationship_changes,
        "workflow_changes": local_timeline.get("workflow_changes", []),
        "capability_changes": local_timeline.get("capability_changes", []),
        "mcp_changes": local_timeline.get("mcp_changes", []),
        "session_history": local_timeline.get("session_history", []),
        "snapshot_history": local_timeline.get("snapshot_history", []),
        "timeline": timeline,
        "local_timeline_summary": local_timeline.get("summary", {}),
        "summary": {
            "peers": len(peer_nodes),
            "relationships": len(federation_edges),
            "local_events": local_timeline.get("summary", {}).get("events", 0),
            "local_sessions": local_timeline.get("summary", {}).get("sessions", 0),
            "local_snapshots": local_timeline.get("summary", {}).get("snapshots", 0),
        },
    }


def build_federation_replay(timeline: dict[str, Any]) -> dict[str, Any]:
    replay = build_replay_from_timeline(timeline)
    return {
        **replay,
        "policy": federation_policy(),
        "source": {
            **replay.get("source", {}),
            "metadata_only": True,
            "remote_execution": False,
            "remote_control": False,
        },
    }


def federation_query_catalog() -> dict[str, Any]:
    return {
        "supported_queries": [
            "federation peers",
            "federation relationships",
            "federation snapshots",
            "federation timelines",
            "federation replays",
        ],
        "metadata_only": True,
    }


def query_federation_registry(
    registry: dict[str, Any], query: str, *, limit: int = 100
) -> dict[str, Any]:
    normalized = query.strip().lower()
    if "peer" in normalized:
        results = registry.get("peers", [])
    elif "relationship" in normalized:
        results = registry.get("relationships", [])
    elif "snapshot" in normalized:
        results = [registry.get("snapshot", {})]
    elif "timeline" in normalized:
        results = [registry.get("timeline", {})]
    elif "replay" in normalized:
        results = [registry.get("replay", {})]
    else:
        results = registry.get("registry", {}).get("instances", [])
    return {
        "query": query,
        "status": "ok",
        "count": len(results[:limit]),
        "results": results[:limit],
        "metadata_only": True,
    }


def inspect_federation_registry_node(
    registry: dict[str, Any], node_ref: str | None = None
) -> dict[str, Any] | None:
    node_id = node_ref or registry.get("local_node", {}).get("id")
    nodes = registry.get("registry", {}).get("instances", [])
    node = _find_federation_node(nodes, str(node_id))
    if not node:
        return None
    relationships = [
        relationship
        for relationship in registry.get("relationships", [])
        if node["id"] in {relationship.get("source"), relationship.get("target")}
    ]
    return {
        "node": node,
        "node_id": node["id"],
        "name": node["name"],
        "status": node.get("status"),
        "organization": node.get("organization"),
        "cluster": node.get("cluster"),
        "endpoint": node.get("endpoint"),
        "capabilities": node.get("capabilities", []),
        "relationships": relationships,
        "relationship_count": len(relationships),
        "snapshot": registry.get("snapshot", {}),
        "timeline": registry.get("timeline", {}),
        "replay": registry.get("replay", {}),
        "policy": registry.get("policy", federation_policy()),
    }


def federation_policy() -> dict[str, Any]:
    return {
        "metadata_only": True,
        "remote_execution": False,
        "remote_control": False,
        "code_execution": False,
        "security_analysis": False,
    }


def _normalize_peer_metadata(peer: dict[str, Any], index: int) -> dict[str, Any]:
    endpoint = peer.get("endpoint")
    instance_id = (
        peer.get("instance_id")
        or peer.get("peer_id")
        or peer.get("id")
        or _peer_id_from_endpoint(str(endpoint or index))
    )
    return {
        "instance_id": str(instance_id),
        "name": peer.get("name") or str(instance_id),
        "organization": peer.get("organization") or peer.get("org") or "unknown",
        "cluster": peer.get("cluster") or "default",
        "endpoint": endpoint,
        "status": peer.get("status") or "configured",
        "last_seen": peer.get("last_seen"),
        "capabilities": peer.get("capabilities") or list(FEDERATION_CAPABILITIES),
    }


def _peer_id_from_endpoint(endpoint: str) -> str:
    cleaned = (
        endpoint.replace("https://", "")
        .replace("http://", "")
        .replace("/", "-")
        .replace(":", "-")
        .strip("-")
    )
    return cleaned or "peer"


def _peer_timeline_entry(peer: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": peer.get("last_seen") or datetime.utcnow().isoformat() + "Z",
        "kind": "federation.peer.discovered",
        "peer_id": peer["id"],
        "name": peer["name"],
        "organization": peer.get("organization"),
        "cluster": peer.get("cluster"),
        "metadata_only": True,
    }


def _peer_name(peers: list[dict[str, Any]], peer_id: str) -> str:
    for peer in peers:
        if peer.get("id") == peer_id:
            return str(peer.get("name") or peer_id)
    return peer_id


def _find_federation_node(
    nodes: list[dict[str, Any]], node_ref: str
) -> dict[str, Any] | None:
    normalized = node_ref.strip().lower()
    for node in nodes:
        aliases = {
            str(node.get("id", "")),
            str(node.get("node_id", "")),
            str(node.get("name", "")),
            str(node.get("metadata", {}).get("instance_id", "")),
        }
        if normalized in {alias.lower() for alias in aliases if alias}:
            return node
    return None
