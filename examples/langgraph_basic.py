from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:
    raise SystemExit(
        "LangGraph is not installed. Install it with `pip install langgraph` to run this example."
    ) from exc

from src.sdk import OpenMeshClient
from src.sdk.integrations.langgraph import OpenMeshLangGraph


class ResearchState(TypedDict):
    topic: str
    notes: list[str]


mesh = OpenMeshLangGraph(
    client=OpenMeshClient(),
    graph_name="LangGraph Basic",
)


def node_a(state: ResearchState) -> ResearchState:
    return {**state, "notes": [*state["notes"], f"collected context for {state['topic']}"]}


def node_b(state: ResearchState) -> ResearchState:
    return {**state, "notes": [*state["notes"], "ranked candidate sources"]}


def node_c(state: ResearchState) -> ResearchState:
    return {**state, "notes": [*state["notes"], "prepared final summary"]}


def build_graph():
    workflow = StateGraph(ResearchState)
    workflow.add_node("Node A", mesh.node("Node A", node_a))
    workflow.add_node("Node B", mesh.node("Node B", node_b))
    workflow.add_node("Node C", mesh.node("Node C", node_c))
    workflow.add_edge(START, "Node A")
    mesh.add_edge(workflow, "Node A", "Node B")
    mesh.add_edge(workflow, "Node B", "Node C")
    workflow.add_edge("Node C", END)
    return workflow.compile()


def main() -> None:
    graph = build_graph()
    try:
        result = graph.invoke({"topic": "agent observability", "notes": []})
    except Exception as exc:
        mesh.fail(exc)
        raise
    mesh.complete(result)
    print("LangGraph result:")
    for note in result["notes"]:
        print(f"- {note}")


if __name__ == "__main__":
    main()
