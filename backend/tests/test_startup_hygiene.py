import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class StartupHygieneTests(unittest.TestCase):
    def _run_python(
        self,
        code: str,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        test_env = os.environ.copy()
        test_env["PYTHONPATH"] = str(BACKEND_ROOT)
        for name in (
            "OPENMESH_SEED_ENABLED",
            "OPENMESH_DEMO_MODE",
            "WARMUP_TICKS",
            "WARMUP_AGENTS_PER_TICK",
            "MAX_ACTIVE_AGENTS",
            "OPENMESH_DB_MODE",
            "OPENMESH_SQLITE_PATH",
            "DATABASE_URL",
        ):
            test_env.pop(name, None)
        if env:
            test_env.update(env)
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=cwd,
            env=test_env,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_startup_defaults_are_empty(self):
        result = self._run_python(
            """
import json
from src import main
from src.services import scheduler

print(json.dumps({
    "warmup_ticks": main.WARMUP_TICKS,
    "warmup_agents_per_tick": main.WARMUP_AGENTS_PER_TICK,
    "scheduler_enabled": main.SCHEDULER_ENABLED,
    "seed_enabled": main.SEED_ENABLED,
    "demo_mode": main.DEMO_MODE,
    "max_agents": scheduler.MAX_AGENTS,
}))
"""
        )
        values = json.loads(result.stdout)
        self.assertEqual(values["warmup_ticks"], 0)
        self.assertEqual(values["warmup_agents_per_tick"], 0)
        self.assertFalse(values["scheduler_enabled"])
        self.assertFalse(values["seed_enabled"])
        self.assertFalse(values["demo_mode"])
        self.assertEqual(values["max_agents"], 0)

    def test_backend_env_is_loaded_before_database_url_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend_env = root / "backend" / ".env"
            backend_env.parent.mkdir()
            sqlite_path = root / "configured.db"
            backend_env.write_text(
                "\n".join(
                    [
                        "OPENMESH_DB_MODE=sqlite",
                        f"OPENMESH_SQLITE_PATH={sqlite_path}",
                        "WARMUP_TICKS=0",
                        "WARMUP_AGENTS_PER_TICK=0",
                        "MAX_ACTIVE_AGENTS=0",
                    ]
                )
            )
            result = self._run_python(
                """
from src.db.session import DATABASE_URL
print(DATABASE_URL)
""",
                cwd=str(root),
            )
            self.assertEqual(result.stdout.strip(), f"sqlite:///{sqlite_path}")


if __name__ == "__main__":
    unittest.main()
