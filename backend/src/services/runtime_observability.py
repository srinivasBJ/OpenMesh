from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.openmesh_events import list_openmesh_events
from ..db.openmesh_sessions import complete_openmesh_session, create_openmesh_session
from ..runtimes.registry import (
    RuntimeStatus,
    canonical_runtime_id,
    discover_runtimes,
    get_runtime_definition,
)
from ..shared.openmesh_events import make_openmesh_event
from .openmesh_collector import collector


def runtime_node(status: RuntimeStatus) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "status": status.status,
        "detected": status.available,
    }
    if status.executable:
        metadata["executable"] = status.executable
    if status.path:
        metadata["path"] = status.path
    return {
        "node_id": f"runtime:{status.runtime_id}",
        "node_type": "runtime",
        "name": status.name,
        "runtime": "openmesh.runtime-discovery",
        "metadata": metadata,
    }


def runtime_agent_node(status: RuntimeStatus) -> dict[str, Any]:
    definition = get_runtime_definition(status.runtime_id)
    name = (
        definition.agent_name if definition and definition.agent_name else status.name
    )
    return {
        "node_id": f"agent:runtime:{status.runtime_id}",
        "node_type": "agent",
        "name": name,
        "runtime": status.runtime_id,
        "metadata": {"role": "coding-agent-runtime"},
    }


def runtime_tool_node(status: RuntimeStatus) -> dict[str, Any]:
    return {
        "node_id": f"tool:runtime:{status.runtime_id}:cli",
        "node_type": "tool",
        "name": f"{status.name} CLI",
        "runtime": status.runtime_id,
        "metadata": {"capabilities": ["agent-runtime", "tool-calls", "commands"]},
    }


def runtime_model_node(status: RuntimeStatus) -> dict[str, Any]:
    return {
        "node_id": f"model:runtime:{status.runtime_id}:default",
        "node_type": "model",
        "name": f"{status.name} model",
        "runtime": status.runtime_id,
        "metadata": {"provider": status.name, "local": True},
    }


def runtime_file_node(
    status: RuntimeStatus, path: Path | None = None
) -> dict[str, Any]:
    observed_path = path or Path.cwd()
    return {
        "node_id": f"file:runtime:{status.runtime_id}:{_slug(str(observed_path))}",
        "node_type": "file",
        "name": observed_path.name or str(observed_path),
        "runtime": "filesystem",
        "metadata": {"path": str(observed_path)},
    }


def runtime_command_node(status: RuntimeStatus) -> dict[str, Any]:
    executable = status.executable or status.path or status.runtime_id
    return {
        "node_id": f"command:runtime:{status.runtime_id}",
        "node_type": "command",
        "name": executable,
        "runtime": "shell",
        "metadata": {"executable": executable},
    }


