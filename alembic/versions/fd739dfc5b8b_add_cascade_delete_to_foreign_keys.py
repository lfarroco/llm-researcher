"""add_cascade_delete_to_foreign_keys

Revision ID: fd739dfc5b8b
Revises: b3f8a1c2d4e5
Create Date: 2026-03-10 14:14:44.456279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd739dfc5b8b'
down_revision: Union[str, None] = 'b3f8a1c2d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
