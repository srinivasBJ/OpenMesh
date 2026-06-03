from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime
from shlex import join as shell_join
from typing import Any, Callable
from uuid import uuid4

from ..db.session import AsyncSessionLocal
from ..db.openmesh_events import list_openmesh_events
from ..db.openmesh_sessions import complete_openmesh_session, create_openmesh_session
from ..services.openmesh_collector import collector
from ..services.discovery import get_discovery
from ..services.mcp_discovery import get_mcp_registry
from ..services.openmesh_doctor import run_doctor
from ..services.openmesh_queries import get_events, get_graph, get_health, get_trace, get_traces
from ..services.registry_status import build_registry_status
from ..shared.openmesh_events import make_openmesh_event
from ..sdk.integrations import list_integrations
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


def _short(value: Any, width: int) -> str:
    if value is None:
        return "-"
    text = str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


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


def _print_trace_detail(trace: dict[str, Any]) -> None:
    print(f"Trace {trace['trace_id']}")
    print(f"Status: {trace['status']}")
    print(f"Events: {trace['event_count']}")
    print()
    print("Hierarchy")
    for line in _hierarchy_lines(trace.get("hierarchy", [])):
        print(line)
    print()
    print("Spans")
    for span in trace.get("spans", []):
        parent = span.get("parent_span_id") or "-"
        duration = span.get("duration_ms")
        duration_text = f"{duration}ms" if duration is not None else "-"
        print(
            f"- {span['span_id']} parent:{parent} status:{span.get('status', 'unknown')} "
            f"events:{span['event_count']} duration:{duration_text}"
        )
        for link in span.get("links", []):
            linked = link.get("trace_id") or link.get("span_id") or link.get("event_id") or link.get("url")
            relationship = link.get("relationship") or "linked"
            print(f"  link:{relationship} -> {linked}")
    span_tree = trace.get("span_tree") or []
    if span_tree:
        print()
        print("Span Tree")
        for line in _span_tree_lines(span_tree):
            print(line)
    print()
    print("Graph Relationships")
    relationships = trace.get("relationships", [])
    if not relationships:
        print("- none")
    for edge in relationships:
        print(f"- {edge['source']} --{edge['type']}--> {edge['target']} event:{edge['event_id']}")
    print()
    validation = trace.get("validation", {})
    print(f"Validation: {validation.get('status', 'UNKNOWN')}")


