"""
Unit and integration tests for User table redundant unique indexes cleanup (ADV-DB-002).

Tests:
1. Migration upgrade -> downgrade -> upgrade cycle on SQLite:
   - Verifies ix_users_email and ix_users_username dropped on upgrade.
   - Verifies exact user rows preserved with 0 data loss.
   - Verifies post-conditions: exactly 2 unique constraint indexes (origin='u'),
     zero redundant explicit unique indexes (origin='c' + unique=1),
     and non-unique index ix_users_id preserved.
   - Verifies uniqueness constraints on email and username enforced after upgrade.
   - Verifies downgrade restores explicit indexes.
   - Verifies re-upgrade drops them cleanly again.
2. SQLAlchemy User model table inspection:
   - Verifies explicit indexes do NOT contain ix_users_email or ix_users_username.
   - Verifies table-level UniqueConstraints (uq_users_email, uq_users_username) exist.
   - Verifies SQLite DDL generated from Base.metadata enforces uniqueness without duplicate indexes.
"""
import os
import sqlite3
import subprocess
import uuid
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.user import User


def test_user_model_metadata_has_no_redundant_explicit_unique_indexes():
    """
    Verify SQLAlchemy User model metadata:
    - Explicit indexes must only include ix_users_id (no ix_users_email or ix_users_username).
    - Table constraints must include named UniqueConstraint for email and username.
    """
    table = User.__table__
    index_names = {idx.name for idx in table.indexes}
    assert "ix_users_id" in index_names, "ix_users_id should be defined on User model."
    assert "ix_users_email" not in index_names, "ix_users_email should not be explicitly defined as an index."
    assert "ix_users_username" not in index_names, "ix_users_username should not be explicitly defined as an index."

    # Check unique constraints
    constraint_names = {c.name for c in table.constraints if hasattr(c, "name") and c.name}
    assert "uq_users_email" in constraint_names, "uq_users_email UniqueConstraint must be present."
    assert "uq_users_username" in constraint_names, "uq_users_username UniqueConstraint must be present."


