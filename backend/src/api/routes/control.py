"""
Agent runner control + live status for the dashboard top bar.

POST /api/agents/start → spawn default agent if needed, start the tick loop
POST /api/agents/stop  → stop the tick loop
GET  /api/status/live  → backend/provider/agents/events-per-second snapshot
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import protect_write
from ...db.models import Agent, AgentStatus
from ...db.session import get_db
from ...providers.registry import configured_provider
from ...providers.runtime_settings import (
    effective_llm_mode,
    load_runtime_provider_config,
)
from ...services.agent_runner import runner
from ...websocket.manager import manager

router = APIRouter()


@router.post("/agents/start")
async def start_agents(_: None = Depends(protect_write)):
    return await runner.start()


@router.post("/agents/stop")
async def stop_agents(_: None = Depends(protect_write)):
    return await runner.stop()


@router.get("/status/live")
async def live_status(db: AsyncSession = Depends(get_db)):
    stored = load_runtime_provider_config()
    provider = configured_provider(stored.provider if stored else None)
    active_agents = (
        await db.execute(
            select(func.count(Agent.id)).where(Agent.status == AgentStatus.ACTIVE)
        )
    ).scalar() or 0
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
            "running": runner.running,
        },
        "runner": runner.status(),
        "events_per_second": manager.events_per_second(),
        "websocket_clients": len(manager.active_connections),
    }
