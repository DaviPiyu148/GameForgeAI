"""
B7-updated build job API tests.

Changes from B6: all build endpoints now require authentication.
Tests pass Authorization: Bearer <token> with all API calls.
The wait_for_build_completion helper also passes the token.
"""
import asyncio
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import Base, get_db
from app.models.build import BuildJob
from app.models.build_log import BuildLog
from app.models.project import Project
from app.services.build_service import build_service
from app.ai.provider import AIProvider
from tests.test_dsl import get_sample_valid_dsl_dict


class MockBuildAIProvider(AIProvider):
    """Mock AI Provider for fast, reliable unit testing without live API keys."""
    async def generate_structured(self, system_prompt: str, user_prompt: str, json_schema=None):
        return get_sample_valid_dsl_dict()


# Isolated SQLite in-memory database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create fresh schema for each test and inject mock provider."""
    Base.metadata.create_all(bind=test_engine)
    original_session_factory = build_service.session_factory
    original_provider = build_service.generation_service.provider

    build_service.session_factory = TestingSessionLocal
    build_service.generation_service.provider = MockBuildAIProvider()

    yield

    build_service.session_factory = original_session_factory
    build_service.generation_service.provider = original_provider
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """TestClient fixture overriding get_db dependency."""
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


def _register_and_token(client):
    """Register a test user and return (token, user_id)."""
    res = client.post("/api/auth/register", json={
        "email": "buildtest@example.com",
        "username": "BuildTester",
        "password": "securepass123",
    })
    assert res.status_code == 201
    return res.json()["access_token"], res.json()["user"]["id"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def wait_for_build_completion(
    client: TestClient, build_id: str, token: str, timeout: float = 2.0
) -> dict:
    """Helper to poll build status until terminal state (SUCCESS / ERROR)."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        res = client.get(f"/api/builds/{build_id}", headers=_auth(token))
        if res.status_code == 200:
            data = res.json()
            if data["status"] in ("SUCCESS", "ERROR"):
                return data
        await asyncio.sleep(0.005)
    raise TimeoutError(f"Build {build_id} did not finish within {timeout}s")


@pytest.mark.asyncio
async def test_submit_build_returns_202_and_queued(client: TestClient):
    """POST /api/builds returns 202, server-owned UUID, and starts QUEUED/RUNNING."""
    token, _ = _register_and_token(client)
    payload = {
        "prompt": "A fast paced cyberpunk arcade game",
        "parameters": {
            "engine": "Phaser",
            "artDensity": 60,
            "physics": 75,
            "modules": ["combat", "score_tracker"]
        }
    }
    response = client.post("/api/builds", json=payload, headers=_auth(token))
    assert response.status_code == 202
    data = response.json()

    assert "build_id" in data
    assert len(data["build_id"]) > 10
    assert data["status"] in ("QUEUED", "RUNNING")
    assert data["project_id"] is None


@pytest.mark.asyncio
async def test_submit_build_requires_auth(client: TestClient):
    """POST /api/builds without token returns 401."""
    res = client.post("/api/builds", json={
        "prompt": "Test",
        "parameters": {"artDensity": 50, "physics": 50}
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_build_success_lifecycle_and_project_creation(client: TestClient):
    """Build transitions to SUCCESS, creates Project server-side with matching parameters."""
    token, _ = _register_and_token(client)
    payload = {
        "prompt": "Retro Dungeon Crawler",
        "parameters": {
            "engine": "Phaser",
            "artDensity": 45,
            "physics": 55,
            "modules": ["dungeon_gen", "ai_mobs"]
        }
    }
    res = client.post("/api/builds", json=payload, headers=_auth(token))
    assert res.status_code == 202
    build_id = res.json()["build_id"]

    # Wait for completion
    status_data = await wait_for_build_completion(client, build_id, token)
    assert status_data["status"] == "SUCCESS"
    assert status_data["project_id"] is not None
    assert status_data["game_dsl"] is not None
    assert status_data["game_dsl"]["metadata"]["title"] == "Neon Grid Runner"
    project_id = status_data["project_id"]

    # Verify created Project via Project API (using same authenticated user)
    proj_res = client.get(f"/api/projects/{project_id}", headers=_auth(token))
    assert proj_res.status_code == 200
    proj_data = proj_res.json()
    assert proj_data["id"] == project_id
    assert proj_data["title"] == "Neon Grid Runner"
    assert proj_data["prompt"] == "Retro Dungeon Crawler"
    assert proj_data["parameters"]["engine"] == "Phaser"
    assert proj_data["parameters"]["artDensity"] == 45
    assert proj_data["parameters"]["physics"] == 55
    assert proj_data["parameters"]["modules"] == ["dungeon_gen", "ai_mobs"]


@pytest.mark.asyncio
async def test_build_logs_persisted_and_ordered(client: TestClient):
    """Persisted logs have ascending sequence numbers and contain AI stages."""
    token, _ = _register_and_token(client)
    res = client.post("/api/builds", json={
        "prompt": "Pixel Space Shooter",
        "parameters": {"modules": ["lasers", "shields"]}
    }, headers=_auth(token))
    build_id = res.json()["build_id"]

    await wait_for_build_completion(client, build_id, token)

    logs_res = client.get(f"/api/builds/{build_id}/logs", headers=_auth(token))
    assert logs_res.status_code == 200
    data = logs_res.json()
    assert data["build_id"] == build_id
    logs = data["logs"]
    assert len(logs) >= 3

    # Verify ascending sequence ordering starting at 1
    for i, log in enumerate(logs):
        assert log["sequence"] == i + 1
        assert "message" in log
        assert "level" in log
        assert "timestamp" in log

    # Check for AI logging markers
    assert any("[AI]" in log["message"] for log in logs)


@pytest.mark.asyncio
async def test_build_failure_on_error_prompt(client: TestClient):
    """Error trigger transitions build to ERROR, does NOT create Project."""
    token, _ = _register_and_token(client)
    payload = {
        "prompt": "Create a simulation with an ERROR in physics",
        "parameters": {"artDensity": 50, "physics": 50}
    }
    res = client.post("/api/builds", json=payload, headers=_auth(token))
    assert res.status_code == 202
    build_id = res.json()["build_id"]

    status_data = await wait_for_build_completion(client, build_id, token)
    assert status_data["status"] == "ERROR"
    assert status_data["project_id"] is None
    assert status_data["error_code"] == "BUILD_SYNTAX_ERROR"
    assert "Prompt contains deterministic error trigger" in status_data["error_message"]

    # Verify NO projects were created
    projects_res = client.get("/api/projects", headers=_auth(token))
    assert len(projects_res.json()["projects"]) == 0


@pytest.mark.asyncio
async def test_sse_event_stream_and_replay(client: TestClient):
    """SSE emits status and log events, supports replay, closes on terminal state."""
    token, _ = _register_and_token(client)
    res = client.post("/api/builds", json={
        "prompt": "SSE Streaming Test Game",
        "parameters": {"modules": ["audio"]}
    }, headers=_auth(token))
    build_id = res.json()["build_id"]

    await wait_for_build_completion(client, build_id, token)

    # 1. Obtain short-lived SSE token
    sse_auth = client.post(f"/api/builds/{build_id}/sse-token", headers=_auth(token))
    assert sse_auth.status_code == 200
    sse_token = sse_auth.json()["sse_token"]

    # 2. Connect to SSE stream using short-lived sse_token (replays history + terminal status)
    with client.stream("GET", f"/api/builds/{build_id}/events?sse_token={sse_token}") as sse_res:
        assert sse_res.status_code == 200
        assert "text/event-stream" in sse_res.headers["content-type"]

        events = []
        for line in sse_res.iter_lines():
            if line.startswith("event:"):
                events.append(line)

        assert len(events) >= 2
        assert any("event: log" in e for e in events)
        assert any("event: status" in e for e in events)


def test_nonexistent_build_returns_404(client: TestClient):
    """Nonexistent build returns 404 with structured error envelope."""
    token, _ = _register_and_token(client)
    res = client.get("/api/builds/nonexistent-build-id-9999", headers=_auth(token))
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "BUILD_NOT_FOUND"

    logs_res = client.get("/api/builds/nonexistent-build-id-9999/logs", headers=_auth(token))
    assert logs_res.status_code == 404
    assert logs_res.json()["error"]["code"] == "BUILD_NOT_FOUND"


@pytest.mark.asyncio
async def test_duplicate_worker_execution_prevented():
    """Concurrency guard prevents duplicate worker runs for the same build ID."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(prompt="Concurrency Guard Test", status="QUEUED")
        db.add(build)
        db.commit()
        db.refresh(build)
        build_id = build.id

        # Launch two workers concurrently on the exact same build ID
        await asyncio.gather(
            build_service._run_build_worker(build_id),
            build_service._run_build_worker(build_id),
        )

        # Check logs - there should be only 1 set of logs, not duplicates
        logs = db.query(BuildLog).filter(BuildLog.build_id == build_id).all()
        sequences = [l.sequence_number for l in logs]
        assert len(sequences) == len(set(sequences)), "Log sequence numbers must be unique"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_build_cancellation(client: TestClient):
    """Test cancelling an active build job via POST /api/builds/{id}/cancel."""
    class SlowMockAIProvider(AIProvider):
        async def generate_structured(self, system_prompt: str, user_prompt: str, json_schema=None):
            await asyncio.sleep(2.0)
            return get_sample_valid_dsl_dict()

    orig_provider = build_service.generation_service.provider
    build_service.generation_service.provider = SlowMockAIProvider()
    try:
        token, _ = _register_and_token(client)
        res = client.post("/api/builds", json={
            "prompt": "Test Cancellation Game",
            "parameters": {"artDensity": 40, "physics": 60}
        }, headers=_auth(token))
        assert res.status_code == 202
        build_id = res.json()["build_id"]

        # Cancel build while it is sleeping/generating
        cancel_res = client.post(f"/api/builds/{build_id}/cancel", headers=_auth(token))
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.json()
        assert cancel_data["status"] == "CANCELLED"
        assert cancel_data["error_code"] == "BUILD_CANCELLED"

        # Verify logs contain cancellation record
        logs_res = client.get(f"/api/builds/{build_id}/logs", headers=_auth(token))
        assert logs_res.status_code == 200
        logs = logs_res.json()["logs"]
        assert any("[SYS] BUILD CANCELLED BY USER" in l["message"] for l in logs)

        # Verify NO project was created
        projects_res = client.get("/api/projects", headers=_auth(token))
        assert len(projects_res.json()["projects"]) == 0
    finally:
        build_service.generation_service.provider = orig_provider


@pytest.mark.asyncio
async def test_build_cancellation_idor_protection(client: TestClient):
    """User B cannot cancel User A's build (returns 404 IDOR protection)."""
    token_a, _ = _register_and_token(client)

    # Register User B
    res_b = client.post("/api/auth/register", json={
        "email": "user_b_cancel@example.com",
        "username": "UserBCancel",
        "password": "securepass123",
    })
    assert res_b.status_code == 201
    token_b = res_b.json()["access_token"]

    # User A creates a build
    res = client.post("/api/builds", json={
        "prompt": "User A build to be attacked",
    }, headers=_auth(token_a))
    assert res.status_code == 202
    build_id = res.json()["build_id"]

    # User B tries to cancel User A's build
    cancel_res = client.post(f"/api/builds/{build_id}/cancel", headers=_auth(token_b))
    assert cancel_res.status_code == 404
    assert cancel_res.json()["error"]["code"] == "BUILD_NOT_FOUND"


@pytest.mark.asyncio
async def test_sse_with_query_token(client: TestClient):
    """EventSource SSE connects successfully with ?sse_token=<short-lived-token> and rejects raw ?token=<jwt>."""
    token, _ = _register_and_token(client)
    res = client.post("/api/builds", json={
        "prompt": "SSE Query Token Test Game",
        "parameters": {"artDensity": 50}
    }, headers=_auth(token))
    build_id = res.json()["build_id"]

    await wait_for_build_completion(client, build_id, token)

    # 1. Raw ?token=<jwt> in URL is rejected (CRIT-01 security mitigation)
    with client.stream("GET", f"/api/builds/{build_id}/events?token={token}") as sse_bad:
        assert sse_bad.status_code == 401

    # 2. Dedicated short-lived SSE credential connects successfully
    sse_auth = client.post(f"/api/builds/{build_id}/sse-token", headers=_auth(token))
    assert sse_auth.status_code == 200
    sse_token = sse_auth.json()["sse_token"]

    with client.stream("GET", f"/api/builds/{build_id}/events?sse_token={sse_token}") as sse_res:
        assert sse_res.status_code == 200
        assert "text/event-stream" in sse_res.headers["content-type"]


def test_builder_parameters_in_prompt():
    """Verify prompt builder injects physics, artDensity, and logic modules semantically."""
    from app.ai.prompts import build_generation_prompt

    prompt = build_generation_prompt(
        prompt="Cyberpunk neon ninja",
        engine="Phaser 3.88.2",
        art_density=85,
        physics=90,
        modules=["Procedural Generation", "Enhanced NPC Behavior", "Resource & Score Economy"],
    )

    assert "Cyberpunk neon ninja" in prompt
    assert "Phaser 3.88.2" in prompt
    assert "90/100" in prompt
    assert "High/Dynamic" in prompt
    assert "85/100" in prompt
    assert "Rich Procedural Details" in prompt
    assert "Procedural Generation" in prompt
    assert "Enhanced NPC Behavior" in prompt
    assert "Resource & Score Economy" in prompt
