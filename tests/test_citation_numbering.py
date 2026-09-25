"""Tests for reader-facing citation numbering.

The defect these cover: the finished document numbered its citations with the
pipeline's collection markers (which have gaps after uncited sources are
dropped), while ``GET /research/{id}/sources`` returned the knowledge base's
row ids. Following citation ``[16]`` in a report could therefore land on a
different source than the sentence was written from.

``renumber_document`` assigns one contiguous ``1..N`` sequence, rewrites the
inline markers to match, and returns the marker for each source identity so the
API can publish the same number.
"""

import pytest

from app import models
from app.database import Base
import app.database as db_module
from app.memory.research_state import Citation, SourceType
from app.services.citation_numbering import (
    cited_markers_in_order,
    format_reference_line,
    marker_number,
    renumber_document,
    split_references,
)
from app.services.research_service import save_citations_to_db


def make_citation(marker: int, url: str, title: str, **kwargs) -> Citation:
    return Citation(
        id=f"[{marker}]",
        url=url,
        title=title,
        snippet=kwargs.pop("snippet", f"snippet for {title}"),
        source_type=kwargs.pop("source_type", SourceType.WEB),
        relevance_score=kwargs.pop("relevance_score", 0.5),
        **kwargs,
    )


def build_document(body: str, references: str = "[0] placeholder\n") -> str:
    """Build a document shaped like the formatter's output."""
    return (
        "# Research Report: a query\n\n---\n\n"
        f"{body}\n\n---\n\n## References\n\n{references}"
    )


class TestMarkerHelpers:
    def test_marker_number_parses_bracketed_id(self):
        assert marker_number("[17]") == 17
        assert marker_number("article [3]") == 3
        assert marker_number("") is None
        assert marker_number(None) is None
        # Bare digits are not markers; ids are always bracketed.
        assert marker_number("17") is None

    def test_cited_markers_in_order_is_reading_order(self):
        body = "claim [3] then [1] then [3] again"
        assert cited_markers_in_order(body) == [3, 1]

    def test_split_references_finds_heading(self):
        document = "body text\n\n## References\n\n[1] a\n"
        body, refs = split_references(document)
        assert body == "body text"
        assert refs.startswith("[1] a")

    def test_split_references_without_heading(self):
        assert split_references("just prose") == ("just prose", "")

    def test_reference_line_omits_missing_author(self):
        citation = make_citation(2, "https://example.com/a", "A title")
        citation.author = None
        line = format_reference_line(citation, 2)
        assert line.startswith('[2] "A title." Retrieved from')
        assert "None" not in line

    def test_reference_line_includes_author(self):
        citation = make_citation(2, "https://example.com/a", "A title")
        citation.author = "Ada Lovelace"
        assert format_reference_line(citation, 2).startswith(
            '[2] Ada Lovelace. "A title."'
        )


class TestRenumberDocument:
    def test_closes_gaps_and_rewrites_inline_markers(self):
        citations = [
            make_citation(1, "https://example.com/1", "One"),
            make_citation(2, "https://example.com/2", "Two"),
            make_citation(5, "https://example.com/5", "Five"),
            make_citation(7, "https://example.com/7", "Seven"),
        ]
        # Marker 2 is never cited; 5 and 7 are cited first.
        document = build_document(
            "first claim [5] then [7] then [1]"
        )

        new_document, markers = renumber_document(document, citations)
        body, references = split_references(new_document)

        assert "[5]" not in body and "[7]" not in body
        assert body.endswith("first claim [1] then [2] then [3]")
        assert cited_markers_in_order(body) == [1, 2, 3]
        assert markers == {
            "url:https://example.com/5": 1,
            "url:https://example.com/7": 2,
            "url:https://example.com/1": 3,
        }
        # Uncited source 2 is dropped from the reference list entirely.
        assert "Two" not in references
        assert renumbered_reference_markers(references) == [1, 2, 3]

    def test_reference_list_has_no_gaps(self):
        citations = [
            make_citation(i, f"https://example.com/{i}", f"Source {i}")
            for i in (1, 2, 3, 11, 12, 18)
        ]
        document = build_document("a [11] b [18] c [1] d [2] e [3] f [12]")

        new_document, _ = renumber_document(document, citations)
        _, references = split_references(new_document)

        assert renumbered_reference_markers(references) == [1, 2, 3, 4, 5, 6]

    def test_reference_entries_follow_first_appearance(self):
        citations = [
            make_citation(4, "https://example.com/4", "Fourth"),
            make_citation(9, "https://example.com/9", "Ninth"),
        ]
        document = build_document("see [9] and [4]")

        new_document, markers = renumber_document(document, citations)
        body, references = split_references(new_document)

        # [9] appears first in the prose, so it becomes [1].
        assert body.endswith("see [1] and [2]")
        entries = [e for e in references.split("\n\n") if e.strip()]
        assert "Ninth" in entries[0]
        assert "Fourth" in entries[1]
        assert markers["url:https://example.com/9"] == 1
        assert markers["url:https://example.com/4"] == 2

    def test_document_without_citations_is_unchanged(self):
        citations = [make_citation(1, "https://example.com/1", "One")]
        document = build_document("prose with no markers")

        new_document, markers = renumber_document(document, citations)
        assert new_document == document
        assert markers == {}

    def test_marker_without_matching_citation_is_left_alone(self):
        citations = [make_citation(1, "https://example.com/1", "One")]
        document = build_document("cited [1] and unknown [42]")

        new_document, _ = renumber_document(document, citations)
        body, _ = split_references(new_document)
        # [1] is already first, so it stays [1]; the orphan is untouched.
        assert "[42]" in body

    def test_duplicate_pipeline_markers_keep_the_first(self):
        citations = [
            make_citation(1, "https://example.com/first", "First"),
            make_citation(1, "https://example.com/second", "Second"),
        ]
        document = build_document("claim [1]")

        new_document, markers = renumber_document(document, citations)

        assert markers == {"url:https://example.com/first": 1}
        assert "First" in new_document
        assert "Second" not in new_document

    def test_empty_document_is_returned_as_is(self):
        assert renumber_document("", []) == ("", {})

    def test_url_variants_of_one_source_share_a_marker(self):
        """The KB merges URL variants, so the report must not split them.

        A fragment or tracking parameter does not make a different document.
        Numbering such a pair separately produced a marker (and a reference)
        that no ``ResearchSource`` row carried.
        """
        citations = [
            make_citation(1, "https://example.com/a", "Alpha"),
            make_citation(
                2, "https://example.com/a#section", "Alpha"
            ),
            make_citation(3, "https://example.com/b", "Beta"),
        ]
        document = build_document("first [1] then [2] then [3]")

        new_document, markers = renumber_document(document, citations)
        body, references = split_references(new_document)

        assert body.endswith("first [1] then [1] then [2]")
        assert renumbered_reference_markers(references) == [1, 2]
        assert markers == {
            "url:https://example.com/a": 1,
            "url:https://example.com/b": 2,
        }

    def test_tracking_parameters_do_not_split_a_source(self):
        citations = [
            make_citation(
                1, "https://example.com/a?utm_source=news", "Alpha"
            ),
            make_citation(2, "https://example.com/a", "Alpha"),
        ]
        document = build_document("see [1] and [2]")

        new_document, markers = renumber_document(document, citations)
        _, references = split_references(new_document)

        assert renumbered_reference_markers(references) == [1]
        assert len(markers) == 1


