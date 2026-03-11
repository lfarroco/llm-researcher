"""add_cascade_delete_to_foreign_keys

Revision ID: 1b10e0e3b8b9
Revises: fd739dfc5b8b
Create Date: 2026-03-10 14:14:48.980962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b10e0e3b8b9'
down_revision: Union[str, None] = 'fd739dfc5b8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add CASCADE delete to conversation_messages foreign key
    op.drop_constraint(
        'conversation_messages_research_id_fkey',
        'conversation_messages',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'conversation_messages_research_id_fkey',
        'conversation_messages',
        'research',
        ['research_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Add CASCADE delete to research_sources foreign key
    op.drop_constraint(
        'research_sources_research_id_fkey',
        'research_sources',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'research_sources_research_id_fkey',
        'research_sources',
        'research',
        ['research_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Add CASCADE delete to research_findings foreign key
    op.drop_constraint(
        'research_findings_research_id_fkey',
        'research_findings',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'research_findings_research_id_fkey',
        'research_findings',
        'research',
        ['research_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Reverse: remove CASCADE from conversation_messages
    op.drop_constraint(
        'conversation_messages_research_id_fkey',
        'conversation_messages',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'conversation_messages_research_id_fkey',
        'conversation_messages',
        'research',
        ['research_id'],
        ['id']
    )

    # Reverse: remove CASCADE from research_sources
    op.drop_constraint(
        'research_sources_research_id_fkey',
        'research_sources',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'research_sources_research_id_fkey',
        'research_sources',
        'research',
        ['research_id'],
        ['id']
    )

    # Reverse: remove CASCADE from research_findings
    op.drop_constraint(
        'research_findings_research_id_fkey',
        'research_findings',
        type_='foreignkey'
    )
    op.create_foreign_key(
        'research_findings_research_id_fkey',
        'research_findings',
        'research',
        ['research_id'],
        ['id']
    )
