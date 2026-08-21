"""Creator Progression V1: add user_milestones table with unique constraint on (user_id, milestone_key)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-21 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_milestones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('milestone_key', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'milestone_key', name='uq_user_milestones_user_key')
    )
    op.create_index(op.f('ix_user_milestones_id'), 'user_milestones', ['id'], unique=False)
    op.create_index(op.f('ix_user_milestones_user_id'), 'user_milestones', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_milestones_milestone_key'), 'user_milestones', ['milestone_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_milestones_milestone_key'), table_name='user_milestones')
    op.drop_index(op.f('ix_user_milestones_user_id'), table_name='user_milestones')
    op.drop_index(op.f('ix_user_milestones_id'), table_name='user_milestones')
    op.drop_table('user_milestones')
