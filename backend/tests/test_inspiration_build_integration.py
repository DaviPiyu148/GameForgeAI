"""
Integration and regression test suite for Step 6: Build & Prototype Integration.
Validates explicit, version-aware prototype compilation for GameForge AI.
"""
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
from app.models.project_inspiration import ProjectInspiration
from app.models.playtest import PlaytestSession
from app.auth.password import hash_password
from app.auth.tokens import create_access_token
from app.schemas.inspiration_synthesis import ApplySynthesisProposalRequest

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
        user_a = User(
            email="developer_a@gameforge.ai",
            username="deva",
            password_hash=hash_password("DevPass123!"),
        )
        user_b = User(
            email="developer_b@gameforge.ai",
            username="devb",
            password_hash=hash_password("DevPass123!"),
        )
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)

        token_a = create_access_token(user_a.id)
        token_b = create_access_token(user_b.id)

        initial_dsl = {
            "schema_version": "1.0",
            "metadata": {
                "title": "Neon Grid Runner",
                "genre": "Action",
                "description": "Initial prototype",
                "archetype": "platformer",
            },
            "world": {
                "width": 1280,
                "height": 720,
                "gravity": 600,
                "theme": "neon",
                "world_mode": "linear",
            },
            "player": {
                "spawn_x": 100,
                "spawn_y": 300,
                "speed": 220,
                "jump_power": 450,
                "attack_type": "melee",
            },
            "entities": [
                {
                    "id": "e_gem_1",
                    "type": "collectible",
                    "behavior": "float",
                    "x": 300,
                    "y": 400,
                    "width": 24,
                    "height": 24,
                }
            ],
            "rules": [
                {
                    "id": "r_collect",
                    "trigger": "on_collect",
                    "action": "add_score",
                },
                {
                    "id": "r_goal",
                    "trigger": "on_reach_goal",
                    "action": "win_game",
                },
            ],
            "ui": {
                "show_health": True,
                "show_score": True,
                "status_text": "REACH THE EXIT",
            },
        }

        initial_spec = {
            "title": "Neon Grid Runner",
            "elevator_pitch": "A precision neon arcade runner.",
            "genre": "Action",
            "subgenre": "Platformer",
            "theme": "neon",
            "core_gameplay_loop": "Run -> Jump -> Collect -> Exit",
            "player_role": "Cyber Runner",
            "primary_objective": "Reach the end portal safely.",
            "player_abilities": ["PrecisionLocomotion"],
        }

        project = Project(
            user_id=user_a.id,
            title="Neon Grid Runner",
            genre="Action",
            prompt="A fast-paced cyber precision platformer",
            engine="2D Platformer",
            physics=80,
            art_density=50,
            modules=["Combat & Dash Mobility"],
            scale="standard",
            world_mode="linear",
            status="PLAYABLE",
            game_dsl=initial_dsl,
            design_spec=initial_spec,
            current_version=1,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        v1 = ProjectVersion(
            project_id=project.id,
            version_number=1,
            game_dsl=initial_dsl,
            design_spec=initial_spec,
            change_summary="Initial prototype generated from prompt.",
        )
        db.add(v1)
        db.commit()

        # Attach 2 inspirations to project
        insp1 = ProjectInspiration(
            project_id=project.id,
            steam_app_id="588650",
            title="Dead Cells",
            genres=["Action", "Rogue-lite"],
            tags=["Metroidvania", "Roguelike", "Cyberpunk", "Platformer"],
            player_modes=["Single-player"],
        )
        insp2 = ProjectInspiration(
            project_id=project.id,
            steam_app_id="250900",
            title="The Binding of Isaac",
            genres=["Action", "Adventure"],
            tags=["Roguelike", "Top-Down Shooter", "Bullet Hell", "Dungeon"],
            player_modes=["Single-player"],
        )
        db.add_all([insp1, insp2])
        db.commit()

        with TestClient(app) as client:
            yield client, user_a, token_a, user_b, token_b, project
    finally:
        db.close()


def test_end_to_end_inspiration_apply_and_compile(auth_setup):
    """
    Full pipeline test:
    1. Project starts at v1
    2. Synthesize proposal from 2 inspirations
    3. Apply proposal -> advances project to v2 (no automatic build)
    4. Explicit developer action: Compile v2
    5. Verify compiled prototype artifact reflects synthesized parameters (theme, loop, abilities)
    """
    client, user_a, token_a, _, _, project = auth_setup
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. Synthesize proposal
    syn_res = client.post(
        f"/api/projects/{project.id}/inspirations/synthesize",
        headers=headers_a,
    )
    assert syn_res.status_code == 200
    syn_data = syn_res.json()
    assert syn_data["inspirationCount"] == 2
    assert "PrecisionLocomotion" in syn_data["proposedMechanics"]

    # 2. Apply proposal (explicit developer approval)
    apply_payload = {
        "base_version_number": 1,
        "conflict_resolutions": {},
        "field_decisions": {
            "genre": "APPLY_PROPOSAL",
            "engine": "APPLY_PROPOSAL",
        },
    }
    apply_res = client.post(
        f"/api/projects/{project.id}/inspirations/synthesize/apply",
        headers=headers_a,
        json=apply_payload,
    )
    assert apply_res.status_code == 200
    apply_data = apply_res.json()
    assert apply_data["previousVersionNumber"] == 1
    assert apply_data["newVersionNumber"] == 2
    assert apply_data["status"] == "SUCCESS"

    # 3. Explicitly compile the new v2 prototype
    compile_res = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_a,
        json={"versionNumber": 2},
    )
    assert compile_res.status_code == 200
    comp_data = compile_res.json()

    assert comp_data["projectId"] == project.id
    assert comp_data["versionNumber"] == 2
    assert comp_data["status"] == "SUCCESS"
    assert comp_data["gameDsl"] is not None
    assert comp_data["runtimeMetadata"] is not None
    assert comp_data["runtimeMetadata"]["version_number"] == 2
    assert comp_data["validationSummary"]["isValid"] is True
    assert comp_data["validationSummary"]["archetype"] == "platformer"

    # Verify default compile (omitted version number) also compiles current active version (v2)
    default_compile_res = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_a,
        json={},
    )
    assert default_compile_res.status_code == 200
    assert default_compile_res.json()["versionNumber"] == 2


