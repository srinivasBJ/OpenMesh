from __future__ import annotations

import time
from typing import Any

import httpx

from .base import (
    LLMProvider,
    LLMResponse,
    ProviderModel,
    response_text_from_openai_shape,
)


class LocalOpenAICompatibleProvider(LLMProvider):
    is_local = True

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    def _models_url(self) -> str:
        return f"{self.endpoint}/v1/models"

    def _chat_url(self) -> str:
        return f"{self.endpoint}/v1/chat/completions"

    async def verify(self):
        try:
            await self.list_models()
            return self.connected_status(self.endpoint)
        except Exception as exc:
            return self.failed_status(exc)

    async def list_models(self) -> list[ProviderModel]:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(self._models_url())
            response.raise_for_status()
            data = response.json()
        models = []
        for item in data.get("data") or []:
            model_id = item.get("id")
            if model_id:
                models.append(
                    ProviderModel(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        model=str(model_id),
                        endpoint=self.endpoint,
                        metadata={
                            key: value for key, value in item.items() if key != "id"
                        },
                    )
                )
        return models

    async def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> LLMResponse:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self._chat_url(), json=body)
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = data.get("usage") or {}
        output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        tokens_per_second = _tokens_per_second(output_tokens, latency_ms)
        return LLMResponse(
            provider=self.provider_id,
            model=self.model,
            content=response_text_from_openai_shape(data).strip(),
            usage=usage,
            latency_ms=latency_ms,
            tokens_per_second=tokens_per_second,
        )


def _tokens_per_second(tokens: Any, latency_ms: int | None) -> float | None:
    if not latency_ms:
        return None
    try:
        count = float(tokens)
    except (TypeError, ValueError):
        return None
    return round(count / (latency_ms / 1000), 2) if count > 0 else None
