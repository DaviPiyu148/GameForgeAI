import os
import uuid
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB

ALLOWED_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}


def get_avatar_storage_dir() -> str:
    """Resolve and ensure local avatar upload directory exists."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    upload_dir = os.path.join(backend_dir, "data", "uploads", "avatars")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def validate_magic_bytes(content: bytes, mime_type: str) -> bool:
    """Verify image magic byte signatures to prevent malicious payload uploads."""
    if len(content) < 12:
        return False

    if mime_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")

    if mime_type in ("image/jpeg", "image/jpg"):
        return content.startswith(b"\xff\xd8\xff")

    if mime_type == "image/webp":
        return content.startswith(b"RIFF") and content[8:12] == b"WEBP"

    return False


class AvatarService:
    """Service for validating, storing, and serving user profile avatars."""

    @classmethod
    def save_avatar(
        cls,
        db: Session,
        user_id: str,
        file_bytes: bytes,
        content_type: str,
    ) -> Tuple[str, str]:
        """
        Validate, store user profile picture, clean up old file, and update User record.
        Returns (avatar_url, message).
        """
        # 1. Size check
        if len(file_bytes) > MAX_AVATAR_SIZE_BYTES:
            raise ValueError(f"Profile picture exceeds maximum allowed size of 2 MB ({len(file_bytes)} bytes).")

        if len(file_bytes) < 100:
            raise ValueError("Uploaded file is too small to be a valid image.")

        # 2. MIME type check
        norm_mime = content_type.lower().strip()
        if norm_mime not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported image format '{content_type}'. Allowed formats: PNG, JPEG, WebP.")

        # 3. Magic bytes validation
        if not validate_magic_bytes(file_bytes, norm_mime):
            raise ValueError("File content does not match declared image signature.")

        # 4. Cleanup previous avatar file if exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise KeyError("User not found.")

        storage_dir = get_avatar_storage_dir()

        if user.avatar_url:
            old_filename = os.path.basename(user.avatar_url)
            old_path = os.path.join(storage_dir, old_filename)
            if os.path.exists(old_path) and os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except Exception as e:
                    logger.warning(f"Could not remove old avatar file {old_path}: {e}")

        # 5. Generate secure random filename
        ext = ALLOWED_MIME_TYPES[norm_mime]
        safe_filename = f"{uuid.uuid4().hex}{ext}"
        target_path = os.path.join(storage_dir, safe_filename)

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        # 6. Update user avatar_url
        avatar_url = f"/api/auth/avatar/{safe_filename}"
        user.avatar_url = avatar_url
        db.commit()
        db.refresh(user)

        logger.info("Saved avatar for user %s: %s", user_id, safe_filename)
        return avatar_url, "Profile picture uploaded successfully."

    @classmethod
    def delete_avatar(cls, db: Session, user_id: str) -> bool:
        """Remove user profile picture and reset User.avatar_url."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise KeyError("User not found.")

        if user.avatar_url:
            storage_dir = get_avatar_storage_dir()
            old_filename = os.path.basename(user.avatar_url)
            old_path = os.path.join(storage_dir, old_filename)
            if os.path.exists(old_path) and os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except Exception as e:
                    logger.warning(f"Could not remove avatar file {old_path}: {e}")

            user.avatar_url = None
            db.commit()
            return True

        return False

    @classmethod
    def get_avatar_file_path(cls, filename: str) -> Optional[Tuple[str, str]]:
        """
        Safely resolve file path and media type for an avatar filename.
        Guards against directory traversal.
        """
        clean_name = os.path.basename(filename)
        storage_dir = get_avatar_storage_dir()
        target_path = os.path.join(storage_dir, clean_name)

        if not os.path.exists(target_path) or not os.path.isfile(target_path):
            return None

        ext = os.path.splitext(clean_name)[1].lower()
        content_type = "image/png"
        if ext in (".jpg", ".jpeg"):
            content_type = "image/jpeg"
        elif ext == ".webp":
            content_type = "image/webp"

        return target_path, content_type


avatar_service = AvatarService()
