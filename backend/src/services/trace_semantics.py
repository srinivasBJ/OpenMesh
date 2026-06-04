from __future__ import annotations

from datetime import datetime
from typing import Any

from .graph_state import edge_type_for


def build_event_hierarchy(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nodes = {
        event["event_id"]: {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "span_id": event.get("span_id"),
            "parent_span_id": event.get("parent_span_id"),
            "parent_event_id": event.get("parent_event_id"),
            "root_event_id": event.get("root_event_id") or event["event_id"],
            "source": event.get("source"),
            "target": event.get("target"),
            "timestamp": event.get("timestamp"),
            "children": [],
        }
        for event in events
    }

    roots: list[dict[str, Any]] = []
    latest_event_by_span: dict[str, str] = {}
    for event in events:
        node = nodes[event["event_id"]]
        parent_id = event.get("parent_event_id")
        if not parent_id and event.get("parent_span_id"):
            parent_id = latest_event_by_span.get(event["parent_span_id"])
        if parent_id and parent_id in nodes and parent_id != event["event_id"]:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)
        if event.get("span_id"):
            latest_event_by_span[event["span_id"]] = event["event_id"]
    return roots


def build_span_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: dict[str, dict[str, Any]] = {}
    for index, event in enumerate(events):
        span_id = event.get("span_id") or f"span:{event['event_id']}"
        span = spans.setdefault(
            span_id,
            {
                "span_id": span_id,
                "parent_span_id": event.get("parent_span_id"),
                "trace_id": event["trace_id"],
                "first_seen_index": index,
                "started_at": event.get("timestamp"),
                "ended_at": event.get("timestamp"),
                "duration_ms": None,
                "status": "active",
                "event_count": 0,
                "events": [],
                "event_types": [],
                "links": [],
                "child_span_ids": [],
                "first_event_id": event["event_id"],
                "last_event_id": event["event_id"],
            },
        )
        span["event_count"] += 1
        span["events"].append(event["event_id"])
        span["event_types"].append(event["event_type"])
        span["ended_at"] = event.get("timestamp")
        span["last_event_id"] = event["event_id"]
        if not span.get("parent_span_id") and event.get("parent_span_id"):
            span["parent_span_id"] = event["parent_span_id"]
        for link in event.get("links", []):
            if link not in span["links"]:
                span["links"].append(link)
        span["status"] = _span_status(span["event_types"], event)
        span["duration_ms"] = _duration_ms(span.get("started_at"), span.get("ended_at"))
    for span in spans.values():
        parent_span_id = span.get("parent_span_id")
        if (
            parent_span_id
            and parent_span_id in spans
            and span["span_id"] not in spans[parent_span_id]["child_span_ids"]
        ):
            spans[parent_span_id]["child_span_ids"].append(span["span_id"])
    return sorted(spans.values(), key=lambda span: span["first_seen_index"])


