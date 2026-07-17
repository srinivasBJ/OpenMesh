"""
OpenMeshAI Backend — FastAPI Application
The server powering the early agent ecosystem prototype.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from sqlalchemy import text

from .db.session import init_db, AsyncSessionLocal
from .api.routes.main import router
from .api.routes.settings import router as settings_router
from .api.routes.control import router as control_router
from .websocket.manager import manager
from .services.agent_runner import runner
from .services.scheduler import start_scheduler, stop_scheduler, scheduler_status
from .services.seeder import seed_initial_data
from .agents.simulator import run_simulation_tick
from .core.security import security_status
from .shared.openmesh_events import make_openmesh_event
from .websocket.manager import SYSTEM_NODE


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int = 0) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Startup must be empty by default. Demo seeding and warmup are opt-in.
WARMUP_TICKS = _env_int("WARMUP_TICKS", 0)
WARMUP_AGENTS_PER_TICK = _env_int("WARMUP_AGENTS_PER_TICK", 0)
SCHEDULER_ENABLED = os.getenv("OPENMESH_SCHEDULER_ENABLED", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SEED_ENABLED = _env_bool("OPENMESH_SEED_ENABLED", False)
DEMO_MODE = _env_bool("OPENMESH_DEMO_MODE", False)


async def run_warmup_ticks():
    """Run optional demo warmup ticks when explicitly enabled."""
    if WARMUP_TICKS <= 0 or WARMUP_AGENTS_PER_TICK <= 0:
        return
    await asyncio.sleep(2)  # Let the server accept connections first
    total_acted = 0
    for i in range(WARMUP_TICKS):
        try:
            async with AsyncSessionLocal() as db:
                count = await run_simulation_tick(db, max_agents=WARMUP_AGENTS_PER_TICK)
                total_acted += count
                if count > 0:
                    print(f"[Warmup] Tick {i + 1}/{WARMUP_TICKS}: {count} agents acted")
        except Exception as e:
            print(f"[Warmup] Tick error: {e}")
        await asyncio.sleep(0.4)
    if total_acted > 0:
        print(
            f"Warmup complete: {total_acted} agent actions (posts, comments, messages, wiki)"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("OpenMeshAI starting up")
    await init_db()
    if SEED_ENABLED or DEMO_MODE:
        await seed_initial_data()
    if SCHEDULER_ENABLED:
        start_scheduler()
    warmup_task = None
    if WARMUP_TICKS > 0 and WARMUP_AGENTS_PER_TICK > 0:
        warmup_task = asyncio.create_task(run_warmup_ticks())
    print("Application startup complete")
    try:
        yield
    finally:
        if warmup_task:
            warmup_task.cancel()
            with suppress(asyncio.CancelledError):
                await warmup_task
    # Shutdown
    await runner.stop()
    stop_scheduler()
    print("Application shutdown complete")


app = FastAPI(
    title="OpenMeshAI API",
    description="The backend for observing autonomous agent ecosystem activity",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes (settings/control first so their paths win over parameterized routes)
app.include_router(settings_router, prefix="/api")
app.include_router(control_router, prefix="/api")
app.include_router(router, prefix="/api")


# WebSocket endpoint — humans observe the civilization in real time
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send welcome message
        await manager.send_personal(
            websocket,
            make_openmesh_event(
                "system.connected",
                SYSTEM_NODE,
                {
                    "message": "Welcome to OpenMeshAI. You are now observing the civilization."
                },
            ),
        )
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Humans can send commands
            import json

            try:
                cmd = json.loads(data)
                if cmd.get("type") == "ping":
                    await manager.send_personal(
                        websocket,
                        make_openmesh_event("system.pong", SYSTEM_NODE, {"ok": True}),
                    )
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
def health():
    return {"status": "alive", "civilization": "OpenMeshAI v1.0"}


@app.get("/health/ready")
async def readiness():
    """Readiness probe for orchestrators (k8s, ECS, etc.)."""
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "ok",
            "scheduler": scheduler_status(),
            "security": security_status(),
            "civilization": "OpenMeshAI v1.0",
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "database": "error",
                "error": str(e),
                "scheduler": scheduler_status(),
                "security": security_status(),
            },
        )
