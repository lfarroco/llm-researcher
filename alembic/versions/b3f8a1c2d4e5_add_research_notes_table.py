"""add research_notes table

Revision ID: b3f8a1c2d4e5
Revises: 2ebd621972ef
Create Date: 2026-03-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f8a1c2d4e5'
down_revision: Union[str, None] = '2ebd621972ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'research_notes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            'research_id', sa.Integer(),
            sa.ForeignKey('research.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('agent', sa.String(50), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        'ix_research_notes_research_id',
        'research_notes',
        ['research_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_research_notes_research_id', 'research_notes')
    op.drop_table('research_notes')