async def observe_runtime(
    db: AsyncSession,
    runtime_id: str,
    *,
    runtime_status: RuntimeStatus | None = None,
    workspace: Path | None = None,
    broadcast: bool = False,
) -> dict[str, Any]:
    status = runtime_status or _status_for_runtime(runtime_id)
    if status is None:
        raise ValueError(f"Unknown OpenMesh runtime: {runtime_id}")
    if not status.available:
        raise RuntimeError(
            f"{status.name} is not installed or detectable on this host."
        )

    session_id = f"sess_runtime_{uuid4().hex}"
    trace_id = f"trace_runtime_{uuid4().hex}"
    root_span_id = f"span_{uuid4().hex}"
    file_span_id = f"span_{uuid4().hex}"
    command_span_id = f"span_{uuid4().hex}"
    model_span_id = f"span_{uuid4().hex}"
    started_at = datetime.utcnow()
    command = f"openmesh observe {canonical_runtime_id(runtime_id)}"
    emitted: list[dict[str, Any]] = []

    await create_openmesh_session(
        db, session_id=session_id, command=command, started_at=started_at
    )

    agent = runtime_agent_node(status)
    runtime = runtime_node(status)
    tool = runtime_tool_node(status)
    model = runtime_model_node(status)
    file_node = runtime_file_node(status, workspace)
    command_node = runtime_command_node(status)

    async def emit(
        event_type: str,
        source: dict[str, Any],
        payload: dict[str, Any],
        *,
        target: dict[str, Any] | None = None,
        span_id: str,
        parent_span_id: str | None = None,
        parent_event_id: str | None = None,
        root_event_id: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = make_openmesh_event(
            event_type,
            source,
            payload,
            target=target,
            metrics=metrics,
            session_id=session_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            parent_event_id=parent_event_id,
            root_event_id=root_event_id,
        )
        await collector.accept(db, event, broadcast=broadcast)
        emitted.append(event)
        return event

    started = await emit(
        "runtime.started",
        agent,
        {
            "runtime_id": status.runtime_id,
            "runtime": status.name,
            "status": status.status,
            "executable": status.executable,
            "path": status.path,
            "started_at": started_at.isoformat() + "Z",
        },
        target=runtime,
        span_id=root_span_id,
    )
    root_event_id = started["event_id"]

    read_event = await emit(
        "file.read",
        agent,
        {"path": file_node["metadata"]["path"], "operation": "workspace_probe"},
        target=file_node,
        span_id=file_span_id,
        parent_span_id=root_span_id,
        parent_event_id=root_event_id,
        root_event_id=root_event_id,
    )
    write_event = await emit(
        "file.write",
        agent,
        {"path": file_node["metadata"]["path"], "operation": "observability_record"},
        target=file_node,
        span_id=file_span_id,
        parent_span_id=root_span_id,
        parent_event_id=read_event["event_id"],
        root_event_id=root_event_id,
    )
    command_event = await emit(
        "command.executed",
        agent,
        {
            "command": command_node["name"],
            "runtime_id": status.runtime_id,
            "dry_run": True,
        },
        target=command_node,
        span_id=command_span_id,
        parent_span_id=root_span_id,
        parent_event_id=write_event["event_id"],
        root_event_id=root_event_id,
        metrics={"exit_code": 0},
    )
    tool_event = await emit(
        "tool.called",
        agent,
        {"tool": tool["name"], "runtime_id": status.runtime_id},
        target=tool,
        span_id=command_span_id,
        parent_span_id=root_span_id,
        parent_event_id=command_event["event_id"],
        root_event_id=root_event_id,
    )
    request_event = await emit(
        "model.request",
        agent,
        {
            "provider": status.name,
            "model": model["name"],
            "runtime_id": status.runtime_id,
        },
        target=model,
        span_id=model_span_id,
        parent_span_id=root_span_id,
        parent_event_id=tool_event["event_id"],
        root_event_id=root_event_id,
    )
    response_event = await emit(
        "model.response",
        agent,
        {
            "provider": status.name,
            "model": model["name"],
            "runtime_id": status.runtime_id,
            "response": "runtime activity observed",
        },
        target=model,
        span_id=model_span_id,
        parent_span_id=root_span_id,
        parent_event_id=request_event["event_id"],
        root_event_id=root_event_id,
        metrics={"latency_ms": 0},
    )
    ended_at = datetime.utcnow()
    await emit(
        "runtime.stopped",
        agent,
        {
            "runtime_id": status.runtime_id,
            "runtime": status.name,
            "status": "completed",
            "started_at": started_at.isoformat() + "Z",
            "ended_at": ended_at.isoformat() + "Z",
            "duration_ms": int((ended_at - started_at).total_seconds() * 1000),
        },
        target=runtime,
        span_id=root_span_id,
        parent_event_id=response_event["event_id"],
        root_event_id=root_event_id,
    )
    await complete_openmesh_session(
        db,
        session_id=session_id,
        ended_at=ended_at,
        status="completed",
        exit_code=0,
    )

    return {
        "runtime": status.to_dict(),
        "session_id": session_id,
        "trace_id": trace_id,
        "events": emitted,
    }


async def get_runtime_metrics(db: AsyncSession, *, limit: int = 5000) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    statuses = discover_runtimes()
    event_types = [record.event_type for record in records]
    started_by_trace = {
        record.trace_id
        for record in records
        if record.event_type == "runtime.started" and record.trace_id
    }
    stopped_by_trace = {
        record.trace_id
        for record in records
        if record.event_type == "runtime.stopped" and record.trace_id
    }
    active_traces = started_by_trace - stopped_by_trace
    durations = [
        int(record.payload_json.get("duration_ms", 0))
        for record in records
        if record.event_type == "runtime.stopped"
        and isinstance(record.payload_json, dict)
        and record.payload_json.get("duration_ms") is not None
    ]
    available = [status for status in statuses if status.available]
    return {
        "active_runtimes": len(active_traces),
        "detected_runtimes": len(available),
        "total_runtimes": len(statuses),
        "commands_executed": event_types.count("command.executed"),
        "files_modified": event_types.count("file.write")
        + event_types.count("file.modified"),
        "model_requests": event_types.count("model.request")
        + event_types.count("llm.request"),
        "runtime_uptime": {
            "available": len(available),
            "total": len(statuses),
            "ratio": round(len(available) / len(statuses), 2) if statuses else 0,
        },
        "average_runtime_duration_ms": round(sum(durations) / len(durations), 2)
        if durations
        else None,
        "runtimes": [status.to_dict() for status in statuses],
    }


def _status_for_runtime(runtime_id: str) -> RuntimeStatus | None:
    canonical = canonical_runtime_id(runtime_id)
    return next(
        (status for status in discover_runtimes() if status.runtime_id == canonical),
        None,
    )


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")
