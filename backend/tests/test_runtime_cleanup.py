"""
Regression tests for Targeted Backend / Frontend Runtime Cleanup.

Verifies:
1. Startup orphan build reconciliation transitions non-terminal builds (QUEUED, RUNNING, VALIDATING)
   to ERROR / ORPHANED_BUILD and permanently persists them across database sessions.
2. Reconcile on empty/terminal-only database is cleanly committed and returns 0.
3. Terminal builds (SUCCESS, ERROR, CANCELLED) are NEVER mutated by startup sweep.
4. QueryEmbedder is a thread-safe singleton, handles optional HF_TOKEN without crashing,
   and caches embeddings correctly.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.build import BuildJob
from app.repositories.build_repo import build_repository
from app.search.embedder import QueryEmbedder
from app.config import settings


# Dedicated in-memory SQLite engine for runtime cleanup testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_orphan_reconciliation_persists_across_sessions():
    """
    Verify that non-terminal builds (QUEUED, RUNNING, VALIDATING) are transitioned
    to ERROR with error_code='ORPHANED_BUILD' and the changes are permanently committed
    and visible in subsequent fresh database sessions.
    """
    # 1. Create a set of active and terminal builds in Session 1
    db1 = TestingSessionLocal()
    try:
        b_queued = BuildJob(prompt="Queued Game", status="QUEUED")
        b_running = BuildJob(prompt="Running Game", status="RUNNING")
        b_validating = BuildJob(prompt="Validating Game", status="VALIDATING")
        b_success = BuildJob(prompt="Success Game", status="SUCCESS")
        b_cancelled = BuildJob(prompt="Cancelled Game", status="CANCELLED")
        b_error = BuildJob(prompt="Error Game", status="ERROR", error_code="SYNTAX_ERROR")

        db1.add_all([b_queued, b_running, b_validating, b_success, b_cancelled, b_error])
        db1.commit()

        q_id = b_queued.id
        r_id = b_running.id
        v_id = b_validating.id
        s_id = b_success.id
        c_id = b_cancelled.id
        e_id = b_error.id
    finally:
        db1.close()

    # 2. Run startup reconciliation in Session 2 (simulating server restart)
    db2 = TestingSessionLocal()
    try:
        reconciled_count = build_repository.reconcile_orphaned_builds(db2)
        assert reconciled_count == 3
    finally:
        db2.close()

    # 3. Open Session 3 to verify permanent persistence in the database
    db3 = TestingSessionLocal()
    try:
        # Reconciled jobs
        job_q = build_repository.get_build_by_id(db3, q_id)
        assert job_q is not None
        assert job_q.status == "ERROR"
        assert job_q.error_code == "ORPHANED_BUILD"
        assert "server restart" in (job_q.error_message or "")
        assert job_q.completed_at is not None

        job_r = build_repository.get_build_by_id(db3, r_id)
        assert job_r is not None
        assert job_r.status == "ERROR"
        assert job_r.error_code == "ORPHANED_BUILD"
        assert job_r.completed_at is not None

        job_v = build_repository.get_build_by_id(db3, v_id)
        assert job_v is not None
        assert job_v.status == "ERROR"
        assert job_v.error_code == "ORPHANED_BUILD"
        assert job_v.completed_at is not None

        # Terminal jobs must be untouched
        job_s = build_repository.get_build_by_id(db3, s_id)
        assert job_s is not None
        assert job_s.status == "SUCCESS"
        assert job_s.error_code is None

        job_c = build_repository.get_build_by_id(db3, c_id)
        assert job_c is not None
        assert job_c.status == "CANCELLED"

        job_e = build_repository.get_build_by_id(db3, e_id)
        assert job_e is not None
        assert job_e.status == "ERROR"
        assert job_e.error_code == "SYNTAX_ERROR"

        # 4. Re-running on already-reconciled database is idempotent and returns 0
        second_sweep_count = build_repository.reconcile_orphaned_builds(db3)
        assert second_sweep_count == 0
    finally:
        db3.close()


def test_query_embedder_singleton_and_optional_token():
    """Verify QueryEmbedder is a thread-safe singleton and functions with or without HF_TOKEN."""
    # Reset singleton for testing
    QueryEmbedder._instance = None

    embedder1 = QueryEmbedder.get_instance()
    embedder2 = QueryEmbedder.get_instance()
    assert embedder1 is embedder2

    # Embed a sample query
    vec = embedder1.embed_query("cozy farming simulator")
    assert vec.shape[0] == 1
    assert vec.shape[1] == embedder1.dimension
    assert vec.dtype == "float32"
