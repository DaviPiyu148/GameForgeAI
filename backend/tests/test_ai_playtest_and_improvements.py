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
def auth_setup():
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
            email="ai_improve_tester@example.com",
            username="improvetester",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user.id)

        project = Project(
            user_id=user.id,
            title="Improvement Test Project",
            prompt="Cyberpunk action test",
            status="PLAYABLE",
            game_dsl={
                "schema_version": "1.0",
                "metadata": {"title": "Improvement Test Project", "genre": "Action", "description": "Desc", "archetype": "survival"},
                "player": {"spawn_x": 400, "spawn_y": 300, "speed": 250},
            },
            current_version=1,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        from app.models.project_version import ProjectVersion
        v1 = ProjectVersion(
            project_id=project.id,
            version_number=1,
            game_dsl=project.game_dsl,
            change_summary="Initial generated prototype",
        )
        db.add(v1)
        db.commit()

        with TestClient(app) as client:
            yield client, user, token, project
    finally:
        db.close()


from unittest.mock import AsyncMock, patch
from app.schemas.playtest import PlaytestAnalysisResponse


def test_analyze_playtest_endpoint(auth_setup):
    client, user, token, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "telemetry": {
            "duration_seconds": 110,
            "score": 850,
            "damage_taken": 45,
            "enemies_defeated": 12,
            "outcome": "WON",
        }
    }

    mock_analysis = PlaytestAnalysisResponse(
        fun_rating=8,
        difficulty_rating=6,
        clarity_rating=9,
        strengths=["Responsive controls", "Engaging progression"],
        problems=[],
        recommendations=[
            {
                "id": "rec_1",
                "category": "mobility",
                "description": "Increase player speed",
                "dsl_change_type": "player_speed",
                "suggested_patch": {"player": {"speed": 290}},
            }
        ],
    )

    with patch("app.services.project_service.project_service.analyze_playtest_session", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_analysis
        res = client.post(f"/api/projects/{project.id}/analyze-playtest", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "fun_rating" in data
        assert "difficulty_rating" in data
        assert "recommendations" in data
        assert len(data["recommendations"]) >= 1


def test_apply_improvements_and_version_bump(auth_setup):
    client, user, token, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    improve_payload = {
        "selected_recommendations": [
            {
                "id": "rec_speed",
                "category": "mobility",
                "description": "Increase player speed to 290 for improved evasion",
                "dsl_change_type": "player_speed",
                "suggested_patch": {"player": {"speed": 290}},
            }
        ],
        "user_notes": "Speed up the player",
    }

    from app.generation.dsl_models import GameDSL
    from app.services.game_generation_service import GenerationResult

    mock_patched_dsl = GameDSL.model_validate({
        "schema_version": "2.0",
        "metadata": {"title": "Improvement Test Project", "genre": "Action", "description": "Desc", "archetype": "survival"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 290},
    })

    with patch("app.services.project_service.game_generation_service.apply_improvements", new_callable=AsyncMock) as mock_apply:
        mock_apply.return_value = GenerationResult(success=True, dsl=mock_patched_dsl, attempts_used=1)
        res = client.post(f"/api/projects/{project.id}/improvements", json=improve_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert (data.get("newVersionNumber") or data.get("versionNumber") or data.get("version_number")) == 2
        dsl_res = data.get("gameDsl") or data.get("game_dsl")
        assert dsl_res["player"]["speed"] == 290

        # Verify version listing
        ver_res = client.get(f"/api/projects/{project.id}/versions", headers=headers)
        assert ver_res.status_code == 200
        versions = ver_res.json()
        assert len(versions) >= 2
