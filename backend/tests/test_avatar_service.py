import io
import pytest
from sqlalchemy.orm import Session
from app.models.user import User
from app.services.avatar_service import avatar_service, validate_magic_bytes


@pytest.fixture
def avatar_user(db_session: Session) -> User:
    user = User(
        email="avatar_user@example.com",
        username="avatar_user",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_magic_bytes_validation():
    """Verify image magic bytes security checks."""
    # Valid PNG header
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert validate_magic_bytes(png_bytes, "image/png")

    # Fake PNG (wrong header)
    fake_png = b"FAKE_PNG_HEADER" + b"\x00" * 20
    assert not validate_magic_bytes(fake_png, "image/png")

    # Valid JPEG header
    jpg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    assert validate_magic_bytes(jpg_bytes, "image/jpeg")

    # Valid WebP header
    webp_bytes = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20
    assert validate_magic_bytes(webp_bytes, "image/webp")


def test_save_and_delete_avatar(db_session: Session, avatar_user: User):
    """Verify avatar saving, DB URL update, and deletion cleanup."""
    valid_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 150

    avatar_url, msg = avatar_service.save_avatar(
        db=db_session,
        user_id=avatar_user.id,
        file_bytes=valid_png,
        content_type="image/png",
    )

    assert avatar_url.startswith("/api/auth/avatar/")
    db_session.refresh(avatar_user)
    assert avatar_user.avatar_url == avatar_url

    # Check file exists and can be retrieved
    filename = avatar_url.split("/")[-1]
    path_info = avatar_service.get_avatar_file_path(filename)
    assert path_info is not None
    target_path, c_type = path_info
    assert c_type == "image/png"

    # Delete avatar
    deleted = avatar_service.delete_avatar(db_session, avatar_user.id)
    assert deleted
    db_session.refresh(avatar_user)
    assert avatar_user.avatar_url is None

    # Verify file was cleaned up from disk
    path_info_after = avatar_service.get_avatar_file_path(filename)
    assert path_info_after is None


def test_oversized_avatar_rejected(db_session: Session, avatar_user: User):
    """Verify files larger than 2MB are rejected."""
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 100)
    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        avatar_service.save_avatar(
            db=db_session,
            user_id=avatar_user.id,
            file_bytes=oversized,
            content_type="image/png",
        )
