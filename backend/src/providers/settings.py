from __future__ import annotations

import os
from dataclasses import dataclass, replace

from .runtime_settings import (
    list_runtime_provider_configs,
    selected_model,
    selected_provider_id,
)


@dataclass(frozen=True)
class ProviderSettings:
    openai_api_key: str
    anthropic_api_key: str
    openrouter_api_key: str
    openai_model: str
    anthropic_model: str
    openrouter_model: str
    ollama_base_url: str
    lmstudio_base_url: str
    vllm_base_url: str
    ollama_model: str
    lmstudio_model: str
    vllm_model: str


def load_provider_settings() -> ProviderSettings:
    settings = _env_provider_settings()
    return _apply_runtime_config(settings)


def _env_provider_settings() -> ProviderSettings:
    return ProviderSettings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip(),
        lmstudio_base_url=os.getenv(
            "LMSTUDIO_BASE_URL", "http://localhost:1234"
        ).strip(),
        vllm_base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8000").strip(),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2").strip(),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", "local-model").strip(),
        vllm_model=os.getenv("VLLM_MODEL", "local-model").strip(),
    )


def _apply_runtime_config(settings: ProviderSettings) -> ProviderSettings:
    """Overlay keys saved via the web UI; they win over environment variables.

    Every stored provider's key is applied, and the selected model (if any)
    overrides the default model of the selected provider.
    """
    for provider, config in list_runtime_provider_configs().items():
        if provider == "anthropic":
            settings = replace(
                settings,
                anthropic_api_key=config.api_key,
                anthropic_model=config.model or settings.anthropic_model,
            )
        elif provider == "openai":
            settings = replace(
                settings,
                openai_api_key=config.api_key,
                openai_model=config.model or settings.openai_model,
            )
        elif provider == "openrouter":
            settings = replace(
                settings,
                openrouter_api_key=config.api_key,
                openrouter_model=config.model or settings.openrouter_model,
            )
    active_model = selected_model()
    active_provider = selected_provider_id()
    if active_model and active_provider == "anthropic":
        settings = replace(settings, anthropic_model=active_model)
    elif active_model and active_provider == "openai":
        settings = replace(settings, openai_model=active_model)
    elif active_model and active_provider == "openrouter":
        settings = replace(settings, openrouter_model=active_model)
    return settings
