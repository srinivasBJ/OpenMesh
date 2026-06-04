from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


PLAYBACK_CONTROLS = ("start", "pause", "stop", "step", "previous", "jump")


def resolve_replay_position(
    frames: list[dict[str, Any]],
    *,
    control: str,
    position: int = 0,
    timestamp: str | None = None,
    event_id: str | None = None,
) -> int:
    frame_count = len(frames)
    if frame_count == 0 or control == "stop":
        return -1

    if event_id:
        event_position = _position_for_event_id(frames, event_id)
        if event_position is not None:
            return event_position

    if timestamp:
        timestamp_position = _position_for_timestamp(frames, timestamp)
        if timestamp_position is not None:
            return timestamp_position

    if control == "step":
        return min(max(position, 0) + 1, frame_count - 1)
    if control == "previous":
        return max(min(position, frame_count - 1) - 1, 0)
    return min(max(position, 0), frame_count - 1)


def replay_metrics(
    frames: list[dict[str, Any]], visible_frames: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "events_replayed": len(visible_frames),
        "duration": _duration_seconds(frames),
        "graph_mutations": sum(
            1
            for frame in visible_frames
            if frame.get("category") in {"node", "relationship"}
        ),
        "workflow_duration": _workflow_duration_seconds(frames),
    }


def _position_for_event_id(frames: list[dict[str, Any]], event_id: str) -> int | None:
    for index, frame in enumerate(frames):
        if frame.get("event_id") == event_id:
            return index
        provenance = frame.get("provenance") or {}
        if event_id in (provenance.get("event_ids") or []):
            return index
    return None


def _position_for_timestamp(frames: list[dict[str, Any]], timestamp: str) -> int | None:
    target = _parse_time(timestamp)
    if not target:
        return None
    selected = None
    for index, frame in enumerate(frames):
        frame_time = _parse_time(str(frame.get("timestamp") or ""))
        if not frame_time:
            continue
        if frame_time <= target:
            selected = index
        else:
            break
    return selected if selected is not None else 0


def _duration_seconds(frames: list[dict[str, Any]]) -> float | None:
    times = [
        parsed
        for frame in frames
        if (parsed := _parse_time(str(frame.get("timestamp") or "")))
    ]
    if len(times) < 2:
        return None
    return round((times[-1] - times[0]).total_seconds(), 3)


def _workflow_duration_seconds(frames: list[dict[str, Any]]) -> float | None:
    started = None
    completed = None
    for frame in frames:
        if frame.get("event_type") == "workflow.started" and started is None:
            started = _parse_time(str(frame.get("timestamp") or ""))
        if frame.get("event_type") == "workflow.completed":
            completed = _parse_time(str(frame.get("timestamp") or ""))
    if not started or not completed:
        return None
    return round((completed - started).total_seconds(), 3)


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)
