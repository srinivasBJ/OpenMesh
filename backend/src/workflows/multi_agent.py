from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import OpenMeshEventRecord
from ..db.openmesh_events import list_openmesh_events
from ..db.openmesh_sessions import complete_openmesh_session, create_openmesh_session
from ..services.openmesh_collector import collector
from ..services.openmesh_queries import list_workflows
from ..services.workflow_registry import workflow_node
from ..shared.openmesh_events import OpenMeshNode, make_openmesh_event


MULTI_AGENT_AGENT_SPECS = (
    ("research-agent", "Research Agent", "researcher"),
    ("planner-agent", "Planner Agent", "planner"),
    ("coder-agent", "Coder Agent", "coder"),
    ("reviewer-agent", "Reviewer Agent", "reviewer"),
    ("writer-agent", "Writer Agent", "writer"),
)

MESSAGE_TEMPLATES = (
    "Need current evidence for the next step.",
    "Confirmed scope and constraints.",
    "Passing context with trace notes.",
    "Tool results are attached to the workflow state.",
    "Please verify the handoff output.",
    "Acknowledged, continuing from the prior span.",
)

WORKFLOW_OPERATOR: OpenMeshNode = {
    "node_id": "agent:openmesh-multi-agent-operator",
    "node_type": "agent",
    "name": "OpenMesh Multi-Agent Operator",
    "runtime": "openmesh.run-demo",
    "metadata": {"role": "operator", "source": "openmesh run-demo multi-agent"},
}


