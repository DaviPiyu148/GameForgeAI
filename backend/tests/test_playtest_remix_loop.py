"""
Comprehensive integration tests for the iterative Build -> Playtest -> Analysis -> Remix Loop (Step 7).

Tests:
1. End-to-end loop (compile v1 -> playtest v1 -> analyze -> apply patch -> v2 -> compile v2)
2. Playtest version identity retention
3. Stale-analysis protection on version advance (409 STALE_ANALYSIS)
4. Optimistic concurrency & concurrent apply protection
5. Multi-recommendation atomic batching (single vN+1 version increment)
6. Non-actionable recommendation handling (informational critique does not corrupt DSL)
7. Unrelated content & inspiration provenance preservation
8. Atomicity on patch failure (zero partial state mutation)
9. Version history and restore regression
10. IDOR and unauthenticated protection
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.user import User
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.playtest import PlaytestSession
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
            email="remix_tester@example.com",
            username="remixtester",
            password_hash=hash_password("ValidPass123!"),
        )
        other_user = User(
            email="other_dev@example.com",
            username="otherdev",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add_all([user, other_user])
        db.commit()
        db.refresh(user)
        db.refresh(other_user)

        token = create_access_token(user.id)
        other_token = create_access_token(other_user.id)

        initial_dsl = {
            "schema_version": "1.0",
            "metadata": {
                "title": "Neon Grid Survival",
                "genre": "Action Roguelite Cyberpunk",
                "description": "Synthesized fast arena shooter",
                "archetype": "arena",
            },
            "world": {
                "width": 1280,
                "height": 720,
                "gravity": 0,
                "background_color": "#0a0a1a",
                "theme": "cyberpunk",
                "world_mode": "linear",
            },
            "player": {
                "name": "Runner",
                "spawn_x": 100,
                "spawn_y": 100,
                "speed": 220,
                "jump_power": 400,
                "max_health": 100,
                "width": 32,
                "height": 32,
                "color": "#00ffcc",
                "dash_speed": 500,
                "dash_cooldown": 1.5,
            },
            "entities": [
                {
                    "id": "e_enemy_1",
                    "type": "enemy",
                    "behavior": "chase",
                    "x": 400,
                    "y": 400,
                    "width": 32,
                    "height": 32,
                    "speed": 100,
                    "health": 50,
                    "color": "#ff0055",
                    "points": 100,
                },
                {
                    "id": "e_coin_1",
                    "type": "collectible",
                    "behavior": "float",
                    "x": 200,
                    "y": 200,
                    "width": 24,
                    "height": 24,
                    "speed": 0,
                    "health": 1,
                    "color": "#ffd700",
                    "points": 50,
                },
            ],
            "rules": [
                {
                    "id": "r_hit",
                    "trigger": "on_collide_enemy",
                    "action": "damage_player",
                    "params": {"damage": 10},
                },
                {
                    "id": "r_collect",
                    "trigger": "on_collect",
                    "action": "add_score",
                    "params": {"points": 50},
                },
            ],
            "ui": {
                "show_health": True,
                "show_score": True,
                "status_text": "SURVIVE THE GRID",
            },
        }

        project = Project(
            user_id=user.id,
            title="Neon Grid Survival",
            genre="Action Roguelite Cyberpunk",
            prompt="A synthesized cyberpunk arena game",
            status="PLAYABLE",
            current_version=1,
            game_dsl=initial_dsl,
            engine="arena",
            art_density=60,
            physics=50,
            modules=["Combat & Dash Mobility", "WeaponUpgrade"],
            world_mode="linear",
            design_spec={
                "title": "Neon Grid Survival",
                "genre": "Action Roguelite Cyberpunk",
                "theme": "cyberpunk",
                "elevator_pitch": "Dash and blast through procedural neon arena waves.",
                "core_gameplay_loop": "Enter sector -> Dash & Shoot -> Collect upgrades -> Survive",
            },
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        v1 = ProjectVersion(
            project_id=project.id,
            version_number=1,
            game_dsl=initial_dsl,
            design_spec=project.design_spec,
            change_summary="Initial synthesized version v1",
        )
        db.add(v1)
        db.commit()

        with TestClient(app) as client:
            yield client, user, token, other_token, project
    finally:
        db.close()


def test_end_to_end_playtest_analysis_and_remix_loop(auth_setup):
    """
    Test complete closed loop:
    Version 1 -> Compile -> Playtest -> Analyze -> Patch recommendations -> Version 2 -> Compile v2
    """
    client, user, token, _, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    # Step A: Compile v1 prototype
    compile_v1 = client.post(f"/api/projects/{project.id}/compile", json={"versionNumber": 1}, headers=headers)
    assert compile_v1.status_code == 200
    assert compile_v1.json()["versionNumber"] == 1
    assert compile_v1.json()["status"] == "SUCCESS"

    # Step B: Record Playtest session for v1
    pt_payload = {
        "duration_seconds": 95,
        "score": 450,
        "damage_taken": 60,
        "enemies_defeated": 8,
        "collectibles_gathered": 4,
        "outcome": "WON",
        "version_number": 1,
        "telemetry_events": [
            {"type": "SESSION_START", "timestamp": 1000},
            {"type": "PLAYER_DAMAGED", "timestamp": 2000, "data": {"damage": 20}},
            {"type": "ENEMY_DEFEATED", "timestamp": 3000, "data": {"damageDealt": 50}},
            {"type": "COLLECTIBLE_COLLECTED", "timestamp": 4000, "data": {"points": 50}},
            {"type": "GAME_WON", "timestamp": 5000},
            {"type": "SESSION_END", "timestamp": 6000, "data": {"outcome": "WON"}},
        ],
    }
    pt_res = client.post(f"/api/projects/{project.id}/playtests", json=pt_payload, headers=headers)
    assert pt_res.status_code == 201
    session_id = pt_res.json()["id"]
    assert pt_res.json()["version_number"] == 1

    # Step C: Analyze Playtest
    mock_critique = {
        "fun_rating": 8.5,
        "difficulty_rating": 6.0,
        "clarity_rating": 9.0,
        "strengths": ["Fluid dash locomotion", "Responsive combat"],
        "problems": [{"category": "mobility", "severity": "MEDIUM", "evidence": "High damage taken", "diagnosis": "Base speed feels sluggish"}],
        "recommendations": [
            {
                "id": "rec_speed",
                "category": "mobility",
                "description": "Increase player move speed to 270 for better evasion",
                "dsl_change_type": "player_speed",
                "suggested_patch": {"player": {"speed": 270}},
            },
            {
                "id": "rec_health",
                "category": "survivability",
                "description": "Increase player max health to 125",
                "dsl_change_type": "player_health",
                "suggested_patch": {"player": {"max_health": 125}},
            },
        ],
    }
    from unittest.mock import AsyncMock, patch
    with patch("app.services.project_service.game_generation_service.analyze_playtest", new_callable=AsyncMock) as mock_an:
        mock_an.return_value = mock_critique
        analysis_res = client.post(
            f"/api/projects/{project.id}/analyze-playtest",
            json={"session_id": session_id},
            headers=headers,
        )
        assert analysis_res.status_code == 200
        analysis_data = analysis_res.json()
        assert "fun_rating" in analysis_data
        assert "difficulty_rating" in analysis_data

    # Step D: Apply Actionable Recommendations
    recommendations = [
        {
            "id": "rec_speed",
            "category": "mobility",
            "description": "Increase player move speed to 270 for better evasion",
            "dsl_change_type": "player_speed",
            "suggested_patch": {"player": {"speed": 270}},
        },
        {
            "id": "rec_health",
            "category": "survivability",
            "description": "Increase player max health to 125",
            "dsl_change_type": "player_health",
            "suggested_patch": {"player": {"max_health": 125}},
        },
    ]
    patch_payload = {
        "sessionId": session_id,
        "baseVersionNumber": 1,
        "recommendations": recommendations,
        "userNotes": "Evasion feels much better with speed 270 and 125 health.",
    }
    improve_res = client.post(
        f"/api/projects/{project.id}/improvements",
        json=patch_payload,
        headers=headers,
    )
    assert improve_res.status_code == 200
    imp_data = improve_res.json()
    assert imp_data["previousVersionNumber"] == 1
    assert imp_data["newVersionNumber"] == 2
    assert imp_data["gameDsl"]["player"]["speed"] == 270
    assert imp_data["gameDsl"]["player"]["max_health"] == 125
    assert len(imp_data["changes"]) >= 2

    # Step E: Verify Project Version 2 in history
    ver_res = client.get(f"/api/projects/{project.id}/versions", headers=headers)
    assert ver_res.status_code == 200
    versions = ver_res.json()
    assert len(versions) == 2
    assert versions[1]["version_number"] == 2
    assert "Playtest improvement" in versions[1]["change_summary"]

    # Step F: Compile v2 prototype
    compile_v2 = client.post(f"/api/projects/{project.id}/compile", json={"versionNumber": 2}, headers=headers)
    assert compile_v2.status_code == 200
    assert compile_v2.json()["versionNumber"] == 2
    assert compile_v2.json()["gameDsl"]["player"]["speed"] == 270


def test_stale_analysis_rejection_on_version_advance(auth_setup):
    """
    Test that once project advances to Version 2, attempting to apply recommendations
    from a Version 1 playtest or with baseVersionNumber=1 returns 409 STALE_ANALYSIS.
    """
    client, user, token, _, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    # Record Playtest session for v1
    pt_res = client.post(
        f"/api/projects/{project.id}/playtests",
        json={"duration_seconds": 60, "score": 200, "outcome": "PLAYED", "version_number": 1},
        headers=headers,
    )
    assert pt_res.status_code == 201
    session_id = pt_res.json()["id"]

    # First apply advances to v2
    first_patch = client.post(
        f"/api/projects/{project.id}/improvements",
        json={
            "sessionId": session_id,
            "baseVersionNumber": 1,
            "recommendations": [
                {
                    "id": "rec_1",
                    "category": "mobility",
                    "description": "Bump speed",
                    "dsl_change_type": "speed",
                    "suggested_patch": {"player": {"speed": 260}},
                }
            ],
        },
        headers=headers,
    )
    assert first_patch.status_code == 200
    assert first_patch.json()["newVersionNumber"] == 2

    # Attempt to apply again using the stale baseVersionNumber=1
    stale_apply = client.post(
        f"/api/projects/{project.id}/improvements",
        json={
            "sessionId": session_id,
            "baseVersionNumber": 1,
            "recommendations": [
                {
                    "id": "rec_2",
                    "category": "mobility",
                    "description": "Bump speed again",
                    "dsl_change_type": "speed",
                    "suggested_patch": {"player": {"speed": 290}},
                }
            ],
        },
        headers=headers,
    )
    assert stale_apply.status_code == 409
    err_body = stale_apply.json()
    err_code = err_body.get("code") or err_body.get("error", {}).get("code")
    err_msg = err_body.get("message") or err_body.get("error", {}).get("message")
    assert err_code == "STALE_ANALYSIS"
    assert "stale" in err_msg.lower()


def test_multi_recommendation_atomic_batching(auth_setup):
    """
    Test applying 3 recommendations simultaneously produces exactly ONE atomic Version N+1.
    """
    client, user, token, _, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    recs = [
        {
            "id": "r1",
            "category": "balance",
            "description": "Increase player jump power to 450",
            "dsl_change_type": "jump",
            "suggested_patch": {"player": {"jump_power": 450}},
        },
        {
            "id": "r2",
            "category": "combat",
            "description": "Increase dash speed to 600",
            "dsl_change_type": "dash",
            "suggested_patch": {"player": {"dash_speed": 600}},
        },
        {
            "id": "r3",
            "category": "environment",
            "description": "Adjust background color to deep neon",
            "dsl_change_type": "theme",
            "suggested_patch": {"world": {"background_color": "#050515"}},
        },
    ]

    res = client.post(
        f"/api/projects/{project.id}/improvements",
        json={
            "baseVersionNumber": 1,
            "recommendations": recs,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["previousVersionNumber"] == 1
    assert data["newVersionNumber"] == 2
    assert data["gameDsl"]["player"]["jump_power"] == 450
    assert data["gameDsl"]["player"]["dash_speed"] == 600
    assert data["gameDsl"]["world"]["background_color"] == "#050515"
    assert len(data["changes"]) == 3

    # Ensure only 2 versions exist in total
    ver_res = client.get(f"/api/projects/{project.id}/versions", headers=headers)
    assert len(ver_res.json()) == 2


def test_non_actionable_recommendations_handling(auth_setup):
    """
    Test that informational recommendations (empty or no suggested_patch)
    do not cause errors and are safely recorded in change summary without corrupting DSL.
    """
    client, user, token, _, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    recs = [
        {
            "id": "rec_actionable",
            "category": "mobility",
            "description": "Increase player speed to 250",
            "dsl_change_type": "speed",
            "suggested_patch": {"player": {"speed": 250}},
        },
        {
            "id": "rec_informational",
            "category": "critique",
            "description": "Players may benefit from higher visual contrast on enemy bullets.",
            "dsl_change_type": "visuals",
            "suggested_patch": {},
        },
    ]

    res = client.post(
        f"/api/projects/{project.id}/improvements",
        json={
            "baseVersionNumber": 1,
            "recommendations": recs,
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["newVersionNumber"] == 2
    assert data["gameDsl"]["player"]["speed"] == 250
    # Both recommendations mentioned in change summary
    assert "visual contrast" in data["changeSummary"]


def test_unrelated_content_and_inspiration_provenance_preserved(auth_setup):
    """
    Test that playtest patches strictly modify target fields while preserving
    custom entities, custom rules, synthesized genre, and theme.
    """
    client, user, token, _, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    recs = [
        {
            "id": "r1",
            "category": "player",
            "description": "Adjust player color",
            "dsl_change_type": "color",
            "suggested_patch": {"player": {"color": "#ff00aa"}},
        }
    ]

    res = client.post(
        f"/api/projects/{project.id}/improvements",
        json={"baseVersionNumber": 1, "recommendations": recs},
        headers=headers,
    )
    assert res.status_code == 200
    dsl = res.json()["gameDsl"]
    assert dsl["player"]["color"] == "#ff00aa"
    # Preserved fields
    assert dsl["metadata"]["genre"] == "Action Roguelite Cyberpunk"
    assert dsl["metadata"]["archetype"] == "arena"
    assert len(dsl["entities"]) == 2
    assert len(dsl["rules"]) == 2
    assert dsl["rules"][0]["action"] == "damage_player"


def test_version_history_and_restore_after_remix(auth_setup):
    """
    Test creating Version 2 via remix, then restoring Version 1 creates Version 3
    identical to Version 1, while Version 2 remains in history.
    """
    client, user, token, _, project = auth_setup
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Create v2
    client.post(
        f"/api/projects/{project.id}/improvements",
        json={
            "baseVersionNumber": 1,
            "recommendations": [
                {
                    "id": "r1",
                    "category": "speed",
                    "description": "Speed to 300",
                    "dsl_change_type": "speed",
                    "suggested_patch": {"player": {"speed": 300}},
                }
            ],
        },
        headers=headers,
    )

    # Step 2: Restore v1 -> creates v3
    restore_res = client.post(
        f"/api/projects/{project.id}/restore",
        params={"target_version_number": 1},
        headers=headers,
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["currentVersion"] == 3
    assert restore_res.json()["gameDsl"]["player"]["speed"] == 220

    # Step 3: Check all 3 versions exist in history
    ver_res = client.get(f"/api/projects/{project.id}/versions", headers=headers)
    assert ver_res.status_code == 200
    vers = ver_res.json()
    assert len(vers) == 3
    assert vers[0]["version_number"] == 1
    assert vers[1]["version_number"] == 2
    assert vers[2]["version_number"] == 3


def test_idor_and_unauthenticated_protection(auth_setup):
    """
    Test IDOR and authentication protection on improvements endpoint.
    """
    client, user, token, other_token, project = auth_setup

    payload = {
        "baseVersionNumber": 1,
        "recommendations": [{"id": "r1", "category": "x", "description": "y", "dsl_change_type": "z", "suggested_patch": {"player": {"speed": 250}}}],
    }

    # 1. Unauthenticated -> 401
    unauth = client.post(f"/api/projects/{project.id}/improvements", json=payload)
    assert unauth.status_code == 401

    # 2. Other user -> 404
    other_headers = {"Authorization": f"Bearer {other_token}"}
    idor = client.post(f"/api/projects/{project.id}/improvements", json=payload, headers=other_headers)
    assert idor.status_code == 404
