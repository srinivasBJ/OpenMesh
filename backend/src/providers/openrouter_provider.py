from __future__ import annotations

import time
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, response_text_from_openai_shape


class OpenRouterProvider(LLMProvider):
    provider_id = "openrouter"
    display_name = "OpenRouter"
    env_var = "OPENROUTER_API_KEY"
    default_model = "openai/gpt-4o-mini"
    base_url = "https://openrouter.ai/api/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/srinivasBJ/OpenMesh",
            "X-Title": "OpenMesh",
        }

    async def verify(self):
        if not self.configured:
            return self.missing_status()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models", headers=self._headers()
                )
                response.raise_for_status()
            return self.connected_status("models endpoint reachable")
        except Exception as exc:  # pragma: no cover - exercised through tests by shape
            return self.failed_status(exc)

    async def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> LLMResponse:
        self.ensure_configured()
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
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        return LLMResponse(
            provider=self.provider_id,
            model=self.model,
            content=response_text_from_openai_shape(data).strip(),
            usage=data.get("usage") or {},
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
