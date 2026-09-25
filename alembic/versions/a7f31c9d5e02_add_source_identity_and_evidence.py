"""add source identity, full-text columns, and research_evidence

Adds the schema needed for idempotent source merging and full-text grounding:

* ``research_sources.dedupe_key`` — normalized URL/DOI identity, with a unique
  constraint per research item so re-running or resuming merges instead of
  duplicating.
* ``research_sources.full_text_*`` — retrieval bookkeeping for parsed PDFs.
* ``research_evidence`` — quotable passages from a source's full text.

The migration backfills ``dedupe_key`` for existing rows and reconciles
pre-existing duplicates (keeping the earliest row and re-pointing findings at
it) before the unique constraint is applied, so it is safe on a populated
database.

Revision ID: a7f31c9d5e02
Revises: 7d61b92156ce
Create Date: 2026-09-25 00:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.source_identity import source_identity


# revision identifiers, used by Alembic.
revision: str = 'a7f31c9d5e02'
down_revision: Union[str, None] = '7d61b92156ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_and_dedupe(bind) -> None:
    """Populate dedupe_key and collapse existing duplicates.

    Uses a plain connection rather than the ORM so the migration stays valid
    even if the models change later.
    """
    rows = bind.execute(sa.text(
        "SELECT id, research_id, url, title FROM research_sources "
        "ORDER BY id"
    )).fetchall()

    # key -> (research_id, surviving source id)
    canonical: dict[tuple[int, str], int] = {}
    # Every duplicate id -> the canonical id it folds into. Built for the
    # whole table before any re-pointing, so a finding referencing several
    # duplicates is re-pointed correctly in one pass.
    remap: dict[int, int] = {}

    for row in rows:
        source_id, research_id, url, title = row
        key = source_identity(url, title=title)
        identity = (research_id, key)
        survivor = canonical.get(identity)
        if survivor is None:
            canonical[identity] = source_id
            bind.execute(
                sa.text(
                    "UPDATE research_sources SET dedupe_key = :key "
                    "WHERE id = :id"
                ),
                {"key": key, "id": source_id},
            )
        else:
            remap[source_id] = survivor

    if not remap:
        return

    # Re-point finding evidence links from duplicates to the survivor before
    # deleting them, so no finding loses its supporting sources.
    findings = bind.execute(sa.text(
        "SELECT id, source_ids FROM research_findings "
        "WHERE source_ids IS NOT NULL"
    )).fetchall()

    for finding_id, raw_source_ids in findings:
        # A JSON column comes back already decoded on PostgreSQL but as a
        # string through a dialect-agnostic text() query. Handle both, and
        # never silently skip a row whose links need re-pointing.
        if isinstance(raw_source_ids, str):
            try:
                source_ids = json.loads(raw_source_ids)
            except (TypeError, ValueError):
                continue
        else:
            source_ids = raw_source_ids

        if not isinstance(source_ids, list):
            continue

        re_pointed = []
        for sid in source_ids:
            mapped = remap.get(sid, sid)
            if mapped not in re_pointed:
                re_pointed.append(mapped)
        if re_pointed == source_ids:
            continue
        bind.execute(
            sa.text(
                "UPDATE research_findings "
                "SET source_ids = :source_ids WHERE id = :id"
            ),
            {"source_ids": json.dumps(re_pointed), "id": finding_id},
        )

    for duplicate_id in remap:
        bind.execute(
            sa.text("DELETE FROM research_sources WHERE id = :id"),
            {"id": duplicate_id},
        )


def upgrade() -> None:
    op.add_column(
        'research_sources',
        sa.Column('dedupe_key', sa.String(length=2000), nullable=True),
    )
    op.add_column(
        'research_sources',
        sa.Column('full_text_status', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'research_sources',
        sa.Column('full_text_parser', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'research_sources',
        sa.Column('full_text_chars', sa.Integer(), nullable=True),
    )
    op.add_column(
        'research_sources',
        sa.Column(
            'full_text_fetched_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_research_sources_dedupe_key',
        'research_sources',
        ['dedupe_key'],
        unique=False,
    )

    op.create_table(
        'research_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('research_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('start_char', sa.Integer(), nullable=True),
        sa.Column('end_char', sa.Integer(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('section', sa.String(length=300), nullable=True),
        sa.Column('sub_query', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['research_id'], ['research.id']),
        sa.ForeignKeyConstraint(['source_id'], ['research_sources.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_research_evidence_id', 'research_evidence', ['id'], unique=False
    )
    op.create_index(
        'ix_research_evidence_source_index',
        'research_evidence',
        ['source_id', 'chunk_index'],
        unique=False,
    )

    # Backfill and reconcile before enforcing uniqueness, so the constraint
    # cannot fail on pre-existing data.
    _backfill_and_dedupe(op.get_bind())

    op.create_unique_constraint(
        'uq_research_sources_identity',
        'research_sources',
        ['research_id', 'dedupe_key'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_research_sources_identity', 'research_sources', type_='unique'
    )
    op.drop_index(
        'ix_research_evidence_source_index', table_name='research_evidence'
    )
    op.drop_index('ix_research_evidence_id', table_name='research_evidence')
    op.drop_table('research_evidence')
    op.drop_index(
        'ix_research_sources_dedupe_key', table_name='research_sources'
    )
    for column in (
        'full_text_fetched_at',
        'full_text_chars',
        'full_text_parser',
        'full_text_status',
        'dedupe_key',
    ):
        op.drop_column('research_sources', column)
