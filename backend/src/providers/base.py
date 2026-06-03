from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


class ProviderConfigurationError(RuntimeError):
    """Raised when an LLM provider cannot be used with current settings."""


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    name: str
    configured: bool
    connected: bool
    status: str
    message: str


@dataclass(frozen=True)
class LLMResponse:
    provider: str
    model: str
    content: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: int | None = None


class LLMProvider:
    provider_id: str = ""
    display_name: str = ""
    env_var: str = ""
    default_model: str = ""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = (model or self.default_model).strip()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def ensure_configured(self) -> None:
        if not self.configured:
            raise ProviderConfigurationError(
                f"{self.display_name} is not configured. Set {self.env_var}."
            )

    async def verify(self) -> ProviderStatus:
        raise NotImplementedError

    async def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.2,
    ) -> LLMResponse:
        raise NotImplementedError

    def missing_status(self) -> ProviderStatus:
        return ProviderStatus(
            provider=self.provider_id,
            name=self.display_name,
            configured=False,
            connected=False,
            status="missing",
            message=f"{self.env_var} is not set",
        )

    def connected_status(self, message: str = "connected") -> ProviderStatus:
        return ProviderStatus(
            provider=self.provider_id,
            name=self.display_name,
            configured=True,
            connected=True,
            status="connected",
            message=message,
        )

    def failed_status(self, error: Exception) -> ProviderStatus:
        message = str(error) or error.__class__.__name__
        if isinstance(error, httpx.HTTPStatusError):
            message = f"HTTP {error.response.status_code}"
        return ProviderStatus(
            provider=self.provider_id,
            name=self.display_name,
            configured=True,
            connected=False,
            status="failed",
            message=message,
        )


def response_text_from_openai_shape(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("text")
        ]
        return "\n".join(parts)
    return ""
