"""Game Generation V2: add playtest_sessions, project_versions, and project versioning columns

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add design_spec and current_version columns to projects
    op.add_column('projects', sa.Column('design_spec', sa.JSON(), nullable=True))
    op.add_column('projects', sa.Column('current_version', sa.Integer(), nullable=False, server_default="1"))

    # 2. Create playtest_sessions table
    op.create_table(
        'playtest_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('score', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('damage_taken', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('damage_dealt', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('enemies_defeated', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('collectibles_gathered', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('objectives_completed', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('outcome', sa.String(length=50), nullable=False, server_default="PLAYED"),
        sa.Column('telemetry_events', sa.JSON(), nullable=True),
        sa.Column('ai_analysis', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_playtest_sessions_id'), 'playtest_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_playtest_sessions_project_id'), 'playtest_sessions', ['project_id'], unique=False)
    op.create_index(op.f('ix_playtest_sessions_user_id'), 'playtest_sessions', ['user_id'], unique=False)

    # 3. Create project_versions table
    op.create_table(
        'project_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default="1"),
        sa.Column('game_dsl', sa.JSON(), nullable=False),
        sa.Column('design_spec', sa.JSON(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_project_versions_id'), 'project_versions', ['id'], unique=False)
    op.create_index(op.f('ix_project_versions_project_id'), 'project_versions', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_project_versions_project_id'), table_name='project_versions')
    op.drop_index(op.f('ix_project_versions_id'), table_name='project_versions')
    op.drop_table('project_versions')

    op.drop_index(op.f('ix_playtest_sessions_user_id'), table_name='playtest_sessions')
    op.drop_index(op.f('ix_playtest_sessions_project_id'), table_name='playtest_sessions')
    op.drop_index(op.f('ix_playtest_sessions_id'), table_name='playtest_sessions')
    op.drop_table('playtest_sessions')

    op.drop_column('projects', 'current_version')
    op.drop_column('projects', 'design_spec')
