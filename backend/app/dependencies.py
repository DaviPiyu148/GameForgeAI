"""
FastAPI dependency providers for GameForge AI.

Includes:
- get_db: SQLAlchemy session dependency (B0)
- get_current_user: JWT-authenticated user dependency (B7)
- get_optional_user: Optional auth dependency for semi-protected endpoints
"""
import uuid
import jwt
from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.auth.tokens import decode_access_token

# OAuth2 Bearer scheme — tokenUrl is the login endpoint path.
# auto_error=False allows optional auth patterns.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _make_401() -> HTTPException:
    """Produce a structured 401 error consistent with the API error envelope."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "UNAUTHORIZED",
            "message": "Invalid or expired authentication token.",
            "request_id": str(uuid.uuid4()),
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency: extract and validate JWT Bearer token from Authorization header, resolve User.
    Bearer tokens in URL query params are strictly prohibited.
    """
    from app.repositories.user_repo import user_repository

    if not token:
        raise _make_401()

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise _make_401()
    except jwt.InvalidTokenError:
        raise _make_401()

    user = user_repository.get_by_id(db, user_id)
    if not user:
        raise _make_401()

    return user


__all__ = ["get_db", "get_current_user"]
