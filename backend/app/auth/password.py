"""
Password hashing and validation using pwdlib with Argon2.

Security properties:
- Argon2id variant (resistant to GPU and side-channel attacks)
- Work factors: pwdlib defaults (memory=65536 KiB, time=2, parallelism=1)
- Hash stored as opaque string; plaintext is never stored or logged

Password requirements:
- Minimum 8 characters (usable without frustration)
- Maximum 128 characters (prevent DoS via extremely long passwords)
"""
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# Module-level hasher — reused across the application lifecycle.
_hasher = PasswordHash([Argon2Hasher()])


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2. Returns an opaque hash string."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    return _hasher.verify(plain, hashed)


def validate_password_strength(plain: str) -> None:
    """
    Validate password meets minimum requirements.
    Raises ValueError with a safe, user-facing message on failure.
    Does NOT log the password value.
    """
    if len(plain) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(plain) > 128:
        raise ValueError("Password must not exceed 128 characters.")
