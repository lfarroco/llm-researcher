"""Tests for knowledge-base persistence.

Two properties matter here and both were previously broken:

1. **Idempotence** — running or resuming a research must merge into the
   knowledge base, never append duplicates, so findings keep pointing at the
   same source rows.
2. **Non-destructiveness** — user-authored notes, tags, and source
   annotations must survive a re-run. Resume used to delete every source,
   finding, and note, including rows the user wrote.
"""

import pytest

from app import models
from app.database import Base
import app.database as db_module
from app.memory.research_state import Citation, ResearchNote, SourceType, SubQueryResult
from app.services.research_service import (
    get_existing_sources_by_identity,
    save_citations_to_db,
    save_findings_to_db,
    save_notes_to_db,
)


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


def make_citation(url, title="Title", snippet="snippet", score=0.5):
    return Citation(
        id="[1]",
        url=url,
        title=title,
        snippet=snippet,
        source_type=SourceType.WEB,
        relevance_score=score,
    )


class TestCitationMerging:
    def test_first_save_inserts(self, db, research):
        saved = save_citations_to_db(
            db, research.id, [make_citation("https://example.com/a")]
        )
        db.commit()
        assert len(saved) == 1
        assert db.query(models.ResearchSource).count() == 1

    def test_saving_twice_does_not_duplicate(self, db, research):
        citation = make_citation("https://example.com/a")
        save_citations_to_db(db, research.id, [citation])
        db.commit()
        save_citations_to_db(db, research.id, [citation])
        db.commit()

        assert db.query(models.ResearchSource).count() == 1

    def test_url_variants_merge_into_one_source(self, db, research):
        """The same paper under four spellings is one source."""
        for url in [
            "http://example.com/paper",
            "https://example.com/paper",
            "https://www.example.com/paper/",
            "https://example.com/paper?utm_source=newsletter",
        ]:
            save_citations_to_db(db, research.id, [make_citation(url)])
            db.commit()

        assert db.query(models.ResearchSource).count() == 1

    def test_doi_urls_merge(self, db, research):
        for url in [
            "https://doi.org/10.1038/s41586-021-03819-2",
            "http://dx.doi.org/10.1038/S41586-021-03819-2",
        ]:
            save_citations_to_db(db, research.id, [make_citation(url)])
            db.commit()

        assert db.query(models.ResearchSource).count() == 1

    def test_merge_enriches_but_does_not_blank_fields(self, db, research):
        save_citations_to_db(db, research.id, [Citation(
            id="[1]",
            url="https://example.com/a",
            title="",
            author=None,
            snippet="short",
            source_type=SourceType.WEB,
            relevance_score=0.2,
        )])
        db.commit()

        save_citations_to_db(db, research.id, [Citation(
            id="[2]",
            url="https://example.com/a",
            title="The Real Title",
            author="A. Author",
            snippet="a much longer snippet of text",
            source_type=SourceType.WEB,
            relevance_score=0.9,
        )])
        db.commit()

        source = db.query(models.ResearchSource).one()
        assert source.title == "The Real Title"
        assert source.author == "A. Author"
        assert source.content_snippet == "a much longer snippet of text"
        assert source.relevance_score == pytest.approx(0.9)

    def test_merge_never_lowers_relevance(self, db, research):
        save_citations_to_db(db, research.id, [make_citation(
            "https://example.com/a", score=0.9
        )])
        db.commit()
        save_citations_to_db(db, research.id, [make_citation(
            "https://example.com/a", score=0.1
        )])
        db.commit()

        assert db.query(models.ResearchSource).one().relevance_score == (
            pytest.approx(0.9)
        )

    def test_merge_preserves_user_notes_and_tags(self, db, research):
        """User annotations are not pipeline-owned and must survive re-runs."""
        save_citations_to_db(
            db, research.id, [make_citation("https://example.com/a")]
        )
        db.commit()

        source = db.query(models.ResearchSource).one()
        source.user_notes = "user's own note"
        source.tags = ["important"]
        db.commit()

        save_citations_to_db(db, research.id, [make_citation(
            "https://example.com/a", title="Updated"
        )])
        db.commit()

        source = db.query(models.ResearchSource).one()
        assert source.user_notes == "user's own note"
        assert source.tags == ["important"]

    def test_merge_does_not_clobber_existing_title(self, db, research):
        """A populating merge must not overwrite metadata already present.

        Titles are user-editable in the UI, so re-running a search must not
        silently revert a user's correction back to the source's spelling.
        """
        save_citations_to_db(db, research.id, [make_citation(
            "https://example.com/a", title="User Corrected Title"
        )])
        db.commit()

        save_citations_to_db(db, research.id, [make_citation(
            "https://example.com/a", title="Original Feed Title"
        )])
        db.commit()

        assert db.query(models.ResearchSource).one().title == (
            "User Corrected Title"
        )

    def test_merge_fills_a_blank_title(self, db, research):
        """Enrichment still fills fields the first observation left empty."""
        save_citations_to_db(db, research.id, [Citation(
            id="[1]",
            url="https://example.com/a",
            title="",
            author=None,
            snippet="x",
            source_type=SourceType.WEB,
            relevance_score=0.5,
        )])
        db.commit()

        save_citations_to_db(db, research.id, [make_citation(
            "https://example.com/a", title="Now Known"
        )])
        db.commit()

        assert db.query(models.ResearchSource).one().title == "Now Known"

    def test_returned_map_is_stable_across_runs(self, db, research):
        """The identity map must resolve to the same rows every time."""
        citation = make_citation("https://example.com/a")
        first = save_citations_to_db(db, research.id, [citation])
        db.commit()
        first_id = next(iter(first.values())).id

        second = save_citations_to_db(db, research.id, [citation])
        db.commit()
        assert next(iter(second.values())).id == first_id

    def test_legacy_rows_without_key_still_merge(self, db, research):
        """Rows written before dedupe_key existed must still be recognized."""
        legacy = models.ResearchSource(
            research_id=research.id,
            url="https://example.com/a",
            dedupe_key=None,
            title="Legacy",
        )
        db.add(legacy)
        db.commit()

        save_citations_to_db(
            db, research.id, [make_citation("https://example.com/a")]
        )
        db.commit()

        assert db.query(models.ResearchSource).count() == 1

    def test_same_url_in_different_research_is_separate(self, db, research):
        other = models.Research(query="Other", status="pending")
        db.add(other)
        db.commit()

        save_citations_to_db(
            db, research.id, [make_citation("https://example.com/a")]
        )
        save_citations_to_db(
            db, other.id, [make_citation("https://example.com/a")]
        )
        db.commit()

        assert db.query(models.ResearchSource).count() == 2


