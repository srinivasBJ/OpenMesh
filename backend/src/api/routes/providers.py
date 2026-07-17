"""
Provider management API — the Provider → Model layer.

GET    /api/providers                      → all providers with status
POST   /api/providers/{id}/connect        → validate key, discover models, store
GET    /api/providers/{id}/models         → live model discovery
POST   /api/providers/select              → choose active (provider, model)
DELETE /api/providers/{id}                → forget a stored key

Models are never hardcoded: discovery always calls the provider's own
models endpoint with the stored (or environment) key.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.security import protect_write
from ...providers.base import ProviderModel
from ...providers.model_catalog import curate_models, rank_models
from ...providers.registry import get_provider, list_providers
from ...providers.runtime_settings import (
    SUPPORTED_PROVIDERS,
    list_runtime_provider_configs,
    mask_key,
    remove_runtime_provider,
    save_runtime_provider_config,
    select_runtime_provider,
    selected_model,
    selected_provider_id,
)

router = APIRouter()


class ConnectProviderRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)
    model: Optional[str] = Field(default=None, max_length=200)


class SelectProviderRequest(BaseModel):
    provider: str = Field(max_length=50)
    model: Optional[str] = Field(default=None, max_length=200)


def _model_to_dict(model: ProviderModel) -> dict:
    return {
        "provider": model.provider,
        "model": model.model,
        "metadata": model.metadata,
    }


@router.get("/providers")
async def list_provider_status():
    stored = list_runtime_provider_configs()
    active_provider = selected_provider_id()
    active_model = selected_model()
    providers = []
    for provider in list_providers():
        entry = {
            "provider": provider.provider_id,
            "name": provider.display_name,
            "is_local": provider.is_local,
            "configured": provider.configured,
            "default_model": provider.model,
            "selected": provider.provider_id == active_provider,
        }
        config = stored.get(provider.provider_id)
        if config:
            entry["source"] = "settings"
            entry["masked_key"] = mask_key(config.api_key)
            entry["model"] = config.model
        elif provider.configured and not provider.is_local:
            entry["source"] = "environment"
            entry["masked_key"] = mask_key(provider.api_key)
        if entry["selected"] and active_model:
            entry["model"] = active_model
        providers.append(entry)
    return {
        "providers": providers,
        "selected": {"provider": active_provider, "model": active_model}
        if active_provider
        else None,
    }


@router.post("/providers/{provider_id}/connect")
async def connect_provider(
    provider_id: str,
    req: ConnectProviderRequest,
    _: None = Depends(protect_write),
):
    provider_id = provider_id.strip().lower()
    if provider_id not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            400,
            f"Unsupported provider '{provider_id}'. Choose from: {', '.join(SUPPORTED_PROVIDERS)}",
        )
    template = get_provider(provider_id)
    candidate = type(template)(
        api_key=req.api_key.strip(), model=(req.model or template.model).strip()
    )
    status = await candidate.verify()
    if not status.connected:
        raise HTTPException(400, f"{status.name} rejected the API key: {status.message}")
    try:
        models = await candidate.list_models()
    except Exception:
        models = []
    save_runtime_provider_config(provider_id, req.api_key, model=req.model)
    model_dicts = [_model_to_dict(model) for model in models]
    return {
        "provider": provider_id,
        "name": status.name,
        "connected": True,
        "message": status.message,
        "models": rank_models(model_dicts),
        "curated": curate_models(model_dicts),
        "selected": {"provider": provider_id, "model": req.model},
    }


@router.get("/providers/{provider_id}/models")
async def discover_provider_models(provider_id: str):
    provider = get_provider(provider_id.strip().lower())
    if provider is None:
        raise HTTPException(404, f"Unknown provider '{provider_id}'")
    if not provider.configured:
        raise HTTPException(
            400, f"{provider.display_name} is not configured. Connect an API key first."
        )
    try:
        models = await provider.list_models()
    except Exception as error:
        raise HTTPException(
            502, f"Model discovery failed for {provider.display_name}: {error}"
        )
    model_dicts = [_model_to_dict(m) for m in models]
    return {
        "provider": provider.provider_id,
        "models": rank_models(model_dicts),
        "curated": curate_models(model_dicts),
    }


@router.post("/providers/select")
async def select_provider(
    req: SelectProviderRequest,
    _: None = Depends(protect_write),
):
    provider = get_provider(req.provider.strip().lower())
    if provider is None or provider.is_local:
        raise HTTPException(400, f"Unsupported provider '{req.provider}'")
    if not provider.configured and req.provider.strip().lower() not in list_runtime_provider_configs():
        raise HTTPException(
            400, f"{provider.display_name} has no API key. Connect it first."
        )
    select_runtime_provider(req.provider, req.model)
    return {
        "selected": {
            "provider": selected_provider_id(),
            "model": selected_model(),
        }
    }


@router.delete("/providers/{provider_id}")
async def disconnect_provider(
    provider_id: str,
    _: None = Depends(protect_write),
):
    removed = remove_runtime_provider(provider_id)
    return {
        "provider": provider_id.strip().lower(),
        "removed": removed,
        "selected": {"provider": selected_provider_id(), "model": selected_model()},
    }
