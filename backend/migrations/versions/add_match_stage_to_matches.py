"""add_match_stage_to_matches

Revision ID: add_match_stage
Revises: 221e7d81013f
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_match_stage'
down_revision: Union[str, None] = '221e7d81013f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add match_stage column to matches table
    op.add_column('matches', sa.Column('match_stage', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove match_stage column from matches table
    op.drop_column('matches', 'match_stage')

