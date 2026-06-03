from __future__ import annotations

import os
from dataclasses import dataclass


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
