from __future__ import annotations

from showcase_common import showcase_client, tool_node, trace_id, workflow_node


def main() -> None:
    client = showcase_client("research")
    trace = trace_id("multi_agent_research")
    workflow = workflow_node("research-brief", "Multi-Agent Research Brief")

    research = client.agent(
        id="showcase.research-agent",
        name="Research Agent",
        role="researcher",
        metadata={"team": "showcase", "domain": "market intelligence"},
    )
    planner = client.agent(
        id="showcase.planner-agent",
        name="Planner Agent",
        role="planner",
        metadata={"team": "showcase", "domain": "workflow planning"},
    )
    writer = client.agent(
        id="showcase.writer-agent",
        name="Writer Agent",
        role="writer",
        metadata={"team": "showcase", "domain": "brief synthesis"},
    )

    planner.emit(
        "workflow.started",
        {
            "workflow": "Multi-Agent Research Brief",
            "framework": "openmesh.showcase",
            "source": "examples/showcase_multi_agent_research.py",
        },
        target=workflow,
        trace_id=trace,
    )

    with planner.task("Plan research brief", trace_id=trace):
        planner.emit(
            "delegation.created",
            {
                "task": "Collect source material on agent observability",
                "priority": "high",
            },
            target=research.node,
        )

    with research.task("Collect source material", trace_id=trace):
        with research.tool("web_search"):
            print("Research Agent searches framework observability patterns")
        research.emit(
            "message.sent",
            {
                "message": "Found relevant examples from tracing, graph databases, and terminal observability.",
                "artifact": "source-notes",
            },
            target=planner.node,
        )

    with planner.task("Refine outline", trace_id=trace):
        with planner.tool("document_store"):
            print("Planner Agent stores outline and source notes")
        planner.emit(
            "delegation.created",
            {
                "task": "Draft executive brief from approved outline",
                "priority": "medium",
            },
            target=writer.node,
        )

    with writer.task("Draft research brief", trace_id=trace):
        with writer.tool("document_store"):
            print("Writer Agent retrieves notes and outline")
        writer.emit(
            "message.sent",
            {
                "message": "Draft complete with recommendations and source citations.",
                "artifact": "agent-observability-brief.md",
            },
            target=planner.node,
        )

    planner.emit(
        "tool.call.completed",
        {
            "tool": "document_store",
            "artifact": "agent-observability-brief.md",
            "status": "published",
        },
        target=tool_node("document_store", capabilities=["read", "write", "version"]),
        trace_id=trace,
    )
    planner.emit(
        "workflow.completed",
        {
            "workflow": "Multi-Agent Research Brief",
            "status": "completed",
            "outputs": ["source-notes", "agent-observability-brief.md"],
        },
        target=workflow,
        trace_id=trace,
    )

    print("OpenMesh showcase completed: multi-agent research workflow")
    print(f"trace_id={trace}")


if __name__ == "__main__":
    main()
