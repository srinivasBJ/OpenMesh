from __future__ import annotations

import asyncio

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ProviderModel, ProviderStatus
from .lmstudio_provider import LMStudioProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider
from .settings import load_provider_settings
from .vllm_provider import VLLMProvider


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
        OllamaProvider(
            endpoint=settings.ollama_base_url,
            model=settings.ollama_model,
        ),
        LMStudioProvider(
            endpoint=settings.lmstudio_base_url,
            model=settings.lmstudio_model,
        ),
        VLLMProvider(
            endpoint=settings.vllm_base_url,
            model=settings.vllm_model,
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
    providers = list_providers()
    cloud = next(
        (
            provider
            for provider in providers
            if provider.configured and not provider.is_local
        ),
        None,
    )
    return cloud or next((provider for provider in providers if provider.configured), None)


async def verify_providers() -> list[ProviderStatus]:
    return list(await asyncio.gather(*(provider.verify() for provider in list_providers())))


def list_local_providers() -> list[LLMProvider]:
    return [provider for provider in list_providers() if provider.is_local]


async def discover_local_providers() -> list[ProviderStatus]:
    return list(
        await asyncio.gather(*(provider.verify() for provider in list_local_providers()))
    )


async def list_local_models() -> list[ProviderModel]:
    models: list[ProviderModel] = []
    results = await asyncio.gather(
        *(provider.list_models() for provider in list_local_providers()),
        return_exceptions=True,
    )
    for result in results:
        if not isinstance(result, Exception):
            models.extend(result)
    return sorted(models, key=lambda item: (item.provider_name.lower(), item.model))
