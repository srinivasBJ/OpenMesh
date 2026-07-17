# ruff: noqa: E402
"""Stabilization tests: curated model ranking, filesystem browsing safety,
and clean session termination state."""

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import HTTPException

from src.api.routes.filesystem import browse_filesystem
from src.providers.model_catalog import classify_model, curate_models, rank_models
from src.services.agent_runner import AgentRunner


def _model(model_id: str, context_length: int = 0) -> dict:
    return {
        "provider": "openrouter",
        "model": model_id,
        "metadata": {"context_length": context_length},
    }


class ModelCatalogTests(unittest.TestCase):
    def test_classification_categories(self):
        self.assertEqual(classify_model("anthropic/claude-sonnet-4")[0], "coding")
        self.assertEqual(classify_model("anthropic/claude-opus-4")[0], "reasoning")
        self.assertEqual(classify_model("anthropic/claude-3-5-haiku")[0], "fast")
        self.assertEqual(classify_model("openai/gpt-4o-mini")[0], "fast")
        self.assertEqual(classify_model("openai/o3-mini")[0], "reasoning")
        self.assertEqual(classify_model("deepseek/deepseek-coder")[0], "coding")
        self.assertEqual(classify_model("qwen/qwen-2.5-coder-32b")[0], "coding")
        self.assertEqual(classify_model("google/gemini-2.0-flash")[0], "fast")
        self.assertEqual(classify_model("some/unknown-model")[0], "general")

    def test_ranking_sorts_best_first(self):
        ranked = rank_models(
            [
                _model("some/unknown-model"),
                _model("anthropic/claude-opus-4"),
                _model("openai/gpt-4o-mini"),
            ]
        )
        self.assertEqual(ranked[0]["model"], "anthropic/claude-opus-4")
        self.assertEqual(ranked[-1]["model"], "some/unknown-model")

    def test_ranking_excludes_non_chat_models(self):
        ranked = rank_models(
            [_model("openai/text-embedding-3-large"), _model("openai/gpt-4o")]
        )
        self.assertEqual([m["model"] for m in ranked], ["openai/gpt-4o"])

    def test_curation_caps_at_limit(self):
        many = [_model(f"vendor/model-{index}") for index in range(200)]
        many += [
            _model("anthropic/claude-sonnet-4"),
            _model("anthropic/claude-opus-4"),
            _model("openai/gpt-4o-mini"),
        ]
        curated = curate_models(many, limit=25)
        self.assertEqual(len(curated), 25)

    def test_curation_includes_each_category(self):
        models = [
            _model("anthropic/claude-sonnet-4"),
            _model("anthropic/claude-opus-4"),
            _model("google/gemini-2.0-flash"),
        ] + [_model(f"vendor/model-{index}") for index in range(50)]
        curated = curate_models(models, limit=25)
        categories = {entry["category"] for entry in curated}
        self.assertIn("coding", categories)
        self.assertIn("reasoning", categories)
        self.assertIn("fast", categories)

    def test_context_length_breaks_ties(self):
        ranked = rank_models(
            [_model("vendor/a-model", 8000), _model("vendor/b-model", 200000)]
        )
        self.assertEqual(ranked[0]["model"], "vendor/b-model")


class FilesystemBrowseTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_to_home(self):
        listing = await browse_filesystem(None)
        self.assertEqual(listing["path"], str(Path.home().resolve()))
        self.assertIsNone(listing["parent"])
        for entry in listing["directories"]:
            self.assertFalse(entry["name"].startswith("."))

    async def test_rejects_paths_outside_home(self):
        for candidate in ("/etc", "/", "/tmp", str(Path.home().parent)):
            with self.assertRaises(HTTPException) as ctx:
                await browse_filesystem(candidate)
            self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_traversal(self):
        sneaky = str(Path.home() / ".." / "..")
        with self.assertRaises(HTTPException) as ctx:
            await browse_filesystem(sneaky)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_missing_directory_404(self):
        with self.assertRaises(HTTPException) as ctx:
            await browse_filesystem(str(Path.home() / "definitely-not-a-real-dir-xyz"))
        self.assertEqual(ctx.exception.status_code, 404)


class SessionStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_terminate_clears_workspace_and_pause_state(self):
        runner = AgentRunner()
        self.assertFalse(runner.running)
        status = runner.pause()  # pausing an idle runner must not mark paused
        self.assertFalse(status["paused"])
        runner.paused = True
        runner.workspace_id = "ws-1"
        status = await runner.stop()
        self.assertFalse(status["running"])
        self.assertFalse(status["paused"])
        self.assertIsNone(status["workspace_id"])


if __name__ == "__main__":
    unittest.main()
