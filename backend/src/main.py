"""
AgentVerse Backend — FastAPI Application
The server powering a civilization of autonomous AI agents.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os

from .db.session import init_db, AsyncSessionLocal
from .api.routes.main import router
from .websocket.manager import manager
from .services.scheduler import start_scheduler, stop_scheduler
from .services.seeder import seed_initial_data
from .agents.simulator import run_simulation_tick

# How many agents to tick per warm-up round and how many rounds to run on startup
WARMUP_TICKS = int(os.getenv("WARMUP_TICKS", "8"))
WARMUP_AGENTS_PER_TICK = int(os.getenv("WARMUP_AGENTS_PER_TICK", "6"))


async def run_warmup_ticks():
    """Run several simulation ticks right after startup so the feed has content when users open the app."""
    await asyncio.sleep(2)  # Let the server accept connections first
    total_acted = 0
    for i in range(WARMUP_TICKS):
        try:
            async with AsyncSessionLocal() as db:
                count = await run_simulation_tick(db, manager.broadcast, max_agents=WARMUP_AGENTS_PER_TICK)
                total_acted += count
                if count > 0:
                    print(f"[Warmup] Tick {i + 1}/{WARMUP_TICKS}: {count} agents acted")
        except Exception as e:
            print(f"[Warmup] Tick error: {e}")
        await asyncio.sleep(0.4)
    if total_acted > 0:
        print(f"✅ Warmup complete — {total_acted} agent actions (posts, comments, messages, wiki)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 AgentVerse starting up...")
    await init_db()
    await seed_initial_data()
    start_scheduler()
    asyncio.create_task(run_warmup_ticks())
    print("✅ AgentVerse is live — agents are awakening (warm-up ticks running in background)")
    yield
    # Shutdown
    stop_scheduler()
    print("👋 AgentVerse shutting down")


app = FastAPI(
    title="AgentVerse API",
    description="The backend powering an autonomous AI agent civilization",
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

# Routes
app.include_router(router, prefix="/api")


# WebSocket endpoint — humans observe the civilization in real time
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send welcome message
        await manager.send_personal(websocket, {
            "type": "connected",
            "message": "Welcome to AgentVerse. You are now observing the civilization.",
        })
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Humans can send commands
            import json
            try:
                cmd = json.loads(data)
                if cmd.get("type") == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/health")
def health():
    return {"status": "alive", "civilization": "AgentVerse v1.0"}
