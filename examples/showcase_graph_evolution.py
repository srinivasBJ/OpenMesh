from __future__ import annotations

from showcase_common import showcase_client, tool_node, trace_id, workflow_node


def file_node(path: str):
    return {
        "node_id": f"file:{path}",
        "node_type": "file",
        "name": path,
        "runtime": "openmesh.showcase",
        "metadata": {"path": path},
    }


def main() -> None:
    client = showcase_client("evolution")
    trace = trace_id("graph_evolution")
    workflow = workflow_node("evolution-demo", "Graph Evolution Demo")

    operator = client.agent(
        id="showcase.evolution-agent",
        name="Evolution Agent",
        role="operator",
        metadata={"team": "showcase", "domain": "graph evolution"},
    )
    reviewer = client.agent(
        id="showcase.reviewer-agent",
        name="Reviewer Agent",
        role="reviewer",
        metadata={"team": "showcase", "domain": "quality review"},
    )
    analyzer_tool = tool_node("relationship_analyzer", capabilities=["map", "inspect"])
    report_file = file_node("reports/openmesh-graph-evolution.md")

    operator.emit(
        "tool.connected",
        {
            "tool": "relationship_analyzer",
            "status": "attached",
            "reason": "needed to map new graph relationships",
        },
        target=analyzer_tool,
        trace_id=trace,
    )
    operator.emit(
        "workflow.started",
        {
            "workflow": "Graph Evolution Demo",
            "framework": "openmesh.showcase",
            "source": "examples/showcase_graph_evolution.py",
        },
        target=workflow,
        trace_id=trace,
    )

    with operator.task("Observe graph evolution", trace_id=trace):
        with operator.tool("relationship_analyzer"):
            print("Evolution Agent maps newly observed relationships")
        operator.emit(
            "file.modified",
            {
                "path": "reports/openmesh-graph-evolution.md",
                "change": "created graph evolution summary",
            },
            target=report_file,
        )
        operator.emit(
            "message.sent",
            {
                "message": "Graph evolution report is ready for review.",
                "artifact": "reports/openmesh-graph-evolution.md",
            },
            target=reviewer.node,
        )

    with reviewer.task("Review graph evolution report", trace_id=trace):
        reviewer.emit(
            "message.sent",
            {
                "message": "Report accepted. Relationships are explainable.",
                "status": "approved",
            },
            target=operator.node,
        )

    operator.emit(
        "workflow.completed",
        {
            "workflow": "Graph Evolution Demo",
            "status": "completed",
            "artifact": "reports/openmesh-graph-evolution.md",
        },
        target=workflow,
        trace_id=trace,
    )

    print("OpenMesh showcase completed: graph evolution")
    print(f"trace_id={trace}")


if __name__ == "__main__":
    main()
