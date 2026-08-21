"""add game_dsl and runtime_metadata to projects table

Revision ID: 7b8c9d0e1f2a
Revises: efcb82ffe8c4
Create Date: 2026-08-16 21:07:30.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b8c9d0e1f2a'
down_revision: Union[str, Sequence[str], None] = 'efcb82ffe8c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('game_dsl', sa.JSON(), nullable=True))
    op.add_column('projects', sa.Column('runtime_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'runtime_metadata')
    op.drop_column('projects', 'game_dsl')
