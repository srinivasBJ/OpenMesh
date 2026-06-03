from __future__ import annotations

import time
from typing import Any

import httpx

from .base import LLMProvider, LLMResponse, ProviderModel


class OllamaProvider(LLMProvider):
    provider_id = "ollama"
    display_name = "Ollama"
    env_var = "OLLAMA_BASE_URL"
    default_model = "llama3.2"
    default_endpoint = "http://localhost:11434"
    is_local = True

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    async def verify(self):
        try:
            await self.list_models()
            return self.connected_status(self.endpoint)
        except Exception as exc:
            return self.failed_status(exc)

    async def list_models(self) -> list[ProviderModel]:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{self.endpoint}/api/tags")
            response.raise_for_status()
            data = response.json()
        models = []
        for item in data.get("models") or []:
            model_name = item.get("name") or item.get("model")
            if model_name:
                models.append(
                    ProviderModel(
                        provider=self.provider_id,
                        provider_name=self.display_name,
                        model=str(model_name),
                        endpoint=self.endpoint,
                        metadata={key: value for key, value in item.items() if key != "name"},
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
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            body["system"] = system
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.endpoint}/api/generate", json=body)
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = {
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
            "total_duration": data.get("total_duration"),
            "load_duration": data.get("load_duration"),
            "prompt_eval_duration": data.get("prompt_eval_duration"),
            "eval_duration": data.get("eval_duration"),
        }
        return LLMResponse(
            provider=self.provider_id,
            model=self.model,
            content=str(data.get("response") or "").strip(),
            usage={key: value for key, value in usage.items() if value is not None},
            latency_ms=latency_ms,
            tokens_per_second=_ollama_tokens_per_second(data),
        )


def _ollama_tokens_per_second(data: dict[str, Any]) -> float | None:
    eval_count = data.get("eval_count")
    eval_duration = data.get("eval_duration")
    if not eval_count or not eval_duration:
        return None
    try:
        return round(float(eval_count) / (float(eval_duration) / 1_000_000_000), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
