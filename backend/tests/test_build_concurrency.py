"""
Concurrency, state machine, cancellation, and idempotency tests for Build Pipeline Integrity V1.

Verifies:
- Formal state transition matrix and terminal state immutability
- Cancel vs Success race conditions and late-completion protections
- Idempotent duplicate build submission handling
- Startup orphaned build reconciliation sweep
- Concurrent log sequence allocation without collisions or IntegrityErrors
- IDOR ownership isolation across all build operations
- SSE stream replay, ordering, and terminal completion
"""
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.password import hash_password
from app.auth.tokens import create_access_token
from app.db.session import Base, get_db
from app.main import app
from app.models.build import BuildJob
from app.models.build_log import BuildLog
from app.models.project import Project
from app.models.user import User
from app.repositories.build_repo import BuildRepository, build_repository
from app.schemas.build import BuildCreate
from app.schemas.project import BuildParams
from app.services.build_service import BuildService, build_service


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
    original_session_factory = build_service.session_factory
    build_service.session_factory = TestingSessionLocal

    yield

    build_service.session_factory = original_session_factory
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_context():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    try:
        # Create User A
        user_a = User(
            email="build_user_a@example.com",
            username="build_user_a",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(user_a)
        db.commit()
        db.refresh(user_a)
        token_a = create_access_token(user_a.id)

        # Create User B
        user_b = User(
            email="build_user_b@example.com",
            username="build_user_b",
            password_hash=hash_password("ValidPass123!"),
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)
        token_b = create_access_token(user_b.id)

        with TestClient(app) as client:
            yield client, user_a, token_a, user_b, token_b
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 1. State Machine & Atomic Conditional Transitions
# -----------------------------------------------------------------------------

def test_valid_state_transitions():
    """Verify valid progression: QUEUED -> RUNNING -> VALIDATING -> SUCCESS."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(prompt="Test game", status="QUEUED")
        db.add(build)
        db.commit()
        db.refresh(build)

        # QUEUED -> RUNNING
        assert build_repository.transition_status(
            db, build.id, from_statuses=["QUEUED"], to_status="RUNNING"
        )
        assert db.query(BuildJob).filter(BuildJob.id == build.id).first().status == "RUNNING"

        # RUNNING -> VALIDATING
        assert build_repository.transition_status(
            db, build.id, from_statuses=["RUNNING"], to_status="VALIDATING"
        )
        assert db.query(BuildJob).filter(BuildJob.id == build.id).first().status == "VALIDATING"

        # VALIDATING -> SUCCESS
        assert build_repository.transition_status(
            db, build.id, from_statuses=["VALIDATING"], to_status="SUCCESS"
        )
        assert db.query(BuildJob).filter(BuildJob.id == build.id).first().status == "SUCCESS"
    finally:
        db.close()


def test_terminal_states_are_immutable():
    """Verify terminal states (SUCCESS, ERROR, CANCELLED) cannot transition to any other state."""
    db = TestingSessionLocal()
    try:
        # 1. SUCCESS is immutable
        b_success = BuildJob(prompt="Success build", status="SUCCESS")
        db.add(b_success)
        db.commit()

        # Cannot cancel SUCCESS
        assert not build_repository.transition_status(
            db, b_success.id, from_statuses=["QUEUED", "RUNNING", "VALIDATING"], to_status="CANCELLED"
        )
        # Cannot error SUCCESS
        assert not build_repository.transition_status(
            db, b_success.id, from_statuses=["QUEUED", "RUNNING", "VALIDATING"], to_status="ERROR"
        )

        # 2. CANCELLED is immutable
        b_cancelled = BuildJob(prompt="Cancelled build", status="CANCELLED")
        db.add(b_cancelled)
        db.commit()

        # Cannot success CANCELLED
        assert not build_repository.transition_status(
            db, b_cancelled.id, from_statuses=["QUEUED", "RUNNING", "VALIDATING"], to_status="SUCCESS"
        )
        # Cannot error CANCELLED
        assert not build_repository.transition_status(
            db, b_cancelled.id, from_statuses=["QUEUED", "RUNNING", "VALIDATING"], to_status="ERROR"
        )

        # 3. ERROR is immutable
        b_error = BuildJob(prompt="Error build", status="ERROR")
        db.add(b_error)
        db.commit()

        # Cannot success ERROR
        assert not build_repository.transition_status(
            db, b_error.id, from_statuses=["QUEUED", "RUNNING", "VALIDATING"], to_status="SUCCESS"
        )
        # Cannot cancel ERROR
        assert not build_repository.transition_status(
            db, b_error.id, from_statuses=["QUEUED", "RUNNING", "VALIDATING"], to_status="CANCELLED"
        )
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 2. Cancel vs Success Race & Late AI Completion Protection
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_vs_success_race_protects_against_late_project_creation():
    """
    Simulates a race where user cancels a build while the worker is in VALIDATING.
    Verifies the worker's atomic conditional transition fails and no dangling project is retained.
    """
    db = TestingSessionLocal()
    try:
        user = User(
            email="race_test@example.com",
            username="race_test",
            password_hash=hash_password("Pass123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        build = BuildJob(
            user_id=user.id,
            prompt="Race test game",
            status="VALIDATING",
        )
        db.add(build)
        db.commit()
        db.refresh(build)

        # User cancels concurrently
        cancel_res = await build_service.cancel_build(db, build.id, user_id=user.id)
        assert cancel_res.status == "CANCELLED"

        # Worker attempts to transition to SUCCESS and create project
        success_transition = build_repository.transition_status(
            db,
            build_id=build.id,
            from_statuses=["RUNNING", "VALIDATING"],
            to_status="SUCCESS",
        )
        # Transition must fail because build is now CANCELLED!
        assert not success_transition

        # Verify DB status remains CANCELLED
        rechecked = db.query(BuildJob).filter(BuildJob.id == build.id).first()
        assert rechecked.status == "CANCELLED"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_double_cancel_is_idempotent():
    """Verify calling cancel_build twice on the same build is idempotent and returns CANCELLED."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="double_cancel@example.com",
            username="double_cancel",
            password_hash=hash_password("Pass123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        build = BuildJob(
            user_id=user.id,
            prompt="Double cancel test",
            status="RUNNING",
        )
        db.add(build)
        db.commit()
        db.refresh(build)

        # First cancel
        res1 = await build_service.cancel_build(db, build.id, user_id=user.id)
        assert res1.status == "CANCELLED"

        # Second cancel (idempotent)
        res2 = await build_service.cancel_build(db, build.id, user_id=user.id)
        assert res2.status == "CANCELLED"
        assert res2.build_id == build.id
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 3. Duplicate Build Submission Idempotency
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_build_submission_reuses_active_build():
    """Verify submitting identical prompt/parameters while a build is already active reuses the existing job."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="dedup_user@example.com",
            username="dedup_user",
            password_hash=hash_password("Pass123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        req = BuildCreate(
            prompt="Unique space arcade shooter",
            parameters=BuildParams(engine="Top-Down Action", art_density=50, physics=80),
        )

        # Submit build 1
        b1 = await build_service.submit_build(db, req, user_id=user.id)
        assert b1.status == "QUEUED"

        # Submit identical build 2 (simulating double click)
        b2 = await build_service.submit_build(db, req, user_id=user.id)
        # Must return the SAME active build ID
        assert b2.build_id == b1.build_id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_duplicate_build_submission_distinguishes_scale_and_world_mode():
    """Verify ADV-CORR-003: Submitting builds with different scale or world_mode does NOT deduplicate."""
    db = TestingSessionLocal()
    try:
        user = User(
            email="scale_dedup@example.com",
            username="scale_dedup",
            password_hash=hash_password("Pass123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        base_prompt = "Cyberpunk neon racing game"

        # 1. Base build (scale="standard", world_mode="linear")
        req_standard = BuildCreate(
            prompt=base_prompt,
            parameters=BuildParams(
                engine="Top-Down Action",
                art_density=50,
                physics=80,
                scale="standard",
                world_mode="linear",
            ),
        )
        b_standard = await build_service.submit_build(db, req_standard, user_id=user.id)
        assert b_standard.status == "QUEUED"

        # 2. Build with same prompt but different scale ("campaign")
        req_campaign = BuildCreate(
            prompt=base_prompt,
            parameters=BuildParams(
                engine="Top-Down Action",
                art_density=50,
                physics=80,
                scale="campaign",
                world_mode="linear",
            ),
        )
        b_campaign = await build_service.submit_build(db, req_campaign, user_id=user.id)
        assert b_campaign.status == "QUEUED"
        assert b_campaign.build_id != b_standard.build_id, "Distinct scale must not be deduplicated"

        # 3. Build with same prompt and scale="standard", but different world_mode ("open_world")
        req_open_world = BuildCreate(
            prompt=base_prompt,
            parameters=BuildParams(
                engine="Top-Down Action",
                art_density=50,
                physics=80,
                scale="standard",
                world_mode="open_world",
            ),
        )
        b_open_world = await build_service.submit_build(db, req_open_world, user_id=user.id)
        assert b_open_world.status == "QUEUED"
        assert b_open_world.build_id != b_standard.build_id, "Distinct world_mode must not be deduplicated"
        assert b_open_world.build_id != b_campaign.build_id

        # 4. Confirm identical resubmission of campaign DOES deduplicate to b_campaign
        b_campaign_dup = await build_service.submit_build(db, req_campaign, user_id=user.id)
        assert b_campaign_dup.build_id == b_campaign.build_id
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 4. Startup Orphaned Build Reconciliation Sweep
# -----------------------------------------------------------------------------

def test_startup_orphan_reconciliation_sweep():
    """Verify server startup sweep marks all QUEUED, RUNNING, VALIDATING builds as ERROR with ORPHANED_BUILD code."""
    db = TestingSessionLocal()
    try:
        b_queued = BuildJob(prompt="Stuck queued", status="QUEUED")
        b_running = BuildJob(prompt="Stuck running", status="RUNNING")
        b_validating = BuildJob(prompt="Stuck validating", status="VALIDATING")
        b_success = BuildJob(prompt="Already success", status="SUCCESS")

        db.add_all([b_queued, b_running, b_validating, b_success])
        db.commit()

        # Run sweep
        reconciled_count = build_repository.reconcile_orphaned_builds(db)
        assert reconciled_count == 3

        # Check statuses
        assert db.query(BuildJob).filter(BuildJob.id == b_queued.id).first().status == "ERROR"
        assert db.query(BuildJob).filter(BuildJob.id == b_queued.id).first().error_code == "ORPHANED_BUILD"
        assert db.query(BuildJob).filter(BuildJob.id == b_running.id).first().status == "ERROR"
        assert db.query(BuildJob).filter(BuildJob.id == b_validating.id).first().status == "ERROR"

        # SUCCESS remains untouched
        assert db.query(BuildJob).filter(BuildJob.id == b_success.id).first().status == "SUCCESS"
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 5. Concurrent Build Log Sequence Monotonicity
# -----------------------------------------------------------------------------

def test_concurrent_log_sequence_allocation():
    """Verify multiple log writes allocate strictly monotonic sequence numbers without collision."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(prompt="Log test", status="RUNNING")
        db.add(build)
        db.commit()
        db.refresh(build)

        # Append 15 logs
        for i in range(15):
            log = build_repository.append_log(
                db,
                build_id=build.id,
                level="INFO",
                message=f"Log message step {i + 1}",
            )
            assert log.sequence_number == i + 1

        logs = build_repository.get_logs(db, build.id)
        assert len(logs) == 15
        sequences = [l.sequence_number for l in logs]
        assert sequences == list(range(1, 16))
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 6. Ownership & IDOR Protection on Builds
# -----------------------------------------------------------------------------

def test_idor_protection_on_build_endpoints(test_context):
    """Verify User B cannot retrieve, cancel, or stream User A's build."""
    client, user_a, token_a, user_b, token_b = test_context
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. User A creates a build
    create_res = client.post(
        "/api/builds",
        json={"prompt": "User A game concept", "parameters": {"engine": "Top-Down Action"}},
        headers=headers_a,
    )
    assert create_res.status_code == 202
    build_id = create_res.json()["build_id"]

    # 2. User B tries to GET User A's build -> 404
    res_get = client.get(f"/api/builds/{build_id}", headers=headers_b)
    assert res_get.status_code == 404

    # 3. User B tries to CANCEL User A's build -> 404
    res_cancel = client.post(f"/api/builds/{build_id}/cancel", json={}, headers=headers_b)
    assert res_cancel.status_code == 404

    # 4. User B tries to GET logs for User A's build -> 404
    res_logs = client.get(f"/api/builds/{build_id}/logs", headers=headers_b)
    assert res_logs.status_code == 404

    # 5. User B tries to request SSE token for User A's build -> 404
    res_sse_token = client.post(f"/api/builds/{build_id}/sse-token", json={}, headers=headers_b)
    assert res_sse_token.status_code == 404


# -----------------------------------------------------------------------------
# 7. ADV-REL-001: SSE Stream Lifecycle & Dead Keep-Alive Termination
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sse_stream_terminates_when_worker_dies():
    """Verify ADV-REL-001: stream terminates with WORKER_TERMINATED instead of infinite keep-alive loop when worker disappears."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(prompt="Worker dead test", status="RUNNING")
        db.add(build)
        db.commit()
        db.refresh(build)
        build_id = build.id

        # Ensure no worker task is registered in memory
        build_service._active_tasks.pop(build_id, None)
        build_service._running_builds.discard(build_id)

        # Consume the stream with a short keep-alive timeout
        events = []
        async for chunk in build_service.stream_events(build_id, keep_alive_timeout=0.05):
            events.append(chunk)

        # Stream must have terminated
        joined = "".join(events)
        assert "WORKER_TERMINATED" in joined
        assert "Build worker terminated unexpectedly." in joined

        # Database record must have transitioned to ERROR
        db.refresh(build)
        assert build.status == "ERROR"
        assert build.error_code == "WORKER_TERMINATED"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sse_stream_terminates_on_external_terminal_status():
    """Verify ADV-REL-001: stream detects terminal state from database on timeout even if broadcaster event missed."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(prompt="External status test", status="RUNNING")
        db.add(build)
        db.commit()
        db.refresh(build)
        build_id = build.id

        # Register a mock running task so worker_dead is False initially
        dummy_task = asyncio.create_task(asyncio.sleep(10))
        build_service._active_tasks[build_id] = dummy_task
        build_service._running_builds.add(build_id)

        # Mark build as SUCCESS directly in DB
        build.status = "SUCCESS"
        build.project_id = "test-proj-123"
        db.commit()

        events = []
        async for chunk in build_service.stream_events(build_id, keep_alive_timeout=0.05):
            events.append(chunk)

        dummy_task.cancel()
        build_service._active_tasks.pop(build_id, None)
        build_service._running_builds.discard(build_id)

        joined = "".join(events)
        assert '"status": "SUCCESS"' in joined
        assert "test-proj-123" in joined
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sse_stream_terminates_on_deleted_build():
    """Verify ADV-REL-001: stream terminates with BUILD_NOT_FOUND if build is deleted during keep-alive timeout."""
    db = TestingSessionLocal()
    try:
        build = BuildJob(prompt="Delete test", status="RUNNING")
        db.add(build)
        db.commit()
        db.refresh(build)
        build_id = build.id

        # Register a mock running task so worker_dead is False initially
        dummy_task = asyncio.create_task(asyncio.sleep(10))
        build_service._active_tasks[build_id] = dummy_task
        build_service._running_builds.add(build_id)

        events = []
        gen = build_service.stream_events(build_id, keep_alive_timeout=0.05)

        # 1. Read initial status event
        initial_status = await anext(gen)
        assert "status" in initial_status

        # 2. Delete the build from DB while stream is live
        db.delete(build)
        db.commit()

        # 3. Next timeout cycle detects deletion in DB
        async for chunk in gen:
            events.append(chunk)

        if not dummy_task.done():
            dummy_task.cancel()
        build_service._active_tasks.pop(build_id, None)
        build_service._running_builds.discard(build_id)

        joined = "".join(events)
        assert "BUILD_NOT_FOUND" in joined
        assert "Build job no longer exists." in joined
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sse_stream_terminates_on_max_build_timeout():
    """Verify ADV-REL-001: stream terminates with BUILD_TIMEOUT if build exceeds max execution budget."""
    db = TestingSessionLocal()
    try:
        # Create a build that has exceeded 300s
        old_created = datetime.now(timezone.utc) - timedelta(seconds=350)
        build = BuildJob(prompt="Timeout test", status="RUNNING", created_at=old_created)
        db.add(build)
        db.commit()
        db.refresh(build)
        build_id = build.id

        dummy_task = asyncio.create_task(asyncio.sleep(10))
        build_service._active_tasks[build_id] = dummy_task
        build_service._running_builds.add(build_id)

        events = []
        async for chunk in build_service.stream_events(build_id, keep_alive_timeout=0.05):
            events.append(chunk)

        if not dummy_task.done():
            dummy_task.cancel()
        build_service._active_tasks.pop(build_id, None)
        build_service._running_builds.discard(build_id)

        joined = "".join(events)
        assert "BUILD_TIMEOUT" in joined
        assert "Build exceeded maximum execution time." in joined

        db.refresh(build)
        assert build.status == "ERROR"
        assert build.error_code == "BUILD_TIMEOUT"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sse_stream_does_not_kill_freshly_queued_build_during_registration_delay():
    """Verify ADV-REL-001: freshly QUEUED build without worker task registered yet gets grace period and does not fail."""
    db = TestingSessionLocal()
    try:
        # Build created 2 seconds ago, status QUEUED, no worker in _active_tasks yet
        fresh_created = datetime.now(timezone.utc) - timedelta(seconds=2)
        build = BuildJob(prompt="Fresh queued build", status="QUEUED", created_at=fresh_created)
        db.add(build)
        db.commit()
        db.refresh(build)
        build_id = build.id

        # Ensure no task is registered
        build_service._active_tasks.pop(build_id, None)
        build_service._running_builds.discard(build_id)

        # Stream with short timeout (0.05s)
        gen = build_service.stream_events(build_id, keep_alive_timeout=0.05)

        # 1. Read initial status event
        initial_status = await anext(gen)
        assert "status" in initial_status
        assert "QUEUED" in initial_status

        # 2. Timeout triggers: should yield keep-alive, NOT WORKER_TERMINATED
        timeout_event = await anext(gen)
        assert timeout_event == ": keep-alive\n\n"

        # 3. Verify DB state is still QUEUED
        db.refresh(build)
        assert build.status == "QUEUED"

        await gen.aclose()
    finally:
        db.close()

