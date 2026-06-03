from __future__ import annotations

from typing import Any, Optional

from src.sdk.client import OpenMeshClient

from ._framework import FrameworkAgentHandle, OpenMeshFrameworkRuntime
from .registry import mark_integration_active


OPENMESH_PLUGIN = {
    "plugin_id": "autogen",
    "name": "AutoGen",
    "version": "0.1.0",
    "plugin_api_version": "1.0",
    "kind": "integration",
    "status": "reference",
    "package": "autogen_agentchat",
    "entrypoint": "OpenMeshAutoGen",
    "description": "Observe AutoGen agents, group-chat workflows, messages, tasks, and tool calls.",
    "capabilities": [
        "agent.lifecycle",
        "workflow.lifecycle",
        "task.lifecycle",
        "tool.lifecycle",
        "message.lifecycle",
        "trace.spans",
        "graph.relationships",
    ],
    "metadata": {"framework": "AutoGen", "protocol_version": "v1"},
}


def _attr(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            candidate = getattr(value, name)
            if candidate is not None:
                return candidate
    return None


class OpenMeshAutoGen(OpenMeshFrameworkRuntime):
    """AutoGen instrumentation backed by the OpenMesh Python SDK.

    The adapter is intentionally dependency-light: callers can pass AutoGen
    objects when they have them, or use explicit handles around custom runners.
    """

    def __init__(
        self,
        *,
        client: Optional[OpenMeshClient] = None,
        workflow_name: str = "AutoGen Workflow",
        trace_id: Optional[str] = None,
        version: Optional[str] = None,
        source: str = "autogen",
    ) -> None:
        super().__init__(
            framework_name="AutoGen",
            runtime="autogen",
            workflow_name=workflow_name,
            client=client,
            trace_id=trace_id,
            version=version,
            source=source,
        )
        mark_integration_active("autogen")

    def assistant(
        self,
        *,
        id: Optional[str] = None,
        name: str = "AutoGen Assistant",
        role: str = "assistant",
        autogen_agent: Any = None,
    ) -> FrameworkAgentHandle:
        return self.agent(
            id=id or _attr(autogen_agent, "name", "id"),
            name=str(_attr(autogen_agent, "name") or name),
            role=str(_attr(autogen_agent, "role") or role),
        )

    def user_proxy(
        self,
        *,
        id: Optional[str] = None,
        name: str = "AutoGen User Proxy",
        autogen_agent: Any = None,
    ) -> FrameworkAgentHandle:
        return self.agent(
            id=id or _attr(autogen_agent, "name", "id"),
            name=str(_attr(autogen_agent, "name") or name),
            role="user_proxy",
        )

    def observe_message(
        self,
        source: FrameworkAgentHandle,
        target: FrameworkAgentHandle,
        *,
        content: Any = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self.message(
            source=source,
            target=target,
            content=content,
            metadata=metadata,
        )
