from __future__ import annotations

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ProviderStatus
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider
from .settings import load_provider_settings


def list_providers() -> list[LLMProvider]:
    settings = load_provider_settings()
    return [
        OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model),
        AnthropicProvider(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        ),
        OpenRouterProvider(
            api_key=settings.openrouter_api_key, model=settings.openrouter_model
        ),
    ]


def get_provider(provider_id: str) -> LLMProvider | None:
    provider_id = provider_id.lower().strip()
    return next(
        (provider for provider in list_providers() if provider.provider_id == provider_id),
        None,
    )


def configured_provider(preferred: str | None = None) -> LLMProvider | None:
    if preferred and preferred != "auto":
        provider = get_provider(preferred)
        return provider if provider and provider.configured else None
    return next((provider for provider in list_providers() if provider.configured), None)


async def verify_providers() -> list[ProviderStatus]:
    return [await provider.verify() for provider in list_providers()]
