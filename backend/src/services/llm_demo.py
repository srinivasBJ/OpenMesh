from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.openmesh_sessions import complete_openmesh_session, create_openmesh_session
from ..providers import LLMProvider, ProviderConfigurationError, configured_provider
from ..shared.openmesh_events import make_openmesh_event
from .openmesh_collector import collector


DEMO_AGENT = {
    "node_id": "agent:llm-research",
    "node_type": "agent",
    "name": "LLM Research Agent",
    "runtime": "openmesh.run-demo",
    "metadata": {"role": "researcher", "source": "openmesh run-demo research"},
}

RESEARCH_TOOL = {
    "node_id": "tool:research_brief_builder",
    "node_type": "tool",
    "name": "research_brief_builder",
    "runtime": "openmesh.local",
    "metadata": {"capabilities": ["summarize", "extract_findings"]},
}


async def run_research_demo(
    db: AsyncSession,
    *,
    query: str,
    provider_id: str = "auto",
    model: str | None = None,
    max_tokens: int = 500,
    provider: LLMProvider | None = None,
    broadcast: bool = False,
) -> dict[str, Any]:
    selected_provider = provider or configured_provider(provider_id)
    if not selected_provider:
        raise ProviderConfigurationError(
            "No configured LLM provider found. Set OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY, OPENROUTER_API_KEY, or start Ollama, "
            "LM Studio, or vLLM locally."
        )
    if model:
        selected_provider.model = model.strip()

    session_id = f"sess_{uuid4().hex}"
    trace_id = f"trace_{uuid4().hex}"
    trace_span_id = f"span_{uuid4().hex}"
    llm_span_id = f"span_{uuid4().hex}"
    tool_span_id = f"span_{uuid4().hex}"
    command = (
        f"openmesh run-demo research --provider {selected_provider.provider_id} "
        f"--model {selected_provider.model}"
    )
    started_at = datetime.utcnow()
    model_node = _model_node(selected_provider)
    events: list[dict[str, Any]] = []

    await create_openmesh_session(
        db, session_id=session_id, command=command, started_at=started_at
    )

    trace_started = await _emit(
        db,
        "trace.started",
        session_id=session_id,
        trace_id=trace_id,
        span_id=trace_span_id,
        source=DEMO_AGENT,
        payload={
            "query": query,
            "workflow": "research",
            "provider": selected_provider.provider_id,
            "model": selected_provider.model,
        },
        broadcast=broadcast,
    )
    events.append(trace_started)
    root_event_id = trace_started["event_id"]
    parent_event_id = root_event_id

    if selected_provider.is_local:
        loaded_event = await _emit(
            db,
            "model.loaded",
            session_id=session_id,
            trace_id=trace_id,
            span_id=trace_span_id,
            parent_event_id=root_event_id,
            root_event_id=root_event_id,
            source=model_node,
            target=_provider_node(selected_provider),
            payload={
                "provider": selected_provider.provider_id,
                "model": selected_provider.model,
                "endpoint": selected_provider.endpoint,
                "local": True,
            },
            broadcast=broadcast,
        )
        events.append(loaded_event)
        parent_event_id = loaded_event["event_id"]

    request_event = await _emit(
        db,
        "llm.request",
        session_id=session_id,
        trace_id=trace_id,
        span_id=llm_span_id,
        parent_span_id=trace_span_id,
        parent_event_id=parent_event_id,
        root_event_id=root_event_id,
        source=DEMO_AGENT,
        target=model_node,
        payload={
            "provider": selected_provider.provider_id,
            "model": selected_provider.model,
            "query": query,
            "prompt": _research_prompt(query),
            "local": selected_provider.is_local,
        },
        metrics={"max_tokens": max_tokens, "temperature": 0.2},
        broadcast=broadcast,
    )
    events.append(request_event)

    status = "completed"
    answer = ""
    usage: dict[str, Any] = {}
    latency_ms: int | None = None
    ended_at = started_at
    try:
        response = await selected_provider.complete(
            system=_research_system_prompt(),
            prompt=_research_prompt(query),
            max_tokens=max_tokens,
            temperature=0.2,
        )
        answer = response.content
        usage = response.usage
        latency_ms = response.latency_ms
        response_event = await _emit(
            db,
            "llm.response",
            session_id=session_id,
            trace_id=trace_id,
            span_id=llm_span_id,
            parent_span_id=trace_span_id,
            parent_event_id=request_event["event_id"],
            root_event_id=root_event_id,
            source=DEMO_AGENT,
            target=model_node,
            payload={
                "provider": response.provider,
                "model": response.model,
                "response": answer,
                "local": selected_provider.is_local,
            },
            metrics={
                "usage": usage,
                "latency_ms": latency_ms,
                "tokens_per_second": response.tokens_per_second,
            },
            broadcast=broadcast,
        )
        events.append(response_event)

        tool_started = await _emit(
            db,
            "tool.call.started",
            session_id=session_id,
            trace_id=trace_id,
            span_id=tool_span_id,
            parent_span_id=trace_span_id,
            parent_event_id=response_event["event_id"],
            root_event_id=root_event_id,
            source=DEMO_AGENT,
            target=RESEARCH_TOOL,
            payload={"tool": "research_brief_builder", "input": answer},
            broadcast=broadcast,
        )
        events.append(tool_started)
        brief = _build_research_brief(query, answer)
        tool_completed = await _emit(
            db,
            "tool.call.completed",
            session_id=session_id,
            trace_id=trace_id,
            span_id=tool_span_id,
            parent_span_id=trace_span_id,
            parent_event_id=tool_started["event_id"],
            root_event_id=root_event_id,
            source=DEMO_AGENT,
            target=RESEARCH_TOOL,
            payload={"tool": "research_brief_builder", "result": brief},
            broadcast=broadcast,
        )
        events.append(tool_completed)
    except Exception as exc:
        status = "failed"
        response_event = await _emit(
            db,
            "llm.response",
            session_id=session_id,
            trace_id=trace_id,
            span_id=llm_span_id,
            parent_span_id=trace_span_id,
            parent_event_id=request_event["event_id"],
            root_event_id=root_event_id,
            source=DEMO_AGENT,
            target=model_node,
            payload={
                "provider": selected_provider.provider_id,
                "model": selected_provider.model,
                "error": str(exc),
                "local": selected_provider.is_local,
            },
            severity="error",
            broadcast=broadcast,
        )
        events.append(response_event)
    finally:
        ended_at = datetime.utcnow()
        completed = await _emit(
            db,
            "trace.completed",
            session_id=session_id,
            trace_id=trace_id,
            span_id=trace_span_id,
            parent_event_id=events[-1]["event_id"],
            root_event_id=root_event_id,
            source=DEMO_AGENT,
            payload={
                "query": query,
                "provider": selected_provider.provider_id,
                "model": selected_provider.model,
                "status": status,
                "event_count": len(events) + 1,
            },
            severity="error" if status == "failed" else "info",
            broadcast=broadcast,
        )
        events.append(completed)
        await complete_openmesh_session(
            db,
            session_id=session_id,
            ended_at=ended_at,
            status=status,
            exit_code=0 if status == "completed" else 1,
        )

    if status == "failed":
        error = events[-2].get("payload", {}).get("error", "LLM provider call failed")
        raise RuntimeError(error)

    return {
        "session_id": session_id,
        "trace_id": trace_id,
        "provider": selected_provider.provider_id,
        "model": selected_provider.model,
        "query": query,
        "response": answer,
        "usage": usage,
        "latency_ms": latency_ms,
        "tokens_per_second": response.tokens_per_second if "response" in locals() else None,
        "events": events,
        "started_at": started_at.isoformat() + "Z",
        "ended_at": ended_at.isoformat() + "Z",
    }


