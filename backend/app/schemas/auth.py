"""Authentication request and response schemas for Phase B7."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for POST /api/auth/register."""
    email: EmailStr = Field(..., description="User email — normalized to lowercase.")
    username: str = Field(..., min_length=2, max_length=50, description="Display username — unique.")
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext password — never stored.")

    model_config = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    """Request body for POST /api/auth/login."""
    email: EmailStr = Field(..., description="Registered email address.")
    password: str = Field(..., min_length=1, max_length=128, description="Account password.")

    model_config = ConfigDict(extra="forbid")


class UserResponse(BaseModel):
    """
    Safe user profile response — NEVER includes password_hash.
    Returned from register, login, and /auth/me endpoints.
    """
    id: str
    email: str
    username: str
    level: int
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class AuthResponse(BaseModel):
    """Response body for register and login endpoints."""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"

    model_config = ConfigDict(from_attributes=True)


class UpdateProfileRequest(BaseModel):
    """Request body for PATCH /api/auth/profile."""
    username: str = Field(
        ...,
        min_length=2,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="New display username (alphanumeric, underscore, hyphen only).",
    )

    model_config = ConfigDict(extra="forbid")


class ChangePasswordRequest(BaseModel):
    """Request body for POST /api/auth/change-password."""
    current_password: str = Field(..., min_length=1, max_length=128, description="Current plaintext password.")
    new_password: str = Field(..., min_length=8, max_length=128, description="New plaintext password (min 8 chars).")

    model_config = ConfigDict(extra="forbid")


class ChangePasswordResponse(BaseModel):
    """Response body for successful password change."""
    success: bool = True
    message: str = "Password changed successfully."