class TestFindings:
    def test_findings_link_to_sources_without_duplicate_urls(
        self, db, research
    ):
        """Evidence links resolve through identity, not a URL dict.

        With two spellings of one URL the old URL-keyed dict let the last row
        win; identity lookup must point at the single canonical source.
        """
        citations = [
            make_citation("http://example.com/paper"),
            make_citation("https://www.example.com/paper/"),
        ]
        sources = save_citations_to_db(db, research.id, citations)
        db.flush()

        sqr = SubQueryResult(
            sub_query="Does X cause Y?",
            status="complete",
            citations=citations,
        )
        save_findings_to_db(
            db, research.id, [sqr], citations, sources_by_identity=sources
        )
        db.commit()

        finding = db.query(models.ResearchFinding).one()
        assert len(finding.source_ids) == 1
        assert finding.source_ids[0] == next(iter(sources.values())).id

    def test_findings_do_not_duplicate_on_re_run(self, db, research):
        citations = [make_citation("https://example.com/a")]
        sources = save_citations_to_db(db, research.id, citations)
        db.flush()
        sqr = SubQueryResult(
            sub_query="Q", status="complete", citations=citations
        )

        save_findings_to_db(
            db, research.id, [sqr], citations, sources_by_identity=sources
        )
        db.commit()
        save_findings_to_db(
            db, research.id, [sqr], citations, sources_by_identity=sources
        )
        db.commit()

        assert db.query(models.ResearchFinding).count() == 1

    def test_user_findings_are_untouched(self, db, research):
        db.add(models.ResearchFinding(
            research_id=research.id,
            content="Q\n\nSupported by 1 source(s): T",
            created_by="user",
        ))
        db.commit()

        citations = [make_citation("https://example.com/a")]
        sources = save_citations_to_db(db, research.id, citations)
        db.flush()
        sqr = SubQueryResult(
            sub_query="Q", status="complete", citations=citations
        )
        save_findings_to_db(
            db, research.id, [sqr], citations, sources_by_identity=sources
        )
        db.commit()

        # The user row is preserved; the pipeline adds its own AI finding.
        assert db.query(models.ResearchFinding).filter(
            models.ResearchFinding.created_by == "user"
        ).count() == 1
        assert db.query(models.ResearchFinding).count() == 2


class TestNotes:
    def test_agent_notes_do_not_duplicate_on_re_run(self, db, research):
        notes = [
            ResearchNote(agent="search", content="Found 3 sources."),
            ResearchNote(agent="planner", content="Broke into 2 parts."),
        ]
        save_notes_to_db(db, research.id, notes)
        db.commit()
        save_notes_to_db(db, research.id, notes)
        db.commit()

        assert db.query(models.ResearchNote).count() == 2

    def test_user_notes_are_never_written_by_pipeline(self, db, research):
        """The pipeline must not fabricate or duplicate human notes."""
        save_notes_to_db(db, research.id, [
            ResearchNote(agent="user", content="My own note"),
        ])
        db.commit()

        assert db.query(models.ResearchNote).count() == 0

    def test_existing_user_notes_are_preserved(self, db, research):
        db.add(models.ResearchNote(
            research_id=research.id, agent="user", content="My own note"
        ))
        db.commit()

        save_notes_to_db(db, research.id, [
            ResearchNote(agent="search", content="Found sources."),
        ])
        db.commit()

        contents = {
            n.content for n in db.query(models.ResearchNote).all()
        }
        assert "My own note" in contents
        assert "Found sources." in contents

    def test_distinct_notes_both_kept(self, db, research):
        save_notes_to_db(db, research.id, [
            ResearchNote(agent="search", content="First observation."),
        ])
        db.commit()
        save_notes_to_db(db, research.id, [
            ResearchNote(agent="search", content="Second observation."),
        ])
        db.commit()

        assert db.query(models.ResearchNote).count() == 2


class TestExistingSourceLookup:
    def test_keys_are_derived_for_legacy_rows(self, db, research):
        db.add(models.ResearchSource(
            research_id=research.id,
            url="https://www.example.com/a/",
            dedupe_key=None,
        ))
        db.commit()

        by_key = get_existing_sources_by_identity(db, research.id)
        assert "url:https://example.com/a" in by_key
