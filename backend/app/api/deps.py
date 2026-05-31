from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import redis as redis_lib
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db

# ---------------------------------------------------------------------------
# Database dependency
# ---------------------------------------------------------------------------

DbSession = Annotated[Session, Depends(get_db)]


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_bearer_scheme),
    ] = None,
) -> None:
    """Validate the Bearer token against ``settings.sync_bearer_token``.

    Raises ``HTTPException(401)`` when the header is absent or the token does
    not match.
    """
    settings = get_settings()
    expected = settings.sync_bearer_token.get_secret_value()

    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


AuthRequired = Annotated[None, Depends(require_auth)]


# ---------------------------------------------------------------------------
# Redis dependency
# ---------------------------------------------------------------------------


def get_redis() -> redis_lib.Redis:
    """Return a Redis client built from settings.redis_url.

    ``from_url`` is lazy; it does not open a socket until first use, so this is
    cheap to construct per request and trivial to override in tests.
    """
    settings = get_settings()
    return redis_lib.Redis.from_url(str(settings.redis_url), decode_responses=True)


RedisClient = Annotated[redis_lib.Redis, Depends(get_redis)]
