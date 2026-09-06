"""drop redundant unique indexes on users

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-06 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop redundant explicit unique indexes on users table (ix_users_email, ix_users_username).

    The table-level UniqueConstraint('email', name='uq_users_email') and
    UniqueConstraint('username', name='uq_users_username') already enforce uniqueness
    and create underlying unique constraint indexes in the database engine.

    Defensive: only drops indexes that actually exist (no-op safe on schemas that
    never created them or already removed them).
    """
    conn = op.get_bind()
    insp = inspect(conn)
    # Only drop if the users table exists and the index is present
    if 'users' in insp.get_table_names():
        existing_indexes = {idx['name'] for idx in insp.get_indexes('users')}
        if 'ix_users_email' in existing_indexes:
            op.drop_index('ix_users_email', table_name='users')
        if 'ix_users_username' in existing_indexes:
            op.drop_index('ix_users_username', table_name='users')


def downgrade() -> None:
    """Recreate explicit unique indexes on users table.

    Defensive: no-op if the users table does not exist (mirrors the upgrade guard
    for test environments that use a minimal schema without the users table).
    """
    conn = op.get_bind()
    insp = inspect(conn)
    if 'users' not in insp.get_table_names():
        return
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
