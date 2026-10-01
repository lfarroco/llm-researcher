"""Tests for the two-segment workflow that inserts full-text retrieval.

The research service runs the graph in two parts::

    plan -> search -> chase_references   (segment 1, interrupted here)
                        | full-text evidence retrieval |
    hypothesize -> synthesize -> format  (segment 2)

This is the seam where grounding is injected, so it is worth testing
directly: if ``interrupt_after`` silently stopped working, evidence would
never be collected and reports would quietly fall back to abstracts.
"""

from unittest.mock import AsyncMock, patch

import asyncio

import pytest

from app.agents import orchestrator
from app.memory.research_state import Citation, EvidenceSpan, SourceType


def make_citation(url, marker="[1]"):
    return Citation(
        id=marker,
        url=url,
        title="A Paper",
        snippet="abstract text",
        source_type=SourceType.ARXIV,
        relevance_score=0.8,
    )


@pytest.fixture()
def staged_nodes():
    """Replace every graph node with a deterministic stub.

    Each stub records that it ran and returns a partial state update, so the
    test observes real graph traversal without touching an LLM or network.
    """
    calls = []

    async def plan_research(state):
        calls.append("plan")
        return {"sub_queries": ["q1", "q2"], "status": "searching"}

    async def execute_searches(state):
        calls.append("search")
        return {
            "citations": [make_citation("https://arxiv.org/abs/2301.12345")],
            "sub_query_results": [],
            "status": "synthesizing",
        }

    async def chase_references(state):
        calls.append("chase_references")
        return {"status": "hypothesizing"}

    async def generate_hypotheses(state):
        calls.append("hypothesize")
        return {"status": "synthesizing"}

    async def synthesize_findings(state):
        calls.append("synthesize")
        # Record the evidence the segment was handed, which is the whole
        # point of the split.
        return {
            "draft": "draft body",
            "status": "formatting",
            "_evidence_seen": len(state.evidence),
        }

    async def format_final_document(state):
        calls.append("format")
        return {"final_document": "final body", "status": "complete"}

    with patch.multiple(
        orchestrator,
        plan_research=plan_research,
        execute_searches=execute_searches,
        chase_references=chase_references,
        generate_hypotheses=generate_hypotheses,
        synthesize_findings=synthesize_findings,
        format_final_document=format_final_document,
    ):
        yield calls


class TestInterruptedSegment:
    @pytest.mark.asyncio
    async def test_first_segment_stops_before_hypothesize(self, staged_nodes):
        state = await orchestrator.run_research_workflow(
            1, "query", interrupt_after=["chase_references"]
        )

        assert "plan" in staged_nodes
        assert "search" in staged_nodes
        assert "chase_references" in staged_nodes
        # The segment must stop here so evidence can be gathered.
        assert "hypothesize" not in staged_nodes
        assert "synthesize" not in staged_nodes
        assert state.citations
        assert not state.draft

    @pytest.mark.asyncio
    async def test_uninterrupted_run_reaches_the_end(self, staged_nodes):
        state = await orchestrator.run_research_workflow(1, "query")

        assert staged_nodes == [
            "plan", "search", "chase_references",
            "hypothesize", "synthesize", "format",
        ]
        assert state.final_document == "final body"

    @pytest.mark.asyncio
    async def test_second_segment_resumes_with_evidence(self, staged_nodes):
        """The resumed segment must run the back half and see the evidence."""
        first = await orchestrator.run_research_workflow(
            1, "query", interrupt_after=["chase_references"]
        )
        first.evidence = [EvidenceSpan(
            source_id=1,
            citation_id="[1]",
            title="A Paper",
            url="https://arxiv.org/abs/2301.12345",
            text="The measured effect was large.",
            chunk_index=0,
        )]

        staged_nodes.clear()
        second = await orchestrator.run_research_workflow(
            1, "query", resume_state=first
        )

        # It resumes after search; it must not repeat the first half.
        assert "plan" not in staged_nodes
        assert "search" not in staged_nodes
        assert staged_nodes == ["hypothesize", "synthesize", "format"]
        assert second.final_document == "final body"
        # Evidence reached the synthesis node.
        assert second.evidence
        assert len(second.evidence) == 1


class TestEvidenceRetrievalIdempotence:
    """Resuming must not re-download PDFs that were already retrieved."""

    @pytest.mark.asyncio
    async def test_already_fetched_sources_are_not_downloaded_again(self):
        from app import models
        from app.config import settings
        from app.database import Base
        import app.database as db_module
        from app.services import fulltext

        Base.metadata.create_all(bind=db_module.engine)
        db = db_module.SessionLocal()
        try:
            item = models.Research(query="q", status="pending")
            db.add(item)
            db.commit()

            citation = make_citation("https://arxiv.org/abs/2301.12345")
            source = models.ResearchSource(
                research_id=item.id,
                url=citation.url,
                dedupe_key="arxiv:2301.12345",
                title="A Paper",
                source_type="arxiv",
                relevance_score=0.8,
                full_text_status="fetched",
            )
            db.add(source)
            db.commit()

            parse = AsyncMock()
            with patch.object(
                settings, "research_fulltext_enabled", True
            ), patch.object(
                settings, "research_fulltext_max_sources", 5
            ), patch.object(
                fulltext, "parse_pdf_from_url", parse
            ):
                await fulltext.collect_fulltext_evidence(
                    db=db,
                    research_id=item.id,
                    query="q",
                    citations=[citation],
                )

            # The network boundary must not be touched for fetched sources.
            parse.assert_not_awaited()
        finally:
            db.close()
            Base.metadata.drop_all(bind=db_module.engine)

    @pytest.mark.asyncio
    async def test_disabled_setting_skips_retrieval_entirely(self):
        from app.config import settings
        from app.services import fulltext

        parse = AsyncMock()
        with patch.object(
            settings, "research_fulltext_enabled", False
        ), patch.object(fulltext, "parse_pdf_from_url", parse):
            result = await fulltext.collect_fulltext_evidence(
                db=None,
                research_id=1,
                query="q",
                citations=[make_citation("https://arxiv.org/abs/2301.12345")],
            )

        assert result == []
        parse.assert_not_awaited()


