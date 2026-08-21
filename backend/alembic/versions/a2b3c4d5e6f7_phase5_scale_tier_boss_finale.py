"""Phase 5: add scale column to build_jobs table (generation scale tier: prototype/standard/campaign)

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-08-22 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'build_jobs',
        sa.Column('scale', sa.String(length=20), nullable=False, server_default='standard'),
    )


def downgrade() -> None:
    op.drop_column('build_jobs', 'scale')
