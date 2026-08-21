"""B7: add users, ownership fields, and saved_discoveries

Revision ID: a1b2c3d4e5f6
Revises: 7b8c9d0e1f2a
Create Date: 2026-08-16 23:10:00.000000

Migration strategy:
- Creates the users table with unique email and username.
- Adds nullable user_id FK to projects and build_jobs (backward-compatible with
  pre-B7 orphaned rows — they remain in the DB but are inaccessible via API
  because the ownership filter excludes null user_id rows).
- Creates saved_discoveries with UNIQUE(user_id, steam_app_id) constraint and
  ON DELETE CASCADE so removing a user cleans up all their bookmarks.
- Development databases should be reset with `alembic upgrade head` after
  running this migration. Production migration policy is explicitly deferred.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7b8c9d0e1f2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add auth + ownership tables for B7."""

    # 1. Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
        sa.UniqueConstraint('username', name='uq_users_username'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # 2. Add nullable user_id FK to projects
    # Nullable for backward compat with pre-B7 orphaned rows.
    # Post-B7: all API-created rows will have non-null user_id.
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_projects_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_projects_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 3. Add nullable user_id FK to build_jobs
    with op.batch_alter_table('build_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_build_jobs_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_build_jobs_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='SET NULL',
        )

    # 4. Create saved_discoveries table
    op.create_table(
        'saved_discoveries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('steam_app_id', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name='fk_saved_discoveries_user_id',
            ondelete='CASCADE',
        ),
        sa.UniqueConstraint(
            'user_id', 'steam_app_id',
            name='uq_saved_discoveries_user_game',
        ),
    )
    op.create_index(op.f('ix_saved_discoveries_id'), 'saved_discoveries', ['id'], unique=False)
    op.create_index('ix_saved_discoveries_user_id', 'saved_discoveries', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: remove B7 auth + ownership tables."""
    op.drop_index('ix_saved_discoveries_user_id', table_name='saved_discoveries')
    op.drop_index(op.f('ix_saved_discoveries_id'), table_name='saved_discoveries')
    op.drop_table('saved_discoveries')

    with op.batch_alter_table('build_jobs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_build_jobs_user_id', type_='foreignkey')
        batch_op.drop_index('ix_build_jobs_user_id')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_constraint('fk_projects_user_id', type_='foreignkey')
        batch_op.drop_index('ix_projects_user_id')
        batch_op.drop_column('user_id')

    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
