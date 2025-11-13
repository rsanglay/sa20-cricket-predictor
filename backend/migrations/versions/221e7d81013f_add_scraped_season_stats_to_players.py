"""add_scraped_season_stats_to_players

Revision ID: 221e7d81013f
Revises: 9219ef2b623e
Create Date: 2025-11-11 12:24:30.895934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '221e7d81013f'
down_revision: Union[str, None] = '9219ef2b623e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

