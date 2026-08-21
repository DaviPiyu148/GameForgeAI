"""Product Expansion V1: add avatar_url to users, user_progress, xp_events, and user_genre_preferences tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-21 18:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add avatar_url column to users table
    op.add_column('users', sa.Column('avatar_url', sa.String(length=500), nullable=True))

    # 2. Create user_progress table
    op.create_table(
        'user_progress',
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('total_xp', sa.Integer(), nullable=False, server_default="0"),
        sa.Column('current_level', sa.Integer(), nullable=False, server_default="1"),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # 3. Create xp_events table
    op.create_table(
        'xp_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('xp_amount', sa.Integer(), nullable=False),
        sa.Column('source_reference', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_xp_events_id'), 'xp_events', ['id'], unique=False)
    op.create_index(op.f('ix_xp_events_user_id'), 'xp_events', ['user_id'], unique=False)
    op.create_index(op.f('ix_xp_events_created_at'), 'xp_events', ['created_at'], unique=False)

    # 4. Create user_genre_preferences table
    op.create_table(
        'user_genre_preferences',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('genre', sa.String(length=50), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default="0.0"),
        sa.Column('interaction_count', sa.Integer(), nullable=False, server_default="1"),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'genre', name='uq_user_genre_preference')
    )
    op.create_index(op.f('ix_user_genre_preferences_id'), 'user_genre_preferences', ['id'], unique=False)
    op.create_index(op.f('ix_user_genre_preferences_user_id'), 'user_genre_preferences', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_genre_preferences_genre'), 'user_genre_preferences', ['genre'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_genre_preferences_genre'), table_name='user_genre_preferences')
    op.drop_index(op.f('ix_user_genre_preferences_user_id'), table_name='user_genre_preferences')
    op.drop_index(op.f('ix_user_genre_preferences_id'), table_name='user_genre_preferences')
    op.drop_table('user_genre_preferences')

    op.drop_index(op.f('ix_xp_events_created_at'), table_name='xp_events')
    op.drop_index(op.f('ix_xp_events_user_id'), table_name='xp_events')
    op.drop_index(op.f('ix_xp_events_id'), table_name='xp_events')
    op.drop_table('xp_events')

    op.drop_table('user_progress')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('avatar_url')
