"""Tests for full-text evidence retrieval and prompt grounding.

Covers the two halves of the PDF-grounding feature:

1. **Selection and ranking** — which sources are worth a download, and which
   passages of a paper are worth keeping.
2. **Prompt assembly** — evidence reaching the synthesis prompt with the
   citation markers the report actually uses.
"""

from app.memory.research_state import Citation, EvidenceSpan, SourceType
from app.services.fulltext import (
    is_fulltext_candidate,
    rank_chunks,
    select_fulltext_candidates,
)
from app.agents.synthesis_agent import format_evidence_for_prompt
from app.tools.document_chunker import DocumentChunk


def make_chunk(text, index=0, tokens=None):
    return DocumentChunk(
        text=text,
        chunk_index=index,
        start_char=0,
        end_char=len(text),
        token_count=tokens if tokens is not None else len(text.split()),
    )


def make_citation(url, **kwargs):
    defaults = dict(
        id="[1]",
        url=url,
        title="Title",
        snippet="abstract",
        source_type=SourceType.WEB,
        relevance_score=0.5,
    )
    defaults.update(kwargs)
    return Citation(**defaults)


def make_arxiv_citation(arxiv_id, **kwargs):
    """An arXiv citation, which is eligible for full-text retrieval."""
    return make_citation(
        f"https://arxiv.org/abs/{arxiv_id}",
        source_type=SourceType.ARXIV,
        **kwargs,
    )


class TestCandidateSelection:
    def test_direct_pdf_url_is_candidate(self):
        assert is_fulltext_candidate(
            make_citation("https://example.com/paper.pdf")
        )

    def test_pdf_url_with_query_is_candidate(self):
        assert is_fulltext_candidate(
            make_citation("https://example.com/download?file=paper.pdf&v=2")
        )

    def test_open_access_source_types_are_candidates(self):
        """Only source types with reliably open full text are auto-selected."""
        arxiv_citation = make_citation("https://example.com/a")
        arxiv_citation.source_type = SourceType.ARXIV
        assert is_fulltext_candidate(arxiv_citation)

        web_citation = make_citation("https://example.com/a")
        web_citation.source_type = SourceType.WEB
        # A generic web page is not a PDF, so it is not a candidate.
        assert not is_fulltext_candidate(web_citation)

    def test_direct_pdf_url_is_candidate_for_any_source_type(self):
        web_citation = make_citation("https://example.com/paper.pdf")
        web_citation.source_type = SourceType.WEB
        assert is_fulltext_candidate(web_citation)

    def test_non_http_url_is_not_candidate(self):
        assert not is_fulltext_candidate(make_citation("mailto:a@b.com"))
        assert not is_fulltext_candidate(make_citation(""))

    def test_selection_respects_limit(self):
        citations = [make_arxiv_citation(f"2301.0000{i}") for i in range(10)]
        selected = select_fulltext_candidates(citations, limit=3)
        assert len(selected) == 3

    def test_selection_prefers_higher_relevance(self):
        low = make_arxiv_citation("2301.00001", relevance_score=0.1)
        high = make_arxiv_citation("2301.00002", relevance_score=0.9)
        selected = select_fulltext_candidates([low, high], limit=1)
        assert selected[0].url == high.url

    def test_selection_deduplicates_by_identity(self):
        citations = [
            make_arxiv_citation("2301.12345").model_copy(
                update={"url": "http://arxiv.org/abs/2301.12345"}
            ),
            make_arxiv_citation("2301.12345").model_copy(
                update={"url": "https://arxiv.org/pdf/2301.12345.pdf"}
            ),
        ]
        assert len(select_fulltext_candidates(citations, limit=5)) == 1


