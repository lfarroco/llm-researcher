"""add user_notes and tags to research_sources

Revision ID: 2ebd621972ef
Revises: ac9b8aa99681
Create Date: 2026-03-04 23:19:22.697765

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ebd621972ef'
down_revision: Union[str, None] = 'ac9b8aa99681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_notes and tags columns to research_sources table
    op.add_column('research_sources', sa.Column(
        'user_notes', sa.Text(), nullable=True))
    op.add_column('research_sources', sa.Column(
        'tags', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove user_notes and tags columns from research_sources table
    op.drop_column('research_sources', 'tags')
    op.drop_column('research_sources', 'user_notes')
