from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from src.sdk import OpenMeshClient
from src.sdk.integrations.crewai import OpenMeshCrewAI


def main() -> None:
    mesh = OpenMeshCrewAI(
        client=OpenMeshClient(),
        crew_name="CrewAI Research Crew",
        source="examples/crewai_basic.py",
    )

    researcher = mesh.agent(
        id="crewai-researcher",
        name="Research Agent",
        role="Researcher",
    )
    writer = mesh.agent(
        id="crewai-writer",
        name="Writing Agent",
        role="Writer",
    )

    notes: list[str] = []
    with mesh.workflow():
        with researcher.task(
            "Research agent observability",
            description="Collect context about terminal-first AI agent observability.",
            expected_output="Research notes",
        ) as task:
            with task.tool("web_search"):
                notes.append("Collected current context for agent observability.")
            with task.tool("knowledge_base"):
                notes.append("Mapped OpenTelemetry-style concepts to agent workflows.")

        with writer.task(
            "Draft OpenMesh summary",
            description="Turn research notes into a short implementation summary.",
            expected_output="Summary",
        ):
            notes.append("Prepared summary for the CrewAI workflow.")

    print("CrewAI example completed:")
    for note in notes:
        print(f"- {note}")


if __name__ == "__main__":
    main()
