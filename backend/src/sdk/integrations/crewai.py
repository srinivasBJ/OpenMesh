from __future__ import annotations

from contextvars import ContextVar
from types import TracebackType
from typing import Any, Optional
from uuid import uuid4

from src.sdk.client import OpenMeshClient
from src.shared.openmesh_events import OpenMeshEvent, OpenMeshNode, OpenMeshSeverity

from .registry import mark_integration_active


_current_crewai_task: ContextVar[Optional["CrewAITaskContext"]] = ContextVar(
    "openmesh_crewai_task",
    default=None,
)


def _stable_id(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-") or "entity"


def _safe_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {"keys": sorted(str(key) for key in value.keys())}
    if isinstance(value, (str, int, float, bool)):
        return {"value": value}
    return {"type": value.__class__.__name__}


def _attr(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            candidate = getattr(value, name)
            if candidate is not None:
                return candidate
    return None


class OpenMeshCrewAI:
    """CrewAI instrumentation that emits OpenMesh events through the Python SDK."""

    def __init__(
        self,
        *,
        client: Optional[OpenMeshClient] = None,
        crew_name: str = "CrewAI Workflow",
        trace_id: Optional[str] = None,
        version: Optional[str] = None,
        source: str = "crewai",
    ) -> None:
        if not crew_name.strip():
            raise ValueError("CrewAI integration requires a non-empty crew_name")
        self.client = client or OpenMeshClient()
        self.crew_name = crew_name
        self.trace_id = trace_id or f"trace_{uuid4().hex}"
        self.version = version
        self.source = source
        self._workflow_span_id = f"span_{uuid4().hex}"
        self._workflow_event_id: Optional[str] = None
        self._root_event_id: Optional[str] = None
        self._agents: dict[str, CrewAIAgentHandle] = {}
        self._workflow_agent_events: set[str] = set()
        self._last_task_context: Optional[dict[str, str]] = None
        mark_integration_active("crewai")

    def agent(
        self,
        *,
        id: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        crewai_agent: Any = None,
    ) -> "CrewAIAgentHandle":
        agent_name = name or role or str(_attr(crewai_agent, "role", "name") or "CrewAI Agent")
        agent_role = role or str(_attr(crewai_agent, "role") or agent_name)
        agent_id = id or f"crewai:agent:{_stable_id(agent_role)}"
        if agent_id not in self._agents:
            self._agents[agent_id] = CrewAIAgentHandle(
                self,
                {
                    "node_id": agent_id,
                    "node_type": "agent",
                    "name": agent_name,
                    "runtime": "crewai",
                    "metadata": {
                        "framework": "CrewAI",
                        "role": agent_role,
                        **({"version": self.version} if self.version else {}),
                    },
                },
            )
        return self._agents[agent_id]

    def observe_crew(self, crew: Any) -> list["CrewAIAgentHandle"]:
        """Register agents discovered from a CrewAI Crew-like object."""
        self._ensure_workflow_started()
        agents = []
        for raw_agent in _attr(crew, "agents") or []:
            agents.append(self.agent(crewai_agent=raw_agent))
        if _attr(crew, "tasks"):
            self._ensure_workflow_started()
        for agent in agents:
            agent.ensure_registered()
            self._ensure_agent_runs_workflow(agent)
        return agents

    def workflow(self) -> "CrewAIWorkflowContext":
        return CrewAIWorkflowContext(self)

    def task(
        self,
        name: str,
        *,
        agent: "CrewAIAgentHandle",
        description: Optional[str] = None,
        expected_output: Optional[str] = None,
    ) -> "CrewAITaskContext":
        return CrewAITaskContext(
            self,
            agent,
            name,
            description=description,
            expected_output=expected_output,
        )

    def transition(self, source_task: str, target_task: str) -> OpenMeshEvent:
        self._validate_name(source_task, "CrewAI source task")
        self._validate_name(target_task, "CrewAI target task")
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "node.transition",
            self._task_node(source_task),
            {
                "workflow": self.crew_name,
                "from": source_task,
                "to": target_task,
                "runtime": self._runtime_payload(),
            },
            target=self._task_node(target_task),
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            parent_event_id=workflow_event["event_id"],
        )
        self._remember_root(event)
        return event

    def kickoff(self, crew: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a CrewAI Crew-like object while observing the workflow lifecycle."""
        self.observe_crew(crew)
        with self.workflow():
            return crew.kickoff(*args, **kwargs)

    def complete(self, output: Any = None) -> OpenMeshEvent:
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.completed",
            self._runtime_node(),
            {
                "workflow": self.crew_name,
                "framework": "CrewAI",
                "runtime": self._runtime_payload(),
                "output": _safe_payload(output),
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
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
                "workflow": self.crew_name,
                "framework": "CrewAI",
                "runtime": self._runtime_payload(),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            parent_event_id=workflow_event["event_id"],
            severity="error",
        )
        self._remember_root(event)
        return event

    def _ensure_workflow_started(self) -> OpenMeshEvent:
        if self._workflow_event_id:
            return {
                "event_id": self._workflow_event_id,
                "root_event_id": self._root_event_id or self._workflow_event_id,
            }
        event = self.client.emit(
            "workflow.started",
            self._runtime_node(),
            {
                "workflow": self.crew_name,
                "framework": "CrewAI",
                "version": self.version,
                "source": self.source,
                "runtime": self._runtime_payload(),
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            span_id=self._workflow_span_id,
        )
        self._workflow_event_id = event["event_id"]
        self._remember_root(event)
        return event

    def _ensure_agent_runs_workflow(self, agent: "CrewAIAgentHandle") -> None:
        if agent.node["node_id"] in self._workflow_agent_events:
            return
        workflow_event = self._ensure_workflow_started()
        event = self.client.emit(
            "workflow.registered",
            agent.node,
            {
                "workflow": self.crew_name,
                "framework": "CrewAI",
                "version": self.version,
                "source": self.source,
            },
            target=self._workflow_node(),
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
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
                "workflow": self.crew_name,
                "from": previous["name"],
                "to": task_name,
                "runtime": self._runtime_payload(),
            },
            target=current,
            trace_id=self.trace_id,
            root_event_id=self._root_event_id,
            span_id=self._workflow_span_id,
            parent_event_id=previous["event_id"],
            links=[{
                "trace_id": self.trace_id,
                "span_id": previous["span_id"],
                "event_id": previous["event_id"],
                "relationship": "follows_from",
            }],
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
            "node_id": "crewai.runtime",
            "node_type": "service",
            "name": "CrewAI Runtime",
            "runtime": "crewai",
            "metadata": {
                "framework": "CrewAI",
                "source": self.source,
                **({"version": self.version} if self.version else {}),
            },
        }

    def _workflow_node(self) -> OpenMeshNode:
        return {
            "node_id": f"workflow:crewai:{_stable_id(self.crew_name)}",
            "node_type": "workflow",
            "name": self.crew_name,
            "runtime": "crewai",
            "metadata": {
                "framework": "CrewAI",
                "source": self.source,
                **({"version": self.version} if self.version else {}),
            },
        }

    def _task_node(self, task_name: str) -> OpenMeshNode:
        return {
            "node_id": f"crewai:{_stable_id(self.crew_name)}:task:{_stable_id(task_name)}",
            "node_type": "service",
            "name": task_name,
            "runtime": "crewai",
            "metadata": {
                "framework": "CrewAI",
                "source": self.source,
            },
        }

    def _runtime_payload(self) -> dict[str, Any]:
        return {
            "framework": "CrewAI",
            "workflow": self.crew_name,
            "source": self.source,
            **({"version": self.version} if self.version else {}),
        }

    def _remember_root(self, event: OpenMeshEvent) -> None:
        if self._root_event_id is None:
            self._root_event_id = event.get("root_event_id") or event["event_id"]

    def _validate_name(self, value: str, label: str) -> None:
        if not value.strip():
            raise ValueError(f"{label} cannot be empty")


class CrewAIAgentHandle:
    def __init__(self, mesh: OpenMeshCrewAI, node: OpenMeshNode) -> None:
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
        workflow_event_id = self.mesh._workflow_event_id
        event = self.mesh.client.emit(
            "agent.registered",
            self.node,
            {
                "agent_id": self.node["node_id"],
                "name": self.node["name"],
                "role": (self.node.get("metadata") or {}).get("role"),
                "framework": "CrewAI",
            },
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh._root_event_id,
            parent_event_id=workflow_event_id,
            span_id=self.mesh._workflow_span_id if workflow_event_id else None,
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
    ) -> "CrewAITaskContext":
        return self.mesh.task(
            name,
            agent=self,
            description=description,
            expected_output=expected_output,
        )

    def tool(self, name: str) -> "CrewAIToolContext":
        task = _current_crewai_task.get()
        return CrewAIToolContext(self.mesh, self, name, task=task)


class CrewAIWorkflowContext:
    def __init__(self, mesh: OpenMeshCrewAI) -> None:
        self.mesh = mesh

    def __enter__(self) -> "CrewAIWorkflowContext":
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


class CrewAITaskContext:
    def __init__(
        self,
        mesh: OpenMeshCrewAI,
        agent: CrewAIAgentHandle,
        name: str,
        *,
        description: Optional[str],
        expected_output: Optional[str],
    ) -> None:
        mesh._validate_name(name, "CrewAI task name")
        self.mesh = mesh
        self.agent = agent
        self.name = name
        self.description = description
        self.expected_output = expected_output
        self.span_id = f"span_{uuid4().hex}"
        self.start_event_id: Optional[str] = None
        self.node_start_event_id: Optional[str] = None
        self._task_token = None

    def __enter__(self) -> "CrewAITaskContext":
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
            root_event_id=self.mesh._root_event_id,
            span_id=self.span_id,
            parent_span_id=self.mesh._workflow_span_id,
            parent_event_id=parent_event_id,
        )
        self.node_start_event_id = node_started["event_id"]
        event = self.mesh.client.emit(
            "task.started",
            self.agent.node,
            self._payload(),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh._root_event_id,
            span_id=self.span_id,
            parent_span_id=self.mesh._workflow_span_id,
            parent_event_id=node_started["event_id"],
        )
        self.start_event_id = event["event_id"]
        self._task_token = _current_crewai_task.set(self)
        self.mesh._remember_root(event)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> bool:
        try:
            event_type, payload, severity = self._completion_event(exc)
            event = self.mesh.client.emit(
                event_type,
                self.agent.node,
                payload,
                trace_id=self.mesh.trace_id,
                root_event_id=self.mesh._root_event_id,
                span_id=self.span_id,
                parent_span_id=self.mesh._workflow_span_id,
                parent_event_id=self.start_event_id,
                severity=severity,
            )
            self.mesh.client.emit(
                "node.failed" if exc else "node.completed",
                self.mesh._task_node(self.name),
                payload,
                trace_id=self.mesh.trace_id,
                root_event_id=self.mesh._root_event_id,
                span_id=self.span_id,
                parent_span_id=self.mesh._workflow_span_id,
                parent_event_id=event["event_id"],
                severity=severity,
            )
            self.mesh._remember_task(self.name, self.span_id, event["event_id"])
        finally:
            if self._task_token is not None:
                _current_crewai_task.reset(self._task_token)
        return False

    def tool(self, name: str) -> "CrewAIToolContext":
        return CrewAIToolContext(self.mesh, self.agent, name, task=self)

    def _payload(self) -> dict[str, Any]:
        return {
            "task": self.name,
            "workflow": self.mesh.crew_name,
            "framework": "CrewAI",
            "description": self.description,
            "expected_output": self.expected_output,
            "runtime": self.mesh._runtime_payload(),
        }

    def _completion_event(self, exc: Optional[BaseException]) -> tuple[str, dict[str, Any], OpenMeshSeverity]:
        payload = self._payload()
        if exc:
            payload["error"] = str(exc)
            payload["error_type"] = exc.__class__.__name__
            return "task.failed", payload, "error"
        return "task.completed", payload, "info"


class CrewAIToolContext:
    def __init__(
        self,
        mesh: OpenMeshCrewAI,
        agent: CrewAIAgentHandle,
        name: str,
        *,
        task: Optional[CrewAITaskContext],
    ) -> None:
        mesh._validate_name(name, "CrewAI tool name")
        self.mesh = mesh
        self.agent = agent
        self.name = name
        self.task = task
        self.span_id = f"span_{uuid4().hex}"
        self.start_event_id: Optional[str] = None

    def __enter__(self) -> "CrewAIToolContext":
        self.agent.ensure_registered()
        parent_event_id = self.task.start_event_id if self.task else self.mesh._ensure_workflow_started()["event_id"]
        parent_span_id = self.task.span_id if self.task else self.mesh._workflow_span_id
        event = self.mesh.client.emit(
            "tool.call.started",
            self.agent.node,
            self._payload(),
            target=self._tool_node(),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh._root_event_id,
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
            target=self._tool_node(),
            trace_id=self.mesh.trace_id,
            root_event_id=self.mesh._root_event_id,
            span_id=self.span_id,
            parent_span_id=self.task.span_id if self.task else self.mesh._workflow_span_id,
            parent_event_id=self.start_event_id,
            severity=severity,
        )
        return False

    def _tool_node(self) -> OpenMeshNode:
        return {
            "node_id": f"tool:crewai:{_stable_id(self.name)}",
            "node_type": "tool",
            "name": self.name,
            "runtime": "crewai",
            "metadata": {"framework": "CrewAI"},
        }

    def _payload(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "task": self.task.name if self.task else None,
            "workflow": self.mesh.crew_name,
            "framework": "CrewAI",
            "runtime": self.mesh._runtime_payload(),
        }
