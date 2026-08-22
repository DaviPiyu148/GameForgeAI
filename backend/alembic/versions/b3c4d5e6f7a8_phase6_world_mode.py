"""Phase 6: add world_mode column to build_jobs table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'build_jobs',
        sa.Column('world_mode', sa.String(length=20), nullable=False, server_default='linear'),
    )


def downgrade() -> None:
    op.drop_column('build_jobs', 'world_mode')
