from __future__ import annotations

import logging
import time
from typing import Any

import redis as redis_lib
from fastapi import HTTPException, Request

from app.config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token-bucket rate limiter backed by Redis.

    Usage as a FastAPI dependency::

        limiter = RateLimiter(requests_per_minute=30)

        @router.get("/endpoint", dependencies=[Depends(limiter)])
        async def endpoint() -> dict[str, str]:
            ...

    If Redis is unavailable the limiter **fails open** — it logs a warning and
    allows the request through rather than causing a service outage.
    """

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.requests_per_minute = requests_per_minute
        self._client: redis_lib.Redis[Any] | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> redis_lib.Redis[Any] | None:
        """Return a lazily-initialised Redis client, or *None* on error."""
        if self._client is not None:
            return self._client
        try:
            settings = get_settings()
            self._client = redis_lib.Redis.from_url(
                str(settings.redis_url),
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            # Verify connectivity immediately so we fail fast at startup.
            self._client.ping()
        except Exception as exc:  # noqa: BLE001
            logger.warning("RateLimiter: Redis unavailable — failing open. Error: %s", exc)
            self._client = None
        return self._client

    @staticmethod
    def _client_ip(request: Request) -> str:
        """Extract the real client IP, honouring *X-Forwarded-For*."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # The leftmost address is the original client.
            return forwarded_for.split(",")[0].strip()
        host = request.client.host if request.client else "unknown"
        return host

    # ------------------------------------------------------------------
    # FastAPI dependency protocol
    # ------------------------------------------------------------------

    def __call__(self, request: Request) -> None:
        """Increment the per-minute bucket counter and raise 429 if exceeded."""
        client = self._get_client()
        if client is None:
            # Fail open: Redis is down, allow the request.
            return

        ip = self._client_ip(request)
        minute_bucket = int(time.time()) // 60
        key = f"rl:{ip}:{minute_bucket}"

        try:
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            results: list[Any] = pipe.execute()
            count: int = int(results[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning("RateLimiter: Redis error during check — failing open. Error: %s", exc)
            return

        if count > self.requests_per_minute:
            seconds_until_next_minute = 60 - (int(time.time()) % 60)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(seconds_until_next_minute)},
            )