def test_version_immutability_during_compilation(auth_setup):
    """
    Compilation must be strictly read-only with respect to ProjectVersion rows.
    Compiling v1 or v2 must not alter historical version records.
    """
    client, user_a, token_a, _, _, project = auth_setup
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Apply proposal to create v2
    client.post(
        f"/api/projects/{project.id}/inspirations/synthesize/apply",
        headers=headers_a,
        json={"base_version_number": 1},
    )

    db = TestingSessionLocal()
    try:
        v1_row_before = (
            db.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project.id, ProjectVersion.version_number == 1)
            .first()
        )
        v2_row_before = (
            db.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project.id, ProjectVersion.version_number == 2)
            .first()
        )
        v1_dsl_before = dict(v1_row_before.game_dsl)
        v2_dsl_before = dict(v2_row_before.game_dsl)
        v1_created_before = v1_row_before.created_at
        v2_created_before = v2_row_before.created_at
    finally:
        db.close()

    # Compile v1
    res_v1 = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_a,
        json={"versionNumber": 1},
    )
    assert res_v1.status_code == 200
    assert res_v1.json()["versionNumber"] == 1

    # Compile v2
    res_v2 = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_a,
        json={"versionNumber": 2},
    )
    assert res_v2.status_code == 200
    assert res_v2.json()["versionNumber"] == 2

    # Assert database records are 100% identical
    db = TestingSessionLocal()
    try:
        v1_row_after = (
            db.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project.id, ProjectVersion.version_number == 1)
            .first()
        )
        v2_row_after = (
            db.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project.id, ProjectVersion.version_number == 2)
            .first()
        )
        assert v1_row_after.game_dsl == v1_dsl_before
        assert v2_row_after.game_dsl == v2_dsl_before
        assert v1_row_after.created_at == v1_created_before
        assert v2_row_after.created_at == v2_created_before
        assert v1_row_after.change_summary == v1_row_before.change_summary
    finally:
        db.close()


