from __future__ import annotations

from typing import Any, Optional

from src.sdk.client import OpenMeshClient

from ._framework import FrameworkAgentHandle, OpenMeshFrameworkRuntime
from .registry import mark_integration_active


OPENMESH_PLUGIN = {
    "plugin_id": "openhands",
    "name": "OpenHands",
    "version": "0.1.0",
    "plugin_api_version": "1.0",
    "kind": "integration",
    "status": "reference",
    "package": "openhands",
    "entrypoint": "OpenMeshOpenHands",
    "description": "Observe OpenHands coding sessions, agents, tasks, commands, files, and tools.",
    "capabilities": [
        "agent.lifecycle",
        "workflow.lifecycle",
        "task.lifecycle",
        "tool.lifecycle",
        "process.lifecycle",
        "file.lifecycle",
        "trace.spans",
        "graph.relationships",
    ],
    "metadata": {"framework": "OpenHands", "protocol_version": "v1"},
}


class OpenMeshOpenHands(OpenMeshFrameworkRuntime):
    """OpenHands integration for session and action-level observability."""

    def __init__(
        self,
        *,
        client: Optional[OpenMeshClient] = None,
        workflow_name: str = "OpenHands Session",
        trace_id: Optional[str] = None,
        version: Optional[str] = None,
        source: str = "openhands",
    ) -> None:
        super().__init__(
            framework_name="OpenHands",
            runtime="openhands",
            workflow_name=workflow_name,
            client=client,
            trace_id=trace_id,
            version=version,
            source=source,
        )
        mark_integration_active("openhands")

    def coding_agent(
        self,
        *,
        id: str = "openhands-agent",
        name: str = "OpenHands Agent",
        role: str = "coding_agent",
    ) -> FrameworkAgentHandle:
        return self.agent(id=id, name=name, role=role)

    def observe_action(
        self,
        name: str,
        *,
        agent: FrameworkAgentHandle,
        description: Optional[str] = None,
    ):
        return agent.task(name, description=description)

    def observe_command(
        self,
        command: str,
        *,
        agent: Optional[FrameworkAgentHandle] = None,
        exit_code: int = 0,
        cwd: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return self.command(command, agent=agent, exit_code=exit_code, cwd=cwd)

    def observe_file(
        self,
        path: str,
        *,
        agent: FrameworkAgentHandle,
        operation: str = "modified",
    ) -> dict[str, Any]:
        return self.file_modified(path, agent=agent, operation=operation)
