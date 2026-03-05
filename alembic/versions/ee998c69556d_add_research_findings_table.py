"""add_research_findings_table

Revision ID: ee998c69556d
Revises: 2ebd621972ef
Create Date: 2026-03-04 23:58:32.831761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee998c69556d'
down_revision: Union[str, None] = '2ebd621972ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'research_findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('research_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source_ids', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=50),
                  nullable=True, server_default='user'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['research_id'], ['research.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_findings_id'),
                    'research_findings', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_research_findings_id'),
                  table_name='research_findings')
    op.drop_table('research_findings')
