"""Add conversation messages table

Revision ID: ac9b8aa99681
Revises: 60e54212dad1
Create Date: 2026-03-04 22:46:38.102670

NOTE: This migration is intentionally a no-op. The ``conversation_messages``
table it used to create is already created by the initial schema migration
``60e54212dad1`` (which this revision was repointed at after the migration
history was squashed). Keeping the original ``op.create_table(...)`` here
makes `alembic upgrade head` fail on fresh databases with
``relation "conversation_messages" already exists``.

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'ac9b8aa99681'
down_revision: Union[str, None] = '60e54212dad1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: the conversation_messages table (and its id index) is created by
    # the initial schema migration 60e54212dad1. Re-creating it here would
    # fail with a DuplicateTable error on every fresh database.
    pass


def downgrade() -> None:
    # No-op: conversation_messages belongs to 60e54212dad1, so it must not be
    # dropped when this revision is downgraded.
    pass
