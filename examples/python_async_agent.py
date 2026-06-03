from __future__ import annotations

import asyncio
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))

from openmesh import OpenMeshClient  # noqa: E402


async def main() -> None:
    client = OpenMeshClient()
    agent = client.agent(
        id="async-research-agent", name="Async Research Agent", role="researcher"
    )

    async with agent.task("Research async vector database workflows"):
        async with agent.tool("web_search"):
            await asyncio.sleep(0.01)
            print("async search completed")

        await agent.emit_async(
            "message.sent",
            {
                "message": "Async research summary prepared",
                "artifact": "async-vector-database-notes",
            },
        )

    print("OpenMesh async Python SDK example completed")


if __name__ == "__main__":
    asyncio.run(main())