def renumbered_reference_markers(references: str) -> list[int]:
    """Collect the ``[n]`` markers opening each reference entry."""
    markers = []
    for line in references.splitlines():
        line = line.strip()
        if line.startswith("[") and "]" in line:
            markers.append(int(line[1:line.index("]")]))
    return markers


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=db_module.engine)
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=db_module.engine)


@pytest.fixture()
def research(db):
    item = models.Research(query="Does X cause Y?", status="pending")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class TestMarkersReachTheKnowledgeBase:
    """The document and ``GET /sources`` must agree on citation numbers."""

    def test_persisted_marker_matches_the_document(self, db, research):
        citations = [
            make_citation(3, "https://example.com/a", "Alpha"),
            make_citation(4, "https://example.com/b", "Beta"),
            make_citation(9, "https://example.com/c", "Gamma"),
        ]
        document = build_document("alpha [3] beta [4] gamma [9]")

        new_document, markers = renumber_document(document, citations)
        save_citations_to_db(
            db, research.id, citations, markers_by_identity=markers
        )
        db.commit()

        rows = db.query(models.ResearchSource).all()
        marker_by_url = {row.url: row.citation_marker for row in rows}
        assert marker_by_url == {
            "https://example.com/a": 1,
            "https://example.com/b": 2,
            "https://example.com/c": 3,
        }

        # Every marker in the document resolves to the row with that URL.
        _, references = split_references(new_document)
        for marker, url in (
            (1, "https://example.com/a"),
            (2, "https://example.com/b"),
            (3, "https://example.com/c"),
        ):
            entry = next(
                line for line in references.splitlines()
                if line.startswith(f"[{marker}]")
            )
            assert url in entry
            assert marker_by_url[url] == marker

    def test_uncited_source_is_persisted_without_a_marker(self, db, research):
        citations = [
            make_citation(1, "https://example.com/cited", "Cited"),
            make_citation(2, "https://example.com/uncited", "Uncited"),
        ]
        document = build_document("only [1] is used")

        _, markers = renumber_document(document, citations)
        save_citations_to_db(
            db, research.id, citations, markers_by_identity=markers
        )
        db.commit()

        rows = {row.url: row for row in db.query(models.ResearchSource).all()}
        assert rows["https://example.com/cited"].citation_marker == 1
        assert rows["https://example.com/uncited"].citation_marker is None

    def test_rerun_replaces_stale_markers(self, db, research):
        first = [
            make_citation(1, "https://example.com/a", "Alpha"),
            make_citation(2, "https://example.com/b", "Beta"),
        ]
        _, markers = renumber_document(
            build_document("a [1] b [2]"), first
        )
        save_citations_to_db(
            db, research.id, first, markers_by_identity=markers
        )
        db.commit()

        # A second run cites only one of them, which becomes [1].
        second = [
            make_citation(1, "https://example.com/a", "Alpha"),
            make_citation(2, "https://example.com/b", "Beta"),
        ]
        _, markers = renumber_document(build_document("b only [2]"), second)
        save_citations_to_db(
            db, research.id, second, markers_by_identity=markers
        )
        db.commit()

        rows = {row.url: row for row in db.query(models.ResearchSource).all()}
        assert rows["https://example.com/b"].citation_marker == 1
        assert rows["https://example.com/a"].citation_marker is None

    def test_save_without_markers_leaves_them_untouched(self, db, research):
        citations = [make_citation(1, "https://example.com/a", "Alpha")]
        save_citations_to_db(
            db,
            research.id,
            citations,
            markers_by_identity={"url:https://example.com/a": 7},
        )
        db.commit()

        save_citations_to_db(db, research.id, citations)
        db.commit()

        row = db.query(models.ResearchSource).one()
        assert row.citation_marker == 7
