from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.openmesh_events import list_openmesh_events
from ..providers import discover_local_providers, list_local_models


LOCAL_PROVIDER_IDS = {"ollama", "lmstudio", "vllm"}


async def get_local_llm_metrics(
    db: AsyncSession, *, limit: int = 5000
) -> dict[str, Any]:
    records = await list_openmesh_events(db, limit=limit)
    providers = await discover_local_providers()
    live_models = await list_local_models()

    observed_models: dict[str, dict[str, Any]] = {}
    latencies: list[float] = []
    tokens_per_second: list[float] = []

    for record in records:
        payload = record.payload_json or {}
        metrics = record.metrics_json or {}
        provider = str(payload.get("provider") or "").lower()
        is_local = bool(payload.get("local")) or provider in LOCAL_PROVIDER_IDS

        for node in (record.source_json, record.target_json):
            if node and node.get("node_type") == "model":
                metadata = node.get("metadata") or {}
                if metadata.get("local") or metadata.get("provider") in LOCAL_PROVIDER_IDS:
                    observed_models[node["node_id"]] = {
                        "id": node["node_id"],
                        "name": node.get("name") or node["node_id"],
                        "provider": metadata.get("provider"),
                        "endpoint": metadata.get("endpoint"),
                        "last_seen": record.timestamp.isoformat() + "Z",
                    }

        if record.event_type == "llm.response" and is_local:
            latency = metrics.get("latency_ms")
            if isinstance(latency, int | float):
                latencies.append(float(latency))
            tps = metrics.get("tokens_per_second")
            if isinstance(tps, int | float):
                tokens_per_second.append(float(tps))

    live_model_rows = [
        {
            "id": f"model:{model.provider}:{_stable_id(model.model)}",
            "name": model.model,
            "provider": model.provider,
            "endpoint": model.endpoint,
            "metadata": model.metadata,
        }
        for model in live_models
    ]
    model_ids = {model["id"] for model in live_model_rows} | set(observed_models)
    connected = [provider for provider in providers if provider.connected]
    provider_rows = [
        {
            "provider": provider.provider,
            "name": provider.name,
            "endpoint": provider.endpoint,
            "connected": provider.connected,
            "status": provider.status,
            "message": provider.message,
        }
        for provider in providers
    ]

    return {
        "providers": provider_rows,
        "models": live_model_rows or list(observed_models.values()),
        "active_model_count": len(model_ids),
        "average_latency_ms": round(mean(latencies), 2) if latencies else None,
        "average_tokens_per_second": round(mean(tokens_per_second), 2)
        if tokens_per_second
        else None,
        "provider_uptime": {
            "connected": len(connected),
            "total": len(providers),
            "ratio": round(len(connected) / len(providers), 2) if providers else 0,
        },
        "observed_response_count": len(latencies),
    }


def _stable_id(value: str) -> str:
    return (
        "".join(character.lower() if character.isalnum() else "-" for character in value)
        .strip("-")
        .replace("--", "-")
        or "model"
    )
