import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.user import User
from app.models.project import Project
from app.auth.password import hash_password
from app.auth.tokens import create_access_token

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def auth_client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    try:
        user = User(
            email="playtest_tester@example.com",
            username="playtester",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user.id)

        project = Project(
            user_id=user.id,
            title="Playtest Test Project",
            prompt="Cyberpunk action test",
            status="PLAYABLE",
            game_dsl={
                "schema_version": "1.0",
                "metadata": {"title": "Playtest Test Project", "genre": "Action", "description": "Desc", "archetype": "survival"},
                "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250},
            },
            current_version=1,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        with TestClient(app) as client:
            yield client, user, token, project
    finally:
        db.close()


def test_record_and_list_playtests(auth_client):
    client, user, token, project = auth_client
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "duration_seconds": 85,
        # `score` here is deliberately NOT what the server should trust — the
        # authoritative score is derived purely from the scoring events below (2 x 625
        # points = 1250), never from this client-declared field. See
        # PlaytestSummaryEngine's security invariant docstring.
        "score": 999999,
        "damage_taken": 30,
        "damage_dealt": 150,
        "enemies_defeated": 6,
        "collectibles_gathered": 8,
        "objectives_completed": 2,
        "outcome": "WON",
        "telemetry_events": [
            {"type": "SESSION_START", "timestamp": 1234567},
            {"type": "COLLECTIBLE_COLLECTED", "timestamp": 1234600, "data": {"points": 625}},
            {"type": "COLLECTIBLE_COLLECTED", "timestamp": 1234700, "data": {"points": 625}},
        ],
    }

    res = client.post(f"/api/projects/{project.id}/playtests", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["score"] == 1250
    assert data["outcome"] == "WON"
    assert data["project_id"] == project.id
    assert data["user_id"] == user.id

    list_res = client.get(f"/api/projects/{project.id}/playtests", headers=headers)
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) >= 1
    assert sessions[0]["id"] == data["id"]


def test_playtest_idor_protection(auth_client):
    client, user, token, project = auth_client

    db = TestingSessionLocal()
    try:
        other_user = User(
            email="other_tester@example.com",
            username="othertester",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        other_token = create_access_token(other_user.id)
    finally:
        db.close()

    other_headers = {"Authorization": f"Bearer {other_token}"}

    res = client.get(f"/api/projects/{project.id}/playtests", headers=other_headers)
    assert res.status_code == 404
