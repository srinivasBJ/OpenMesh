"""
Runtime provider settings — lets the web UI manage LLM providers without
.env edits or a backend restart.

Architecture: Provider → Model → Agent. Multiple providers can be connected
at once; one (provider, model) pair is "selected" and used by the agent
brain. Keys are persisted under the OpenMesh config directory
(``~/.openmesh`` by default, override with ``OPENMESH_CONFIG_DIR``):

- ``providers.json`` — v2 store: per-provider API keys (Fernet-encrypted
  when the ``cryptography`` package is available, base64-obfuscated
  otherwise), the selected provider/model, and the LLM mode. 0600 perms.
- ``provider.json``  — legacy v1 single-provider file; migrated to v2 on
  first read and left in place.
- ``secret.key``     — locally generated Fernet key, 0600 permissions.

Everything reads this store at call time, so saving a key takes effect
immediately: ``load_provider_settings()`` overlays these values on top of
environment variables, and the provider registry rebuilds providers from
settings on every call.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken

    _FERNET_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional install
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment,misc]
    _FERNET_AVAILABLE = False

STORE_FILE_NAME = "providers.json"
LEGACY_CONFIG_FILE_NAME = "provider.json"
CONFIG_FILE_NAME = LEGACY_CONFIG_FILE_NAME  # backward-compat export
SECRET_FILE_NAME = "secret.key"
SUPPORTED_PROVIDERS = ("anthropic", "openai", "openrouter")

_lock = threading.RLock()


@dataclass(frozen=True)
class RuntimeProviderConfig:
    provider: str
    api_key: str
    model: str | None
    mode: str  # online | auto | offline
    encrypted: bool
    saved_at: str | None


def config_dir() -> Path:
    override = os.getenv("OPENMESH_CONFIG_DIR", "").strip()
    return Path(override).expanduser() if override else Path.home() / ".openmesh"


def _store_path() -> Path:
    return config_dir() / STORE_FILE_NAME


def _legacy_path() -> Path:
    return config_dir() / LEGACY_CONFIG_FILE_NAME


def _secret_path() -> Path:
    return config_dir() / SECRET_FILE_NAME


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, 0o600)


def _fernet() -> "Fernet | None":
    if not _FERNET_AVAILABLE:
        return None
    secret_path = _secret_path()
    if secret_path.exists():
        key = secret_path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _write_private(secret_path, key)
    return Fernet(key)


def _encrypt_key(api_key: str) -> tuple[str, str]:
    """Return (scheme, encoded_value) for the API key at rest."""
    fernet = _fernet()
    if fernet is not None:
        return "fernet", fernet.encrypt(api_key.encode("utf-8")).decode("ascii")
    return "b64", base64.b64encode(api_key.encode("utf-8")).decode("ascii")


def _decrypt_key(scheme: str, value: str) -> str | None:
    try:
        if scheme == "fernet":
            fernet = _fernet()
            if fernet is None:
                return None
            return fernet.decrypt(value.encode("ascii")).decode("utf-8")
        if scheme == "b64":
            return base64.b64decode(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
    return None


# ── Store (v2) ────────────────────────────────────────────────────────────


def _empty_store() -> dict[str, Any]:
    return {"version": 2, "mode": None, "selected": None, "providers": {}}


def _load_store() -> dict[str, Any]:
    with _lock:
        path = _store_path()
        if path.exists():
            try:
                data = json.loads(path.read_text("utf-8"))
                if isinstance(data, dict) and isinstance(data.get("providers"), dict):
                    return data
            except (OSError, json.JSONDecodeError):
                return _empty_store()
            return _empty_store()
        migrated = _migrate_legacy_store()
        return migrated if migrated is not None else _empty_store()


def _save_store(store: dict[str, Any]) -> None:
    with _lock:
        _write_private(
            _store_path(), json.dumps(store, indent=2).encode("utf-8")
        )


def _migrate_legacy_store() -> dict[str, Any] | None:
    """Convert a v1 single-provider file into the v2 multi-provider store."""
    legacy = _legacy_path()
    if not legacy.exists():
        return None
    try:
        data = json.loads(legacy.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    provider = str(data.get("provider", "")).strip().lower()
    key_entry = data.get("api_key") or {}
    if provider not in SUPPORTED_PROVIDERS or not key_entry.get("value"):
        return None
    store = _empty_store()
    store["mode"] = data.get("mode") or "online"
    store["selected"] = {"provider": provider, "model": data.get("model")}
    store["providers"][provider] = {
        "api_key": key_entry,
        "model": data.get("model"),
        "saved_at": data.get("saved_at"),
    }
    _save_store(store)
    return store


def _entry_to_config(
    provider: str, entry: dict[str, Any], mode: str
) -> RuntimeProviderConfig | None:
    key_entry = entry.get("api_key") or {}
    api_key = _decrypt_key(
        str(key_entry.get("scheme", "")), str(key_entry.get("value", ""))
    )
    if not api_key:
        return None
    model = entry.get("model")
    return RuntimeProviderConfig(
        provider=provider,
        api_key=api_key,
        model=str(model).strip() if model else None,
        mode=mode,
        encrypted=key_entry.get("scheme") == "fernet",
        saved_at=entry.get("saved_at"),
    )


def _store_mode(store: dict[str, Any]) -> str:
    mode = str(store.get("mode") or "").strip().lower()
    return mode if mode in {"online", "auto", "offline"} else "online"


# ── Public API ────────────────────────────────────────────────────────────


def list_runtime_provider_configs() -> dict[str, RuntimeProviderConfig]:
    """All providers with stored keys."""
    store = _load_store()
    mode = _store_mode(store)
    configs: dict[str, RuntimeProviderConfig] = {}
    for provider, entry in store["providers"].items():
        if provider not in SUPPORTED_PROVIDERS or not isinstance(entry, dict):
            continue
        config = _entry_to_config(provider, entry, mode)
        if config:
            configs[provider] = config
    return configs


def load_runtime_provider_config() -> RuntimeProviderConfig | None:
    """Config of the selected provider (with a stored key), if any."""
    store = _load_store()
    configs = list_runtime_provider_configs()
    if not configs:
        return None
    selected = store.get("selected") or {}
    provider = str(selected.get("provider") or "").strip().lower()
    if provider in configs:
        config = configs[provider]
        model = selected.get("model") or config.model
        return RuntimeProviderConfig(
            provider=config.provider,
            api_key=config.api_key,
            model=str(model).strip() if model else None,
            mode=config.mode,
            encrypted=config.encrypted,
            saved_at=config.saved_at,
        )
    if len(configs) == 1:
        return next(iter(configs.values()))
    return None


def save_runtime_provider_config(
    provider: str,
    api_key: str,
    model: str | None = None,
    mode: str = "online",
) -> RuntimeProviderConfig:
    provider = provider.strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. Choose from: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key must not be empty")
    scheme, value = _encrypt_key(api_key)
    saved_at = datetime.now(timezone.utc).isoformat()
    with _lock:
        store = _load_store()
        store["mode"] = mode
        store["providers"][provider] = {
            "api_key": {"scheme": scheme, "value": value},
            "model": model.strip() if model else None,
            "saved_at": saved_at,
        }
        store["selected"] = {
            "provider": provider,
            "model": model.strip() if model else None,
        }
        _save_store(store)
    return RuntimeProviderConfig(
        provider=provider,
        api_key=api_key,
        model=model.strip() if model else None,
        mode=mode,
        encrypted=scheme == "fernet",
        saved_at=saved_at,
    )


def select_runtime_provider(provider: str, model: str | None = None) -> None:
    """Choose the active (provider, model) pair for the agent brain."""
    provider = provider.strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'")
    with _lock:
        store = _load_store()
        store["selected"] = {
            "provider": provider,
            "model": model.strip() if model else None,
        }
        if model and provider in store["providers"]:
            store["providers"][provider]["model"] = model.strip()
        _save_store(store)


def remove_runtime_provider(provider: str) -> bool:
    provider = provider.strip().lower()
    with _lock:
        store = _load_store()
        removed = store["providers"].pop(provider, None) is not None
        selected = store.get("selected") or {}
        if selected.get("provider") == provider:
            remaining = next(iter(store["providers"]), None)
            store["selected"] = {"provider": remaining, "model": None} if remaining else None
        if removed:
            _save_store(store)
        return removed


def clear_runtime_provider_config() -> bool:
    """Forget every stored provider (legacy single-provider semantics)."""
    with _lock:
        removed = False
        store_path = _store_path()
        if store_path.exists():
            store_path.unlink()
            removed = True
        legacy = _legacy_path()
        if legacy.exists():
            legacy.unlink()
            removed = True
        return removed


def effective_llm_mode() -> str:
    """Runtime store mode wins over the LLM_MODE env var (default: auto)."""
    store = _load_store()
    if store["providers"] and store.get("mode"):
        return _store_mode(store)
    mode = os.getenv("LLM_MODE", "auto").strip().lower()
    return mode if mode in {"online", "auto", "offline"} else "auto"


def selected_provider_id() -> str | None:
    """Provider explicitly chosen via the UI, if any."""
    store = _load_store()
    selected = store.get("selected") or {}
    provider = str(selected.get("provider") or "").strip().lower()
    if provider in SUPPORTED_PROVIDERS:
        return provider
    configs = list_runtime_provider_configs()
    if len(configs) == 1:
        return next(iter(configs))
    return None


def selected_model() -> str | None:
    store = _load_store()
    selected = store.get("selected") or {}
    model = selected.get("model")
    return str(model).strip() if model else None


def mask_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:4]}…{api_key[-4:]}"


def encryption_available() -> bool:
    return _FERNET_AVAILABLE