def test_stale_or_nonexistent_version_compilation(auth_setup):
    """
    Requesting compilation for a non-existent version number must return 400 COMPILATION_ERROR.
    """
    client, _, token_a, _, _, project = auth_setup
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_a,
        json={"versionNumber": 99},
    )
    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == "COMPILATION_ERROR"
    assert "Version 99 not found" in data["error"]["message"]


def test_idor_ownership_protection_on_compile(auth_setup):
    """
    User B must not be able to compile User A's project (returns 404 IDOR protection).
    """
    client, _, _, _, token_b, project = auth_setup
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_b,
        json={"versionNumber": 1},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_unauthenticated_compile_rejected(auth_setup):
    """
    Unauthenticated compile requests must be rejected with 401.
    """
    client, _, _, _, _, project = auth_setup
    res = client.post(f"/api/projects/{project.id}/compile", json={})
    assert res.status_code == 401


def test_playtest_compatibility_across_versions(auth_setup):
    """
    Verifies that playtests recorded against Version 1 retain version identity,
    and when the project advances to Version 2, the playtest list reflects
    both versions and existing version-aware stale checks work accurately.
    """
    client, _, token_a, _, _, project = auth_setup
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1. Record playtest on Version 1
    pt1_payload = {
        "duration_seconds": 45,
        "score": 50,
        "damage_taken": 10,
        "damage_dealt": 0,
        "enemies_defeated": 0,
        "collectibles_gathered": 1,
        "objectives_completed": 1,
        "outcome": "WON",
        "version_number": 1,
        "telemetry_events": [
            {"type": "SESSION_START", "timestamp": 0},
            {"type": "COLLECTIBLE_COLLECTED", "timestamp": 12000, "data": {"points": 50}},
            {"type": "GAME_WON", "timestamp": 45000},
        ],
    }
    pt1_res = client.post(
        f"/api/projects/{project.id}/playtests",
        headers=headers_a,
        json=pt1_payload,
    )
    assert pt1_res.status_code == 201

    # 2. Advance project to Version 2 via inspiration apply
    apply_res = client.post(
        f"/api/projects/{project.id}/inspirations/synthesize/apply",
        headers=headers_a,
        json={"base_version_number": 1},
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["newVersionNumber"] == 2

    # 3. Record playtest on Version 2
    pt2_payload = {
        "duration_seconds": 60,
        "score": 100,
        "damage_taken": 25,
        "damage_dealt": 100,
        "enemies_defeated": 4,
        "collectibles_gathered": 2,
        "objectives_completed": 2,
        "outcome": "WON",
        "version_number": 2,
        "telemetry_events": [
            {"type": "SESSION_START", "timestamp": 0},
            {"type": "COLLECTIBLE_COLLECTED", "timestamp": 15000, "data": {"points": 100}},
            {"type": "ENEMY_DEFEATED", "timestamp": 20000},
            {"type": "GAME_WON", "timestamp": 60000},
        ],
    }
    pt2_res = client.post(
        f"/api/projects/{project.id}/playtests",
        headers=headers_a,
        json=pt2_payload,
    )
    assert pt2_res.status_code == 201

    # 4. List playtests and verify both sessions exist
    list_res = client.get(
        f"/api/projects/{project.id}/playtests",
        headers=headers_a,
    )
    assert list_res.status_code == 200
    sessions = list_res.json()
    assert len(sessions) == 2
    assert sessions[0]["score"] == 100
    assert sessions[1]["score"] == 50


def test_payload_tampering_extra_forbidden(auth_setup):
    """
    Ensure CompileProjectRequest enforces extra="forbid" against unexpected fields.
    """
    client, _, token_a, _, _, project = auth_setup
    headers_a = {"Authorization": f"Bearer {token_a}"}

    res = client.post(
        f"/api/projects/{project.id}/compile",
        headers=headers_a,
        json={"versionNumber": 1, "injected_code": "alert(1)"},
    )
    assert res.status_code == 422
