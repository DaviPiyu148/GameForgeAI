"""
JWT access token creation and verification using PyJWT.

Token format (HS256):
  {
    "sub": "<user_uuid>",
    "exp": <unix_timestamp>,
    "type": "access"
  }

SSE credential format (HS256):
  {
    "sub": "<user_uuid>",
    "bid": "<build_id>",
    "exp": <unix_timestamp>,
    "type": "sse"
  }

Security notes:
- Secret loaded from settings.AUTH_JWT_SECRET — never hardcoded.
- Payload contains only: sub (user UUID), exp, type. No sensitive data.
- SSE credentials additionally contain "bid" (build_id) and "type"="sse".
- SSE credentials cannot be used as normal API access tokens (type mismatch).
- Expired tokens raise jwt.ExpiredSignatureError (subclass of InvalidTokenError).
- Tampered tokens raise jwt.InvalidSignatureError (subclass of InvalidTokenError).
- Callers should catch jwt.InvalidTokenError as the base exception.
"""
from datetime import datetime, timezone, timedelta

import jwt

from app.config import settings

# SSE credentials expire after this many seconds (short-lived by design).
_SSE_CREDENTIAL_TTL_SECONDS = 90


def create_access_token(user_id: str) -> str:
    """
    Create a signed JWT access token for the given user UUID.
    Token is valid for AUTH_ACCESS_TOKEN_EXPIRE_MINUTES minutes.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "exp": now + timedelta(minutes=settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed, tampered, or otherwise invalid.

    Returns the decoded payload dict on success.
    """
    payload = jwt.decode(token, settings.AUTH_JWT_SECRET, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type is not 'access'.")
    return payload


def create_sse_token(user_id: str, build_id: str) -> str:
    """
    Create a short-lived SSE credential scoped to a specific build.

    The credential:
    - Expires in _SSE_CREDENTIAL_TTL_SECONDS (90 seconds) — enough for EventSource
      to connect and receive the stream start before it expires.
    - Contains type="sse" so it is rejected by decode_access_token.
    - Is bound to the given build_id — server validates this before streaming.
    - Does NOT grant any normal API access.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "bid": build_id,
        "exp": now + timedelta(seconds=_SSE_CREDENTIAL_TTL_SECONDS),
        "type": "sse",
    }
    return jwt.encode(payload, settings.AUTH_JWT_SECRET, algorithm="HS256")


def decode_sse_token(token: str, expected_build_id: str) -> dict:
    """
    Decode and verify a short-lived SSE credential.

    Validates:
    - Valid signature and not expired.
    - Token type must be "sse" (cannot use normal access tokens).
    - build_id ("bid") must match expected_build_id (prevents cross-build access).

    Raises:
        jwt.ExpiredSignatureError: Credential has expired.
        jwt.InvalidTokenError: Credential is malformed, wrong type, or wrong build.

    Returns the decoded payload dict on success.
    """
    payload = jwt.decode(token, settings.AUTH_JWT_SECRET, algorithms=["HS256"])
    if payload.get("type") != "sse":
        raise jwt.InvalidTokenError("Token type is not 'sse'. Use a dedicated SSE credential.")
    if payload.get("bid") != expected_build_id:
        raise jwt.InvalidTokenError("SSE credential is not valid for this build ID.")
    return payload