def test_sqlite_in_memory_schema_index_census_and_uniqueness():
    """
    Verify that creating tables from Base.metadata in SQLite:
    - Creates exactly 2 unique constraint indexes (origin='u') for email and username.
    - Creates zero redundant explicit unique indexes (origin='c' with unique=1).
    - Preserves non-unique index ix_users_id.
    - Blocks duplicate email and duplicate username.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    with engine.connect() as conn:
        raw_con = conn.connection.dbapi_connection
        cursor = raw_con.cursor()
        cursor.execute("PRAGMA index_list('users')")
        index_list = cursor.fetchall()
        # Each row in index_list: (seq, name, unique, origin, partial)
        # origin: 'c' = created via CREATE INDEX, 'u' = created by UNIQUE constraint, 'pk' = PRIMARY KEY

        # Filter by origin and unique
        u_indexes = [idx for idx in index_list if idx[3] == "u"]
        c_unique_indexes = [idx for idx in index_list if idx[3] == "c" and idx[2] == 1]
        c_non_unique_indexes = [idx for idx in index_list if idx[3] == "c" and idx[2] == 0]

        # Post-condition 1: Exactly 2 unique constraint indexes (origin='u')
        assert len(u_indexes) == 2, f"Expected exactly 2 unique constraint indexes (origin='u'), got {len(u_indexes)}"

        # Post-condition 2: Zero redundant explicit unique copies (origin='c' + unique=1)
        assert len(c_unique_indexes) == 0, f"Expected 0 explicit unique indexes (origin='c' + unique=1), got {c_unique_indexes}"

        # Post-condition 3: Non-unique ix_users_id preserved
        assert len(c_non_unique_indexes) == 1
        assert c_non_unique_indexes[0][1] == "ix_users_id"

    # Verify uniqueness enforcement
    u1 = User(id=str(uuid.uuid4()), email="test@test.com", username="testuser", password_hash="hash")
    session.add(u1)
    session.commit()

    # Duplicate email
    u_dup_email = User(id=str(uuid.uuid4()), email="test@test.com", username="otheruser", password_hash="hash")
    session.add(u_dup_email)
    with pytest.raises(Exception) as exc_info:
        session.commit()
    session.rollback()
    assert "UNIQUE constraint failed" in str(exc_info.value) or "IntegrityError" in type(exc_info.value).__name__

    # Duplicate username
    u_dup_username = User(id=str(uuid.uuid4()), email="other@test.com", username="testuser", password_hash="hash")
    session.add(u_dup_username)
    with pytest.raises(Exception) as exc_info:
        session.commit()
    session.rollback()
    assert "UNIQUE constraint failed" in str(exc_info.value) or "IntegrityError" in type(exc_info.value).__name__

    session.close()


def test_alembic_migration_upgrade_downgrade_cycle(tmp_path):
    """
    Test complete migration lifecycle on a real SQLite database file:
    1. Start with schema at e1f2a3b4c5d6 (containing redundant ix_users_email and ix_users_username).
    2. Populate with multiple user rows.
    3. Run 'alembic upgrade head' (f2a3b4c5d6e7).
    4. Assert:
       - All user rows preserved with 100% exact data.
       - ix_users_email and ix_users_username dropped.
       - Exactly 2 unique constraint indexes (origin='u') exist.
       - Zero redundant explicit unique indexes (origin='c' + unique=1).
       - ix_users_id preserved.
       - Uniqueness constraints enforced (duplicate inserts rejected).
    5. Run 'alembic downgrade -1' (back to e1f2a3b4c5d6).
    6. Assert:
       - All user rows preserved.
       - ix_users_email and ix_users_username restored.
    7. Run 'alembic upgrade head' (re-upgrade).
       - Assert explicit unique indexes dropped again and all users preserved.
    """
    test_db_path = tmp_path / "test_user_indexes.db"
    conn = sqlite3.connect(str(test_db_path))

    # Create users table matching migration e1f2a3b4c5d6 state
    conn.execute('''
        CREATE TABLE users (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            email VARCHAR(254) NOT NULL,
            username VARCHAR(50) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            token_version INTEGER NOT NULL DEFAULT 1,
            avatar_url VARCHAR(500),
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CONSTRAINT uq_users_email UNIQUE (email),
            CONSTRAINT uq_users_username UNIQUE (username)
        )
    ''')
    conn.execute("CREATE INDEX ix_users_id ON users (id)")
    conn.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    conn.execute("CREATE UNIQUE INDEX ix_users_username ON users (username)")

    # Alembic version table set to e1f2a3b4c5d6
    conn.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)')
    conn.execute("INSERT INTO alembic_version (version_num) VALUES ('e1f2a3b4c5d6')")

    # Insert 5 test users
    initial_users = [
        (str(uuid.uuid4()), f"user{i}@example.com", f"user_{i}", "hash", 1, 1, "2026-09-06 12:00:00", "2026-09-06 12:00:00")
        for i in range(5)
    ]
    conn.executemany(
        "INSERT INTO users (id, email, username, password_hash, level, token_version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        initial_users,
    )
    conn.commit()

    # Pre-upgrade check: 6 indexes exist (1 pk, 2 u, 2 c-unique, 1 c-non-unique)
    pre_indexes = conn.execute("PRAGMA index_list('users')").fetchall()
    pre_index_names = {idx[1] for idx in pre_indexes}
    assert "ix_users_email" in pre_index_names
    assert "ix_users_username" in pre_index_names
    assert "ix_users_id" in pre_index_names
    conn.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{test_db_path}"

    # 1. UPGRADE
    res_up = subprocess.run(
        [".venv/Scripts/alembic.exe", "upgrade", "head"],
        cwd="C:/Users/Piyush148/Documents/AI Game/backend",
        env=env,
        capture_output=True,
        text=True,
    )
    assert res_up.returncode == 0, f"Upgrade failed: {res_up.stderr}"

    # Verify post-conditions on SQLite schema
    conn = sqlite3.connect(str(test_db_path))
    post_indexes = conn.execute("PRAGMA index_list('users')").fetchall()
    post_index_names = {idx[1] for idx in post_indexes}

    # Redundant explicit indexes dropped
    assert "ix_users_email" not in post_index_names
    assert "ix_users_username" not in post_index_names

    # Non-unique index preserved
    assert "ix_users_id" in post_index_names

    # Census breakdown
    u_indexes = [idx for idx in post_indexes if idx[3] == "u"]
    c_unique_indexes = [idx for idx in post_indexes if idx[3] == "c" and idx[2] == 1]
    c_non_unique_indexes = [idx for idx in post_indexes if idx[3] == "c" and idx[2] == 0]

    assert len(u_indexes) == 2, f"Expected exactly 2 unique constraint indexes, got {len(u_indexes)}"
    assert len(c_unique_indexes) == 0, f"Expected 0 redundant explicit unique indexes, got {c_unique_indexes}"
    assert len(c_non_unique_indexes) == 1 and c_non_unique_indexes[0][1] == "ix_users_id"

    # Verify all 5 users preserved
    rows = conn.execute("SELECT id, email, username FROM users ORDER BY username").fetchall()
    assert len(rows) == 5
    assert [r[1] for r in rows] == [f"user{i}@example.com" for i in range(5)]

    # Verify uniqueness still enforced by SQLite
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (id, email, username, password_hash, level, token_version, created_at, updated_at) "
            "VALUES ('new-1', 'user0@example.com', 'unique_new', 'h', 1, 1, '2026-09-06', '2026-09-06')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (id, email, username, password_hash, level, token_version, created_at, updated_at) "
            "VALUES ('new-2', 'unique_new@example.com', 'user_0', 'h', 1, 1, '2026-09-06', '2026-09-06')"
        )
    conn.close()

    # 2. DOWNGRADE
    res_down = subprocess.run(
        [".venv/Scripts/alembic.exe", "downgrade", "-1"],
        cwd="C:/Users/Piyush148/Documents/AI Game/backend",
        env=env,
        capture_output=True,
        text=True,
    )
    assert res_down.returncode == 0, f"Downgrade failed: {res_down.stderr}"

    conn = sqlite3.connect(str(test_db_path))
    down_indexes = conn.execute("PRAGMA index_list('users')").fetchall()
    down_index_names = {idx[1] for idx in down_indexes}
    assert "ix_users_email" in down_index_names
    assert "ix_users_username" in down_index_names
    down_rows = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert down_rows == 5
    conn.close()

    # 3. RE-UPGRADE
    res_reup = subprocess.run(
        [".venv/Scripts/alembic.exe", "upgrade", "head"],
        cwd="C:/Users/Piyush148/Documents/AI Game/backend",
        env=env,
        capture_output=True,
        text=True,
    )
    assert res_reup.returncode == 0, f"Re-upgrade failed: {res_reup.stderr}"

    conn = sqlite3.connect(str(test_db_path))
    reup_indexes = conn.execute("PRAGMA index_list('users')").fetchall()
    reup_index_names = {idx[1] for idx in reup_indexes}
    assert "ix_users_email" not in reup_index_names
    assert "ix_users_username" not in reup_index_names
    assert "ix_users_id" in reup_index_names
    reup_rows = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert reup_rows == 5
    conn.close()
