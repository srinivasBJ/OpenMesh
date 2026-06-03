from __future__ import annotations

from showcase_graph_evolution import main as graph_evolution
from showcase_langgraph import main as langgraph
from showcase_mcp_ecosystem import main as mcp_ecosystem
from showcase_multi_agent_research import main as multi_agent_research


def main() -> None:
    print("Running OpenMesh showcase scenarios...")
    multi_agent_research()
    langgraph()
    mcp_ecosystem()
    graph_evolution()
    print("All OpenMesh showcase scenarios completed")


if __name__ == "__main__":
    main()
