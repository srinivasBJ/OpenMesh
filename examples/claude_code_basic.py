from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from src.sdk import OpenMeshClient  # noqa: E402
from src.sdk.integrations.claude_code import OpenMeshClaudeCode  # noqa: E402


def main() -> None:
    mesh = OpenMeshClaudeCode(
        client=OpenMeshClient(),
        workflow_name="Claude Code Refactor Session",
        source="examples/claude_code_basic.py",
    )
    agent = mesh.coding_agent()

    mesh.observe_hook_event(
        {
            "prompt": "Refactor OpenMesh graph inspection output.",
            "tool_name": "Edit",
            "command": "python -m unittest discover -s backend/tests",
            "file_path": "backend/src/cli/openmesh.py",
            "operation": "modified",
            "exit_code": 0,
        },
        agent=agent,
    )

    print("Claude Code example completed.")


if __name__ == "__main__":
    main()
