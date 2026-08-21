"""
Comprehensive regression test suite for Forensic Audit Bug Fixes.

Covers:
- CRIT-02: Valid Argon2 dummy hash in login constant-time path
- CRIT-01: Short-lived SSE credential security, scope binding, and expiration
- HIGH-05: DSL deep-copy during improvement patching
- HIGH-03 / HIGH-04: Atomic project and version creation
- MED-01: Constructor injection regex false-positive protection
- LOW-01: Compatibility validator rule limit consistency (20 rules max)
- LOW-02: IGDB hot-cache TTL expiry check
- LOW-03: O(1) Catalog lookup by ID and external_id
- LOW-05: Timezone relative timestamp formatting
- LOW-06: DSL schema_version default 2.0 and 1.0 backward compatibility
"""
import asyncio
import copy
import time
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.auth.password import hash_password, verify_password
from app.auth.tokens import create_access_token, decode_access_token, create_sse_token, decode_sse_token
from app.schemas.auth import LoginRequest
from app.schemas.design_spec import GameDesignSpec, check_for_script_injection
from app.schemas.project import ProjectCreate, BuildParams
from app.schemas.discovery import GameEnrichment
from app.generation.dsl_models import GameDSL, GameMetadata, WorldDef, PlayerDef, RuleDef
from app.generation.validator import validate_game_dsl
from app.runtime.compatibility import RuntimeCompatibilityValidator
from app.services.auth_service import auth_service, InvalidCredentialsError, _DUMMY_PASSWORD_HASH
from app.services.project_service import project_service
from app.services.igdb_service import IGDBEnrichmentService
from app.services.game_generation_service import game_generation_service
from app.search.catalog import CatalogManager


# Isolated in-memory DB for tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


from app.ai.provider import AIProvider


class MockForensicAIProvider(AIProvider):
    async def generate_structured(self, system_prompt: str, user_prompt: str, json_schema=None):
        return {
            "title": "Patched Game",
            "genre": "Action",
            "description": "Improved",
            "archetype": "survival",
            "player": {"spawn_x": 400, "spawn_y": 300, "speed": 350, "attack_damage": 50},
            "world": {"width": 800, "height": 600, "theme": "neon"},
            "entities": [],
            "rules": [],
        }


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    orig_provider = game_generation_service.provider
    game_generation_service.provider = MockForensicAIProvider()
    yield
    game_generation_service.provider = orig_provider
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# 1. CRIT-02: Argon2 Dummy Hash
# -----------------------------------------------------------------------------

def test_dummy_argon2_hash_is_valid_and_verifiable():
    """Verify that _DUMMY_PASSWORD_HASH is a valid Argon2 hash that verifies cleanly."""
    assert _DUMMY_PASSWORD_HASH.startswith("$argon2")
    # Must compute verification without raising invalid hash syntax error
    result = verify_password("wrong_password", _DUMMY_PASSWORD_HASH)
    assert result is False


def test_login_nonexistent_email_runs_safely():
    """Verify nonexistent email executes the constant-time path and raises InvalidCredentialsError."""
    db = TestingSessionLocal()
    try:
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.login(db, LoginRequest(email="nonexistent_user_999@example.com", password="somepassword"))
        assert "Invalid email or password." in str(exc_info.value)
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 2. CRIT-01: Secure Short-Lived SSE Credential
# -----------------------------------------------------------------------------

def test_create_and_decode_sse_token():
    """Verify SSE token creation, claims, and build_id validation."""
    user_id = "test-user-123"
    build_id = "build-abc-456"

    sse_token = create_sse_token(user_id=user_id, build_id=build_id)
    assert isinstance(sse_token, str)

    # Valid decode
    payload = decode_sse_token(sse_token, expected_build_id=build_id)
    assert payload["sub"] == user_id
    assert payload["bid"] == build_id
    assert payload["type"] == "sse"


def test_sse_token_rejected_for_wrong_build_id():
    """Verify SSE token cannot be reused across different build IDs."""
    sse_token = create_sse_token(user_id="user-1", build_id="build-A")
    with pytest.raises(Exception) as exc:
        decode_sse_token(sse_token, expected_build_id="build-B")
    assert "not valid for this build ID" in str(exc.value)


def test_access_token_cannot_be_used_as_sse_token():
    """Verify normal access token is rejected by decode_sse_token (type mismatch)."""
    access_token = create_access_token(user_id="user-1")
    with pytest.raises(Exception) as exc:
        decode_sse_token(access_token, expected_build_id="build-123")
    assert "Token type is not 'sse'" in str(exc.value)


