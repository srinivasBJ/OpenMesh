from __future__ import annotations

from typing import Any

from showcase_common import showcase_client, trace_id

from src.sdk.integrations.langgraph import OpenMeshLangGraph  # noqa: E402


def classify_topic(state: dict[str, Any]) -> dict[str, Any]:
    return {**state, "route": "research_and_risk_review"}


def deep_research(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "findings": [
            "agent observability needs graph provenance",
            "terminal workflows need inspectable traces",
        ],
    }


def risk_review(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "risks": ["missing relationships", "unexplained tool usage"],
    }


def rank_sources_first_attempt(state: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("source ranking model timed out")


def rank_sources_retry(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "ranked_sources": [
            "OpenTelemetry traces",
            "Neo4j graph provenance",
            "terminal observability tools",
        ],
    }


def synthesize_answer(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "answer": "Use OpenMesh to connect agent actions, traces, and graph relationships.",
    }


def main() -> None:
    trace = trace_id("langgraph_showcase")
    mesh = OpenMeshLangGraph(
        client=showcase_client("langgraph"),
        graph_name="LangGraph Showcase Branching Workflow",
        trace_id=trace,
    )

    classify = mesh.node("Classify Topic", classify_topic)
    research = mesh.node("Deep Research", deep_research)
    review = mesh.node("Risk Review", risk_review)
    rank_first = mesh.node("Rank Sources", rank_sources_first_attempt)
    rank_retry = mesh.node("Rank Sources Retry", rank_sources_retry)
    synthesize = mesh.node("Synthesize Answer", synthesize_answer)

    state: dict[str, Any] = {"topic": "OpenMesh graph observability"}
    state = classify(state)

    mesh.transition("Classify Topic", "Deep Research")
    research_state = research(state)
    mesh.transition("Classify Topic", "Risk Review")
    review_state = review(state)
    state = {**research_state, **review_state}

    try:
        mesh.transition("Deep Research", "Rank Sources")
        state = rank_first(state)
    except RuntimeError as exc:
        print(f"LangGraph retry triggered: {exc}")
        mesh.transition("Rank Sources", "Rank Sources Retry")
        state = rank_retry(state)

    mesh.transition("Rank Sources Retry", "Synthesize Answer")
    result = synthesize(state)
    mesh.complete(result)

    print("OpenMesh showcase completed: LangGraph branching workflow")
    print(f"trace_id={trace}")


if __name__ == "__main__":
    main()
