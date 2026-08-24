"""add scale and world_mode columns to projects table

Revision ID: bc9ae398f146
Revises: b3c4d5e6f7a8
Create Date: 2026-08-24 17:13:22.488833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc9ae398f146'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'projects',
        sa.Column('scale', sa.String(length=20), nullable=False, server_default='standard'),
    )
    op.add_column(
        'projects',
        sa.Column('world_mode', sa.String(length=20), nullable=False, server_default='linear'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'world_mode')
    op.drop_column('projects', 'scale')
