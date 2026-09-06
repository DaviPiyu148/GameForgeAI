"""add foreign key cascade to build_logs

Revision ID: e1f2a3b4c5d6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-06 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add foreign key constraint with CASCADE delete to build_logs.build_id."""
    conn = op.get_bind()

    # Preflight integrity check: do NOT silently delete orphan rows.
    # If any orphan logs exist whose build_id is not present in build_jobs, abort the migration.
    orphan_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM build_logs WHERE build_id NOT IN (SELECT id FROM build_jobs)")
    ).scalar()

    if orphan_count and orphan_count > 0:
        raise RuntimeError(
            f"Migration e1f2a3b4c5d6 aborted: Found {orphan_count} orphaned build_log record(s) "
            f"referencing non-existent build_jobs. Schema migration will not silently delete data. "
            f"Operator action required to inspect and reconcile or purge orphan records before applying foreign key constraint."
        )

    # Use batch_alter_table for SQLite schema modification
    with op.batch_alter_table('build_logs') as batch_op:
        batch_op.create_foreign_key(
            'fk_build_logs_build_id_build_jobs',
            'build_jobs',
            ['build_id'],
            ['id'],
            ondelete='CASCADE',
        )


def downgrade() -> None:
    """Downgrade schema: drop foreign key constraint from build_logs."""
    with op.batch_alter_table('build_logs') as batch_op:
        batch_op.drop_constraint('fk_build_logs_build_id_build_jobs', type_='foreignkey')
