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


def load_provider_settings() -> ProviderSettings:
    return ProviderSettings(
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip(),
    )
