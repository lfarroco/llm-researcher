"""add app_settings table

Revision ID: c4d8f2a9b6e1
Revises: 2cbc80c8543e
Create Date: 2026-03-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8f2a9b6e1'
down_revision: Union[str, None] = '2cbc80c8543e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column(
            'value_type',
            sa.String(length=20),
            nullable=False,
            server_default='string',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint('key', name='uq_app_settings_key'),
    )
    op.create_index('ix_app_settings_id', 'app_settings', ['id'])
    op.create_index('ix_app_settings_key', 'app_settings', ['key'])


def downgrade() -> None:
    op.drop_index('ix_app_settings_key', table_name='app_settings')
    op.drop_index('ix_app_settings_id', table_name='app_settings')
    op.drop_table('app_settings')
