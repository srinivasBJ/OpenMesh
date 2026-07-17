# ruff: noqa: E402
"""Tests for the workspace platform: multi-provider store (v2),
workspace/project/demo lifecycle, and workspace-scoped event tagging.

DB-backed lifecycle tests run in a subprocess with an isolated SQLite file,
mirroring test_startup_hygiene.py, so they never touch a developer DB."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.providers import runtime_settings


class MultiProviderStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.dict(
            os.environ, {"OPENMESH_CONFIG_DIR": self._tmp.name}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(name, None)

    def test_multiple_providers_coexist(self):
        runtime_settings.save_runtime_provider_config("openai", "sk-openai")
        runtime_settings.save_runtime_provider_config("anthropic", "sk-ant")
        configs = runtime_settings.list_runtime_provider_configs()
        self.assertEqual(set(configs), {"openai", "anthropic"})
        # Last saved becomes selected
        self.assertEqual(runtime_settings.selected_provider_id(), "anthropic")

    def test_select_provider_and_model(self):
        runtime_settings.save_runtime_provider_config("openai", "sk-openai")
        runtime_settings.save_runtime_provider_config("openrouter", "sk-or")
        runtime_settings.select_runtime_provider("openai", "gpt-5-mini")
        self.assertEqual(runtime_settings.selected_provider_id(), "openai")
        self.assertEqual(runtime_settings.selected_model(), "gpt-5-mini")
        config = runtime_settings.load_runtime_provider_config()
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.model, "gpt-5-mini")

    def test_remove_provider_reselects(self):
        runtime_settings.save_runtime_provider_config("openai", "sk-openai")
        runtime_settings.save_runtime_provider_config("anthropic", "sk-ant")
        self.assertTrue(runtime_settings.remove_runtime_provider("anthropic"))
        self.assertEqual(runtime_settings.selected_provider_id(), "openai")
        self.assertFalse(runtime_settings.remove_runtime_provider("anthropic"))

    def test_legacy_v1_config_migrates(self):
        legacy_path = Path(self._tmp.name) / runtime_settings.LEGACY_CONFIG_FILE_NAME
        # Write a v1 file via the old shape (plain b64 scheme for portability)
        import base64

        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            json.dumps(
                {
                    "provider": "openrouter",
                    "model": "openai/gpt-4o-mini",
                    "mode": "online",
                    "api_key": {
                        "scheme": "b64",
                        "value": base64.b64encode(b"sk-legacy").decode(),
                    },
                    "saved_at": "2026-01-01T00:00:00+00:00",
                }
            )
        )
        config = runtime_settings.load_runtime_provider_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.provider, "openrouter")
        self.assertEqual(config.api_key, "sk-legacy")
        self.assertTrue(
            (Path(self._tmp.name) / runtime_settings.STORE_FILE_NAME).exists()
        )

    def test_keys_not_plaintext_in_store(self):
        runtime_settings.save_runtime_provider_config("openai", "sk-super-secret")
        raw = (Path(self._tmp.name) / runtime_settings.STORE_FILE_NAME).read_text()
        self.assertNotIn("sk-super-secret", raw)


LIFECYCLE_SCRIPT = """
import asyncio, json

async def main():
    from src.db.session import init_db, AsyncSessionLocal
    from src.db.models import Agent, Post, Workspace, OpenMeshEventRecord
    from src.services.demo import start_demo, terminate_demo, demo_status
    from src.services.agent_runner import runner
    from src.agents.simulator import run_simulation_tick
    from sqlalchemy import select, func

    await init_db(announce=False)

    result = await start_demo()
    await runner.stop()  # keep the test deterministic
    status = await demo_status()
    out = {"after_start": {
        "active": status["active"],
        "agents": sorted(a["name"] for a in status["agents"]),
    }}

    # One scoped tick produces workspace-tagged posts/events (offline mode).
    async with AsyncSessionLocal() as db:
        ws = (await db.execute(select(Workspace).where(Workspace.kind == "demo"))).scalars().first()
        ticked = await run_simulation_tick(db, max_agents=3, workspace_id=ws.id)
        out["ticked"] = ticked
        events = (await db.execute(
            select(func.count(OpenMeshEventRecord.id)).where(OpenMeshEventRecord.workspace_id == ws.id)
        )).scalar()
        out["tagged_events"] = events

    result = await terminate_demo()
    out["terminated"] = result["terminated"]
    async with AsyncSessionLocal() as db:
        out["agents_left"] = (await db.execute(select(func.count(Agent.id)))).scalar()
        out["posts_left"] = (await db.execute(select(func.count(Post.id)))).scalar()
        out["workspaces_left"] = (await db.execute(select(func.count(Workspace.id)))).scalar()
        out["events_left"] = (await db.execute(select(func.count(OpenMeshEventRecord.id)))).scalar()
    print(json.dumps(out))

asyncio.run(main())
"""

WORKSPACE_SCRIPT = """
import asyncio, json

async def main():
    from src.db.session import init_db, AsyncSessionLocal
    from src.db.models import Agent, Project, Workspace
    from sqlalchemy import select

    await init_db(announce=False)
    async with AsyncSessionLocal() as db:
        ws = Workspace(name="AI Research Lab")
        db.add(ws)
        await db.flush()
        project = Project(workspace_id=ws.id, name="Laser Detection", repository_path="~/Desktop/s1")
        db.add(project)
        await db.flush()
        agent = Agent(
            name="Laser Research Agent", role="scientist", workspace_id=ws.id,
            project_id=project.id, personality={}, skills=[],
        )
        db.add(agent)
        await db.commit()

        scoped = (await db.execute(select(Agent).where(Agent.workspace_id == ws.id))).scalars().all()
        print(json.dumps({"scoped_agents": [a.name for a in scoped], "project": project.name}))

asyncio.run(main())
"""


class WorkspaceLifecycleTests(unittest.TestCase):
    def _run(self, script: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(BACKEND_ROOT),
                    "OPENMESH_DB_MODE": "sqlite",
                    "OPENMESH_SQLITE_PATH": str(Path(tmp) / "test.db"),
                    "OPENMESH_CONFIG_DIR": str(Path(tmp) / "config"),
                    "LLM_MODE": "offline",
                    "OPENMESH_SCHEDULER_ENABLED": "0",
                }
            )
            for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"):
                env.pop(name, None)
            result = subprocess.run(
                [sys.executable, "-c", script],
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr[-2000:])
            return json.loads(result.stdout.strip().splitlines()[-1])

    def test_demo_lifecycle_start_tick_terminate(self):
        out = self._run(LIFECYCLE_SCRIPT)
        self.assertTrue(out["after_start"]["active"])
        self.assertEqual(
            out["after_start"]["agents"], ["Explorer", "Pioneer", "Scientist"]
        )
        self.assertEqual(out["ticked"], 3)
        self.assertGreaterEqual(out["tagged_events"], 1)
        self.assertTrue(out["terminated"])
        self.assertEqual(out["agents_left"], 0)
        self.assertEqual(out["posts_left"], 0)
        self.assertEqual(out["workspaces_left"], 0)
        self.assertEqual(out["events_left"], 0)

    def test_workspace_project_agent_hierarchy(self):
        out = self._run(WORKSPACE_SCRIPT)
        self.assertEqual(out["scoped_agents"], ["Laser Research Agent"])
        self.assertEqual(out["project"], "Laser Detection")


if __name__ == "__main__":
    unittest.main()