class TestCitationsPersistedBeforeGrounding:
    """Sources must exist in the DB before full-text evidence is collected.

    Regression guard: ``collect_fulltext_evidence`` resolves its candidates
    against the ``ResearchSource`` rows for the research, but the citations
    used to be written only *after* the whole workflow finished. The identity
    map was therefore empty, ``source`` was ``None`` for every candidate, and
    retrieval silently no-opped — the container log showed
    ``[FULLTEXT] Retrieved full text for 0/3 candidate sources`` and the
    report fell back to search snippets while GROBID sat unused.
    """

    @pytest.mark.asyncio
    async def test_source_rows_exist_when_evidence_is_collected(self):
        from app import models
        from app.database import Base
        import app.database as db_module
        from app.memory.research_state import ResearchState
        from app.services import research_service

        Base.metadata.create_all(bind=db_module.engine)
        db = db_module.SessionLocal()
        observed = {}

        try:
            item = models.Research(query="q", status="pending")
            db.add(item)
            db.commit()
            research_id = item.id

            citation = make_citation("https://arxiv.org/abs/2301.12345")

            search_state = ResearchState(research_id=research_id, query="q")
            search_state.citations = [citation]

            final_state = ResearchState(research_id=research_id, query="q")
            final_state.citations = [citation]
            final_state.final_document = "body [1]"
            final_state.status = "complete"

            async def fake_workflow(rid, q, **kwargs):
                # Second segment is the resumed one.
                if kwargs.get("resume_state") is not None:
                    return final_state
                return search_state

            async def fake_collect(db, research_id, query, citations):
                # This is the real query fulltext.py performs; if the
                # citations have not been persisted yet it sees zero rows.
                observed["source_rows"] = (
                    db.query(models.ResearchSource)
                    .filter(models.ResearchSource.research_id == research_id)
                    .count()
                )
                return []

            with patch.object(
                research_service, "run_research_workflow", fake_workflow
            ), patch.object(
                research_service, "collect_fulltext_evidence", fake_collect
            ):
                await research_service.process_research_async(research_id, "q")

            assert observed.get("source_rows", 0) >= 1, (
                "collect_fulltext_evidence ran before the citations were "
                "persisted, so grounding would silently retrieve nothing"
            )
        finally:
            db.close()
            Base.metadata.drop_all(bind=db_module.engine)


class TestResearchTimeout:
    """``research_timeout`` was dead configuration; now it is enforced."""

    @pytest.mark.asyncio
    async def test_expired_budget_does_not_start_the_segment(self):
        from app.services.research_service import (
            ResearchTimeoutError,
            _run_within_budget,
        )

        started = False

        async def segment():
            nonlocal started
            started = True
            return "unreachable"

        loop = asyncio.get_running_loop()
        with pytest.raises(ResearchTimeoutError):
            await _run_within_budget(
                lambda: segment(), loop.time() - 1, "an expired budget"
            )
        assert started is False

    @pytest.mark.asyncio
    async def test_slow_segment_times_out(self):
        from app.services.research_service import (
            ResearchTimeoutError,
            _run_within_budget,
        )

        async def slow():
            await asyncio.sleep(5)

        loop = asyncio.get_running_loop()
        with pytest.raises(ResearchTimeoutError):
            await _run_within_budget(slow, loop.time() + 0.05, "a slow phase")

    @pytest.mark.asyncio
    async def test_disabled_budget_awaits_normally(self):
        from app.services.research_service import _run_within_budget

        async def segment():
            return "done"

        assert await _run_within_budget(segment, None, "no budget") == "done"

    @pytest.mark.asyncio
    async def test_timed_out_run_reaches_a_terminal_status(self):
        """A hung run must not sit in a non-terminal status forever."""
        from app import models
        from app.config import settings
        from app.database import Base
        import app.database as db_module
        from app.services import research_service

        Base.metadata.create_all(bind=db_module.engine)
        db = db_module.SessionLocal()
        try:
            item = models.Research(query="q", status="pending")
            db.add(item)
            db.commit()
            research_id = item.id

            async def hanging_workflow(rid, q, **kwargs):
                await asyncio.sleep(30)

            with patch.object(
                settings, "research_timeout", 1
            ), patch.object(
                research_service,
                "run_research_workflow",
                hanging_workflow,
            ):
                await research_service.process_research_async(research_id, "q")

            db.expire_all()
            refreshed = db.get(models.Research, research_id)
            assert refreshed.status == "error"
        finally:
            db.close()
            Base.metadata.drop_all(bind=db_module.engine)
