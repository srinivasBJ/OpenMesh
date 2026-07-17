# ruff: noqa: E402
"""Agent identity model tests — the six lifecycle cases:

1. Fresh install            → 0 agents
2. Run demo                 → simulation agents only
3. Terminate demo           → 0 agents
4. Add API key              → provider connected, still 0 agents
5. Connect SDK agent        → real agent appears (and disconnects on stale heartbeat)
6. Switch workspace         → events isolated

Runs the full flow in a subprocess with an isolated SQLite DB and config
dir, mirroring a real install."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.services.agent_identity import effective_agent_status
from types import SimpleNamespace

FLOW_SCRIPT = """
import asyncio, json
from datetime import datetime, timedelta

async def main():
    from src.db.session import init_db, AsyncSessionLocal
    from src.db.models import Agent, Workspace, OpenMeshEventRecord
    from src.services.demo import start_demo, terminate_demo
    from src.services.agent_runner import runner
    from src.services.agent_identity import effective_agent_status
    from src.agents.simulator import run_simulation_tick
    from src.providers.runtime_settings import save_runtime_provider_config
    from src.providers.registry import configured_provider
    from src.api.routes.control import register_agent, RegisterAgentRequest, agent_heartbeat, HeartbeatRequest
    from sqlalchemy import select, func

    out = {}
    await init_db(announce=False)

    async def agent_count(db):
        return (await db.execute(select(func.count(Agent.id)))).scalar()

    # Case 1: fresh install → 0 agents
    async with AsyncSessionLocal() as db:
        out["case1_fresh_agents"] = await agent_count(db)

    # Case 2: run demo → simulation agents only
    await start_demo()
    await runner.stop()
    async with AsyncSessionLocal() as db:
        agents = (await db.execute(select(Agent))).scalars().all()
        out["case2_agents"] = sorted(a.name for a in agents)
        out["case2_sources"] = sorted({a.source for a in agents})
        out["case2_statuses"] = sorted({effective_agent_status(a) for a in agents})
        ws = (await db.execute(select(Workspace).where(Workspace.kind == "demo"))).scalars().first()
        ticked = await run_simulation_tick(db, max_agents=3, workspace_id=ws.id)
        out["case2_ticked"] = ticked

    # Case 3: terminate demo → 0 agents, 0 events
    await terminate_demo()
    async with AsyncSessionLocal() as db:
        out["case3_agents"] = await agent_count(db)
        out["case3_events"] = (await db.execute(select(func.count(OpenMeshEventRecord.id)))).scalar()

    # Case 4: add API key → provider connected, still 0 agents
    save_runtime_provider_config("anthropic", "sk-test-key")
    provider = configured_provider("anthropic")
    async with AsyncSessionLocal() as db:
        out["case4_provider_configured"] = provider is not None and provider.configured
        out["case4_agents"] = await agent_count(db)

    # Case 5: SDK agent registers → real agent appears; simulator ignores it
    async with AsyncSessionLocal() as db:
        registered = await register_agent(
            RegisterAgentRequest(name="Claude Code", source="claude_code", workspace_id=None, model="claude-opus"),
            db=db, _=None,
        )
        out["case5_registered"] = {k: registered[k] for k in ("name", "source", "status", "created")}
        hb = await agent_heartbeat(registered["id"], HeartbeatRequest(status="running"), db=db, _=None)
        out["case5_heartbeat_status"] = hb["status"]
        ticked = await run_simulation_tick(db, max_agents=5)
        out["case5_sim_ticks_real_agent"] = ticked  # must be 0
        # stale heartbeat → disconnected
        agent = (await db.execute(select(Agent).where(Agent.id == registered["id"]))).scalar_one()
        agent.last_active_at = datetime.utcnow() - timedelta(seconds=600)
        await db.commit()
        out["case5_stale_status"] = effective_agent_status(agent)

    # Case 6: workspace isolation — events tagged and filterable
    async with AsyncSessionLocal() as db:
        ws_a = Workspace(name="Smart Glasses")
        ws_b = Workspace(name="Laser Detection")
        db.add_all([ws_a, ws_b])
        await db.flush()
        agent = (await db.execute(select(Agent).where(Agent.name == "Claude Code"))).scalar_one()
        agent.workspace_id = ws_a.id
        await db.commit()
        from src.services.openmesh_collector import collector
        from src.shared.openmesh_events import make_openmesh_event, agent_node
        await collector.accept(db, make_openmesh_event(
            "file.modified", agent_node(agent.id, agent.name, "engineer"),
            {"file": "camera.py"},
        ))
        a_events = (await db.execute(select(func.count(OpenMeshEventRecord.id)).where(OpenMeshEventRecord.workspace_id == ws_a.id))).scalar()
        b_events = (await db.execute(select(func.count(OpenMeshEventRecord.id)).where(OpenMeshEventRecord.workspace_id == ws_b.id))).scalar()
        record = (await db.execute(select(OpenMeshEventRecord).where(OpenMeshEventRecord.workspace_id == ws_a.id))).scalars().first()
        out["case6_a_events"] = a_events
        out["case6_b_events"] = b_events
        out["case6_source_tag"] = record.agent_source if record else None

    print(json.dumps(out))

