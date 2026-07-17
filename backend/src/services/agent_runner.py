"""
AgentRunner — browser-controlled tick loop for SIMULATION agents only.

The runner never creates agents: a provider API key does not mean an agent
exists, and starting a session only drives simulation-source agents that
already exist (created explicitly by the demo environment). Real agents
appear exclusively through the SDK/MCP/collector register + heartbeat path.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from datetime import datetime, timezone

from ..agents.simulator import run_simulation_tick
from ..db.session import AsyncSessionLocal


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
        self.workspace_id: str | None = None
        self.paused = False
        self.started_at: str | None = None
        self.tick_count = 0
        self.last_tick_at: str | None = None
        self.last_tick_agents = 0
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(
        self,
        *,
        workspace_id: str | None = None,
    ) -> dict:
        async with self._lock:
            if not self.running:
                self.workspace_id = workspace_id
                self.paused = False
                self.started_at = datetime.now(timezone.utc).isoformat()
                self.tick_count = 0
                self.last_error = None
                self._task = asyncio.create_task(self._run_loop())
                print(
                    f"[AgentRunner] Started: up to {self.agents_per_tick} agents "
                    f"every {self.interval_seconds}s"
                    + (f" (workspace {workspace_id})" if workspace_id else "")
                )
            return self.status()

    async def stop(self) -> dict:
        async with self._lock:
            if self._task is not None:
                self._task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._task
                self._task = None
                print("[AgentRunner] Stopped")
            self.paused = False
            self.workspace_id = None
            return self.status()

    def pause(self) -> dict:
        if self.running:
            self.paused = True
        return self.status()

    def resume(self) -> dict:
        self.paused = False
        return self.status()

    def status(self) -> dict:
        return {
            "running": self.running,
            "paused": self.paused,
            "workspace_id": self.workspace_id,
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
                if not self.paused:
                    async with AsyncSessionLocal() as db:
                        count = await run_simulation_tick(
                            db,
                            max_agents=self.agents_per_tick,
                            workspace_id=self.workspace_id,
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

runner = AgentRunner()
