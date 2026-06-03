from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from src.sdk import OpenMeshClient  # noqa: E402
from src.sdk.integrations.opencode import OpenMeshOpenCode  # noqa: E402


def main() -> None:
    mesh = OpenMeshOpenCode(
        client=OpenMeshClient(),
        workflow_name="OpenCode Terminal Session",
        source="examples/opencode_basic.py",
    )
    agent = mesh.coding_agent()

    mesh.observe_event(
        {
            "prompt": "Add a benchmark smoke test.",
            "tool": "patch",
            "command": "ruff check .",
            "path": "backend/tests/test_openmesh_core.py",
            "operation": "modified",
            "exit_code": 0,
        },
        agent=agent,
    )

    print("OpenCode example completed.")


if __name__ == "__main__":
    main()
