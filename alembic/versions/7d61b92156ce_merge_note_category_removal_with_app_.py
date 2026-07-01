"""merge note-category removal with app-settings head

Revision ID: 7d61b92156ce
Revises: c4d8f2a9b6e1, d9a7c2f4e6b1
Create Date: 2026-07-01 10:15:34.684187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d61b92156ce'
down_revision: Union[str, None] = ('c4d8f2a9b6e1', 'd9a7c2f4e6b1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
