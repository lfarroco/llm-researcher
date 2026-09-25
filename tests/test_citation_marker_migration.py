"""Tests for the citation-marker migration.

``research_sources.citation_marker`` records the number the generated document
uses for a source, so the report and ``GET /research/{id}/sources`` cannot
disagree about which source citation ``[n]`` points to. The migration is a
plain additive column, but it still has to upgrade and downgrade cleanly.

The migration is loaded by file path because ``alembic/versions`` is not an
importable package (see ``tests/test_migration_source_identity.py``).
"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "b3c91d4f7a20_add_citation_marker_to_sources.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location(
        "citation_marker_migration", MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def engine():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE research_sources ("
            "id INTEGER PRIMARY KEY, url VARCHAR(2000))"
        ))
    return engine


def column_names(engine) -> list[str]:
    with engine.begin() as conn:
        return [
            row[1]
            for row in conn.execute(
                sa.text("PRAGMA table_info(research_sources)")
            )
        ]


def run(engine, migration, direction: str) -> None:
    """Run one migration direction with ``op`` bound to the test engine."""
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        getattr(migration, direction)()


def test_migration_follows_the_previous_head(migration):
    assert migration.down_revision == "a7f31c9d5e02"


def test_upgrade_adds_a_nullable_column(engine, migration):
    run(engine, migration, "upgrade")

    assert "citation_marker" in column_names(engine)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO research_sources (id, url) VALUES (1, 'https://x')"
        ))
        value = conn.execute(sa.text(
            "SELECT citation_marker FROM research_sources WHERE id = 1"
        )).scalar()
    # Existing rows are left without a marker rather than guessing a number.
    assert value is None


def test_downgrade_removes_the_column(engine, migration):
    run(engine, migration, "upgrade")
    run(engine, migration, "downgrade")

    assert "citation_marker" not in column_names(engine)
