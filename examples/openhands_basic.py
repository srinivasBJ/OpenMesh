from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from src.sdk import OpenMeshClient  # noqa: E402
from src.sdk.integrations.openhands import OpenMeshOpenHands  # noqa: E402


def main() -> None:
    mesh = OpenMeshOpenHands(
        client=OpenMeshClient(),
        workflow_name="OpenHands Coding Session",
        source="examples/openhands_basic.py",
    )
    agent = mesh.coding_agent()

    with mesh.workflow():
        with mesh.observe_action(
            "Inspect failing tests",
            agent=agent,
            description="Inspect test output and locate the failure.",
        ) as task:
            with task.tool("terminal"):
                mesh.observe_command("pytest backend/tests", agent=agent, exit_code=0)
        mesh.observe_file("backend/src/services/example.py", agent=agent)

    print("OpenHands example completed.")


if __name__ == "__main__":
    main()
