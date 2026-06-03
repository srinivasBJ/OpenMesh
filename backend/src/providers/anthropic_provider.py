from __future__ import annotations

import time
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    provider_id = "anthropic"
    display_name = "Anthropic"
    env_var = "ANTHROPIC_API_KEY"
    default_model = "claude-3-5-haiku-latest"
    base_url = "https://api.anthropic.com/v1"
    api_version = "2023-06-01"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
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
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        return LLMResponse(
            provider=self.provider_id,
            model=self.model,
            content=_anthropic_text(data).strip(),
            usage=data.get("usage") or {},
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


def _anthropic_text(data: dict[str, Any]) -> str:
    parts = []
    for item in data.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part)
