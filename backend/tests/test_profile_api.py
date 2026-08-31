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


def test_update_username_api(client: TestClient, auth_headers: tuple[dict, User], db_session: Session):
    headers, user = auth_headers

    # Create another user to test uniqueness collision
    other = User(email="other_unique@example.com", username="taken_name", password_hash="fake", level=1)
    db_session.add(other)
    db_session.commit()

    # 1. Successful update
    res = client.patch("/api/auth/profile", headers=headers, json={"username": "new_handle_42"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "new_handle_42"

    # Verify persistence via /auth/me
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "new_handle_42"

    # 2. Collision with taken username
    res_dup = client.patch("/api/auth/profile", headers=headers, json={"username": "taken_name"})
    assert res_dup.status_code == 409
    assert res_dup.json()["error"]["code"] == "USERNAME_TAKEN"

    # 3. Invalid characters
    res_inv = client.patch("/api/auth/profile", headers=headers, json={"username": "invalid space name!"})
    assert res_inv.status_code == 422

    # 4. Unauthenticated
    res_unauth = client.patch("/api/auth/profile", json={"username": "sneaky"})
    assert res_unauth.status_code == 401


def test_change_password_api(client: TestClient, db_session: Session):
    from app.auth.password import hash_password

    # Create user with known password
    user = User(email="pwd_tester@example.com", username="pwd_tester", password_hash=hash_password("OldPassword123!"), level=1)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Wrong current password -> 400
    res_wrong = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "WrongPassword123!", "new_password": "NewValidPassword123!"},
    )
    assert res_wrong.status_code == 400
    assert res_wrong.json()["error"]["code"] == "INCORRECT_PASSWORD"

    # 2. Weak new password -> 422
    res_weak = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "OldPassword123!", "new_password": "short"},
    )
    assert res_weak.status_code == 422

    # 3. Successful password change
    res_ok = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "OldPassword123!", "new_password": "NewValidPassword123!"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["success"] is True

    # 4. Verify login succeeds with new password and fails with old password
    login_new = client.post("/api/auth/login", json={"email": "pwd_tester@example.com", "password": "NewValidPassword123!"})
    assert login_new.status_code == 200

    login_old = client.post("/api/auth/login", json={"email": "pwd_tester@example.com", "password": "OldPassword123!"})
    assert login_old.status_code == 401

