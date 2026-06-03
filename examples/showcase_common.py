from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
backend_root = REPO_ROOT / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from openmesh import OpenMeshClient  # noqa: E402


def showcase_client(name: str) -> OpenMeshClient:
    return OpenMeshClient(session_id=f"sess_showcase_{name}_{uuid4().hex[:8]}")


def trace_id(name: str) -> str:
    return f"trace_showcase_{name}_{uuid4().hex[:8]}"


def workflow_node(workflow_id: str, name: str, framework: str = "openmesh.showcase"):
    return {
        "node_id": f"workflow:showcase:{workflow_id}",
        "node_type": "workflow",
        "name": name,
        "runtime": framework,
        "metadata": {
            "framework": framework,
            "source": "openmesh.showcase",
            "version": "0.2",
        },
    }


def service_node(node_id: str, name: str, runtime: str = "openmesh.showcase"):
    return {
        "node_id": node_id,
        "node_type": "service",
        "name": name,
        "runtime": runtime,
        "metadata": {"source": "openmesh.showcase"},
    }


def tool_node(name: str, *, capabilities: list[str] | None = None):
    return {
        "node_id": f"tool:{name}",
        "node_type": "tool",
        "name": name,
        "runtime": "openmesh.showcase",
        "metadata": {"capabilities": capabilities or []},
    }


def mcp_server_node(
    name: str,
    endpoint: str,
    *,
    transport: str = "stdio",
    version: str = "1.0.0",
    config_source: str | None = None,
    config_path: str | None = None,
):
    metadata = {
        "transport": transport,
        "endpoint": endpoint,
        "version": version,
    }
    if config_source:
        metadata["config_source"] = config_source
    if config_path:
        metadata["config_path"] = config_path
    stable = endpoint.replace("://", "-").replace("/", "-").replace(":", "-")
    return {
        "node_id": f"mcp:{stable}",
        "node_type": "mcp_server",
        "name": name,
        "runtime": "mcp",
        "metadata": metadata,
    }


def capability_node(server: str, capability: str, category: str, description: str):
    stable_server = _stable_id(server)
    stable_capability = _stable_id(capability)
    return {
        "node_id": f"capability:{stable_server}:{stable_capability}",
        "node_type": "capability",
        "name": capability,
        "runtime": "mcp",
        "metadata": {
            "server": server,
            "category": category,
            "description": description,
        },
    }


def config_source_node(source: str, config_path: str):
    return {
        "node_id": f"config:{_stable_id(source)}:{_stable_id(config_path)}",
        "node_type": "service",
        "name": source,
        "runtime": "mcp.config",
        "metadata": {
            "source": source,
            "config_path": config_path,
        },
    }


def _stable_id(value: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else "-" for character in value
    ).strip("-")
