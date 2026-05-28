from __future__ import annotations

import logging

import redis as redis_lib
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.config import get_settings
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_APP_VERSION = "0.1.0"


@router.get("/health", response_model=HealthResponse)
def health_check(db: DbSession) -> HealthResponse:
    """Probe database and Redis connectivity."""
    # DB probe
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health check: DB probe failed: %s", exc)
        db_status = "error"

    # Redis probe
    redis_status = "ok"
    try:
        settings = get_settings()
        client: redis_lib.Redis[str] = redis_lib.Redis.from_url(  # type: ignore[type-arg]
            str(settings.redis_url),
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health check: Redis probe failed: %s", exc)
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        db=db_status,
        redis=redis_status,
        version=_APP_VERSION,
    )