def _hierarchy_lines(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        source = _node_name(node.get("source"))
        target = _node_name(node.get("target")) if node.get("target") else None
        target_text = f" -> {target}" if target else ""
        lines.append(f"{prefix}{branch} {node['event_type']} [{source}{target_text}]")
        child_prefix = prefix + ("   " if index == len(nodes) - 1 else "│  ")
        lines.extend(_hierarchy_lines(node.get("children", []), child_prefix))
    return lines


def _span_tree_lines(nodes: list[dict[str, Any]], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for index, node in enumerate(nodes):
        branch = "└─" if index == len(nodes) - 1 else "├─"
        lines.append(
            f"{prefix}{branch} {node['span_id']} "
            f"{node.get('status', 'unknown')} e:{node.get('event_count', 0)}"
        )
        child_prefix = prefix + ("   " if index == len(nodes) - 1 else "│  ")
        lines.extend(_span_tree_lines(node.get("children", []), child_prefix))
    return lines


def _print_graph(graph: dict[str, Any], *, details: bool = False) -> None:
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
            if details:
                definition = edge.get("relationship_definition") or {}
                print(f"   relationship: {edge.get('relationship_type', edge['type'])}")
                print(f"   validation: {edge.get('validation_status', 'unknown')}")
                if definition.get("description"):
                    print(f"   definition: {definition['description']}")
                print(f"   observations: {edge.get('observation_count', edge.get('event_count', 0))}")
                print(f"   lifecycle: {edge.get('lifecycle_state', 'unknown')}")
                print(f"   first_seen: {edge.get('first_seen')}")
                print(f"   last_seen: {edge.get('last_seen')}")
                print(f"   trace_id: {edge.get('trace_id') or edge.get('first_trace_id') or '-'}")
                print(f"   event_id: {edge.get('event_id') or edge.get('first_event_id') or '-'}")
        print()

    if details:
        validation = graph.get("validation", {})
        print(f"Validation: {validation.get('status', 'UNKNOWN')}")
        missing = validation.get("missing_provenance") or []
        invalid = validation.get("invalid_relationships") or []
        invalid_types = validation.get("invalid_relationship_types") or []
        invalid_sources = validation.get("invalid_source_types") or []
        invalid_targets = validation.get("invalid_target_types") or []
        broken = validation.get("broken_references") or []
        if missing or invalid or broken:
            print(f"missing_provenance: {len(missing)}")
            print(f"invalid_relationships: {len(invalid)}")
            print(f"invalid_relationship_types: {len(invalid_types)}")
            print(f"invalid_source_types: {len(invalid_sources)}")
            print(f"invalid_target_types: {len(invalid_targets)}")
            print(f"broken_references: {len(broken)}")


def _print_nodes(graph: dict[str, Any]) -> None:
    nodes = sorted(graph.get("nodes", []), key=lambda node: (node["type"], node["name"]))
    if not nodes:
        print("No OpenMesh graph nodes found.")
        return
    print(f"{'name':<30} {'type':<14} {'status':<10} {'validation':<10} {'events':>6} last_seen")
    for node in nodes:
        print(
            f"{_short(node['name'], 30):<30} "
            f"{node['type']:<14} "
            f"{node.get('lifecycle_state', 'unknown'):<10} "
            f"{node.get('validation_status', 'unknown'):<10} "
            f"{node.get('event_count', 0):>6} "
            f"{node.get('last_seen') or '-'}"
        )


def _print_registry(registry: dict[str, Any]) -> None:
    compatibility = registry["compatibility"]
    print("OpenMesh Registry")
    print()
    print("Versions")
    for name, version in registry["versions"].items():
        print(f"- {name}: {version}")
    print()
    print(f"Compatibility: {compatibility['severity']}")
    for warning in compatibility.get("warnings", []):
        print(f"WARNING: {warning['message']}")
    for error in compatibility.get("errors", []):
        print(f"ERROR: {error['message']}")
    if not compatibility.get("warnings") and not compatibility.get("errors"):
        print("No compatibility issues detected.")
    print()
    print("Node Definitions")
    for definition in registry["node_definitions"]:
        marker = _definition_marker(definition)
        print(f"{marker} {definition['type']:<16} {definition['display_name']} ({definition['category']})")
    print()
    print("Relationship Definitions")
    for definition in registry["relationship_definitions"]:
        marker = _definition_marker(definition)
        print(f"{marker} {definition['type']:<20} {definition['description']}")


def _definition_marker(definition: dict[str, Any]) -> str:
    if definition.get("removed_in"):
        return "✖"
    if definition.get("deprecated_in"):
        return "!"
    return "✓"


def _print_doctor(report: dict[str, Any]) -> None:
    print("OpenMesh Doctor")
    print()
    for check in report["checks"]:
        severity = check.get("severity", check["status"])
        print(f"{check['name']}: {severity}")
        detail = check.get("detail")
        if isinstance(detail, dict):
            for key, value in detail.items():
                if isinstance(value, list):
                    print(f"  {key}: {len(value)}")
                    for item in value[:5]:
                        print(f"    - {item}")
                    if len(value) > 5:
                        print(f"    ... {len(value) - 5} more")
                else:
                    print(f"  {key}: {value}")
        elif detail:
            print(f"  {detail}")
    print()
    print(f"Overall: {report['status']}")


def _integration_symbol(integration: dict[str, Any]) -> str:
    if integration.get("active") or integration.get("available"):
        return "✓"
    return "○"


def _print_integrations(integrations: list[dict[str, Any]]) -> None:
    print("Installed Integrations")
    print()
    for integration in integrations:
        version = integration.get("version") or "-"
        suffix = ""
        if integration.get("status") == "planned":
            suffix = " (planned)"
        print(
            f"{_integration_symbol(integration)} {integration['name']}{suffix} "
            f"- {integration['status_label']} - version: {version}"
        )


def _print_discovery(discovery: dict[str, list[dict[str, Any]]]) -> None:
    sections = [
        ("Frameworks", "frameworks"),
        ("Agents", "agents"),
        ("Tools", "tools"),
        ("Processes", "processes"),
        ("Services", "services"),
    ]
    for title, key in sections:
        print(title)
        print()
        entries = discovery.get(key, [])
        if not entries:
            print("  none observed")
        for entry in entries:
            marker = "✓" if key == "frameworks" else "-"
            detail = f"{entry['status']} · events:{entry['event_count']} · relationships:{entry['relationship_count']}"
            print(f"{marker} {entry['name']} ({detail})")
        print()


def _print_mcp(servers: list[dict[str, Any]]) -> None:
    print("MCP Servers")
    print()
    if not servers:
        print("No MCP servers discovered.")
        return
    print(f"{'server':<28} {'version':<12} {'transport':<12} last_seen")
    for server in servers:
        print(
            f"{_short(server.get('server'), 28):<28} "
            f"{_short(server.get('version') or '-', 12):<12} "
            f"{_short(server.get('transport') or '-', 12):<12} "
            f"{server.get('last_seen') or '-'}"
        )


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
    span_id: str | None = None,
    parent_span_id: str | None = None,
    parent_event_id: str | None = None,
    root_event_id: str | None = None,
) -> dict[str, Any]:
    event = make_openmesh_event(
        event_type,
        source,
        payload,
        target=target,
        severity=severity,
        session_id=session_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        parent_event_id=parent_event_id,
        root_event_id=root_event_id,
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
    span_id: str,
    parent_event_id: str,
    root_event_id: str,
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
                span_id=span_id,
                parent_event_id=parent_event_id,
                root_event_id=root_event_id,
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


async def _trace(args: argparse.Namespace) -> int:
    async def run(db):
        trace = await get_trace(db, args.trace_id)
        if not trace:
            print(f"Trace not found: {args.trace_id}")
            return 1
        _print_trace_detail(trace)

    return await _with_db(run)


async def _graph(args: argparse.Namespace) -> int:
    async def run(db):
        graph = await get_graph(db)
        _print_graph(graph, details=args.details)

    return await _with_db(run)


async def _nodes(args: argparse.Namespace) -> int:
    async def run(db):
        graph = await get_graph(db)
        _print_nodes(graph)

    return await _with_db(run)


async def _registry(args: argparse.Namespace) -> int:
    async def run(db):
        records = await list_openmesh_events(db, limit=args.limit)
        registry = build_registry_status(records)
        _print_registry(registry)
        return 1 if registry["compatibility"]["severity"] == "ERROR" else 0

    return await _with_db(run)


async def _doctor(args: argparse.Namespace) -> int:
    async def run(db):
        report = await run_doctor(db)
        _print_doctor(report)
        return 1 if report["status"] == "ERROR" else 0

    return await _with_db(run)


async def _integrations(args: argparse.Namespace) -> int:
    _print_integrations(list_integrations())
    return 0


async def _discover(args: argparse.Namespace) -> int:
    async def run(db):
        discovery = await get_discovery(db, limit=args.limit)
        _print_discovery(discovery)

    return await _with_db(run)


async def _mcp(args: argparse.Namespace) -> int:
    async def run(db):
        servers = await get_mcp_registry(db, limit=args.limit)
        _print_mcp(servers)

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
    span_id = f"span_{uuid4().hex}"
    process = _process_node(session_id, command)
    command_target = _command_node(command)

    async def run(db) -> int:
        started_at = _utc_now()
        await create_openmesh_session(db, session_id=session_id, command=command, started_at=started_at)
        started_event = await _emit_process_event(
            db,
            "process.started",
            session_id=session_id,
            trace_id=trace_id,
            source=CLI_NODE,
            target=process,
            payload={"command": command, "argv": command_parts, "started_at": started_at.isoformat() + "Z"},
            span_id=span_id,
        )
        root_event_id = started_event["root_event_id"]

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
                span_id=span_id,
                parent_event_id=started_event["event_id"],
                root_event_id=root_event_id,
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
                span_id=span_id,
                parent_event_id=started_event["event_id"],
                root_event_id=root_event_id,
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
                span_id=span_id,
                parent_event_id=started_event["event_id"],
                root_event_id=root_event_id,
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
            span_id=span_id,
            parent_event_id=started_event["event_id"],
            root_event_id=root_event_id,
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

    trace = subparsers.add_parser("trace", help="Inspect one OpenMesh trace.")
    trace.add_argument("trace_id", help="Trace id to inspect.")
    trace.set_defaults(func=_trace)

    graph = subparsers.add_parser("graph", help="Show OpenMesh graph relationships.")
    graph.add_argument("--details", action="store_true", help="Show edge provenance and lifecycle metadata.")
    graph.set_defaults(func=_graph)

    nodes = subparsers.add_parser("nodes", help="Show governed OpenMesh graph nodes.")
    nodes.set_defaults(func=_nodes)

    registry = subparsers.add_parser("registry", help="Show OpenMesh registry versions and compatibility.")
    registry.add_argument("--limit", type=int, default=5000, help="Maximum events to validate compatibility from.")
    registry.set_defaults(func=_registry)

    doctor = subparsers.add_parser("doctor", help="Check OpenMesh local configuration.")
    doctor.set_defaults(func=_doctor)

    integrations = subparsers.add_parser("integrations", help="Show OpenMesh framework integration status.")
    integrations.set_defaults(func=_integrations)

    discover = subparsers.add_parser("discover", help="Show observed OpenMesh ecosystem registry.")
    discover.add_argument("--limit", type=int, default=5000, help="Maximum events to derive discovery from.")
    discover.set_defaults(func=_discover)

    mcp = subparsers.add_parser("mcp", help="Show discovered MCP server metadata.")
    mcp.add_argument("--limit", type=int, default=5000, help="Maximum events to derive MCP registry from.")
    mcp.set_defaults(func=_mcp)

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
