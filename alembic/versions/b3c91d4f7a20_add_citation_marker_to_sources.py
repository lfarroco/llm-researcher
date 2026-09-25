"""add citation_marker to research_sources

The generated document numbers its citations ``[1]..[N]``. Those numbers used
to be unrelated to the ``research_sources`` primary keys, so a reader — or the
frontend, or an API client — following citation ``[16]`` could land on a
different source than the sentence was written from.

``citation_marker`` stores the marker the report actually uses for a source
(NULL when the report does not cite it), so the document, the knowledge base
and the API agree on which source a citation number points to.

Existing rows are left NULL: markers are assigned when a document is
finalized, and a backfill could only guess at a numbering the current report
may not use.

Revision ID: b3c91d4f7a20
Revises: a7f31c9d5e02
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c91d4f7a20'
down_revision: Union[str, None] = 'a7f31c9d5e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_sources",
        sa.Column("citation_marker", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_sources", "citation_marker")