def build_span_tree(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = build_span_summary(events)
    nodes = {
        span["span_id"]: {
            key: value for key, value in span.items() if key != "child_span_ids"
        }
        for span in summaries
    }
    for node in nodes.values():
        node["children"] = []

    roots: list[dict[str, Any]] = []
    for span in summaries:
        node = nodes[span["span_id"]]
        parent_span_id = span.get("parent_span_id")
        if (
            parent_span_id
            and parent_span_id in nodes
            and parent_span_id != span["span_id"]
        ):
            nodes[parent_span_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def validate_trace_semantics(events: list[dict[str, Any]]) -> dict[str, Any]:
    trace_ids = {event.get("trace_id") for event in events if event.get("trace_id")}
    session_ids = {
        event.get("session_id") for event in events if event.get("session_id")
    }
    event_ids = {event["event_id"] for event in events}
    span_ids = {event.get("span_id") for event in events if event.get("span_id")}
    missing_parent_events = [
        event["event_id"]
        for event in events
        if event.get("parent_event_id") and event["parent_event_id"] not in event_ids
    ]
    missing_root_events = [
        event["event_id"]
        for event in events
        if event.get("root_event_id") and event["root_event_id"] not in event_ids
    ]
    missing_parent_spans = [
        event["event_id"]
        for event in events
        if event.get("parent_span_id") and event["parent_span_id"] not in span_ids
    ]
    malformed_links = [
        event["event_id"]
        for event in events
        for link in event.get("links", [])
        if not isinstance(link, dict)
        or not any(link.get(key) for key in ("url", "trace_id", "span_id", "event_id"))
    ]
    cross_trace_links = [
        {
            "event_id": event["event_id"],
            "trace_id": event.get("trace_id"),
            "linked_trace_id": link.get("trace_id"),
            "relationship": link.get("relationship"),
        }
        for event in events
        for link in event.get("links", [])
        if isinstance(link, dict)
        and link.get("trace_id")
        and link.get("trace_id") != event.get("trace_id")
    ]
    warnings = (
        missing_parent_events
        or missing_parent_spans
        or missing_root_events
        or malformed_links
        or len(trace_ids) > 1
    )
    return {
        "status": "OK" if not warnings else "WARNING",
        "trace_ids": sorted(trace_ids),
        "session_ids": sorted(session_ids),
        "missing_parent_events": missing_parent_events,
        "missing_parent_spans": missing_parent_spans,
        "missing_root_events": missing_root_events,
        "malformed_links": malformed_links,
        "cross_trace_links": cross_trace_links,
    }


def graph_edges_for_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = []
    for event in events:
        source = event.get("source")
        target = event.get("target")
        if not source or not target:
            continue
        edge_type = edge_type_for(
            event["event_type"],
            target.get("node_type"),
            source.get("node_type"),
            payload=event.get("payload"),
        )
        if not edge_type:
            continue
        observation = {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "trace_id": event["trace_id"],
            "span_id": event.get("span_id"),
            "timestamp": event.get("timestamp"),
            "source": {
                "node_id": source.get("node_id"),
                "node_type": source.get("node_type"),
                "name": source.get("name"),
            },
            "target": {
                "node_id": target.get("node_id"),
                "node_type": target.get("node_type"),
                "name": target.get("name"),
            },
        }
        edges.append(
            {
                "source": source["name"],
                "target": target["name"],
                "type": edge_type,
                "relationship_type": edge_type,
                "trace_id": event["trace_id"],
                "event_id": event["event_id"],
                "span_id": event.get("span_id"),
                "first_seen": event.get("timestamp"),
                "last_seen": event.get("timestamp"),
                "observation_count": 1,
                "provenance": {
                    "source": source.get("node_id") or source["name"],
                    "target": target.get("node_id") or target["name"],
                    "relationship_type": edge_type,
                    "event_ids": [event["event_id"]],
                    "trace_ids": [event["trace_id"]],
                    "span_ids": [event["span_id"]] if event.get("span_id") else [],
                    "first_seen": event.get("timestamp"),
                    "last_seen": event.get("timestamp"),
                    "first_event_id": event["event_id"],
                    "last_event_id": event["event_id"],
                    "first_trace_id": event["trace_id"],
                    "last_trace_id": event["trace_id"],
                    "observations": [observation],
                },
            }
        )
    return edges


def _span_status(event_types: list[str], latest_event: dict[str, Any]) -> str:
    if latest_event.get("severity") == "error" or latest_event.get(
        "event_type", ""
    ).endswith(".failed"):
        return "failed"
    if any(event_type.endswith(".failed") for event_type in event_types):
        return "failed"
    if any(event_type.endswith(".completed") for event_type in event_types):
        return "completed"
    if any(event_type.endswith(".started") for event_type in event_types):
        return "active"
    return "observed"


def _duration_ms(started_at: str | None, ended_at: str | None) -> int | None:
    if not started_at or not ended_at:
        return None
    start = _parse_time(started_at)
    end = _parse_time(ended_at)
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
