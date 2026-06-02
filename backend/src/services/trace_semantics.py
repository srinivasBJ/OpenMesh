from __future__ import annotations

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
                "event_count": 0,
                "events": [],
            },
        )
        span["event_count"] += 1
        span["events"].append(event["event_id"])
        if not span.get("parent_span_id") and event.get("parent_span_id"):
            span["parent_span_id"] = event["parent_span_id"]
    return sorted(spans.values(), key=lambda span: span["first_seen_index"])


def validate_trace_semantics(events: list[dict[str, Any]]) -> dict[str, Any]:
    trace_ids = {event.get("trace_id") for event in events if event.get("trace_id")}
    session_ids = {event.get("session_id") for event in events if event.get("session_id")}
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
    warnings = missing_parent_events or missing_parent_spans or missing_root_events or len(trace_ids) > 1
    return {
        "status": "OK" if not warnings else "WARNING",
        "trace_ids": sorted(trace_ids),
        "session_ids": sorted(session_ids),
        "missing_parent_events": missing_parent_events,
        "missing_parent_spans": missing_parent_spans,
        "missing_root_events": missing_root_events,
    }


def graph_edges_for_trace(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = []
    for event in events:
        source = event.get("source")
        target = event.get("target")
        if not source or not target:
            continue
        edge_type = edge_type_for(event["event_type"], target.get("node_type"))
        if not edge_type:
            continue
        edges.append(
            {
                "source": source["name"],
                "target": target["name"],
                "type": edge_type,
                "trace_id": event["trace_id"],
                "event_id": event["event_id"],
                "span_id": event.get("span_id"),
            }
        )
    return edges
