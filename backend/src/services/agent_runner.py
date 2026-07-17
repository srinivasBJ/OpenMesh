"""
AgentRunner — browser-controlled agent loop.

POST /api/agents/start spawns the default OpenMesh agent (if the ecosystem is
empty) and starts a background tick loop, so users never need the terminal to
see agents come alive. Unlike the legacy env-gated scheduler, this runner is
controlled entirely at runtime through the API.
"""

from __future__ import annotations

import asyncio
import os
import random
from contextlib import suppress
from datetime import datetime, timezone

from sqlalchemy import func, select

from ..agents.brain import generate_agent_profile
from ..agents.simulator import run_simulation_tick
from ..db.models import Agent, AgentEvent, AgentStatus
from ..db.session import AsyncSessionLocal
from ..shared.openmesh_events import agent_node, make_openmesh_event
from .openmesh_collector import collector

DEFAULT_AGENT_NAME = os.getenv("OPENMESH_DEFAULT_AGENT_NAME", "Pioneer")
DEFAULT_AGENT_ROLE = os.getenv("OPENMESH_DEFAULT_AGENT_ROLE", "explorer")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


class AgentRunner:
    """Owns the background task that ticks agents on an interval."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.interval_seconds = _env_int("OPENMESH_RUNNER_INTERVAL_SECONDS", 10)
        self.agents_per_tick = _env_int("OPENMESH_RUNNER_AGENTS_PER_TICK", 3)
        self.started_at: str | None = None
        self.tick_count = 0
        self.last_tick_at: str | None = None
        self.last_tick_agents = 0
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> dict:
        async with self._lock:
            spawned = await self._ensure_default_agent()
            if not self.running:
                self.started_at = datetime.now(timezone.utc).isoformat()
                self.tick_count = 0
                self.last_error = None
                self._task = asyncio.create_task(self._run_loop())
                print(
                    f"[AgentRunner] Started: up to {self.agents_per_tick} agents "
                    f"every {self.interval_seconds}s"
                )
            return {**self.status(), "spawned_default_agent": spawned}

    async def stop(self) -> dict:
        async with self._lock:
            if self._task is not None:
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task
                self._task = None
                print("[AgentRunner] Stopped")
            return self.status()

    def status(self) -> dict:
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "agents_per_tick": self.agents_per_tick,
            "started_at": self.started_at,
            "tick_count": self.tick_count,
            "last_tick_at": self.last_tick_at,
            "last_tick_agents": self.last_tick_agents,
            "last_error": self.last_error,
        }

    async def _run_loop(self) -> None:
        # First tick fires immediately so the graph starts moving right away.
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    count = await run_simulation_tick(
                        db, max_agents=self.agents_per_tick
                    )
                self.tick_count += 1
                self.last_tick_at = datetime.now(timezone.utc).isoformat()
                self.last_tick_agents = count
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = str(e)
                print(f"[AgentRunner] Tick error: {e}")
            await asyncio.sleep(self.interval_seconds)

    async def _ensure_default_agent(self) -> bool:
        """Spawn the default OpenMesh agent when the ecosystem is empty."""
        async with AsyncSessionLocal() as db:
            active = (
                await db.execute(
                    select(func.count(Agent.id)).where(
                        Agent.status == AgentStatus.ACTIVE
                    )
                )
            ).scalar() or 0
            if active > 0:
                return False

            profile = await generate_agent_profile(
                DEFAULT_AGENT_NAME, DEFAULT_AGENT_ROLE
            )
            agent = Agent(
                name=DEFAULT_AGENT_NAME,
                role=DEFAULT_AGENT_ROLE,
                bio=profile.get("bio", ""),
                personality=profile.get("personality", {}),
                skills=profile.get("skills", []),
                goals=profile.get("goals", []),
                avatar_seed=DEFAULT_AGENT_NAME.lower(),
                memory=[],
                reputation=random.uniform(40, 60),
                knowledge=random.uniform(5, 20),
                energy=100.0,
                happiness=random.uniform(60, 80),
            )
            db.add(agent)
            db.add(
                AgentEvent(
                    event_type="birth",
                    title=f"{DEFAULT_AGENT_NAME} joined OpenMeshAI",
                    description=f"The default {DEFAULT_AGENT_ROLE} has emerged. {profile.get('bio', '')}",
                    agent_ids=[],
                )
            )
            await db.commit()
            await db.refresh(agent)

            await collector.accept(
                db,
                make_openmesh_event(
                    "agent.started",
                    agent_node(
                        agent.id,
                        agent.name,
                        agent.role.value
                        if hasattr(agent.role, "value")
                        else str(agent.role),
                    ),
                    {
                        "legacy_type": "agent_born",
                        "legacy": {
                            "type": "agent_born",
                            "agent": {
                                "id": agent.id,
                                "name": agent.name,
                                "role": str(agent.role),
                                "bio": agent.bio,
                            },
                        },
                    },
                ),
            )
            return True


runner = AgentRunner()
