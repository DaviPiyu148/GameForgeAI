"""
Auth API routes (Phase B7).

POST /api/auth/register  → public — create new user account
POST /api/auth/login     → public — authenticate and get JWT token
GET  /api/auth/me        → authenticated — return current user profile

Security notes:
- Rate limiting applied on register and login to slow brute force.
- Generic error message for login (same for unknown email and wrong password).
- password_hash is NEVER returned in any response.
"""
import uuid
import logging
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from app.auth.rate_limit import check_login_rate, check_register_rate
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import (
    AuthService,
    DuplicateEmailError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    auth_service,
)
from app.services.avatar_service import avatar_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _error(code: str, message: str, status_code: int) -> JSONResponse:
    """Produce a structured error envelope consistent with the rest of the API."""
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}},
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    request: Request,
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.
    Rate limit: 5 registrations per IP per hour.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_register_rate(client_ip):
        return _error("RATE_LIMITED", "Too many registration attempts. Please try again later.", 429)

    try:
        result = auth_service.register(db, data)
        return result
    except DuplicateEmailError:
        return _error("EMAIL_ALREADY_EXISTS", "An account with this email address already exists.", 409)
    except DuplicateUsernameError:
        return _error("USERNAME_TAKEN", "This username is already taken.", 409)
    except ValueError as e:
        # Password validation failure (safe user-facing message from validate_password_strength)
        return _error("INVALID_PASSWORD", str(e), 422)
    except Exception:
        logger.exception("Unexpected error during registration")
        return _error("REGISTRATION_FAILED", "Registration failed. Please try again.", 500)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate with email and password.
    Rate limit: 10 attempts per IP per 15 minutes.
    Returns the same generic error for unknown email AND wrong password (prevents enumeration).
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_login_rate(client_ip):
        return _error("RATE_LIMITED", "Too many login attempts. Please try again later.", 429)

    try:
        result = auth_service.login(db, data)
        return result
    except InvalidCredentialsError as e:
        return _error("INVALID_CREDENTIALS", str(e), 401)
    except Exception:
        logger.exception("Unexpected error during login")
        return _error("LOGIN_FAILED", "Login failed. Please try again.", 500)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's profile."""
    return auth_service.get_profile(current_user)


@router.patch("/profile", response_model=UserResponse)
@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated user's display username.
    Validates format, length, and uniqueness across accounts.
    """
    try:
        return auth_service.update_username(db, current_user, data.username)
    except DuplicateUsernameError:
        return _error("USERNAME_TAKEN", "This username is already taken.", 409)
    except ValueError as e:
        return _error("INVALID_USERNAME", str(e), 422)
    except Exception:
        logger.exception("Unexpected error updating profile")
        return _error("UPDATE_FAILED", "Failed to update profile. Please try again.", 500)


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change the authenticated user's password.
    Requires validating current password before applying new password.
    """
    try:
        auth_service.change_password(
            db=db,
            user=current_user,
            current_password=data.current_password,
            new_password=data.new_password,
        )
        return ChangePasswordResponse(success=True, message="Password changed successfully.")
    except InvalidCredentialsError:
        return _error("INCORRECT_PASSWORD", "Current password is incorrect.", 400)
    except ValueError as e:
        return _error("INVALID_PASSWORD", str(e), 422)
    except Exception:
        logger.exception("Unexpected error changing password")
        return _error("CHANGE_PASSWORD_FAILED", "Failed to change password. Please try again.", 500)



@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload or replace user profile avatar image (PNG, JPEG, WebP, max 2MB)."""
    try:
        file_bytes = await file.read()
        content_type = file.content_type or "image/png"
        avatar_url, message = avatar_service.save_avatar(
            db=db,
            user_id=current_user.id,
            file_bytes=file_bytes,
            content_type=content_type,
        )
        return {"avatar_url": avatar_url, "message": message}
    except ValueError as e:
        return _error("INVALID_AVATAR", str(e), 422)
    except Exception as e:
        logger.exception("Error during avatar upload")
        return _error("AVATAR_UPLOAD_FAILED", "Failed to upload avatar image.", 500)


@router.delete("/avatar")
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete custom avatar and revert to default generated placeholder."""
    try:
        avatar_service.delete_avatar(db, current_user.id)
        return {"avatar_url": None, "message": "Profile picture removed successfully."}
    except Exception:
        logger.exception("Error deleting avatar")
        return _error("AVATAR_DELETE_FAILED", "Failed to remove profile picture.", 500)


@router.get("/avatar/{filename}")
async def get_avatar_file(filename: str):
    """Serve uploaded avatar file securely."""
    result = avatar_service.get_avatar_file_path(filename)
    if not result:
        return _error("AVATAR_NOT_FOUND", "Avatar image not found.", 404)

    target_path, content_type = result
    return FileResponse(target_path, media_type=content_type)
