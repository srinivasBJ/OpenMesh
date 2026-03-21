"""
Scheduler — Runs agent simulation ticks on a timer.
Every AGENT_TICK_INTERVAL seconds, a batch of agents "wakes up" and acts.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession
import os

from ..db.session import AsyncSessionLocal
from ..agents.simulator import run_simulation_tick
from ..websocket.manager import manager

scheduler = AsyncIOScheduler()
TICK_INTERVAL = int(os.getenv("AGENT_TICK_INTERVAL", "15"))
MAX_AGENTS = int(os.getenv("MAX_ACTIVE_AGENTS", "6"))


async def tick_job():
    """Called by scheduler every N seconds."""
    async with AsyncSessionLocal() as db:
        try:
            count = await run_simulation_tick(db, manager.broadcast, MAX_AGENTS)
            if count > 0:
                print(f"[Scheduler] Ticked {count} agents")
        except Exception as e:
            print(f"[Scheduler] Tick error: {e}")


def start_scheduler():
    scheduler.add_job(tick_job, "interval", seconds=TICK_INTERVAL, id="agent_tick")
    scheduler.start()
    print(f"⏰ Scheduler started — up to {MAX_AGENTS} agents every {TICK_INTERVAL}s")


def stop_scheduler():
    scheduler.shutdown(wait=False)
