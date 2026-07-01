"""remove note category column

Revision ID: d9a7c2f4e6b1
Revises: 1b10e0e3b8b9
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a7c2f4e6b1'
down_revision: Union[str, None] = '1b10e0e3b8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('research_notes') as batch_op:
        batch_op.drop_column('category')


def downgrade() -> None:
    with op.batch_alter_table('research_notes') as batch_op:
        batch_op.add_column(
            sa.Column(
                'category',
                sa.String(length=50),
                nullable=False,
                server_default='note',
            )
        )
