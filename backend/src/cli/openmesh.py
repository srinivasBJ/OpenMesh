from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from typing import Any, Callable

from ..db.session import AsyncSessionLocal
from ..services.openmesh_queries import get_events, get_graph, get_health, get_traces


def _node_name(node: dict[str, Any] | None) -> str:
    if not node:
        return "None"
    return node.get("name") or node.get("node_id") or "Unknown"


def _print_health(status: dict[str, Any]) -> None:
    print("OpenMesh Status")
    print()
    print(f"Collector: {status['collector']}")
    print(f"Database: {status['database']}")
    print()
    print(f"Events: {status['events']}")
    print(f"Traces: {status['traces']}")
    print()
    print(f"Nodes: {status['nodes']}")
    print(f"Edges: {status['edges']}")


def _print_events(events: list[dict[str, Any]]) -> None:
    if not events:
        print("No OpenMesh events found.")
        return
    for event in events:
        print(event["timestamp"])
        print(event["event_type"])
        print(f"{_node_name(event.get('source'))} -> {_node_name(event.get('target'))}")
        print()


def _print_traces(traces: list[dict[str, Any]]) -> None:
    if not traces:
        print("No OpenMesh traces found.")
        return
    print(f"{'trace_id':<40} {'events':>6} {'status':<10} started_at")
    for trace in traces:
        print(
            f"{trace['trace_id']:<40} "
            f"{trace['event_count']:>6} "
            f"{trace['status']:<10} "
            f"{trace['started_at']}"
        )


def _print_graph(graph: dict[str, list[dict[str, Any]]]) -> None:
    nodes = {node["id"]: node for node in graph["nodes"]}
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph["edges"]:
        outgoing[edge["source"]].append(edge)

    if not nodes:
        print("No OpenMesh graph nodes found.")
        return

    for node_id, node in sorted(nodes.items(), key=lambda item: item[1]["name"]):
        print(node["name"])
        relationships = sorted(outgoing.get(node_id, []), key=lambda edge: (edge["type"], edge["target"]))
        if not relationships:
            print("└─ no relationships")
            print()
            continue
        for index, edge in enumerate(relationships):
            branch = "└─" if index == len(relationships) - 1 else "├─"
            target = nodes.get(edge["target"], {"name": edge["target"]})
            print(f"{branch} {edge['type']} -> {target['name']}")
        print()


async def _with_db(handler: Callable[..., Any], *args: Any) -> int:
    try:
        async with AsyncSessionLocal() as db:
            result = await handler(db, *args)
            return result if isinstance(result, int) else 0
    except Exception as exc:
        print("OpenMesh CLI error")
        print()
        print(f"Database: ERROR ({exc.__class__.__name__})")
        if str(exc):
            print(str(exc))
        return 1


async def _health(args: argparse.Namespace) -> int:
    async def run(db):
        status = await get_health(db)
        _print_health(status)

    return await _with_db(run)


async def _events(args: argparse.Namespace) -> int:
    async def run(db):
        events = await get_events(db, limit=args.limit)
        _print_events(events)

    return await _with_db(run)


async def _traces(args: argparse.Namespace) -> int:
    async def run(db):
        traces = await get_traces(db, limit=args.limit)
        _print_traces(traces[: args.limit])

    return await _with_db(run)


async def _graph(args: argparse.Namespace) -> int:
    async def run(db):
        graph = await get_graph(db)
        _print_graph(graph)

    return await _with_db(run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openmesh", description="Inspect persisted OpenMesh events.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health = subparsers.add_parser("health", help="Show collector and storage status.")
    health.set_defaults(func=_health)

    events = subparsers.add_parser("events", help="Show latest OpenMesh events.")
    events.add_argument("--limit", type=int, default=10, help="Maximum events to show.")
    events.set_defaults(func=_events)

    traces = subparsers.add_parser("traces", help="Show OpenMesh traces.")
    traces.add_argument("--limit", type=int, default=20, help="Maximum traces to show.")
    traces.set_defaults(func=_traces)

    graph = subparsers.add_parser("graph", help="Show OpenMesh graph relationships.")
    graph.set_defaults(func=_graph)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