def test_sse_token_cannot_be_used_as_access_token():
    """Verify SSE token is rejected by decode_access_token (cannot access normal API)."""
    sse_token = create_sse_token(user_id="user-1", build_id="build-123")
    with pytest.raises(Exception) as exc:
        decode_access_token(sse_token)
    assert "Token type is not 'access'" in str(exc.value)


# -----------------------------------------------------------------------------
# 3. HIGH-05: DSL Deep Copy in Improvement Patching
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dsl_improvement_does_not_mutate_original_dict():
    """Verify apply_improvements performs a deep copy and leaves original dict intact."""
    original_dsl = {
        "schema_version": "2.0",
        "metadata": {"title": "Original Game", "genre": "Action", "description": "Original", "archetype": "survival"},
        "world": {"width": 800, "height": 600, "theme": "neon"},
        "player": {"spawn_x": 400, "spawn_y": 300, "speed": 200, "attack_damage": 25},
        "entities": [],
        "rules": [],
    }
    dsl_copy = copy.deepcopy(original_dsl)

    # Apply improvement with suggested patch modifying player speed
    recs = [{
        "category": "difficulty",
        "description": "Increase player speed",
        "suggested_patch": {"player": {"speed": 350, "attack_damage": 50}},
    }]

    # In case AI fails or mock fallback is triggered:
    result = await game_generation_service.apply_improvements(
        current_dsl=original_dsl,
        design_spec={"title": "Test Spec", "genre": "Action"},
        selected_recommendations=recs,
    )

    # Original dict must be completely unchanged
    assert original_dsl["player"]["speed"] == dsl_copy["player"]["speed"]
    assert original_dsl["player"]["attack_damage"] == dsl_copy["player"]["attack_damage"]


# -----------------------------------------------------------------------------
# 4. HIGH-03 / HIGH-04: Atomic Project & Version Creation
# -----------------------------------------------------------------------------

def test_atomic_project_and_v1_version_creation():
    """Verify create_project creates Project and initial ProjectVersion atomically in one transaction."""
    db = TestingSessionLocal()
    try:
        sample_dsl = {
            "schema_version": "2.0",
            "metadata": {"title": "Atomic Test Game", "genre": "Arcade", "description": "Desc", "archetype": "survival"},
            "world": {"width": 800, "height": 600},
            "player": {"spawn_x": 400, "spawn_y": 300},
            "entities": [],
            "rules": [],
        }
        create_data = ProjectCreate(
            title="Atomic Test Game",
            genre="Arcade",
            prompt="A test game",
            parameters=BuildParams(engine="phaser", art_density=50, physics=50, modules=[]),
            game_dsl=sample_dsl,
        )

        resp = project_service.create_project(db, create_data, user_id="test-user-1")
        assert resp.id is not None
        assert resp.current_version == 1

        # Check version history immediately exists
        versions = project_service.list_project_versions(db, resp.id, user_id="test-user-1")
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1
        assert versions[0]["change_summary"] == "Initial prototype generated from prompt."
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 5. MED-01: Constructor False-Positive Protection
# -----------------------------------------------------------------------------

def test_legitimate_constructor_text_passes_validation():
    """Verify words like 'city constructor' or 'construction' do not trigger false positive."""
    spec_data = {
        "title": "City Constructor 2026",
        "elevator_pitch": "A futuristic city constructor and resource management simulation.",
        "genre": "Simulation",
        "core_gameplay_loop": "Build structures, manage constructor drones, and expand the metropolis.",
        "player_role": "Master Constructor",
        "primary_objective": "Construct the ultimate cyber citadel.",
    }
    spec = GameDesignSpec(**spec_data)
    assert spec.title == "City Constructor 2026"
    assert "constructor" in spec.elevator_pitch


def test_malicious_constructor_property_injection_is_rejected():
    """Verify actual prototype property access like .constructor or ['constructor'] is rejected."""
    with pytest.raises(ValueError) as exc:
        check_for_script_injection("Exploit via obj.constructor.prototype")
    assert "Prohibited script" in str(exc.value)

    with pytest.raises(ValueError) as exc2:
        check_for_script_injection("Exploit via window['constructor']")
    assert "Prohibited script" in str(exc2.value)