async def _emit(
    db: AsyncSession,
    event_type: str,
    *,
    session_id: str,
    trace_id: str,
    span_id: str,
    source: dict[str, Any],
    payload: dict[str, Any],
    target: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    severity: str = "info",
    parent_span_id: str | None = None,
    parent_event_id: str | None = None,
    root_event_id: str | None = None,
    broadcast: bool = False,
) -> dict[str, Any]:
    event = make_openmesh_event(
        event_type,
        source,
        payload,
        target=target,
        metrics=metrics,
        severity=severity,  # type: ignore[arg-type]
        session_id=session_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        parent_event_id=parent_event_id,
        root_event_id=root_event_id,
    )
    await collector.accept(db, event, broadcast=broadcast)
    return event


def _model_node(provider: LLMProvider) -> dict[str, Any]:
    return {
        "node_id": f"model:{provider.provider_id}:{_stable_id(provider.model)}",
        "node_type": "model",
        "name": provider.model,
        "runtime": provider.provider_id,
        "metadata": {
            "provider": provider.provider_id,
            "endpoint": provider.endpoint,
            "local": provider.is_local,
        },
    }


def _provider_node(provider: LLMProvider) -> dict[str, Any]:
    return {
        "node_id": f"provider:{provider.provider_id}",
        "node_type": "service",
        "name": provider.display_name,
        "runtime": provider.provider_id,
        "metadata": {
            "provider": provider.provider_id,
            "endpoint": provider.endpoint,
            "source": "local-llm" if provider.is_local else "llm-provider",
        },
    }


def _research_system_prompt() -> str:
    return (
        "You are an OpenMesh research agent. Produce concise, practical research "
        "notes for an operator inspecting an AI agent ecosystem."
    )


def _research_prompt(query: str) -> str:
    return (
        f"Research question: {query}\n\n"
        "Return three findings, one risk, and one next action. Keep it concise."
    )


def _build_research_brief(query: str, answer: str) -> dict[str, Any]:
    lines = [line.strip("-• 	") for line in answer.splitlines() if line.strip()]
    findings = lines[:3] if lines else [answer[:240]]
    return {
        "title": f"Research brief: {query[:72]}",
        "findings": findings,
        "source": "llm.response",
    }


def _stable_id(value: str) -> str:
    return (
        "".join(character.lower() if character.isalnum() else "-" for character in value)
        .strip("-")
        .replace("--", "-")
        or "model"
    )


def summary_for_cli(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result[key]
        for key in ("session_id", "trace_id", "provider", "model", "latency_ms")
        if key in result
    } | {"response_preview": result.get("response", "")[:500]}


def event_types_for_cli(result: dict[str, Any]) -> list[str]:
    return [event["event_type"] for event in result.get("events", [])]


def provider_result_asdict(result: dict[str, Any]) -> dict[str, Any]:
    serializable = dict(result)
    serializable["events"] = [dict(event) for event in result.get("events", [])]
    return serializable


def provider_status_asdict(status: Any) -> dict[str, Any]:
    return asdict(status)
