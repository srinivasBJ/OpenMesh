from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from openmesh import OpenMeshClient  # noqa: E402


def main() -> None:
    client = OpenMeshClient()
    agent = client.agent(id="research-agent", name="Research Agent", role="researcher")

    with agent.task("Research vector databases"):
        with agent.tool("web_search"):
            print("searching for vector database notes")

        agent.emit(
            "message.sent",
            {
                "message": "Research summary prepared",
                "artifact": "vector-database-notes",
            },
        )

    print("OpenMesh Python SDK example completed")


if __name__ == "__main__":
    main()
