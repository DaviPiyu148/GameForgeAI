import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.tokens import create_access_token
from app.models.user import User


@pytest.fixture
def auth_headers(db_session: Session) -> tuple[dict, User]:
    user = User(
        email="api_profile_user@example.com",
        username="api_profile_user",
        password_hash="fakehash",
        level=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def test_get_progress_and_preferences_api(client: TestClient, auth_headers: tuple[dict, User]):
    headers, user = auth_headers

    # 1. Get Progress
    prog_res = client.get("/api/profile/progress", headers=headers)
    assert prog_res.status_code == 200
    pdata = prog_res.json()
    assert pdata["user_id"] == user.id
    assert pdata["total_xp"] == 0
    assert pdata["current_level"] == 1

    # 2. Get Preferences
    pref_res = client.get("/api/profile/preferences", headers=headers)
    assert pref_res.status_code == 200
    prdata = pref_res.json()
    assert prdata["user_id"] == user.id
    assert not prdata["has_sufficient_data"]


def test_avatar_upload_and_delete_api(client: TestClient, auth_headers: tuple[dict, User]):
    headers, user = auth_headers

    # Valid PNG image bytes (150 bytes)
    png_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 142
    files = {"file": ("avatar.png", io.BytesIO(png_content), "image/png")}

    # Upload avatar
    up_res = client.post("/api/auth/avatar", headers=headers, files=files)
    assert up_res.status_code == 200
    up_data = up_res.json()
    assert "avatar_url" in up_data
    avatar_url = up_data["avatar_url"]
    assert avatar_url.startswith("/api/auth/avatar/")

    # Fetch avatar image file
    file_res = client.get(avatar_url)
    assert file_res.status_code == 200
    assert file_res.headers["content-type"] == "image/png"

    # Check /auth/me reflects avatar_url
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["avatar_url"] == avatar_url

    # Delete avatar
    del_res = client.delete("/api/auth/avatar", headers=headers)
    assert del_res.status_code == 200

    # Check /auth/me reflects null avatar_url
    me_res2 = client.get("/api/auth/me", headers=headers)
    assert me_res2.status_code == 200
    assert me_res2.json()["avatar_url"] is None
