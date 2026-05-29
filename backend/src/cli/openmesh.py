from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
from shlex import join as shell_join
from typing import Any, Callable
from uuid import uuid4

from ..db.session import AsyncSessionLocal
from ..db.openmesh_sessions import complete_openmesh_session, create_openmesh_session
from ..services.openmesh_collector import collector
from ..services.openmesh_doctor import run_doctor
from ..services.openmesh_queries import get_events, get_graph, get_health, get_traces
from ..shared.openmesh_events import make_openmesh_event
from .tui import run_tui


CLI_NODE = {
    "node_id": "openmesh.cli",
    "node_type": "service",
    "name": "OpenMesh CLI",
    "runtime": "python.argparse",
}


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


def _print_doctor(report: dict[str, Any]) -> None:
    print("OpenMesh Doctor")
    print()
    for check in report["checks"]:
        print(f"{check['name']}: {check['status']}")
        detail = check.get("detail")
        if isinstance(detail, dict):
            for key, value in detail.items():
                print(f"  {key}: {value}")
        elif detail:
            print(f"  {detail}")
    print()
    print(f"Overall: {report['status']}")


def _utc_now() -> datetime:
    return datetime.utcnow()


def _process_node(session_id: str, command: str) -> dict[str, Any]:
    return {
        "node_id": f"process:{session_id}",
        "node_type": "process",
        "name": command,
        "runtime": "subprocess",
        "metadata": {"session_id": session_id},
    }


def _command_node(command: str) -> dict[str, Any]:
    executable = command.split(" ", 1)[0] if command else "command"
    return {
        "node_id": f"command:{executable}",
        "node_type": "command",
        "name": command,
        "runtime": "shell",
    }


async def _emit_process_event(
    db,
    event_type: str,
    *,
    session_id: str,
    trace_id: str,
    source: dict[str, Any],
    payload: dict[str, Any],
    target: dict[str, Any] | None = None,
    severity: str = "info",
) -> dict[str, Any]:
    event = make_openmesh_event(
        event_type,
        source,
        payload,
        target=target,
        severity=severity,
        session_id=session_id,
        trace_id=trace_id,
    )
    await collector.accept(db, event)
    return event


async def _stream_output(
    db,
    stream: asyncio.StreamReader,
    *,
    event_type: str,
    session_id: str,
    trace_id: str,
    process: dict[str, Any],
    command: str,
    severity: str,
    emit_lock: asyncio.Lock,
) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode(errors="replace").rstrip("\n")
        print(text)
        async with emit_lock:
            await _emit_process_event(
                db,
                event_type,
                session_id=session_id,
                trace_id=trace_id,
                source=process,
                payload={"command": command, "line": text},
                severity=severity,
            )


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


async def _doctor(args: argparse.Namespace) -> int:
    async def run(db):
        report = await run_doctor(db)
        _print_doctor(report)
        return 0 if report["status"] == "OK" else 1

    return await _with_db(run)


async def _run_command(args: argparse.Namespace) -> int:
    command_parts = args.command
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        print("Usage: openmesh run -- <command>")
        return 2

    command = shell_join(command_parts)
    session_id = f"sess_{uuid4().hex}"
    trace_id = f"trace_{uuid4().hex}"
    process = _process_node(session_id, command)
    command_target = _command_node(command)

    async def run(db) -> int:
        started_at = _utc_now()
        await create_openmesh_session(db, session_id=session_id, command=command, started_at=started_at)
        await _emit_process_event(
            db,
            "process.started",
            session_id=session_id,
            trace_id=trace_id,
            source=CLI_NODE,
            target=process,
            payload={"command": command, "argv": command_parts, "started_at": started_at.isoformat() + "Z"},
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *command_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:
            ended_at = _utc_now()
            await _emit_process_event(
                db,
                "process.failed",
                session_id=session_id,
                trace_id=trace_id,
                source=process,
                target=command_target,
                payload={
                    "command": command,
                    "error": str(exc),
                    "started_at": started_at.isoformat() + "Z",
                    "ended_at": ended_at.isoformat() + "Z",
                },
                severity="error",
            )
            await complete_openmesh_session(
                db,
                session_id=session_id,
                ended_at=ended_at,
                status="failed",
                exit_code=None,
            )
            raise
        assert proc.stdout is not None
        assert proc.stderr is not None
        emit_lock = asyncio.Lock()
        await asyncio.gather(
            _stream_output(
                db,
                proc.stdout,
                event_type="process.stdout",
                session_id=session_id,
                trace_id=trace_id,
                process=process,
                command=command,
                severity="info",
                emit_lock=emit_lock,
            ),
            _stream_output(
                db,
                proc.stderr,
                event_type="process.stderr",
                session_id=session_id,
                trace_id=trace_id,
                process=process,
                command=command,
                severity="warning",
                emit_lock=emit_lock,
            ),
        )
        exit_code = await proc.wait()
        ended_at = _utc_now()
        status = "completed" if exit_code == 0 else "failed"
        event_type = "process.completed" if exit_code == 0 else "process.failed"
        await _emit_process_event(
            db,
            event_type,
            session_id=session_id,
            trace_id=trace_id,
            source=process,
            target=command_target,
            payload={
                "command": command,
                "exit_code": exit_code,
                "started_at": started_at.isoformat() + "Z",
                "ended_at": ended_at.isoformat() + "Z",
            },
            severity="info" if exit_code == 0 else "error",
        )
        await complete_openmesh_session(
            db,
            session_id=session_id,
            ended_at=ended_at,
            status=status,
            exit_code=exit_code,
        )
        print()
        print(f"OpenMesh session: {session_id}")
        print(f"OpenMesh trace: {trace_id}")
        print(f"Exit code: {exit_code}")
        return exit_code

    return await _with_db(run)


async def _tui(args: argparse.Namespace) -> int:
    try:
        return await run_tui(once=args.once)
    except Exception as exc:
        print("OpenMesh TUI error")
        print()
        print(f"{exc.__class__.__name__}: {exc}")
        return 1


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

    doctor = subparsers.add_parser("doctor", help="Check OpenMesh local configuration.")
    doctor.set_defaults(func=_doctor)

    tui = subparsers.add_parser("tui", help="Launch the OpenMesh terminal UI.")
    tui.add_argument("--once", action="store_true", help="Render one terminal capture and exit.")
    tui.set_defaults(func=_tui)

    run = subparsers.add_parser("run", help="Run and observe a command.")
    run.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --.")
    run.set_defaults(func=_run_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
