"""
Authentication business logic service.

Security invariants:
- Email normalized to lowercase before all operations.
- DuplicateEmailError and DuplicateUsernameError → 409 (not 500).
- Invalid login returns generic error — same message for unknown email AND wrong
  password. This prevents user enumeration attacks.
- password_hash is NEVER returned in any response schema.
- Plaintext passwords are NEVER logged.
"""
from sqlalchemy.orm import Session

from app.auth.password import hash_password, verify_password, validate_password_strength
from app.auth.tokens import create_access_token
from app.models.user import User
from app.repositories.user_repo import UserRepository, user_repository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse


# Generic login failure message — same for unknown email AND wrong password.
# This prevents user enumeration (attacker cannot distinguish the two cases).
_INVALID_CREDENTIALS_MSG = "Invalid email or password."

# Pre-computed valid Argon2 hash used for constant-time dummy verification when
# the login email does not correspond to any registered account.
# This ensures the "unknown email" path runs the full Argon2 KDF, making it
# indistinguishable in timing from the "wrong password" path.
# SECURITY: Do NOT log or expose this value — it is not a real user credential.
_DUMMY_PASSWORD_HASH: str = hash_password("__gameforge_dummy_sentinel_password__")


class DuplicateEmailError(Exception):
    """Raised when a registration email is already in use."""


class DuplicateUsernameError(Exception):
    """Raised when a registration username is already in use."""


class InvalidCredentialsError(Exception):
    """
    Raised when login fails.
    Intentionally opaque — does not reveal whether the email exists.
    """


class AuthService:
    """Business logic for user registration, login, and profile retrieval."""

    def __init__(self, repo: UserRepository = user_repository) -> None:
        self.repo = repo

    def _to_response(self, user: User, token: str) -> AuthResponse:
        """Build an AuthResponse. password_hash is NOT included in UserResponse."""
        user_resp = UserResponse.model_validate(user)
        return AuthResponse(user=user_resp, access_token=token, token_type="bearer")

    def register(self, db: Session, data: RegisterRequest) -> AuthResponse:
        """
        Create a new user account.

        Steps:
          1. Normalize email to lowercase.
          2. Validate password strength (min 8, max 128 chars).
          3. Check for duplicate email → DuplicateEmailError.
          4. Check for duplicate username → DuplicateUsernameError.
          5. Hash password with Argon2 via pwdlib.
          6. Persist User.
          7. Issue JWT access token.
        """
        email_normalized = data.email.lower().strip()
        username_clean = data.username.strip()

        validate_password_strength(data.password)

        if self.repo.get_by_email(db, email_normalized):
            raise DuplicateEmailError("An account with this email address already exists.")

        if self.repo.get_by_username(db, username_clean):
            raise DuplicateUsernameError("This username is already taken.")

        user = User(
            email=email_normalized,
            username=username_clean,
            password_hash=hash_password(data.password),
            level=1,
        )
        saved = self.repo.create(db, user)
        token = create_access_token(saved.id)
        return self._to_response(saved, token)

    def login(self, db: Session, data: LoginRequest) -> AuthResponse:
        """
        Authenticate a user with email + password.

        Returns the same generic error for BOTH unknown email AND wrong password
        to prevent user enumeration.
        """
        email_normalized = data.email.lower().strip()
        user = self.repo.get_by_email(db, email_normalized)

        # Constant-time path: verify password even if user is not found (dummy hash).
        # _DUMMY_PASSWORD_HASH is a valid Argon2 hash pre-computed at module load.
        # This prevents timing attacks from distinguishing missing vs. wrong password.
        if user is None:
            verify_password("dummy_password", _DUMMY_PASSWORD_HASH)
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MSG)

        if not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError(_INVALID_CREDENTIALS_MSG)

        token = create_access_token(user.id)
        return self._to_response(user, token)

    def get_profile(self, user: User) -> UserResponse:
        """Return safe profile data for an already-authenticated user."""
        return UserResponse.model_validate(user)

    def update_username(self, db: Session, user: User, new_username: str) -> UserResponse:
        """
        Update a user's display username.
        Checks for uniqueness against other users.
        """
        clean_username = new_username.strip()
        if len(clean_username) < 2:
            raise ValueError("Username must be at least 2 characters long.")
        if len(clean_username) > 50:
            raise ValueError("Username must not exceed 50 characters.")

        existing = self.repo.get_by_username(db, clean_username)
        if existing and existing.id != user.id:
            raise DuplicateUsernameError("This username is already taken.")

        user.username = clean_username
        db.add(user)
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)

    def change_password(self, db: Session, user: User, current_password: str, new_password: str) -> None:
        """
        Change an authenticated user's password.
        Requires verifying the current password first.
        Validates new password strength before hashing.
        """
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("Current password is incorrect.")

        validate_password_strength(new_password)

        user.password_hash = hash_password(new_password)
        db.add(user)
        db.commit()
        db.refresh(user)


auth_service = AuthService()

