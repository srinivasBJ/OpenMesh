from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FailureCategory:
    key: str
    display_name: str
    description: str
    signals: tuple[str, ...]


FAILURE_TAXONOMY: dict[str, FailureCategory] = {
    "model_failure": FailureCategory(
        "model_failure",
        "Model Failure",
        "A model request, model response, or provider call failed.",
        ("llm", "model", "provider", "completion", "token"),
    ),
    "tool_failure": FailureCategory(
        "tool_failure",
        "Tool Failure",
        "A tool call failed or returned an error.",
        ("tool", "tool.call", "tooling"),
    ),
    "mcp_failure": FailureCategory(
        "mcp_failure",
        "MCP Failure",
        "An MCP server, tool, or transport failed.",
        ("mcp", "server", "transport"),
    ),
    "handoff_failure": FailureCategory(
        "handoff_failure",
        "Handoff Failure",
        "Agent-to-agent delegation, review, or communication failed.",
        ("handoff", "message", "delegate", "delegation", "review"),
    ),
    "context_failure": FailureCategory(
        "context_failure",
        "Context Failure",
        "The runtime lost, exceeded, or could not construct required context.",
        ("context", "prompt", "window", "memory", "tokens", "token"),
    ),
    "timeout_failure": FailureCategory(
        "timeout_failure",
        "Timeout Failure",
        "An operation timed out or exceeded its deadline.",
        ("timeout", "timed out", "deadline", "expired", "cancelled"),
    ),
    "permission_failure": FailureCategory(
        "permission_failure",
        "Permission Failure",
        "A request was denied by authentication, authorization, or filesystem permissions.",
        ("permission", "denied", "unauthorized", "forbidden", "auth", "401", "403"),
    ),
    "resource_failure": FailureCategory(
        "resource_failure",
        "Resource Failure",
        "A file, database, repository, API endpoint, process, or memory resource failed.",
        ("resource", "file", "database", "github", "api", "memory", "process"),
    ),
}

RESOURCE_NODE_TYPES = {
    "file",
    "database",
    "github_repository",
    "api_endpoint",
    "memory_store",
    "process",
}
CAUSE_NODE_TYPES = {
    "tool",
    "model",
    "service",
    "mcp_server",
    "process",
    *RESOURCE_NODE_TYPES,
}
AFFECTED_NODE_TYPES = {"agent", "workflow"}


def taxonomy_definitions() -> list[dict[str, Any]]:
    return [asdict(category) for category in FAILURE_TAXONOMY.values()]


def classify_failure(
    event_type: str,
    payload: dict[str, Any] | None = None,
    source: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    source = source or {}
    target = target or {}
    text = _classification_text(event_type, payload, source, target)

    priority = (
        "permission_failure",
        "timeout_failure",
        "context_failure",
        "mcp_failure",
        "model_failure",
        "tool_failure",
        "handoff_failure",
        "resource_failure",
    )
    matched: list[str] = []
    for category in priority:
        signals = FAILURE_TAXONOMY[category].signals
        if any(signal in text for signal in signals):
            matched.append(category)

    node_types = {source.get("node_type"), target.get("node_type")}
    if "mcp_server" in node_types:
        matched.append("mcp_failure")
    if "model" in node_types:
        matched.append("model_failure")
    if "tool" in node_types:
        matched.append("tool_failure")
    if node_types & RESOURCE_NODE_TYPES:
        matched.append("resource_failure")

    category = next((item for item in matched if item in FAILURE_TAXONOMY), None)
    if not category:
        if event_type.startswith(("llm.", "model.")):
            category = "model_failure"
        elif event_type.startswith("tool."):
            category = "tool_failure"
        elif event_type.startswith("mcp."):
            category = "mcp_failure"
        elif "handoff" in event_type or "message" in event_type:
            category = "handoff_failure"
        else:
            category = "resource_failure"

    confidence = 0.9 if matched else 0.65
    return {
        "category": category,
        "display_name": FAILURE_TAXONOMY[category].display_name,
        "description": FAILURE_TAXONOMY[category].description,
        "confidence": confidence,
        "signals": sorted(set(matched or [category])),
    }


def _classification_text(
    event_type: str,
    payload: dict[str, Any],
    source: dict[str, Any],
    target: dict[str, Any],
) -> str:
    fields = [
        event_type,
        str(payload.get("error", "")),
        str(payload.get("error_type", "")),
        str(payload.get("status", "")),
        str(payload.get("tool", "")),
        str(payload.get("provider", "")),
        str(payload.get("model", "")),
        str(source.get("node_type", "")),
        str(source.get("name", "")),
        str(target.get("node_type", "")),
        str(target.get("name", "")),
    ]
    return " ".join(fields).lower()