class TestChunkRanking:
    def test_ranks_query_relevant_chunks_first(self):
        chunks = [
            make_chunk("We discuss unrelated topics entirely.", index=0),
            make_chunk(
                "Our method reduces retrieval latency by 40 percent.",
                index=1,
            ),
            make_chunk("The appendix lists the survey instrument.", index=2),
        ]
        ranked = rank_chunks(chunks, "retrieval latency reduction", limit=1)
        assert ranked[0].chunk_index == 1

    def test_returns_all_when_query_has_no_content_tokens(self):
        chunks = [make_chunk("alpha", index=0), make_chunk("beta", index=1)]
        # Every token is a stopword or too short, so nothing to rank on.
        assert len(rank_chunks(chunks, "the of a", limit=5)) == 2

    def test_respects_limit(self):
        chunks = [make_chunk(f"chunk about topic {i}", index=i) for i in range(5)]
        assert len(rank_chunks(chunks, "topic", limit=2)) == 2

    def test_empty_input(self):
        assert rank_chunks([], "query", limit=3) == []
        assert rank_chunks([make_chunk("x")], "query", limit=0) == []

    def test_earlier_chunk_wins_ties(self):
        chunks = [make_chunk("topic here", index=0), make_chunk("topic here", index=1)]
        assert rank_chunks(chunks, "topic", limit=1)[0].chunk_index == 0


class TestEvidencePromptFormatting:
    def test_empty_evidence_produces_no_context(self):
        """Runs without full text must keep the prompt unchanged."""
        assert format_evidence_for_prompt([]) == ""

    def test_includes_citation_marker_and_text(self):
        evidence = [EvidenceSpan(
            source_id=1,
            citation_id="[3]",
            title="A Study",
            url="https://example.com/a",
            text="The treatment reduced mortality by 12%.",
            chunk_index=0,
            section="Results",
        )]
        formatted = format_evidence_for_prompt(evidence)
        assert "[3]" in formatted
        assert "A Study" in formatted
        assert "reduced mortality" in formatted
        assert "Results" in formatted

    def test_groups_passages_by_source(self):
        evidence = [
            EvidenceSpan(
                source_id=1, citation_id="[1]", title="One",
                url="https://example.com/1", text="First passage.", chunk_index=0,
            ),
            EvidenceSpan(
                source_id=1, citation_id="[1]", title="One",
                url="https://example.com/1", text="Second passage.", chunk_index=1,
            ),
        ]
        formatted = format_evidence_for_prompt(evidence)
        assert "First passage." in formatted
        assert "Second passage." in formatted
        # One header for the source, not one per passage.
        assert formatted.count("URL: https://example.com/1") == 1

    def test_respects_per_source_budget(self):
        """The passage body stays within the per-source character budget."""
        evidence = [EvidenceSpan(
            source_id=1, citation_id="[1]", title="Long",
            url="https://example.com/1", text="x" * 5000, chunk_index=0,
        )]
        formatted = format_evidence_for_prompt(evidence, per_source_chars=100)
        body = formatted.split("\n\n", 1)[1]
        assert len(body) <= 100
        # The single oversized passage is still included rather than dropped.
        assert "x" in body

    def test_keeps_whole_passages_under_budget(self):
        """Passages are added whole; a budget must not cut one mid-sentence.

        A truncated sentence is worse than an omitted one when it is used to
        ground a claim.
        """
        evidence = [
            EvidenceSpan(
                source_id=1, citation_id="[1]", title="T",
                url="https://example.com/1",
                text="First complete sentence ends here.",
                chunk_index=0,
            ),
            EvidenceSpan(
                source_id=1, citation_id="[1]", title="T",
                url="https://example.com/1",
                text="Y" * 5000,
                chunk_index=1,
            ),
        ]
        formatted = format_evidence_for_prompt(evidence, per_source_chars=200)
        assert "First complete sentence ends here." in formatted
        # The oversized second passage is skipped entirely, not half-included.
        assert "Y" * 50 not in formatted

    def test_falls_back_to_source_id_when_marker_unknown(self):
        evidence = [EvidenceSpan(
            source_id=42, citation_id="", title="T",
            url="https://example.com/1", text="passage", chunk_index=0,
        )]
        assert "source 42" in format_evidence_for_prompt(evidence)
