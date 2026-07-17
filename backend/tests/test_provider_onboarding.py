# ruff: noqa: E402
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import HTTPException

from src.providers import runtime_settings
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.base import ProviderStatus
from src.providers.settings import load_provider_settings

PROVIDER_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "LLM_MODE",
)


class RuntimeSettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.dict(
            os.environ,
            {"OPENMESH_CONFIG_DIR": self._tmp.name},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        for name in PROVIDER_ENV_VARS:
            env_patcher = patch.dict(os.environ, {}, clear=False)
            env_patcher.start()
            self.addCleanup(env_patcher.stop)
            os.environ.pop(name, None)

    def test_save_and_load_roundtrip(self):
        saved = runtime_settings.save_runtime_provider_config(
            "anthropic", "sk-test-123", model="claude-3-5-haiku-latest"
        )
        self.assertEqual(saved.provider, "anthropic")
        loaded = runtime_settings.load_runtime_provider_config()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.api_key, "sk-test-123")
        self.assertEqual(loaded.model, "claude-3-5-haiku-latest")
        self.assertEqual(loaded.mode, "online")

    def test_key_is_not_stored_in_plaintext(self):
        runtime_settings.save_runtime_provider_config("openai", "sk-super-secret")
        config_path = Path(self._tmp.name) / runtime_settings.CONFIG_FILE_NAME
        raw = config_path.read_text("utf-8")
        self.assertNotIn("sk-super-secret", raw)

    def test_config_file_permissions_are_private(self):
        runtime_settings.save_runtime_provider_config("openai", "sk-secret")
        config_path = Path(self._tmp.name) / runtime_settings.CONFIG_FILE_NAME
        mode = config_path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_clear_removes_config(self):
        runtime_settings.save_runtime_provider_config("openrouter", "sk-x")
        self.assertTrue(runtime_settings.clear_runtime_provider_config())
        self.assertIsNone(runtime_settings.load_runtime_provider_config())
        self.assertFalse(runtime_settings.clear_runtime_provider_config())

    def test_invalid_provider_rejected(self):
        with self.assertRaises(ValueError):
            runtime_settings.save_runtime_provider_config("nonsense", "sk-x")
        with self.assertRaises(ValueError):
            runtime_settings.save_runtime_provider_config("anthropic", "   ")

    def test_runtime_config_overrides_environment(self):
        os.environ["ANTHROPIC_API_KEY"] = "env-key"
        runtime_settings.save_runtime_provider_config(
            "anthropic", "ui-key", model="custom-model"
        )
        settings = load_provider_settings()
        self.assertEqual(settings.anthropic_api_key, "ui-key")
        self.assertEqual(settings.anthropic_model, "custom-model")

    def test_effective_llm_mode_prefers_runtime_config(self):
        os.environ["LLM_MODE"] = "offline"
        self.assertEqual(runtime_settings.effective_llm_mode(), "offline")
        runtime_settings.save_runtime_provider_config("anthropic", "sk-x")
        self.assertEqual(runtime_settings.effective_llm_mode(), "online")

    def test_mask_key(self):
        self.assertEqual(runtime_settings.mask_key("sk-abcdef123456"), "sk-a…3456")
        self.assertEqual(runtime_settings.mask_key("short"), "•••••")


class SettingsEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.dict(
            os.environ,
            {"OPENMESH_CONFIG_DIR": self._tmp.name},
            clear=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        for name in PROVIDER_ENV_VARS:
            os.environ.pop(name, None)

    async def test_get_reports_unconfigured(self):
        from src.api.routes.settings import get_provider_settings

        state = await get_provider_settings()
        self.assertEqual(state, {"configured": False, "provider": None})

    async def test_save_validates_and_persists(self):
        from src.api.routes.settings import (
            ProviderConfigRequest,
            save_provider_settings,
        )

        connected = ProviderStatus(
            provider="anthropic",
            name="Anthropic",
            configured=True,
            connected=True,
            status="connected",
            message="models endpoint reachable",
        )
        with patch.object(
            AnthropicProvider, "verify", new=AsyncMock(return_value=connected)
        ):
            result = await save_provider_settings(
                ProviderConfigRequest(provider="anthropic", api_key="sk-live-key"),
                None,
            )
        self.assertTrue(result["configured"])
        self.assertEqual(result["provider"], "anthropic")
        self.assertTrue(result["validated"])
        stored = runtime_settings.load_runtime_provider_config()
        self.assertEqual(stored.api_key, "sk-live-key")

    async def test_save_rejects_bad_key(self):
        from src.api.routes.settings import (
            ProviderConfigRequest,
            save_provider_settings,
        )

        failed = ProviderStatus(
            provider="anthropic",
            name="Anthropic",
            configured=True,
            connected=False,
            status="failed",
            message="HTTP 401",
        )
        with patch.object(
            AnthropicProvider, "verify", new=AsyncMock(return_value=failed)
        ):
            with self.assertRaises(HTTPException) as ctx:
                await save_provider_settings(
                    ProviderConfigRequest(provider="anthropic", api_key="sk-bad"),
                    None,
                )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIsNone(runtime_settings.load_runtime_provider_config())

    async def test_test_endpoint_does_not_persist(self):
        from src.api.routes.settings import (
            ProviderConfigRequest,
            test_provider_settings,
        )

        connected = ProviderStatus(
            provider="anthropic",
            name="Anthropic",
            configured=True,
            connected=True,
            status="connected",
            message="ok",
        )
        with patch.object(
            AnthropicProvider, "verify", new=AsyncMock(return_value=connected)
        ):
            result = await test_provider_settings(
                ProviderConfigRequest(provider="anthropic", api_key="sk-probe"),
                None,
            )
        self.assertTrue(result["connected"])
        self.assertIsNone(runtime_settings.load_runtime_provider_config())

    async def test_get_reflects_saved_provider(self):
        from src.api.routes.settings import get_provider_settings

        runtime_settings.save_runtime_provider_config("openrouter", "sk-or-123456")
        state = await get_provider_settings()
        self.assertTrue(state["configured"])
        self.assertEqual(state["provider"], "openrouter")
        self.assertEqual(state["source"], "settings")
        self.assertNotIn("sk-or-123456", str(state))


if __name__ == "__main__":
    unittest.main()
