"""Tests for the source-identity migration's backfill and de-duplication.

The migration must be safe on a populated database: it backfills
``dedupe_key``, reconciles pre-existing duplicate sources, and re-points
finding evidence links at the surviving row before the unique constraint is
applied. Getting this wrong would either fail the migration or silently
detach findings from their sources.

The migration is loaded by file path because ``alembic/versions`` is not an
importable package.
"""

import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "a7f31c9d5e02_add_source_identity_and_evidence.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location(
        "source_identity_migration", MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def engine():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            """
            CREATE TABLE research_sources (
                id INTEGER PRIMARY KEY,
                research_id INTEGER NOT NULL,
                url VARCHAR(2000) NOT NULL,
                title VARCHAR(500),
                dedupe_key VARCHAR(2000),
                user_notes TEXT,
                tags JSON
            )
            """
        ))
        conn.execute(sa.text(
            """
            CREATE TABLE research_findings (
                id INTEGER PRIMARY KEY,
                research_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                source_ids JSON,
                created_by VARCHAR(50)
            )
            """
        ))
    yield engine
    engine.dispose()


def add_source(conn, source_id, research_id, url, title=None, notes=None):
    conn.execute(
        sa.text(
            "INSERT INTO research_sources "
            "(id, research_id, url, title, user_notes) "
            "VALUES (:id, :rid, :url, :title, :notes)"
        ),
        {"id": source_id, "rid": research_id, "url": url,
         "title": title, "notes": notes},
    )


def add_finding(conn, finding_id, research_id, source_ids):
    conn.execute(
        sa.text(
            "INSERT INTO research_findings "
            "(id, research_id, content, source_ids, created_by) "
            "VALUES (:id, :rid, :content, :source_ids, 'ai')"
        ),
        {
            "id": finding_id,
            "rid": research_id,
            "content": "c",
            "source_ids": json.dumps(source_ids),
        },
    )


def source_keys(conn):
    return {
        row[0]: row[1]
        for row in conn.execute(sa.text(
            "SELECT id, dedupe_key FROM research_sources ORDER BY id"
        ))
    }


class TestBackfill:
    def test_backfills_key_for_every_row(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/a")
            add_source(conn, 2, 1, "https://example.com/b")
            migration._backfill_and_dedupe(conn)

            keys = source_keys(conn)
            assert all(key for key in keys.values())
            assert keys[1] != keys[2]

    def test_reconciles_duplicates_keeping_earliest(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/paper",
                       notes="user note on survivor")
            add_source(conn, 2, 1, "http://www.example.com/paper/")
            migration._backfill_and_dedupe(conn)

            rows = conn.execute(sa.text(
                "SELECT id, user_notes FROM research_sources"
            )).fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1
            # User data on the surviving row is untouched.
            assert rows[0][1] == "user note on survivor"

    def test_repoints_finding_evidence_to_survivor(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/paper")
            add_source(conn, 2, 1, "http://www.example.com/paper/")
            add_finding(conn, 10, 1, [2])

            migration._backfill_and_dedupe(conn)

            source_ids = json.loads(conn.execute(sa.text(
                "SELECT source_ids FROM research_findings WHERE id = 10"
            )).scalar())
            assert source_ids == [1]

    def test_repointing_deduplicates_within_one_finding(self, engine, migration):
        """A finding citing both spellings must not end up with a repeat."""
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/paper")
            add_source(conn, 2, 1, "http://www.example.com/paper/")
            add_finding(conn, 10, 1, [1, 2])

            migration._backfill_and_dedupe(conn)

            source_ids = json.loads(conn.execute(sa.text(
                "SELECT source_ids FROM research_findings WHERE id = 10"
            )).scalar())
            assert source_ids == [1]

    def test_preserves_other_source_references(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/paper")
            add_source(conn, 2, 1, "http://www.example.com/paper/")
            add_source(conn, 3, 1, "https://example.com/other")
            add_finding(conn, 10, 1, [3, 2])

            migration._backfill_and_dedupe(conn)

            source_ids = json.loads(conn.execute(sa.text(
                "SELECT source_ids FROM research_findings WHERE id = 10"
            )).scalar())
            # The unrelated source survives, and the duplicate is re-pointed.
            assert source_ids == [3, 1]

    def test_same_url_in_two_research_items_is_not_a_duplicate(
        self, engine, migration
    ):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/a")
            add_source(conn, 2, 2, "https://example.com/a")
            migration._backfill_and_dedupe(conn)

            assert len(source_keys(conn)) == 2

    def test_doi_urls_reconcile(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://doi.org/10.1000/ABC")
            add_source(conn, 2, 1, "http://dx.doi.org/10.1000/abc")
            migration._backfill_and_dedupe(conn)

            assert len(source_keys(conn)) == 1

    def test_idempotent_second_run(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/a")
            add_source(conn, 2, 1, "http://www.example.com/a")
            migration._backfill_and_dedupe(conn)
            first = source_keys(conn)
            # A re-run must not disturb already-canonical data.
            migration._backfill_and_dedupe(conn)
            assert source_keys(conn) == first

    def test_unique_constraint_holds_after_backfill(self, engine, migration):
        with engine.begin() as conn:
            add_source(conn, 1, 1, "https://example.com/a")
            add_source(conn, 2, 1, "http://www.example.com/a")
            migration._backfill_and_dedupe(conn)
            conn.execute(sa.text(
                "CREATE UNIQUE INDEX uq ON research_sources "
                "(research_id, dedupe_key)"
            ))
            # The constraint must now be satisfiable.
            conn.execute(sa.text(
                "INSERT INTO research_sources "
                "(id, research_id, url, dedupe_key) "
                "VALUES (3, 1, 'https://example.com/b', 'url:https://example.com/b')"
            ))
            assert len(source_keys(conn)) == 2

    def test_empty_table(self, engine, migration):
        with engine.begin() as conn:
            migration._backfill_and_dedupe(conn)
            assert source_keys(conn) == {}
