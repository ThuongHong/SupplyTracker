from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
