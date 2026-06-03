from __future__ import annotations

from typing import Any, Optional

from src.sdk.client import OpenMeshClient

from ._framework import FrameworkAgentHandle, OpenMeshFrameworkRuntime
from .registry import mark_integration_active


OPENMESH_PLUGIN = {
    "plugin_id": "opencode",
    "name": "OpenCode",
    "version": "0.1.0",
    "plugin_api_version": "1.0",
    "kind": "integration",
    "status": "reference",
    "entrypoint": "OpenMeshOpenCode",
    "description": "Observe OpenCode sessions through command, file, tool, and message metadata.",
    "capabilities": [
        "agent.lifecycle",
        "workflow.lifecycle",
        "tool.lifecycle",
        "process.lifecycle",
        "file.lifecycle",
        "message.lifecycle",
        "trace.spans",
        "graph.relationships",
    ],
    "metadata": {
        "framework": "OpenCode",
        "protocol_version": "v1",
        "integration_mode": "cli_metadata",
    },
}


class OpenMeshOpenCode(OpenMeshFrameworkRuntime):
    """OpenCode integration for observable terminal coding-agent metadata."""

    def __init__(
        self,
        *,
        client: Optional[OpenMeshClient] = None,
        workflow_name: str = "OpenCode Session",
        trace_id: Optional[str] = None,
        version: Optional[str] = None,
        source: str = "opencode",
    ) -> None:
        super().__init__(
            framework_name="OpenCode",
            runtime="opencode",
            workflow_name=workflow_name,
            client=client,
            trace_id=trace_id,
            version=version,
            source=source,
        )
        mark_integration_active("opencode")

    def coding_agent(
        self,
        *,
        id: str = "opencode-agent",
        name: str = "OpenCode Agent",
        role: str = "coding_agent",
    ) -> FrameworkAgentHandle:
        return self.agent(id=id, name=name, role=role)

    def observe_event(
        self,
        payload: dict[str, Any],
        *,
        agent: Optional[FrameworkAgentHandle] = None,
    ) -> list[dict[str, Any]]:
        active_agent = agent or self.coding_agent()
        events: list[dict[str, Any]] = []
        tool_name = payload.get("tool_name") or payload.get("tool")
        command = payload.get("command")
        file_path = payload.get("file_path") or payload.get("path")
        message = payload.get("message") or payload.get("prompt")
        with self.workflow():
            if message:
                peer = self.agent(id="opencode-user", name="OpenCode User", role="user")
                events.append(
                    self.message(source=peer, target=active_agent, content=message)
                )
            if tool_name:
                with active_agent.tool(str(tool_name)):
                    pass
            if command:
                events.extend(
                    self.command(
                        str(command),
                        agent=active_agent,
                        exit_code=int(payload.get("exit_code") or 0),
                        cwd=payload.get("cwd"),
                    )
                )
            if file_path:
                events.append(
                    self.file_modified(
                        str(file_path),
                        agent=active_agent,
                        operation=str(payload.get("operation") or "modified"),
                    )
                )
        return events
