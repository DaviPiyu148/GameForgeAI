"""
Unit and integration tests for BuildLog foreign key cascade and retention pruning (ADV-DB-001).

Tests:
1. Preflight migration orphan check: fails explicitly if orphan rows exist (no silent deletion).
2. Migration upgrade -> downgrade -> upgrade cycle with exact ID preservation.
3. Foreign key ON DELETE CASCADE: deleting a BuildJob deletes its logs while preserving unrelated logs.
4. Retention pruning matrix:
   - Terminal + old completed_at: pruned
   - Terminal + recent completed_at: retained
   - Active (RUNNING) + old created_at: retained
   - Active (QUEUED) + old created_at: retained
   - Cancelled + old completed_at: pruned
   - Terminal + completed_at=NULL + old created_at: pruned (fallback to created_at)
   - Terminal + completed_at=NULL + recent created_at: retained
   - Active (RUNNING) + completed_at=NULL + old created_at: retained
"""
import os
import shutil
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.build import BuildJob
from app.models.build_log import BuildLog
from app.repositories.build_repo import build_repository


@pytest.fixture
def sqlite_fk_session():
    """Isolated in-memory SQLite session with PRAGMA foreign_keys=ON."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_con, con_record):
        cursor = dbapi_con.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_build_log_foreign_key_cascade_deletes_target_and_preserves_unrelated(sqlite_fk_session):
    """
    Test ON DELETE CASCADE:
    Deleting target BuildJob deletes all associated BuildLog rows.
    Unrelated BuildJob and its BuildLog rows remain 100% intact.
    """
    db = sqlite_fk_session
    now = datetime.now(timezone.utc)

    # 1. Create target build job and unrelated build job
    target_job = BuildJob(
        id=str(uuid.uuid4()),
        prompt="Target game concept",
        status="SUCCESS",
        created_at=now,
        completed_at=now,
    )
    unrelated_job = BuildJob(
        id=str(uuid.uuid4()),
        prompt="Unrelated game concept",
        status="RUNNING",
        created_at=now,
    )
    db.add_all([target_job, unrelated_job])
    db.commit()

    # 2. Add logs to both jobs
    target_logs = [
        BuildLog(id=str(uuid.uuid4()), build_id=target_job.id, sequence_number=1, level="INFO", message="Target log 1"),
        BuildLog(id=str(uuid.uuid4()), build_id=target_job.id, sequence_number=2, level="INFO", message="Target log 2"),
        BuildLog(id=str(uuid.uuid4()), build_id=target_job.id, sequence_number=3, level="SUCCESS", message="Target log 3"),
    ]
    unrelated_logs = [
        BuildLog(id=str(uuid.uuid4()), build_id=unrelated_job.id, sequence_number=1, level="INFO", message="Unrelated log 1"),
        BuildLog(id=str(uuid.uuid4()), build_id=unrelated_job.id, sequence_number=2, level="INFO", message="Unrelated log 2"),
    ]
    db.add_all(target_logs + unrelated_logs)
    db.commit()

    target_log_ids = {l.id for l in target_logs}
    unrelated_log_ids = {l.id for l in unrelated_logs}

    # 3. Delete target build job
    db.delete(target_job)
    db.commit()

    # 4. Assert target logs are deleted and unrelated logs are retained
    remaining_target_logs = db.query(BuildLog).filter(BuildLog.id.in_(target_log_ids)).all()
    assert len(remaining_target_logs) == 0, "Target build logs should have been deleted via CASCADE."

    remaining_unrelated_logs = db.query(BuildLog).filter(BuildLog.id.in_(unrelated_log_ids)).all()
    assert len(remaining_unrelated_logs) == 2, "Unrelated build logs must remain intact."
    assert {l.id for l in remaining_unrelated_logs} == unrelated_log_ids


def test_prune_build_logs_full_matrix(sqlite_fk_session):
    """
    Test retention pruning policy across all status and timestamp combinations:
    1. Terminal ('SUCCESS') + completed_at > 30 days old -> PRUNED
    2. Terminal ('ERROR') + completed_at < 30 days old -> RETAINED
    3. Active ('RUNNING') + created_at > 30 days old -> RETAINED (non-terminal never pruned)
    4. Active ('QUEUED') + created_at > 30 days old -> RETAINED (non-terminal never pruned)
    5. Terminal ('CANCELLED') + completed_at > 30 days old -> PRUNED
    6. Terminal ('ERROR') + completed_at=NULL + created_at > 30 days old -> PRUNED (fallback to created_at)
    7. Terminal ('SUCCESS') + completed_at=NULL + created_at < 30 days old -> RETAINED (fallback to created_at)
    8. Active ('RUNNING') + completed_at=NULL + created_at > 30 days old -> RETAINED
    """
    db = sqlite_fk_session
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=35)
    recent_time = now - timedelta(days=10)

    # Job 1: Terminal ('SUCCESS') + old completed_at -> should be pruned
    job_terminal_old = BuildJob(
        id=str(uuid.uuid4()), prompt="Old terminal", status="SUCCESS",
        created_at=old_time, completed_at=old_time,
    )
    # Job 2: Terminal ('ERROR') + recent completed_at -> should be retained
    job_terminal_recent = BuildJob(
        id=str(uuid.uuid4()), prompt="Recent terminal", status="ERROR",
        created_at=recent_time, completed_at=recent_time,
    )
    # Job 3: Active ('RUNNING') + old created_at -> should be retained
    job_running_old = BuildJob(
        id=str(uuid.uuid4()), prompt="Old running", status="RUNNING",
        created_at=old_time, completed_at=None,
    )
    # Job 4: Active ('QUEUED') + old created_at -> should be retained
    job_queued_old = BuildJob(
        id=str(uuid.uuid4()), prompt="Old queued", status="QUEUED",
        created_at=old_time, completed_at=None,
    )
    # Job 5: Terminal ('CANCELLED') + old completed_at -> should be pruned
    job_cancelled_old = BuildJob(
        id=str(uuid.uuid4()), prompt="Old cancelled", status="CANCELLED",
        created_at=old_time, completed_at=old_time,
    )
    # Job 6: Terminal ('ERROR') + completed_at=NULL + old created_at -> should be pruned (fallback)
    job_null_comp_old = BuildJob(
        id=str(uuid.uuid4()), prompt="Null completed old", status="ERROR",
        created_at=old_time, completed_at=None,
    )
    # Job 7: Terminal ('SUCCESS') + completed_at=NULL + recent created_at -> should be retained (fallback)
    job_null_comp_recent = BuildJob(
        id=str(uuid.uuid4()), prompt="Null completed recent", status="SUCCESS",
        created_at=recent_time, completed_at=None,
    )
    # Job 8: Active ('RUNNING') + completed_at=NULL + old created_at -> should be retained
    job_running_null_old = BuildJob(
        id=str(uuid.uuid4()), prompt="Running null old", status="RUNNING",
        created_at=old_time, completed_at=None,
    )

    jobs = [
        job_terminal_old, job_terminal_recent, job_running_old, job_queued_old,
        job_cancelled_old, job_null_comp_old, job_null_comp_recent, job_running_null_old
    ]
    db.add_all(jobs)
    db.commit()

    # Add 2 logs per job (16 logs total)
    logs = []
    for j in jobs:
        logs.append(BuildLog(id=str(uuid.uuid4()), build_id=j.id, sequence_number=1, level="INFO", message=f"Log 1 for {j.prompt}"))
        logs.append(BuildLog(id=str(uuid.uuid4()), build_id=j.id, sequence_number=2, level="INFO", message=f"Log 2 for {j.prompt}"))
    db.add_all(logs)
    db.commit()

    assert db.query(BuildLog).count() == 16

    # Execute pruning with 30-day threshold
    pruned_count = build_repository.prune_build_logs(db, max_age_days=30)

    # Expected pruned jobs: job_terminal_old (2), job_cancelled_old (2), job_null_comp_old (2) = 6 logs pruned
    assert pruned_count == 6, f"Expected exactly 6 logs pruned, got {pruned_count}"

    # Verify pruned jobs have 0 logs
    for j in [job_terminal_old, job_cancelled_old, job_null_comp_old]:
        count = db.query(BuildLog).filter(BuildLog.build_id == j.id).count()
        assert count == 0, f"Job {j.prompt} logs should be pruned."

    # Verify retained jobs still have all 2 logs (10 logs total)
    for j in [job_terminal_recent, job_running_old, job_queued_old, job_null_comp_recent, job_running_null_old]:
        count = db.query(BuildLog).filter(BuildLog.build_id == j.id).count()
        assert count == 2, f"Job {j.prompt} logs must be retained."

    assert db.query(BuildLog).count() == 10


def test_migration_orphan_preflight_aborts_without_deleting_data(tmp_path):
    """
    Test migration preflight:
    If orphan rows exist in build_logs referencing non-existent build_jobs,
    the migration MUST abort with an explicit error and MUST NOT delete any data.
    """
    test_db_path = tmp_path / "test_orphan.db"
    conn = sqlite3.connect(str(test_db_path))

    # Create schema up to pre-migration state (c1d2e3f4a5b6)
    conn.execute('''
        CREATE TABLE build_jobs (
            id VARCHAR(36) PRIMARY KEY,
            prompt TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE build_logs (
            id VARCHAR(36) PRIMARY KEY,
            build_id VARCHAR(36) NOT NULL,
            sequence_number INTEGER NOT NULL,
            level VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
    ''')
    # Alembic version table set to c1d2e3f4a5b6
    conn.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)')
    conn.execute("INSERT INTO alembic_version (version_num) VALUES ('c1d2e3f4a5b6')")

    # Insert 1 legitimate job + log
    conn.execute("INSERT INTO build_jobs (id, prompt, status, created_at) VALUES ('job-1', 'Prompt 1', 'SUCCESS', '2026-09-06 12:00:00')")
    conn.execute("INSERT INTO build_logs (id, build_id, sequence_number, level, message, timestamp) VALUES ('log-1', 'job-1', 1, 'INFO', 'Valid log', '2026-09-06 12:00:00')")

    # Insert 1 orphan log pointing to non-existent 'orphan-job-id'
    conn.execute("INSERT INTO build_logs (id, build_id, sequence_number, level, message, timestamp) VALUES ('orphan-log-1', 'orphan-job-id', 1, 'INFO', 'Orphan log', '2026-09-06 12:00:00')")
    conn.commit()
    conn.close()

    # Run alembic upgrade head
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    proc = subprocess.run(
        [".venv/Scripts/alembic.exe", "upgrade", "head"],
        cwd="C:/Users/Piyush148/Documents/AI Game/backend",
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0, "Migration should fail when orphan records are present."
    assert "Found 1 orphaned build_log record(s)" in proc.stderr
    assert "Schema migration will not silently delete data" in proc.stderr

    # Verify zero data was deleted
    conn = sqlite3.connect(str(test_db_path))
    orphan_row = conn.execute("SELECT id FROM build_logs WHERE id='orphan-log-1'").fetchone()
    assert orphan_row is not None, "Orphan row MUST NOT be silently deleted."
    assert conn.execute("SELECT COUNT(*) FROM build_logs").fetchone()[0] == 2
    conn.close()


def test_migration_upgrade_downgrade_cycle_preserves_exact_ids(tmp_path):
    """
    Test complete migration lifecycle on SQLite:
    1. Upgrade to e1f2a3b4c5d6 -> verify PRAGMA foreign_key_list has FK with CASCADE.
    2. Verify exact set of BuildLog IDs is preserved.
    3. Downgrade to c1d2e3f4a5b6 -> verify PRAGMA foreign_key_list is empty.
    4. Verify exact set of BuildLog IDs is preserved.
    5. Re-upgrade to e1f2a3b4c5d6 -> verify FK is restored and exact IDs preserved.
    """
    test_db_path = tmp_path / "test_lifecycle.db"
    conn = sqlite3.connect(str(test_db_path))

    conn.execute('''
        CREATE TABLE build_jobs (
            id VARCHAR(36) PRIMARY KEY,
            prompt TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE build_logs (
            id VARCHAR(36) PRIMARY KEY,
            build_id VARCHAR(36) NOT NULL,
            sequence_number INTEGER NOT NULL,
            level VARCHAR(20) NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
    ''')
    conn.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)')
    conn.execute("INSERT INTO alembic_version (version_num) VALUES ('c1d2e3f4a5b6')")

    # Insert 5 valid jobs and 15 logs
    original_log_ids = set()
    for i in range(5):
        job_id = f"job-{i}"
        conn.execute("INSERT INTO build_jobs (id, prompt, status, created_at) VALUES (?, ?, ?, ?)", (job_id, f"Prompt {i}", "SUCCESS", "2026-09-06 12:00:00"))
        for seq in range(1, 4):
            log_id = f"log-{i}-{seq}"
            original_log_ids.add(log_id)
            conn.execute("INSERT INTO build_logs (id, build_id, sequence_number, level, message, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                         (log_id, job_id, seq, "INFO", f"Message {seq}", "2026-09-06 12:00:00"))
    conn.commit()
    conn.close()

    assert len(original_log_ids) == 15

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    # 1. Upgrade to HEAD (applies e1f2a3b4c5d6 and any subsequent migrations)
    res_up = subprocess.run([".venv/Scripts/alembic.exe", "upgrade", "head"], cwd="C:/Users/Piyush148/Documents/AI Game/backend", env=env, capture_output=True, text=True)
    assert res_up.returncode == 0, f"Upgrade failed: {res_up.stderr}"

    conn = sqlite3.connect(str(test_db_path))
    fk_list = conn.execute("PRAGMA foreign_key_list(build_logs)").fetchall()
    # Format: (id, seq, table, from, to, on_update, on_delete, match)
    assert len(fk_list) == 1
    assert fk_list[0][2] == "build_jobs"
    assert fk_list[0][3] == "build_id"
    assert fk_list[0][6] == "CASCADE"
    up_ids = set(r[0] for r in conn.execute("SELECT id FROM build_logs").fetchall())
    assert up_ids == original_log_ids, "Exact BuildLog IDs must be preserved after upgrade."
    conn.close()

    # 2. Downgrade explicitly past the FK migration (to c1d2e3f4a5b6)
    res_down = subprocess.run([".venv/Scripts/alembic.exe", "downgrade", "c1d2e3f4a5b6"], cwd="C:/Users/Piyush148/Documents/AI Game/backend", env=env, capture_output=True, text=True)
    assert res_down.returncode == 0, f"Downgrade failed: {res_down.stderr}"

    conn = sqlite3.connect(str(test_db_path))
    fk_list_down = conn.execute("PRAGMA foreign_key_list(build_logs)").fetchall()
    assert len(fk_list_down) == 0, "FK should be removed after downgrade past e1f2a3b4c5d6."
    down_ids = set(r[0] for r in conn.execute("SELECT id FROM build_logs").fetchall())
    assert down_ids == original_log_ids, "Exact BuildLog IDs must be preserved after downgrade."
    conn.close()

    # 3. Re-upgrade to HEAD
    res_reup = subprocess.run([".venv/Scripts/alembic.exe", "upgrade", "head"], cwd="C:/Users/Piyush148/Documents/AI Game/backend", env=env, capture_output=True, text=True)
    assert res_reup.returncode == 0, f"Re-upgrade failed: {res_reup.stderr}"

    conn = sqlite3.connect(str(test_db_path))
    fk_list_reup = conn.execute("PRAGMA foreign_key_list(build_logs)").fetchall()
    assert len(fk_list_reup) == 1
    assert fk_list_reup[0][6] == "CASCADE"
    reup_ids = set(r[0] for r in conn.execute("SELECT id FROM build_logs").fetchall())
    assert reup_ids == original_log_ids, "Exact BuildLog IDs must be preserved after re-upgrade."
    conn.close()

