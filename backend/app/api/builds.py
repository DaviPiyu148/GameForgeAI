"""
Builds API router with B7 ownership enforcement.

All routes require authentication via get_current_user().
user_id is sourced exclusively from the JWT token — never from request body.

IDOR protection: owner mismatch on GET/SSE returns 404 (not 403).

SSE authentication protocol:
  1. Client requests a short-lived SSE credential via:
       POST /builds/{build_id}/sse-token   (requires normal Authorization header)
  2. Server returns {"sse_token": "<90-second scoped credential>"}
  3. Client opens EventSource with ?sse_token=<credential>
  4. Server validates the SSE credential (type=sse, bid=build_id, not expired).

This prevents the full JWT bearer token from appearing in server access logs.
"""
import uuid
import jwt
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.build import (
    BuildCreate,
    BuildLogListResponse,
    BuildResponse,
)
from app.services.build_service import (
    BuildNotFoundError,
    BuildService,
    build_service,
)
from app.auth.tokens import create_sse_token, decode_sse_token, decode_access_token
from app.repositories.user_repo import user_repository

router = APIRouter(prefix="/builds", tags=["builds"])


def make_error_response(code: str, message: str, status_code: int) -> JSONResponse:
    """Helper to return consistent structured error envelopes."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@router.post(
    "",
    response_model=BuildResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new asynchronous Game Build job",
)
async def create_build(
    data: BuildCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: BuildService = Depends(lambda: build_service),
) -> BuildResponse:
    """Queue a new build job and trigger async execution. user_id from JWT."""
    return await service.submit_build(db, data, user_id=current_user.id)


@router.get(
    "/{build_id}",
    response_model=BuildResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authoritative status of a Build Job",
)
def get_build(
    build_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: BuildService = Depends(lambda: build_service),
) -> BuildResponse:
    """Retrieve build job status. Returns 404 if not found or not owned by requester."""
    try:
        return service.get_build(db, build_id, user_id=current_user.id)
    except BuildNotFoundError as e:
        return make_error_response("BUILD_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.get(
    "/{build_id}/logs",
    response_model=BuildLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get persisted logs for a Build Job",
)
def get_build_logs(
    build_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: BuildService = Depends(lambda: build_service),
) -> BuildLogListResponse:
    """Retrieve all persisted logs. Returns 404 if not found or not owned by requester."""
    try:
        return service.get_logs(db, build_id, user_id=current_user.id)
    except BuildNotFoundError as e:
        return make_error_response("BUILD_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore


@router.post(
    "/{build_id}/sse-token",
    status_code=status.HTTP_200_OK,
    summary="Issue a short-lived SSE credential scoped to this build",
)
async def get_sse_token(
    build_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: BuildService = Depends(lambda: build_service),
) -> JSONResponse:
    """
    Issue a 90-second SSE credential scoped to this build and user.

    The client should:
    1. Call this endpoint (with normal Authorization: Bearer header).
    2. Use the returned sse_token as ?sse_token= on the EventSource URL.
    3. Open the EventSource — the server will validate the short-lived credential.

    This prevents the user's long-lived JWT from appearing in server access logs.
    """
    try:
        # Ownership check: user must own this build before we issue an SSE credential.
        service.get_build(db, build_id, user_id=current_user.id)
    except BuildNotFoundError as e:
        return make_error_response("BUILD_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)

    sse_token = create_sse_token(user_id=current_user.id, build_id=build_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"sse_token": sse_token, "expires_in_seconds": 90},
    )


_sse_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


@router.get(
    "/{build_id}/events",
    summary="Stream live logs and status events via SSE",
    response_class=StreamingResponse,
)
async def stream_build_events(
    build_id: str,
    sse_token: str | None = None,
    header_token: str | None = Depends(_sse_oauth2_scheme),
    db: Session = Depends(get_db),
    service: BuildService = Depends(lambda: build_service),
):
    """
    Server-Sent Events stream. Replays historical logs first, then streams live events.

    Authentication: requires a short-lived SSE credential obtained from
    POST /builds/{build_id}/sse-token  (NOT the normal JWT access token in URL).
    Clients with header support (like test runners) may also pass Authorization: Bearer <token>.

    Returns 401 if the credential is missing/invalid/expired.
    Returns 404 if not found or not owned by requester (IDOR protection).
    """
    user_id: Optional[str] = None

    if sse_token:
        # Validate the short-lived SSE credential.
        try:
            payload = decode_sse_token(sse_token, expected_build_id=build_id)
            user_id = payload.get("sub", "")
            if not user_id:
                raise jwt.InvalidTokenError("SSE credential missing subject claim.")
        except jwt.ExpiredSignatureError:
            return make_error_response(
                "SSE_CREDENTIAL_EXPIRED",
                "The SSE credential has expired. Request a new one from POST /builds/{id}/sse-token.",
                status.HTTP_401_UNAUTHORIZED,
            )
        except jwt.InvalidTokenError as e:
            return make_error_response(
                "SSE_CREDENTIAL_INVALID",
                f"Invalid SSE credential: {e}",
                status.HTTP_401_UNAUTHORIZED,
            )
    elif header_token:
        # Validate Bearer header token
        try:
            payload = decode_access_token(header_token)
            user_id = payload.get("sub", "")
            if not user_id:
                raise jwt.InvalidTokenError("Access token missing subject claim.")
        except jwt.ExpiredSignatureError:
            return make_error_response(
                "TOKEN_EXPIRED",
                "Authentication token has expired.",
                status.HTTP_401_UNAUTHORIZED,
            )
        except jwt.InvalidTokenError as e:
            return make_error_response(
                "UNAUTHORIZED",
                f"Invalid authentication token: {e}",
                status.HTTP_401_UNAUTHORIZED,
            )
    else:
        return make_error_response(
            "SSE_CREDENTIAL_REQUIRED",
            "A short-lived SSE credential is required in ?sse_token=. Obtain one from POST /builds/{id}/sse-token.",
            status.HTTP_401_UNAUTHORIZED,
        )

    # Verify the user still exists and owns this build.
    user = user_repository.get_by_id(db, user_id)
    if not user:
        return make_error_response("UNAUTHORIZED", "User not found.", status.HTTP_401_UNAUTHORIZED)

    try:
        service.get_build(db, build_id, user_id=user_id)
    except BuildNotFoundError as e:
        return make_error_response("BUILD_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)

    return StreamingResponse(
        service.stream_events(build_id, user_id=user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{build_id}/cancel",
    response_model=BuildResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel an active Build Job",
)
async def cancel_build(
    build_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: BuildService = Depends(lambda: build_service),
) -> BuildResponse:
    """
    Cancel an active build job.
    Transitions QUEUED/RUNNING/VALIDATING -> CANCELLED, aborts generation,
    and returns authoritative updated BuildJob.
    Owner mismatch returns 404 (IDOR protection).
    """
    try:
        return await service.cancel_build(db, build_id, user_id=current_user.id)
    except BuildNotFoundError as e:
        return make_error_response("BUILD_NOT_FOUND", str(e), status.HTTP_404_NOT_FOUND)  # type: ignore