asyncio.run(main())
"""


class AgentIdentityFlowTests(unittest.TestCase):
    def test_full_identity_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(BACKEND_ROOT),
                    "OPENMESH_DB_MODE": "sqlite",
                    "OPENMESH_SQLITE_PATH": str(Path(tmp) / "identity.db"),
                    "OPENMESH_CONFIG_DIR": str(Path(tmp) / "config"),
                    "LLM_MODE": "offline",
                    "OPENMESH_SCHEDULER_ENABLED": "0",
                }
            )
            for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
                env.pop(name, None)
            result = subprocess.run(
                [sys.executable, "-c", FLOW_SCRIPT],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr[-3000:])
            out = json.loads(result.stdout.strip().splitlines()[-1])

        # Case 1: fresh install → 0 agents
        self.assertEqual(out["case1_fresh_agents"], 0)

        # Case 2: demo → simulation agents only, running, tickable
        self.assertEqual(out["case2_agents"], ["Explorer", "Pioneer", "Scientist"])
        self.assertEqual(out["case2_sources"], ["simulation"])
        self.assertEqual(out["case2_statuses"], ["running"])
        self.assertEqual(out["case2_ticked"], 3)

        # Case 3: terminate → truly clean
        self.assertEqual(out["case3_agents"], 0)
        self.assertEqual(out["case3_events"], 0)

        # Case 4: API key connects a provider but creates no agents
        self.assertTrue(out["case4_provider_configured"])
        self.assertEqual(out["case4_agents"], 0)

        # Case 5: real agent lifecycle
        self.assertEqual(out["case5_registered"]["source"], "claude_code")
        self.assertTrue(out["case5_registered"]["created"])
        self.assertEqual(out["case5_heartbeat_status"], "running")
        self.assertEqual(out["case5_sim_ticks_real_agent"], 0)
        self.assertEqual(out["case5_stale_status"], "disconnected")

        # Case 6: workspace isolation with source tagging
        self.assertEqual(out["case6_a_events"], 1)
        self.assertEqual(out["case6_b_events"], 0)
        self.assertEqual(out["case6_source_tag"], "claude_code")


class EffectiveStatusUnitTests(unittest.TestCase):
    def _agent(self, source: str, status: str, last_seen_seconds_ago: int):
        return SimpleNamespace(
            source=source,
            status=status,
            last_active_at=datetime.utcnow() - timedelta(seconds=last_seen_seconds_ago),
        )

    def test_simulation_agents_report_stored_status(self):
        agent = self._agent("simulation", "running", 9999)
        self.assertEqual(effective_agent_status(agent), "running")

    def test_real_agent_fresh_heartbeat(self):
        agent = self._agent("sdk", "running", 5)
        self.assertEqual(effective_agent_status(agent), "running")

    def test_real_agent_stale_heartbeat_disconnects(self):
        agent = self._agent("sdk", "running", 600)
        self.assertEqual(effective_agent_status(agent), "disconnected")

    def test_terminal_status_survives_staleness(self):
        agent = self._agent("claude_code", "completed", 600)
        self.assertEqual(effective_agent_status(agent), "completed")


if __name__ == "__main__":
    unittest.main()
