from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from src.sdk import OpenMeshClient  # noqa: E402
from src.sdk.integrations.autogen import OpenMeshAutoGen  # noqa: E402


def main() -> None:
    mesh = OpenMeshAutoGen(
        client=OpenMeshClient(),
        workflow_name="AutoGen Research Chat",
        source="examples/autogen_basic.py",
    )
    user = mesh.user_proxy(id="autogen-user", name="User Proxy")
    researcher = mesh.assistant(id="autogen-researcher", name="Research Assistant")
    reviewer = mesh.assistant(id="autogen-reviewer", name="Review Assistant")

    with mesh.workflow():
        mesh.observe_message(
            user,
            researcher,
            content="Research terminal-first agent observability.",
        )
        with researcher.task("Research OpenMesh ecosystem mapping") as task:
            with task.tool("web_search"):
                pass
        mesh.observe_message(
            researcher,
            reviewer,
            content={"summary": "OpenMesh maps agents, tools, workflows, and traces."},
        )
        with reviewer.task("Review research summary"):
            pass

    print("AutoGen example completed.")


if __name__ == "__main__":
    main()