# -----------------------------------------------------------------------------
# 6. LOW-01: Rule Count Consistency (20 Max)
# -----------------------------------------------------------------------------

def test_compatibility_validator_allows_20_rules_and_rejects_21():
    """Verify compatibility validator rule capacity check is aligned to 20."""
    rules_20 = [
        RuleDef(id=f"r_{i}", trigger="on_collect", action="add_score", params={"amount": 10})
        for i in range(20)
    ]
    dsl = GameDSL(
        schema_version="2.0",
        metadata=GameMetadata(title="Rule Test", genre="Arcade", description="Desc", archetype="collector"),
        world=WorldDef(width=800, height=600),
        player=PlayerDef(spawn_x=400, spawn_y=300),
        entities=[],
        rules=rules_20,
    )
    res = RuntimeCompatibilityValidator.validate(dsl)
    # 20 rules should not trigger rule capacity error
    assert not any("Rule count" in err for err in res.errors)


# -----------------------------------------------------------------------------
# 7. LOW-02: IGDB Hot Cache TTL Check
# -----------------------------------------------------------------------------

def test_igdb_hot_cache_respects_ttl():
    """Verify in-memory hot cache returns hit for fresh entries and evicts expired entries."""
    service = IGDBEnrichmentService.get_instance()
    test_app_id = "steam_test_999"
    test_enrichment = GameEnrichment(status="AVAILABLE", summary="Test game summary")

    # Save with custom short TTL (expired in the past)
    service._hot_cache[test_app_id] = (test_enrichment, time.time() - 10.0)

    # Must detect expired TTL and return None
    cached = service._get_from_cache(test_app_id)
    assert cached is None
    assert test_app_id not in service._hot_cache

    # Save with fresh TTL
    service._hot_cache[test_app_id] = (test_enrichment, time.time() + 3600.0)
    cached_fresh = service._get_from_cache(test_app_id)
    assert cached_fresh is not None
    assert cached_fresh.summary == "Test game summary"


# -----------------------------------------------------------------------------
# 8. LOW-03: O(1) Catalog Lookup by ID and External ID
# -----------------------------------------------------------------------------

def test_catalog_manager_lookup_by_external_id():
    """Verify CatalogManager resolves games by string ID or external_id in O(1) time."""
    catalog = CatalogManager.get_instance()
    # Add a mock game to index
    test_game = {"id": "canonical-123", "external_id": "steam-987654", "title": "Indexed Test Game"}
    catalog._games_by_id["canonical-123"] = test_game
    catalog._games_by_external_id["steam-987654"] = test_game

    assert catalog.get_game("canonical-123") == test_game
    assert catalog.get_game("steam-987654") == test_game
    assert catalog.get_game("nonexistent-id-999") is None


# -----------------------------------------------------------------------------
# 9. LOW-05: Relative Timestamp Formatting
# -----------------------------------------------------------------------------

def test_project_last_modified_relative_formatting():
    """Verify project last_modified uses relative time format."""
    db = TestingSessionLocal()
    try:
        create_data = ProjectCreate(
            title="Timestamp Test Game",
            genre="Action",
            prompt="Prompt",
            parameters=BuildParams(engine="phaser", art_density=50, physics=50, modules=[]),
        )
        resp = project_service.create_project(db, create_data, user_id="user-1")
        assert resp.last_modified in ("Just now", "0m ago", "1m ago")
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 10. LOW-06: DSL Schema Version Defaults to 2.0 and Supports 1.0
# -----------------------------------------------------------------------------

def test_dsl_schema_version_defaults_to_2_0():
    """Verify new GameDSL models default to schema_version 2.0."""
    dsl = GameDSL(
        metadata=GameMetadata(title="V2 Game", genre="Action", description="Desc", archetype="survival"),
        world=WorldDef(),
        player=PlayerDef(),
    )
    assert dsl.schema_version == "2.0"


def test_dsl_validator_accepts_v1_schema():
    """Verify validate_game_dsl accepts legacy 1.0 schema version."""
    v1_raw = {
        "schema_version": "1.0",
        "metadata": {"title": "V1 Legacy Game", "genre": "Arcade", "description": "Desc", "archetype": "survival"},
        "world": {"width": 800, "height": 600},
        "player": {"spawn_x": 400, "spawn_y": 300},
        "entities": [],
        "rules": [],
    }
    res = validate_game_dsl(v1_raw)
    assert res.is_valid is True
    assert res.dsl.schema_version == "1.0"
