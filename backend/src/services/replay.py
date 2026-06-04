from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..replay import PLAYBACK_CONTROLS, replay_metrics, resolve_replay_position
from ..db.openmesh_snapshots import get_openmesh_snapshot, snapshot_record_to_detail
from .timeline import (
    get_timeline,
    get_trace_timeline,
    get_workflow_timeline,
)


async def get_replay(
    db: AsyncSession,
    *,
    control: str = "start",
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
    speed: float = 1.0,
    limit: int = 5000,
) -> dict[str, Any]:
    timeline = await get_timeline(db, limit=limit)
    return build_replay_from_timeline(
        timeline,
        control=control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
        speed=speed,
    )


async def get_trace_replay(
    db: AsyncSession,
    trace_id: str,
    *,
    control: str = "start",
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
    speed: float = 1.0,
    limit: int = 5000,
) -> dict[str, Any] | None:
    timeline = await get_trace_timeline(db, trace_id, limit=limit)
    if not timeline:
        return None
    return build_replay_from_timeline(
        timeline,
        control=control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
        speed=speed,
    )


async def get_workflow_replay(
    db: AsyncSession,
    workflow_id: str,
    *,
    control: str = "start",
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
    speed: float = 1.0,
    limit: int = 5000,
) -> dict[str, Any] | None:
    timeline = await get_workflow_timeline(db, workflow_id, limit=limit)
    if not timeline:
        return None
    return build_replay_from_timeline(
        timeline,
        control=control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
        speed=speed,
    )


async def get_snapshot_replay(
    db: AsyncSession,
    snapshot_id: str,
    *,
    control: str = "start",
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
    speed: float = 1.0,
) -> dict[str, Any] | None:
    record = await get_openmesh_snapshot(db, snapshot_id)
    if not record:
        return None
    snapshot = snapshot_record_to_detail(record)
    return build_replay_from_snapshot(
        snapshot,
        control=control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
        speed=speed,
    )


def build_replay_from_timeline(
    timeline: dict[str, Any],
    *,
    control: str = "start",
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
    speed: float = 1.0,
) -> dict[str, Any]:
    frames = _timeline_frames(timeline)
    return _replay_payload(
        scope=str(timeline.get("scope") or "ecosystem"),
        subject=timeline.get("subject", {}),
        frames=frames,
        control=control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
        speed=speed,
        source={"type": "timeline", "summary": timeline.get("summary", {})},
    )


def build_replay_from_snapshot(
    snapshot: dict[str, Any],
    *,
    control: str = "start",
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
    speed: float = 1.0,
) -> dict[str, Any]:
    frames = _snapshot_frames(snapshot)
    return _replay_payload(
        scope="snapshot",
        subject={
            "snapshot_id": snapshot.get("snapshot_id"),
            "created_at": snapshot.get("created_at"),
        },
        frames=frames,
        control=control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
        speed=speed,
        source={"type": "snapshot", "counts": snapshot.get("counts", {})},
    )


def _replay_payload(
    *,
    scope: str,
    subject: dict[str, Any],
    frames: list[dict[str, Any]],
    control: str,
    position: int,
    timestamp: str | None,
    event_id: str | None,
    speed: float,
    source: dict[str, Any],
) -> dict[str, Any]:
    normalized_control = control if control in PLAYBACK_CONTROLS else "start"
    frame_count = len(frames)
    current_position = resolve_replay_position(
        frames,
        control=normalized_control,
        position=position,
        timestamp=timestamp,
        event_id=event_id,
    )
    visible_frames = (
        [] if normalized_control == "stop" else frames[: current_position + 1]
    )
    metrics = replay_metrics(frames, visible_frames)
    return {
        "scope": scope,
        "subject": subject,
        "source": source,
        "controls": [
            {"name": "start", "description": "Begin playback from the selected frame."},
            {"name": "pause", "description": "Hold playback at the selected frame."},
            {"name": "stop", "description": "Stop playback and clear visible frames."},
            {
                "name": "step",
                "description": "Advance one frame from the selected frame.",
            },
            {
                "name": "previous",
                "description": "Move one frame backward from the selected frame.",
            },
            {
                "name": "jump",
                "description": "Jump to a timestamp or event id.",
            },
        ],
        "state": {
            "control": normalized_control,
            "status": _status_for_control(normalized_control),
            "position": current_position,
            "requested_position": max(position, 0),
            "next_position": min(current_position + 1, max(frame_count - 1, 0)),
            "previous_position": max(current_position - 1, 0)
            if current_position >= 0
            else -1,
            "jump_timestamp": timestamp,
            "jump_event_id": event_id,
            "speed": speed,
            "frame_count": frame_count,
            "visible_frame_count": len(visible_frames),
            "current_frame": frames[current_position]
            if frames and current_position >= 0
            else None,
        },
        "frames": frames,
        "visible_frames": visible_frames,
        "metrics": metrics,
        "summary": {**_frame_summary(frames), **metrics},
    }


