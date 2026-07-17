"""
Agent runner control, real-agent registration, and live status.

POST /api/agents/start            → start the simulation tick loop (legacy alias)
POST /api/agents/stop             → stop the tick loop
POST /api/agents/register         → a REAL agent (SDK/MCP/collector) reports itself
POST /api/agents/{id}/heartbeat   → keep a real agent alive; stale → disconnected
GET  /api/status/live             → backend/provider/agents/events-per-second

Identity principle: a provider API key never creates agents. `agents.active`
counts only simulation agents currently driven by a session plus real agents
with a fresh heartbeat.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import protect_write
from ...db.models import Agent, AgentRole, AgentStatus
from ...db.session import get_db
from ...providers.registry import configured_provider
from ...providers.runtime_settings import (
    effective_llm_mode,
    load_runtime_provider_config,
)
from ...services.agent_identity import (
    REAL_SOURCES,
    effective_agent_status,
    is_effectively_active,
)
from ...services.agent_runner import runner
from ...services.demo import demo_status
from ...services.openmesh_collector import collector
from ...shared.openmesh_events import agent_node, make_openmesh_event
from ...websocket.manager import manager

router = APIRouter()

NO_AGENTS_MESSAGE = (
    "No active agents detected. Connect Claude Code, SDK, MCP, or start a session."
)

# Real-agent statuses a heartbeat may report.
REPORTABLE_STATUSES = {
    "starting",
    "running",
    "idle",
    "completed",
    "failed",
    "terminated",
}


class RegisterAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source: str = Field(max_length=30)
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    model: Optional[str] = Field(default=None, max_length=200)
    role: str = Field(default="engineer", max_length=30)
    bio: Optional[str] = Field(default=None, max_length=2000)


class HeartbeatRequest(BaseModel):
    status: Optional[str] = Field(default=None, max_length=30)


@router.post("/agents/start")
async def start_agents(_: None = Depends(protect_write)):
    return await runner.start()


@router.post("/agents/stop")
async def stop_agents(_: None = Depends(protect_write)):
    return await runner.stop()


@router.post("/agents/register")
async def register_agent(
    req: RegisterAgentRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    """A real agent reports itself (SDK, MCP connection, or collector)."""
    source = req.source.strip().lower()
    if source not in REAL_SOURCES:
        raise HTTPException(
            400,
            f"Invalid source '{req.source}'. Real sources: {', '.join(sorted(REAL_SOURCES))}",
        )
    role = req.role if req.role in [r.value for r in AgentRole] else "engineer"
    existing = await db.execute(select(Agent).where(Agent.name == req.name))
    agent = existing.scalar_one_or_none()
    created = agent is None
    if agent is None:
        agent = Agent(
            name=req.name,
            role=role,
            source=source,
            status="starting",
            workspace_id=req.workspace_id,
            project_id=req.project_id,
            bio=req.bio or f"Real {source} agent observed by OpenMesh.",
            personality={},
            skills=[],
            goals=[],
            avatar_seed=req.name.lower().replace(" ", "_"),
            memory=[],
        )
        db.add(agent)
    else:
        agent.source = source
        agent.status = "running"
        if req.workspace_id:
            agent.workspace_id = req.workspace_id
        if req.project_id:
            agent.project_id = req.project_id
    agent.last_active_at = datetime.utcnow()
    await db.commit()
    await db.refresh(agent)

    await collector.accept(
        db,
        make_openmesh_event(
            "agent.started" if created else "agent.heartbeat",
            agent_node(agent.id, agent.name, role),
            {
                "agent_source": source,
                "workspace_id": agent.workspace_id,
                "project_id": agent.project_id,
                "model": req.model,
            },
        ),
    )
    return {
        "id": agent.id,
        "name": agent.name,
        "source": source,
        "status": effective_agent_status(agent),
        "workspace_id": agent.workspace_id,
        "project_id": agent.project_id,
        "created": created,
        "heartbeat_timeout_seconds": 90,
    }


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    req: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(protect_write),
):
    agent = (
        await db.execute(select(Agent).where(Agent.id == agent_id))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(404, "Agent not found. Register it first.")
    if agent.source == "simulation":
        raise HTTPException(400, "Simulation agents do not send heartbeats")
    if req.status:
        status = req.status.strip().lower()
        if status not in REPORTABLE_STATUSES:
            raise HTTPException(
                400,
                f"Invalid status '{req.status}'. Allowed: {', '.join(sorted(REPORTABLE_STATUSES))}",
            )
        agent.status = status
    elif agent.status == AgentStatus.STARTING:
        agent.status = "running"
    agent.last_active_at = datetime.utcnow()
    await db.commit()
    return {"id": agent.id, "status": effective_agent_status(agent)}


@router.get("/status/live")
async def live_status(db: AsyncSession = Depends(get_db)):
    stored = load_runtime_provider_config()
    provider = configured_provider(stored.provider if stored else None)
    agents = (await db.execute(select(Agent))).scalars().all()
    now = datetime.utcnow()
    active_agents = sum(1 for agent in agents if is_effectively_active(agent, now))
    real_agents = sum(1 for agent in agents if agent.source in REAL_SOURCES)
    return {
        "backend": "connected",
        "provider": {
            "configured": provider is not None,
            "provider": provider.provider_id if provider else None,
            "name": provider.display_name if provider else None,
            "model": provider.model if provider else None,
            "mode": effective_llm_mode(),
        },
        "agents": {
            "active": active_agents,
            "real": real_agents,
            "total": len(agents),
            "running": runner.running,
            "message": None if active_agents else NO_AGENTS_MESSAGE,
        },
        "runner": runner.status(),
        "demo": await demo_status(),
        "events_per_second": manager.events_per_second(),
        "websocket_clients": len(manager.active_connections),
    }