async def run_multi_agent_demo(
    db: AsyncSession,
    *,
    agents: int = 5,
    handoffs: int = 24,
    messages: int = 60,
    broadcast: bool = False,
) -> dict[str, Any]:
    agent_count = min(max(agents, 4), len(MULTI_AGENT_AGENT_SPECS))
    handoff_count = max(handoffs, 20)
    message_count = max(messages, 50)
    selected_agents = [
        _agent_node(*spec) for spec in MULTI_AGENT_AGENT_SPECS[:agent_count]
    ]
    workflow = workflow_node(
        {
            "workflow": "Multi-Agent Handoff Demo",
            "framework": "OpenMesh",
            "source": "openmesh run-demo multi-agent",
            "metadata": {
                "workflow_type": "multi_agent_handoff",
                "agents": [agent["name"] for agent in selected_agents],
                "handoff_count": handoff_count,
                "message_count": message_count,
            },
        }
    )
    session_id = f"sess_multi_agent_{uuid4().hex}"
    trace_id = f"trace_multi_agent_{uuid4().hex}"
    workflow_span_id = f"span_{uuid4().hex}"
    command = (
        f"openmesh run-demo multi-agent --agents {agent_count} "
        f"--handoffs {handoff_count} --messages {message_count}"
    )
    started_at = datetime.utcnow()
    events: list[dict[str, Any]] = []

    await create_openmesh_session(
        db, session_id=session_id, command=command, started_at=started_at
    )

    async def emit(
        event_type: str,
        source: OpenMeshNode,
        payload: dict[str, Any],
        *,
        target: OpenMeshNode | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        parent_event_id: str | None = None,
        root_event_id: str | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = make_openmesh_event(
            event_type,
            source,
            payload,
            target=target,
            session_id=session_id,
            trace_id=trace_id,
            span_id=span_id or workflow_span_id,
            parent_span_id=parent_span_id,
            parent_event_id=parent_event_id,
            root_event_id=root_event_id,
            metrics=metrics,
        )
        await collector.accept(db, event, broadcast=broadcast)
        events.append(event)
        return event

    workflow_started = await emit(
        "workflow.started",
        WORKFLOW_OPERATOR,
        {
            "workflow_id": workflow["node_id"],
            "workflow": workflow["name"],
            "status": "started",
        },
        target=workflow,
        span_id=workflow_span_id,
    )
    root_event_id = workflow_started["event_id"]

    for index, agent in enumerate(selected_agents, start=1):
        await emit(
            "workflow.started",
            workflow,
            {
                "workflow_id": workflow["node_id"],
                "agent_id": agent["node_id"],
                "role": (agent.get("metadata") or {}).get("role"),
                "sequence": index,
            },
            target=agent,
            span_id=workflow_span_id,
            parent_event_id=root_event_id,
            root_event_id=root_event_id,
        )

    latest_handoff_event_id = root_event_id
    for index in range(handoff_count):
        source = selected_agents[index % agent_count]
        target = selected_agents[(index + 1) % agent_count]
        is_review = source["name"] == "Reviewer Agent" and target["name"] in {
            "Coder Agent",
            "Writer Agent",
        }
        span_id = f"span_{uuid4().hex}"
        handoff_id = f"handoff-{index + 1:02d}"
        latency_ms = 180 + (index % 7) * 45
        started = await emit(
            "agent.handoff.started",
            source,
            {
                "workflow_id": workflow["node_id"],
                "handoff_id": handoff_id,
                "step": index + 1,
                "task": _handoff_task(source, target, index),
                "status": "started",
            },
            target=target,
            span_id=span_id,
            parent_span_id=workflow_span_id,
            parent_event_id=latest_handoff_event_id,
            root_event_id=root_event_id,
            metrics={"sequence": index + 1},
        )
        latest_handoff_event_id = started["event_id"]
        completed_payload = {
            "workflow_id": workflow["node_id"],
            "handoff_id": handoff_id,
            "step": index + 1,
            "status": "completed",
        }
        if is_review:
            completed_payload["relationship_type"] = "reviews"
        completed = await emit(
            "agent.handoff.completed",
            source,
            completed_payload,
            target=target,
            span_id=span_id,
            parent_span_id=workflow_span_id,
            parent_event_id=started["event_id"],
            root_event_id=root_event_id,
            metrics={"latency_ms": latency_ms},
        )
        latest_handoff_event_id = completed["event_id"]

    for index in range(message_count):
        source = selected_agents[index % agent_count]
        target = selected_agents[(index + 2) % agent_count]
        span_id = f"span_{uuid4().hex}"
        message_id = f"message-{index + 1:03d}"
        sent = await emit(
            "agent.message.sent",
            source,
            {
                "workflow_id": workflow["node_id"],
                "message_id": message_id,
                "content": MESSAGE_TEMPLATES[index % len(MESSAGE_TEMPLATES)],
                "sequence": index + 1,
            },
            target=target,
            span_id=span_id,
            parent_span_id=workflow_span_id,
            parent_event_id=latest_handoff_event_id,
            root_event_id=root_event_id,
        )
        await emit(
            "agent.message.received",
            target,
            {
                "workflow_id": workflow["node_id"],
                "message_id": message_id,
                "from_agent": source["name"],
                "status": "received",
                "sequence": index + 1,
            },
            target=source,
            span_id=span_id,
            parent_span_id=workflow_span_id,
            parent_event_id=sent["event_id"],
            root_event_id=root_event_id,
        )

    workflow_completed = await emit(
        "workflow.completed",
        workflow,
        {
            "workflow_id": workflow["node_id"],
            "workflow": workflow["name"],
            "status": "completed",
            "agents": [agent["name"] for agent in selected_agents],
            "handoffs": handoff_count,
            "messages": message_count,
        },
        target=selected_agents[-1],
        span_id=workflow_span_id,
        parent_event_id=latest_handoff_event_id,
        root_event_id=root_event_id,
    )
    await complete_openmesh_session(
        db,
        session_id=session_id,
        ended_at=datetime.utcnow(),
        status="completed",
        exit_code=0,
    )

    return {
        "workflow_id": workflow["node_id"],
        "workflow": workflow["name"],
        "trace_id": trace_id,
        "session_id": session_id,
        "agents": [agent["name"] for agent in selected_agents],
        "handoffs": handoff_count,
        "messages": message_count,
        "events": events,
        "completed_event_id": workflow_completed["event_id"],
    }


async def get_multi_agent_workflow_metrics(
    db: AsyncSession, limit: int = 5000
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    workflows = await list_workflows(db, limit=limit)
    return build_multi_agent_workflow_metrics(records, workflows)


def build_multi_agent_workflow_metrics(
    records: list[OpenMeshEventRecord],
    workflows: list[dict[str, Any]],
) -> dict[str, Any]:
    active = sum(1 for workflow in workflows if workflow.get("status") == "active")
    completed = sum(
        1 for workflow in workflows if workflow.get("status") == "completed"
    )
    handoff_started = [
        record for record in records if record.event_type == "agent.handoff.started"
    ]
    handoff_completed = [
        record for record in records if record.event_type == "agent.handoff.completed"
    ]
    agent_activity: Counter[str] = Counter()
    latencies = []
    workflow_handoffs: dict[str, int] = defaultdict(int)
    for record in records:
        payload = record.payload_json or {}
        if record.event_type.startswith("agent."):
            for node in (record.source_json, record.target_json):
                if node and node.get("node_type") == "agent":
                    agent_activity[node.get("name") or node.get("node_id")] += 1
        if record.event_type == "agent.handoff.started":
            workflow_id = str(payload.get("workflow_id") or record.trace_id)
            workflow_handoffs[workflow_id] += 1
        if record.event_type == "agent.handoff.completed":
            latency = (record.metrics_json or {}).get("latency_ms")
            if isinstance(latency, (int, float)):
                latencies.append(float(latency))

    busiest_agent = agent_activity.most_common(1)[0] if agent_activity else None
    workflow_count = len(workflow_handoffs) or max(len(workflows), 1)
    average_handoffs = (
        round(len(handoff_started) / workflow_count, 2) if workflow_count else 0
    )
    return {
        "active_workflows": active,
        "completed_workflows": completed,
        "handoff_events": len(handoff_started),
        "completed_handoffs": len(handoff_completed),
        "average_handoffs": average_handoffs,
        "busiest_agent": {
            "agent": busiest_agent[0],
            "events": busiest_agent[1],
        }
        if busiest_agent
        else None,
        "handoff_latency_ms": round(sum(latencies) / len(latencies), 2)
        if latencies
        else None,
    }


def _agent_node(agent_id: str, name: str, role: str) -> OpenMeshNode:
    return {
        "node_id": f"agent:{agent_id}",
        "node_type": "agent",
        "name": name,
        "runtime": "openmesh.multi-agent",
        "metadata": {"role": role, "framework": "OpenMesh"},
    }


def _handoff_task(source: OpenMeshNode, target: OpenMeshNode, index: int) -> str:
    action = (
        "research context"
        if index % 4 == 0
        else "implementation notes"
        if index % 4 == 1
        else "review packet"
        if index % 4 == 2
        else "final synthesis"
    )
    return f"{source['name']} hands off {action} to {target['name']}"