def _status_for_control(control: str) -> str:
    if control == "start":
        return "playing"
    if control == "pause":
        return "paused"
    if control == "step":
        return "stepped"
    if control == "previous":
        return "rewound"
    if control == "jump":
        return "jumped"
    return "stopped"


def _timeline_frames(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    relationship_changes = timeline.get("relationship_changes", [])
    for change in relationship_changes:
        source = change.get("source")
        target = change.get("target")
        source_name = change.get("source_name") or source
        target_name = change.get("target_name") or target
        for node_id, name in ((source, source_name), (target, target_name)):
            if node_id and node_id not in seen_nodes:
                seen_nodes.add(node_id)
                frames.append(
                    _frame(
                        change.get("timestamp"),
                        "node.appeared",
                        category="node",
                        description=f"{name} appeared",
                        node_id=node_id,
                        name=name,
                    )
                )
        if source and target:
            operation = change.get("operation")
            relationship_action = (
                "relationship.removed"
                if operation == "removed"
                or str(change.get("kind") or "").endswith(".removed")
                else "relationship.created"
            )
            frames.append(
                _frame(
                    change.get("timestamp"),
                    relationship_action,
                    category="relationship",
                    description=(
                        f"{source_name} {change.get('relationship_type')} {target_name}"
                    ),
                    source=source,
                    target=target,
                    relationship_type=change.get("relationship_type"),
                    provenance=change.get("provenance", {}),
                )
            )

    frames.extend(
        _entity_frames(
            timeline.get("workflow_changes", []), "workflow.evolved", "workflow"
        )
    )
    frames.extend(_entity_frames(timeline.get("mcp_changes", []), "mcp.evolved", "mcp"))
    frames.extend(
        _entity_frames(
            timeline.get("capability_changes", []),
            "capability.evolved",
            "capability",
        )
    )
    frames.extend(_session_frames(timeline.get("session_history", [])))
    frames.extend(_snapshot_history_frames(timeline.get("snapshot_history", [])))
    frames.extend(_event_frames(timeline.get("timeline", [])))
    return _indexed_frames(frames)


def _snapshot_frames(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    contents = snapshot.get("contents", {})
    graph = contents.get("graph", {})
    created_at = snapshot.get("created_at")
    frames = [
        _frame(
            created_at,
            "snapshot.loaded",
            category="snapshot",
            description=f"Loaded snapshot {snapshot.get('snapshot_id')}",
            snapshot_id=snapshot.get("snapshot_id"),
            counts=snapshot.get("counts", {}),
        )
    ]
    for node in graph.get("nodes", []):
        frames.append(
            _frame(
                node.get("first_seen") or created_at,
                "node.appeared",
                category="node",
                description=f"{node.get('name')} appeared",
                node_id=node.get("id"),
                node_type=node.get("type"),
                name=node.get("name"),
                provenance=node.get("provenance", {}),
            )
        )
    for edge in graph.get("edges", contents.get("relationships", [])):
        frames.append(
            _frame(
                edge.get("first_seen") or created_at,
                "relationship.created",
                category="relationship",
                description=f"{edge.get('source')} {edge.get('type')} {edge.get('target')}",
                source=edge.get("source"),
                target=edge.get("target"),
                relationship_type=edge.get("type") or edge.get("relationship_type"),
                provenance=edge.get("provenance", {}),
            )
        )
    frames.extend(
        _snapshot_entity_frames(
            contents.get("workflows", []), "workflow.evolved", created_at
        )
    )
    frames.extend(
        _snapshot_entity_frames(
            contents.get("mcp_servers", []), "mcp.evolved", created_at
        )
    )
    frames.extend(
        _snapshot_entity_frames(
            contents.get("capabilities", []), "capability.evolved", created_at
        )
    )
    frames.extend(_session_frames(contents.get("sessions", [])))
    return _indexed_frames(frames)


def _entity_frames(
    changes: list[dict[str, Any]], action: str, category: str
) -> list[dict[str, Any]]:
    frames = []
    for change in changes:
        name = change.get("name") or change.get("id") or category
        frames.append(
            _frame(
                change.get("timestamp"),
                action,
                category=category,
                description=f"{name} {change.get('kind', 'changed')}",
                entity_id=change.get("id"),
                name=name,
                provenance=change.get("provenance", {}),
            )
        )
    return frames


def _snapshot_entity_frames(
    entities: list[dict[str, Any]], action: str, timestamp: str | None
) -> list[dict[str, Any]]:
    frames = []
    for entity in entities:
        name = (
            entity.get("name")
            or entity.get("workflow")
            or entity.get("server")
            or entity.get("capability")
        )
        frames.append(
            _frame(
                entity.get("first_seen") or entity.get("last_seen") or timestamp,
                action,
                category=str(action).split(".", 1)[0],
                description=f"{name} available",
                entity_id=entity.get("id") or entity.get("workflow_id"),
                name=name,
                metadata=entity.get("metadata", {}),
            )
        )
    return frames


def _session_frames(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frames = []
    for session in sessions:
        frames.append(
            _frame(
                session.get("started_at"),
                "session.started",
                category="session",
                description=f"Session started: {session.get('command')}",
                session_id=session.get("session_id"),
                command=session.get("command"),
                status=session.get("status"),
            )
        )
        if session.get("ended_at"):
            frames.append(
                _frame(
                    session.get("ended_at"),
                    "session.completed"
                    if session.get("status") == "completed"
                    else "session.failed",
                    category="session",
                    description=f"Session {session.get('status')}: {session.get('command')}",
                    session_id=session.get("session_id"),
                    command=session.get("command"),
                    status=session.get("status"),
                    exit_code=session.get("exit_code"),
                )
            )
    return frames


def _snapshot_history_frames(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _frame(
            snapshot.get("created_at"),
            "snapshot.created",
            category="snapshot",
            description=f"Snapshot created: {snapshot.get('snapshot_id')}",
            snapshot_id=snapshot.get("snapshot_id"),
            counts=snapshot.get("counts", {}),
        )
        for snapshot in snapshots
    ]


def _event_frames(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frames = []
    for entry in entries:
        if entry.get("kind") != "event":
            continue
        event_type = str(entry.get("event_type") or "")
        action, category = _event_replay_action(event_type)
        frames.append(
            _frame(
                entry.get("timestamp"),
                action,
                category=category,
                description=f"{entry.get('event_type')} {entry.get('source') or '-'} -> {entry.get('target') or '-'}",
                event_id=entry.get("event_id"),
                event_type=event_type,
                trace_id=entry.get("trace_id"),
                session_id=entry.get("session_id"),
                source=entry.get("source"),
                target=entry.get("target"),
            )
        )
    return frames


def _event_replay_action(event_type: str) -> tuple[str, str]:
    if event_type in {"workflow.started", "workflow.completed"}:
        return event_type, "workflow"
    if event_type.startswith("agent.handoff."):
        return "handoff.occurred", "handoff"
    if event_type.startswith("agent.message."):
        return "message.exchanged", "message"
    return "event.observed", "event"


def _frame(
    timestamp: str | None,
    action: str,
    *,
    category: str,
    description: str,
    **details: Any,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "action": action,
        "category": category,
        "description": description,
        **{key: value for key, value in details.items() if value is not None},
    }


def _indexed_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        [frame for frame in frames if frame.get("timestamp")],
        key=lambda item: (item.get("timestamp") or "", item.get("action") or ""),
    )
    return [{**frame, "frame_index": index} for index, frame in enumerate(ordered)]


def _frame_summary(frames: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "frames": len(frames),
        "nodes": 0,
        "relationships": 0,
        "workflows": 0,
        "capabilities": 0,
        "mcp": 0,
        "sessions": 0,
        "snapshots": 0,
        "handoffs": 0,
        "messages": 0,
        "events": 0,
    }
    for frame in frames:
        category = frame.get("category")
        if category == "node":
            summary["nodes"] += 1
        elif category == "relationship":
            summary["relationships"] += 1
        elif category == "workflow":
            summary["workflows"] += 1
        elif category == "capability":
            summary["capabilities"] += 1
        elif category == "mcp":
            summary["mcp"] += 1
        elif category == "session":
            summary["sessions"] += 1
        elif category == "snapshot":
            summary["snapshots"] += 1
        elif category == "handoff":
            summary["handoffs"] += 1
        elif category == "message":
            summary["messages"] += 1
        elif category == "event":
            summary["events"] += 1
    return summary
