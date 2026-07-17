"""
Provider settings API — the browser-first onboarding path.

GET  /api/settings/provider       → is any LLM provider configured?
POST /api/settings/provider       → validate a key, store it encrypted, hot-reload
POST /api/settings/provider/test  → validate a key without storing it
DELETE /api/settings/provider     → forget the stored key
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.security import protect_write
from ...providers.registry import configured_provider, get_provider
from ...providers.runtime_settings import (
    clear_runtime_provider_config,
    effective_llm_mode,
    encryption_available,
    load_runtime_provider_config,
    mask_key,
    save_runtime_provider_config,
)

router = APIRouter()

ProviderName = Literal["anthropic", "openai", "openrouter"]


class ProviderConfigRequest(BaseModel):
    provider: ProviderName
    api_key: str = Field(min_length=1, max_length=512)
    model: Optional[str] = Field(default=None, max_length=200)


def _provider_state() -> dict:
    """Current provider status, shared by GET and the POST responses.

    Only cloud providers count: local runtimes (Ollama, LM Studio, vLLM) need
    no API key, so they must not suppress the first-run onboarding flow.
    """
    stored = load_runtime_provider_config()
    active = configured_provider(stored.provider if stored else None)
    if active is None or active.is_local:
        return {"configured": False, "provider": None}
    return {
        "configured": True,
        "provider": active.provider_id,
        "provider_name": active.display_name,
        "model": active.model,
        "mode": effective_llm_mode(),
        "masked_key": mask_key(active.api_key) if active.api_key else None,
        "source": "settings"
        if stored and stored.provider == active.provider_id
        else "environment",
        "encrypted_at_rest": stored.encrypted if stored else None,
        "saved_at": stored.saved_at if stored else None,
    }


async def _verify_candidate(provider_id: str, api_key: str, model: Optional[str]):
    template = get_provider(provider_id)
    if template is None or template.is_local:
        raise HTTPException(400, f"Unsupported provider '{provider_id}'")
    candidate = type(template)(
        api_key=api_key.strip(), model=(model or template.model).strip()
    )
    status = await candidate.verify()
    return candidate, status


@router.get("/settings/provider")
async def get_provider_settings():
    return _provider_state()


@router.post("/settings/provider")
async def save_provider_settings(
    req: ProviderConfigRequest,
    _: None = Depends(protect_write),
):
    candidate, status = await _verify_candidate(req.provider, req.api_key, req.model)
    if not status.connected:
        raise HTTPException(
            400,
            f"{status.name} rejected the API key: {status.message}",
        )
    save_runtime_provider_config(
        req.provider, req.api_key, model=req.model, mode="online"
    )
    return {
        **_provider_state(),
        "validated": True,
        "message": f"{status.name} connected ({candidate.model})",
        "encryption_available": encryption_available(),
    }


@router.post("/settings/provider/test")
async def test_provider_settings(
    req: ProviderConfigRequest,
    _: None = Depends(protect_write),
):
    _, status = await _verify_candidate(req.provider, req.api_key, req.model)
    return {
        "provider": status.provider,
        "provider_name": status.name,
        "connected": status.connected,
        "status": status.status,
        "message": status.message,
    }


@router.delete("/settings/provider")
async def delete_provider_settings(_: None = Depends(protect_write)):
    removed = clear_runtime_provider_config()
    return {**_provider_state(), "removed": removed}
