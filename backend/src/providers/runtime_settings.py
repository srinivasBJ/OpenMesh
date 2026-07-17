"""
Runtime provider settings — lets the web UI configure an LLM provider once,
without .env edits or a backend restart.

The selected provider and API key are persisted under the OpenMesh config
directory (``~/.openmesh`` by default, override with ``OPENMESH_CONFIG_DIR``):

- ``provider.json``  — provider choice, model, mode, and the API key
  (encrypted with Fernet when the ``cryptography`` package is available,
  base64-obfuscated otherwise). Written with 0600 permissions.
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

try:
    from cryptography.fernet import Fernet, InvalidToken

    _FERNET_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional install
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment,misc]
    _FERNET_AVAILABLE = False

CONFIG_FILE_NAME = "provider.json"
SECRET_FILE_NAME = "secret.key"
SUPPORTED_PROVIDERS = ("anthropic", "openai", "openrouter")

_lock = threading.Lock()


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


def _config_path() -> Path:
    return config_dir() / CONFIG_FILE_NAME


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


def load_runtime_provider_config() -> RuntimeProviderConfig | None:
    with _lock:
        path = _config_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        provider = str(data.get("provider", "")).strip().lower()
        key_entry = data.get("api_key") or {}
        api_key = _decrypt_key(
            str(key_entry.get("scheme", "")), str(key_entry.get("value", ""))
        )
        if provider not in SUPPORTED_PROVIDERS or not api_key:
            return None
        model = data.get("model")
        return RuntimeProviderConfig(
            provider=provider,
            api_key=api_key,
            model=str(model).strip() if model else None,
            mode=str(data.get("mode", "online")).strip().lower() or "online",
            encrypted=key_entry.get("scheme") == "fernet",
            saved_at=data.get("saved_at"),
        )


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
    payload = {
        "provider": provider,
        "model": model.strip() if model else None,
        "mode": mode,
        "api_key": {"scheme": scheme, "value": value},
        "saved_at": saved_at,
    }
    with _lock:
        _write_private(
            _config_path(), json.dumps(payload, indent=2).encode("utf-8")
        )
    return RuntimeProviderConfig(
        provider=provider,
        api_key=api_key,
        model=model.strip() if model else None,
        mode=mode,
        encrypted=scheme == "fernet",
        saved_at=saved_at,
    )


def clear_runtime_provider_config() -> bool:
    with _lock:
        path = _config_path()
        if path.exists():
            path.unlink()
            return True
        return False


def effective_llm_mode() -> str:
    """Runtime config mode wins over the LLM_MODE env var (default: auto)."""
    config = load_runtime_provider_config()
    if config and config.mode in {"online", "auto", "offline"}:
        return config.mode
    mode = os.getenv("LLM_MODE", "auto").strip().lower()
    return mode if mode in {"online", "auto", "offline"} else "auto"


def selected_provider_id() -> str | None:
    """Provider explicitly chosen via the UI, if any."""
    config = load_runtime_provider_config()
    return config.provider if config else None


def mask_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:4]}…{api_key[-4:]}"


def encryption_available() -> bool:
    return _FERNET_AVAILABLE
