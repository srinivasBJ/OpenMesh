from __future__ import annotations

from types import TracebackType
from typing import Any, Optional
from uuid import uuid4

from src.sdk.client import OpenMeshClient
from src.shared.openmesh_events import OpenMeshEvent, OpenMeshNode, OpenMeshSeverity


def stable_id(value: str) -> str:
    return (
        "".join(
            character.lower() if character.isalnum() else "-" for character in value
        )
        .strip("-")
        .replace("--", "-")
        or "entity"
    )


def safe_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {"keys": sorted(str(key) for key in value)}
    if isinstance(value, (str, int, float, bool)):
        return {"value": value}
    if isinstance(value, (list, tuple, set)):
        return {"type": value.__class__.__name__, "count": len(value)}
    return {"type": value.__class__.__name__}


class OpenMeshFrameworkRuntime:
    """Shared SDK-backed runtime for framework integrations.

    The helper centralizes OpenMesh protocol event emission only. Framework
    adapters still decide where to call it and no integration-specific graph
    model is introduced.
    """

    def __init__(
        self,
        *,
        framework_name: str,
        runtime: str,
        workflow_name: str,
        client: Optional[OpenMeshClient] = None,
        trace_id: Optional[str] = None,
        version: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        if not workflow_name.strip():
            raise ValueError("OpenMesh integration requires a non-empty workflow_name")
        self.framework_name = framework_name
        self.runtime = runtime
        self.workflow_name = workflow_name
        self.version = version
        self.source = source or runtime
        self.client = client or OpenMeshClient()
        self.trace_id = trace_id or f"trace_{uuid4().hex}"
        self.workflow_span_id = f"span_{uuid4().hex}"
        self.workflow_event_id: Optional[str] = None
        self.root_event_id: Optional[str] = None
        self._agents: dict[str, FrameworkAgentHandle] = {}
        self._workflow_agent_events: set[str] = set()
        self._last_task_context: Optional[dict[str, str]] = None

    def agent(
        self,
        *,
        id: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "FrameworkAgentHandle":
        agent_name = name or role or f"{self.framework_name} Agent"
        agent_id = id or f"{self.runtime}:agent:{stable_id(agent_name)}"
        if agent_id not in self._agents:
            self._agents[agent_id] = FrameworkAgentHandle(
                self,
                {
                    "node_id": agent_id,
                    "node_type": "agent",
                    "name": agent_name,
                    "runtime": self.runtime,
                    "metadata": {
                        "framework": self.framework_name,
                        **({"role": role} if role else {}),
                        **({"version": self.version} if self.version else {}),
                        **(metadata or {}),
                    },
                },
            )
        return self._agents[agent_id]

    def workflow(self) -> "FrameworkWorkflowContext":
        return FrameworkWorkflowContext(self)

    def task(
        self,
        name: str,
        *,
        agent: "FrameworkAgentHandle",
        description: Optional[str] = None,
        expected_output: Optional[str] = None,
    ) -> "FrameworkTaskContext":
        return FrameworkTaskContext(
            self,
            agent,
            name,
            description=description,
            expected_output=expected_output,
        )

    def tool(
        self, name: str, *, agent: "FrameworkAgentHandle"
    ) -> "FrameworkToolContext":
        return FrameworkToolContext(self, agent, name, task=None)

    def message(
        self,
        *,
        source: "FrameworkAgentHandle",
        target: "FrameworkAgentHandle",
        content: Any = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> OpenMeshEvent:
        self._ensure_workflow_started()
        source.ensure_registered()
        target.ensure_registered()
        self._ensure_agent_runs_workflow(source)
        self._ensure_agent_runs_workflow(target)
        event = self.client.emit(
            "message.sent",
            source.node,
            {
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
                "message": safe_payload(content),
                "metadata": metadata or {},
            },
            target=target.node,
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=self.workflow_event_id,
        )
        self._remember_root(event)
        return event

    def transition(self, source_task: str, target_task: str) -> OpenMeshEvent:
        self._validate_name(source_task, "source task")
        self._validate_name(target_task, "target task")
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "node.transition",
            self._task_node(source_task),
            {
                "workflow": self.workflow_name,
                "from": source_task,
                "to": target_task,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
            },
            target=self._task_node(target_task),
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        self._remember_root(event)
        return event

    def command(
        self,
        command: str,
        *,
        agent: Optional["FrameworkAgentHandle"] = None,
        exit_code: int = 0,
        cwd: Optional[str] = None,
    ) -> list[OpenMeshEvent]:
        self._validate_name(command, "command")
        workflow_event = self._ensure_workflow_started()
        if agent:
            agent.ensure_registered()
            self._ensure_agent_runs_workflow(agent)
        process = self._process_node(command)
        command_node = self._command_node(command)
        process_event = self.client.emit(
            "process.started",
            agent.node if agent else self._runtime_node(),
            {
                "command": command,
                "cwd": cwd,
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
            },
            target=process,
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        command_event = self.client.emit(
            "command.executed",
            process,
            {
                "command": command,
                "cwd": cwd,
                "exit_code": exit_code,
                "workflow": self.workflow_name,
                "framework": self.framework_name,
            },
            target=command_node,
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=process_event["event_id"],
            severity="error" if exit_code else "info",
        )
        completion_event = self.client.emit(
            "process.failed" if exit_code else "process.completed",
            process,
            {
                "command": command,
                "exit_code": exit_code,
                "workflow": self.workflow_name,
                "framework": self.framework_name,
            },
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=command_event["event_id"],
            severity="error" if exit_code else "info",
        )
        self._remember_root(process_event)
        return [process_event, command_event, completion_event]

    def file_modified(
        self,
        path: str,
        *,
        agent: "FrameworkAgentHandle",
        operation: str = "modified",
    ) -> OpenMeshEvent:
        self._validate_name(path, "file path")
        self._ensure_workflow_started()
        agent.ensure_registered()
        self._ensure_agent_runs_workflow(agent)
        event = self.client.emit(
            "file.modified",
            agent.node,
            {
                "path": path,
                "operation": operation,
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
            },
            target={
                "node_id": f"file:{stable_id(path)}",
                "node_type": "file",
                "name": path,
                "runtime": self.runtime,
                "metadata": {
                    "framework": self.framework_name,
                    "path": path,
                    **({"version": self.version} if self.version else {}),
                },
            },
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=self.workflow_event_id,
        )
        self._remember_root(event)
        return event

    def complete(self, output: Any = None) -> OpenMeshEvent:
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.completed",
            self._runtime_node(),
            {
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
                "output": safe_payload(output),
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        self._remember_root(event)
        return event

    def fail(self, exc: BaseException) -> OpenMeshEvent:
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.failed",
            self._runtime_node(),
            {
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=workflow_event["event_id"],
            severity="error",
        )
        self._remember_root(event)
        return event

    def _ensure_workflow_started(self) -> OpenMeshEvent:
        if self.workflow_event_id:
            return {
                "event_id": self.workflow_event_id,
                "root_event_id": self.root_event_id or self.workflow_event_id,
            }
        event = self.client.emit(
            "workflow.started",
            self._runtime_node(),
            {
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "version": self.version,
                "source": self.source,
                "runtime": self._runtime_payload(),
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            span_id=self.workflow_span_id,
        )
        self.workflow_event_id = event["event_id"]
        self._remember_root(event)
        return event

    def _ensure_agent_runs_workflow(self, agent: "FrameworkAgentHandle") -> None:
        if agent.node["node_id"] in self._workflow_agent_events:
            return
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.registered",
            agent.node,
            {
                "workflow": self.workflow_name,
                "framework": self.framework_name,
                "version": self.version,
                "source": self.source,
                "runtime": self._runtime_payload(),
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        self._workflow_agent_events.add(agent.node["node_id"])
        self._remember_root(event)

    def _transition_from_previous(self, task_name: str) -> Optional[OpenMeshEvent]:
        previous = self._last_task_context
        current = self._task_node(task_name)
        if not previous or previous["node_id"] == current["node_id"]:
            return None
        event = self.client.emit(
            "node.transition",
            self._task_node(previous["name"]),
            {
                "workflow": self.workflow_name,
                "from": previous["name"],
                "to": task_name,
                "framework": self.framework_name,
                "runtime": self._runtime_payload(),
            },
            target=current,
            trace_id=self.trace_id,
            root_event_id=self.root_event_id,
            span_id=self.workflow_span_id,
            parent_event_id=previous["event_id"],
            links=[
                {
                    "trace_id": self.trace_id,
                    "span_id": previous["span_id"],
                    "event_id": previous["event_id"],
                    "relationship": "follows_from",
                }
            ],
        )
        self._remember_root(event)
        return event

    def _remember_task(self, task_name: str, span_id: str, event_id: str) -> None:
        self._last_task_context = {
            "name": task_name,
            "node_id": self._task_node(task_name)["node_id"],
            "span_id": span_id,
            "event_id": event_id,
        }

    def _runtime_node(self) -> OpenMeshNode:
        return {
            "node_id": f"{self.runtime}.runtime",
            "node_type": "service",
            "name": f"{self.framework_name} Runtime",
            "runtime": self.runtime,
            "metadata": {
                "framework": self.framework_name,
                "source": self.source,
                **({"version": self.version} if self.version else {}),
            },
        }

    def _workflow_node(self) -> OpenMeshNode:
        return {
            "node_id": f"workflow:{self.runtime}:{stable_id(self.workflow_name)}",
            "node_type": "workflow",
            "name": self.workflow_name,
            "runtime": self.runtime,
            "metadata": {
                "framework": self.framework_name,
                "source": self.source,
                **({"version": self.version} if self.version else {}),
            },
        }

    def _task_node(self, task_name: str) -> OpenMeshNode:
        return {
            "node_id": (
                f"{self.runtime}:{stable_id(self.workflow_name)}:"
                f"task:{stable_id(task_name)}"
            ),
            "node_type": "service",
            "name": task_name,
            "runtime": self.runtime,
            "metadata": {"framework": self.framework_name, "source": self.source},
        }

    def _tool_node(self, tool_name: str) -> OpenMeshNode:
        return {
            "node_id": f"tool:{self.runtime}:{stable_id(tool_name)}",
            "node_type": "tool",
            "name": tool_name,
            "runtime": self.runtime,
            "metadata": {"framework": self.framework_name},
        }

    def _process_node(self, command: str) -> OpenMeshNode:
        return {
            "node_id": f"process:{self.runtime}:{stable_id(command)}",
            "node_type": "process",
            "name": command,
            "runtime": self.runtime,
            "metadata": {
                "framework": self.framework_name,
                "session_id": self.client.session_id,
            },
        }

    def _command_node(self, command: str) -> OpenMeshNode:
        executable = command.split(" ", 1)[0]
        return {
            "node_id": f"command:{self.runtime}:{stable_id(command)}",
            "node_type": "command",
            "name": command,
            "runtime": self.runtime,
            "metadata": {
                "framework": self.framework_name,
                "executable": executable,
            },
        }

    def _runtime_payload(self) -> dict[str, Any]:
        return {
            "framework": self.framework_name,
            "workflow": self.workflow_name,
            "source": self.source,
            "protocol": {"name": "OpenMesh Protocol", "version": "v1"},
            **({"version": self.version} if self.version else {}),
        }

    def _remember_root(self, event: OpenMeshEvent) -> None:
        if self.root_event_id is None:
            self.root_event_id = event.get("root_event_id") or event["event_id"]

    @staticmethod
    def _validate_name(value: str, label: str) -> None:
        if not value.strip():
            raise ValueError(f"{label} cannot be empty")


class FrameworkAgentHandle:
    def __init__(self, mesh: OpenMeshFrameworkRuntime, node: OpenMeshNode) -> None:
        self.mesh = mesh
        self.node = node
        self._registered = False
        self._registration_event: Optional[OpenMeshEvent] = None

    @property
    def name(self) -> str:
        return self.node["name"]

    def ensure_registered(self) -> Optional[OpenMeshEvent]:
        if self._registered:
            return self._registration_event
        event = self.mesh.client.emit(
            "agent.registered",
            self.node,
            {
                "agent_id": self.node["node_id"],
                "name": self.node["name"],
                "role": (self.node.get("metadata") or {}).get("role"),
                "framework": self.mesh.framework_name,
                "runtime": self.mesh._runtime_payload(),
            },
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            parent_event_id=self.mesh.workflow_event_id,
            span_id=self.mesh.workflow_span_id if self.mesh.workflow_event_id else None,
        )
        self._registered = True
        self._registration_event = event
        self.mesh._remember_root(event)
        return event

    def task(
        self,
        name: str,
        *,
        description: Optional[str] = None,
        expected_output: Optional[str] = None,
    ) -> "FrameworkTaskContext":
        return self.mesh.task(
            name,
            agent=self,
            description=description,
            expected_output=expected_output,
        )

    def tool(self, name: str) -> "FrameworkToolContext":
        return FrameworkToolContext(self.mesh, self, name, task=None)


class FrameworkWorkflowContext:
    def __init__(self, mesh: OpenMeshFrameworkRuntime) -> None:
        self.mesh = mesh

    def __enter__(self) -> "FrameworkWorkflowContext":
        self.mesh._ensure_workflow_started()
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        if exc:
            self.mesh.fail(exc)
        else:
            self.mesh.complete()
        return False


class FrameworkTaskContext:
    def __init__(
        self,
        mesh: OpenMeshFrameworkRuntime,
        agent: FrameworkAgentHandle,
        name: str,
        *,
        description: Optional[str],
        expected_output: Optional[str],
    ) -> None:
        mesh._validate_name(name, "task name")
        self.mesh = mesh
        self.agent = agent
        self.name = name
        self.description = description
        self.expected_output = expected_output
        self.span_id = f"span_{uuid4().hex}"
        self.start_event_id: Optional[str] = None

    def __enter__(self) -> "FrameworkTaskContext":
        workflow_event = self.mesh._ensure_workflow_started()
        self.agent.ensure_registered()
        self.mesh._ensure_agent_runs_workflow(self.agent)
        transition = self.mesh._transition_from_previous(self.name)
        parent_event_id = (transition or workflow_event)["event_id"]
        node_started = self.mesh.client.emit(
            "node.started",
            self.mesh._task_node(self.name),
            self._payload(),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            span_id=self.span_id,
            parent_span_id=self.mesh.workflow_span_id,
            parent_event_id=parent_event_id,
        )
        event = self.mesh.client.emit(
            "task.started",
            self.agent.node,
            self._payload(),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            span_id=self.span_id,
            parent_span_id=self.mesh.workflow_span_id,
            parent_event_id=node_started["event_id"],
        )
        self.start_event_id = event["event_id"]
        self.mesh._remember_root(event)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        event_type, payload, severity = self._completion_event(exc)
        event = self.mesh.client.emit(
            event_type,
            self.agent.node,
            payload,
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            span_id=self.span_id,
            parent_span_id=self.mesh.workflow_span_id,
            parent_event_id=self.start_event_id,
            severity=severity,
        )
        self.mesh.client.emit(
            "node.failed" if exc else "node.completed",
            self.mesh._task_node(self.name),
            payload,
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            span_id=self.span_id,
            parent_span_id=self.mesh.workflow_span_id,
            parent_event_id=event["event_id"],
            severity=severity,
        )
        self.mesh._remember_task(self.name, self.span_id, event["event_id"])
        return False

    def tool(self, name: str) -> "FrameworkToolContext":
        return FrameworkToolContext(self.mesh, self.agent, name, task=self)

    def _payload(self) -> dict[str, Any]:
        return {
            "task": self.name,
            "workflow": self.mesh.workflow_name,
            "framework": self.mesh.framework_name,
            "description": self.description,
            "expected_output": self.expected_output,
            "runtime": self.mesh._runtime_payload(),
        }

    def _completion_event(
        self, exc: Optional[BaseException]
    ) -> tuple[str, dict[str, Any], OpenMeshSeverity]:
        payload = self._payload()
        if exc:
            payload["error"] = str(exc)
            payload["error_type"] = exc.__class__.__name__
            return "task.failed", payload, "error"
        return "task.completed", payload, "info"


class FrameworkToolContext:
    def __init__(
        self,
        mesh: OpenMeshFrameworkRuntime,
        agent: FrameworkAgentHandle,
        name: str,
        *,
        task: Optional[FrameworkTaskContext],
    ) -> None:
        mesh._validate_name(name, "tool name")
        self.mesh = mesh
        self.agent = agent
        self.name = name
        self.task = task
        self.span_id = f"span_{uuid4().hex}"
        self.start_event_id: Optional[str] = None

    def __enter__(self) -> "FrameworkToolContext":
        self.agent.ensure_registered()
        parent_event_id = (
            self.task.start_event_id
            if self.task
            else self.mesh._ensure_workflow_started()["event_id"]
        )
        parent_span_id = self.task.span_id if self.task else self.mesh.workflow_span_id
        event = self.mesh.client.emit(
            "tool.call.started",
            self.agent.node,
            self._payload(),
            target=self.mesh._tool_node(self.name),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            span_id=self.span_id,
            parent_span_id=parent_span_id,
            parent_event_id=parent_event_id,
        )
        self.start_event_id = event["event_id"]
        self.mesh._remember_root(event)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        event_type = "tool.call.failed" if exc else "tool.call.completed"
        severity: OpenMeshSeverity = "error" if exc else "info"
        payload = self._payload()
        if exc:
            payload["error"] = str(exc)
            payload["error_type"] = exc.__class__.__name__
        self.mesh.client.emit(
            event_type,
            self.agent.node,
            payload,
            target=self.mesh._tool_node(self.name),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh.root_event_id,
            span_id=self.span_id,
            parent_span_id=self.task.span_id
            if self.task
            else self.mesh.workflow_span_id,
            parent_event_id=self.start_event_id,
            severity=severity,
        )
        return False

    def _payload(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "task": self.task.name if self.task else None,
            "workflow": self.mesh.workflow_name,
            "framework": self.mesh.framework_name,
            "runtime": self.mesh._runtime_payload(),
        }
