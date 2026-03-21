"""
Security helpers for write endpoint protection and basic rate limiting.
"""
from collections import defaultdict, deque
from hashlib import sha256
import hmac
import os
from threading import Lock
from time import monotonic
from typing import Deque, Dict, Optional, Tuple

from fastapi import HTTPException, Request


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
REQUIRE_WRITE_API_KEY = _env_bool("REQUIRE_WRITE_API_KEY", ENVIRONMENT == "production")
WRITE_API_KEY = os.getenv("WRITE_API_KEY", os.getenv("ADMIN_API_KEY", "")).strip()

WRITE_RATE_LIMIT_ENABLED = _env_bool("WRITE_RATE_LIMIT_ENABLED", True)
WRITE_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("WRITE_RATE_LIMIT_WINDOW_SECONDS", "60"))
WRITE_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("WRITE_RATE_LIMIT_MAX_REQUESTS", "30"))


class SlidingWindowRateLimiter:
    def __init__(self):
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        now = monotonic()
        with self._lock:
            q = self._events[key]
            cutoff = now - window_seconds
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - q[0])))
                return False, retry_after

            q.append(now)
            return True, 0


_write_limiter = SlidingWindowRateLimiter()


def _extract_api_key(request: Request) -> Optional[str]:
    x_api_key = request.headers.get("x-api-key")
    if x_api_key:
        return x_api_key.strip()

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    return None


def _client_identity(request: Request) -> str:
    provided = _extract_api_key(request)
    if provided:
        key_hash = sha256(provided.encode("utf-8")).hexdigest()[:16]
        return f"key:{key_hash}"
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


async def enforce_write_rate_limit(request: Request):
    if not WRITE_RATE_LIMIT_ENABLED:
        return

    allow, retry_after = _write_limiter.allow(
        key=f"{_client_identity(request)}:write",
        max_requests=WRITE_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=WRITE_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not allow:
        raise HTTPException(
            status_code=429,
            detail="Write rate limit exceeded. Please retry shortly.",
            headers={"Retry-After": str(retry_after)},
        )


async def require_write_access(request: Request):
    if not REQUIRE_WRITE_API_KEY:
        return
    if not WRITE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: write key enforcement is enabled but WRITE_API_KEY is missing.",
        )

    provided = _extract_api_key(request)
    if not provided or not hmac.compare_digest(provided, WRITE_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized write request. Provide x-api-key or Authorization: Bearer <key>.",
        )


async def protect_write(request: Request):
    await enforce_write_rate_limit(request)
    await require_write_access(request)


def security_status() -> dict:
    return {
        "environment": ENVIRONMENT,
        "require_write_api_key": REQUIRE_WRITE_API_KEY,
        "write_key_configured": bool(WRITE_API_KEY),
        "write_rate_limit_enabled": WRITE_RATE_LIMIT_ENABLED,
        "write_rate_limit_max_requests": WRITE_RATE_LIMIT_MAX_REQUESTS,
        "write_rate_limit_window_seconds": WRITE_RATE_LIMIT_WINDOW_SECONDS,
    }

