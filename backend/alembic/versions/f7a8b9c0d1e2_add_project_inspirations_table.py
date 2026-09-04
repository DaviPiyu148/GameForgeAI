"""add project_inspirations table

Revision ID: f7a8b9c0d1e2
Revises: bc9ae398f146
Create Date: 2026-09-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'bc9ae398f146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create project_inspirations table."""
    op.create_table(
        'project_inspirations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('steam_app_id', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('cover_url', sa.String(length=500), nullable=True),
        sa.Column('genres', sa.JSON(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('player_modes', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['project_id'],
            ['projects.id'],
            name='fk_project_inspirations_project_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_id',
            'steam_app_id',
            name='uq_project_inspirations_project_game',
        ),
    )
    op.create_index(op.f('ix_project_inspirations_id'), 'project_inspirations', ['id'], unique=False)
    op.create_index('ix_project_inspirations_project_id', 'project_inspirations', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: drop project_inspirations table."""
    op.drop_index('ix_project_inspirations_project_id', table_name='project_inspirations')
    op.drop_index(op.f('ix_project_inspirations_id'), table_name='project_inspirations')
    op.drop_table('project_inspirations')
