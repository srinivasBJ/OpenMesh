"""
Scheduler — Runs agent simulation ticks on a timer.
Every AGENT_TICK_INTERVAL seconds, a batch of agents "wakes up" and acts.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

from ..db.session import AsyncSessionLocal
from ..agents.simulator import run_simulation_tick

scheduler = AsyncIOScheduler()
TICK_INTERVAL = int(os.getenv("AGENT_TICK_INTERVAL", "15"))
MAX_AGENTS = int(os.getenv("MAX_ACTIVE_AGENTS", "6"))


async def tick_job():
    """Called by scheduler every N seconds."""
    async with AsyncSessionLocal() as db:
        try:
            count = await run_simulation_tick(db, MAX_AGENTS)
            if count > 0:
                print(f"[Scheduler] Ticked {count} agents")
        except Exception as e:
            print(f"[Scheduler] Tick error: {e}")


def start_scheduler():
    # Replace the existing job if start_scheduler is called again (e.g. app reload).
    scheduler.add_job(
        tick_job,
        "interval",
        seconds=TICK_INTERVAL,
        id="agent_tick",
        replace_existing=True,
    )
    if scheduler.running:
        print("⏰ Scheduler already running")
        return
    scheduler.start()
    print(f"⏰ Scheduler started — up to {MAX_AGENTS} agents every {TICK_INTERVAL}s")


def stop_scheduler():
    if not scheduler.running:
        return
    scheduler.shutdown(wait=False)


def scheduler_status() -> dict:
    """Expose scheduler state for readiness probes and diagnostics."""
    job = scheduler.get_job("agent_tick")
    return {
        "running": scheduler.running,
        "tick_interval_seconds": TICK_INTERVAL,
        "max_agents_per_tick": MAX_AGENTS,
        "job_present": job is not None,
        "next_run_at": job.next_run_time.isoformat()
        if job and job.next_run_time
        else None,
    }
