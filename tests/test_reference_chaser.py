"""
Tests for reference extraction tool and reference chaser agent.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.reference_extractor import (
    ExtractedReference,
    extract_references_from_html,
    extract_references_from_url,
    extract_wikipedia_references,
    extract_academic_references,
    _is_useful_url,
)
from app.agents.reference_chaser import (
    chase_references,
    chase_references_for_level,
    _classify_citation_source,
    _extract_paper_id,
)
from app.memory.research_state import (
    Citation,
    ResearchState,
    SourceType,
)


class TestUrlFiltering:
    """Tests for URL filtering logic."""

    def test_skips_social_media(self):
        assert not _is_useful_url("https://twitter.com/user", "example.com")
        assert not _is_useful_url("https://facebook.com/page", "example.com")

    def test_skips_image_urls(self):
        assert not _is_useful_url(
            "https://example.com/image.jpg", "other.com"
        )
        assert not _is_useful_url(
            "https://example.com/photo.png", "other.com"
        )

    def test_skips_same_domain_root(self):
        assert not _is_useful_url(
            "https://example.com/", "example.com"
        )

    def test_accepts_valid_reference(self):
        assert _is_useful_url(
            "https://nature.com/articles/12345", "wikipedia.org"
        )
        assert _is_useful_url(
            "https://arxiv.org/abs/2301.12345", "example.com"
        )

    def test_skips_non_http(self):
        assert not _is_useful_url("mailto:user@example.com", "example.com")
        assert not _is_useful_url("ftp://files.example.com/", "example.com")

    def test_accepts_external_domain(self):
        assert _is_useful_url(
            "https://doi.org/10.1234/test", "wikipedia.org"
        )


class TestExtractReferencesFromHtml:
    """Tests for HTML reference extraction."""

    @pytest.mark.asyncio
    async def test_extracts_references_section_links(self):
        """Bibliography section links are found."""
        html = """
        <html><body>
        <article>
            <p>Some article text.</p>
            <h2>References</h2>
            <ol id="references">
                <li><a href="https://nature.com/article/1">Nature paper</a>
                    Study on climate change</li>
                <li><a href="https://science.org/paper/2">Science paper</a>
                    Related research</li>
            </ol>
        </article>
        </body></html>
        """
        refs = await extract_references_from_html(
            "https://example.com/article", html
        )

        urls = [r.url for r in refs]
        assert "https://nature.com/article/1" in urls
        assert "https://science.org/paper/2" in urls
        assert any(r.ref_type == "bibliography" for r in refs)

    @pytest.mark.asyncio
    async def test_extracts_footnote_links(self):
        """Footnote-style [1] links are found."""
        html = """
        <html><body>
        <article>
            <p>Some text <a href="https://source.com/ref1">[1]</a>
               and more <a href="https://source.com/ref2">[2]</a></p>
        </article>
        </body></html>
        """
        refs = await extract_references_from_html(
            "https://example.com/page", html
        )

        urls = [r.url for r in refs]
        assert "https://source.com/ref1" in urls
        assert "https://source.com/ref2" in urls
        assert any(r.ref_type == "footnote" for r in refs)

    @pytest.mark.asyncio
    async def test_extracts_external_links_from_body(self):
        """External links in the article body are extracted."""
        html = """
        <html><body>
        <article>
            <p>According to <a href="https://external.com/study">this study</a>,
            the results show improvement.</p>
        </article>
        </body></html>
        """
        refs = await extract_references_from_html(
            "https://example.com/page", html
        )

        urls = [r.url for r in refs]
        assert "https://external.com/study" in urls

    @pytest.mark.asyncio
    async def test_skips_navigation_links(self):
        """Same-domain navigation links are not extracted as references."""
        html = """
        <html><body>
        <nav>
            <a href="https://example.com/about">About</a>
            <a href="https://example.com/contact">Contact</a>
        </nav>
        <article>
            <p>Content with <a href="https://real-ref.com/paper">real ref</a></p>
        </article>
        </body></html>
        """
        refs = await extract_references_from_html(
            "https://example.com/article", html
        )

        urls = [r.url for r in refs]
        # Navigation links should be excluded (same domain, short path)
        # but real external references should remain
        assert "https://real-ref.com/paper" in urls

    @pytest.mark.asyncio
    async def test_respects_max_refs(self):
        """Max refs limit is respected."""
        links = "".join(
            f'<li><a href="https://ref{i}.com/article">Ref {i}</a></li>'
            for i in range(50)
        )
        html = f"""
        <html><body>
        <div id="references"><ol>{links}</ol></div>
        </body></html>
        """
        refs = await extract_references_from_html(
            "https://example.com/page", html, max_refs=5
        )
        assert len(refs) <= 5

    @pytest.mark.asyncio
    async def test_deduplicates_urls(self):
        """Same URL found in multiple places is deduplicated."""
        html = """
        <html><body>
        <article>
            <p>First mention <a href="https://ref.com/paper">[1]</a></p>
            <p>Second mention <a href="https://ref.com/paper">[1]</a></p>
        </article>
        <div id="references">
            <a href="https://ref.com/paper">Paper</a>
        </div>
        </body></html>
        """
        refs = await extract_references_from_html(
            "https://example.com/page", html
        )

        urls = [r.url for r in refs]
        assert urls.count("https://ref.com/paper") == 1


class TestExtractReferencesFromUrl:
    """Tests for URL-based reference extraction."""

    @pytest.mark.asyncio
    async def test_fetches_and_extracts(self):
        """Fetches a URL and extracts references."""
        html = """
        <html><body>
        <div id="references">
            <a href="https://source.com/ref">A source</a>
        </div>
        </body></html>
        """

        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("app.tools.reference_extractor.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            refs = await extract_references_from_url("https://example.com/page")
            assert len(refs) >= 1
            assert refs[0].url == "https://source.com/ref"

    @pytest.mark.asyncio
    async def test_handles_fetch_failure(self):
        """Returns empty list on fetch failure."""
        with patch("app.tools.reference_extractor.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Network error")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            refs = await extract_references_from_url("https://example.com/page")
            assert refs == []


class TestExtractWikipediaReferences:
    """Tests for Wikipedia reference extraction."""

    @pytest.mark.asyncio
    async def test_extracts_wikipedia_refs(self):
        """Extracts references from a Wikipedia page."""
        mock_page = MagicMock()
        mock_page.url = "https://en.wikipedia.org/wiki/Test"
        mock_page.references = [
            "https://nature.com/article/12345",
            "https://doi.org/10.1234/test",
            "https://twitter.com/user",  # Should be filtered out
        ]

        with patch(
            "wikipedia.page",
            return_value=mock_page,
        ):
            refs = await extract_wikipedia_references("Test")

        urls = [r.url for r in refs]
        assert "https://nature.com/article/12345" in urls
        assert "https://doi.org/10.1234/test" in urls
        # Social media should be filtered
        assert "https://twitter.com/user" not in urls
        assert all(r.ref_type == "wikipedia_ref" for r in refs)

    @pytest.mark.asyncio
    async def test_handles_page_not_found(self):
        """Returns empty list for non-existent pages."""
        import wikipedia

        with patch(
            "wikipedia.page",
            side_effect=wikipedia.exceptions.PageError("Not found"),
        ):
            refs = await extract_wikipedia_references("NonexistentPage12345")
            assert refs == []


class TestExtractAcademicReferences:
    """Tests for academic reference extraction."""

    @pytest.mark.asyncio
    async def test_extracts_academic_refs(self):
        """Extracts references from a Semantic Scholar paper."""
        from app.tools.semantic_scholar import SemanticScholarResult

        mock_papers = [
            SemanticScholarResult(
                paper_id="abc123",
                title="Referenced Paper 1",
                authors=["Author A"],
                abstract="Abstract of paper 1",
                url="https://semanticscholar.org/paper/abc123",
                citation_count=50,
            ),
            SemanticScholarResult(
                paper_id="def456",
                title="Referenced Paper 2",
                authors=["Author B"],
                abstract="Abstract of paper 2",
                url="https://semanticscholar.org/paper/def456",
                citation_count=30,
            ),
        ]

        with patch(
            "app.tools.semantic_scholar.get_paper_references",
            new_callable=AsyncMock,
            return_value=mock_papers,
        ):
            refs = await extract_academic_references("paper123")

        assert len(refs) == 2
        assert refs[0].title == "Referenced Paper 1"
        assert refs[1].title == "Referenced Paper 2"
        assert all(r.ref_type == "academic" for r in refs)


class TestCitationClassification:
    """Tests for citation source classification."""

    def test_classifies_wikipedia(self):
        citation = Citation(
            id="[1]",
            url="https://en.wikipedia.org/wiki/Test",
            title="Test",
            snippet="...",
            source_type=SourceType.WIKIPEDIA,
        )
        assert _classify_citation_source(citation) == "wikipedia"

    def test_classifies_arxiv(self):
        citation = Citation(
            id="[1]",
            url="https://arxiv.org/abs/2301.12345",
            title="Paper",
            snippet="...",
            source_type=SourceType.ARXIV,
        )
        assert _classify_citation_source(citation) == "academic"

    def test_classifies_web(self):
        citation = Citation(
            id="[1]",
            url="https://example.com/article",
            title="Article",
            snippet="...",
            source_type=SourceType.WEB,
        )
        assert _classify_citation_source(citation) == "web"

    def test_classifies_pubmed(self):
        citation = Citation(
            id="[1]",
            url="https://pubmed.ncbi.nlm.nih.gov/12345",
            title="Paper",
            snippet="...",
            source_type=SourceType.PUBMED,
        )
        assert _classify_citation_source(citation) == "academic"


class TestPaperIdExtraction:
    """Tests for extracting paper IDs from citation URLs."""

    def test_extracts_arxiv_id(self):
        citation = Citation(
            id="[1]",
            url="https://arxiv.org/abs/2301.12345",
            title="Paper",
            snippet="...",
        )
        assert _extract_paper_id(citation) == "ARXIV:2301.12345"

    def test_extracts_doi(self):
        citation = Citation(
            id="[1]",
            url="https://doi.org/10.1234/test.paper",
            title="Paper",
            snippet="...",
        )
        result = _extract_paper_id(citation)
        assert result is not None
        assert result.startswith("DOI:")

    def test_extracts_s2_id(self):
        citation = Citation(
            id="[1]",
            url="https://www.semanticscholar.org/paper/abc123def",
            title="Paper",
            snippet="...",
        )
        assert _extract_paper_id(citation) == "abc123def"

    def test_returns_none_for_generic_url(self):
        citation = Citation(
            id="[1]",
            url="https://example.com/article",
            title="Article",
            snippet="...",
        )
        assert _extract_paper_id(citation) is None


class TestChaseReferencesNode:
    """Tests for the chase_references LangGraph node."""

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        """Skips reference chasing when disabled in settings."""
        state = ResearchState(
            research_id=1,
            query="Test query",
            citations=[
                Citation(
                    id="[1]",
                    url="https://example.com",
                    title="Test",
                    snippet="Test snippet",
                )
            ],
        )

        with patch(
            "app.agents.reference_chaser.settings"
        ) as mock_settings:
            mock_settings.research_reference_chase_enabled = False
            result = await chase_references(state)

        assert "agent_steps" in result
        assert result["agent_steps"][0].status == "skipped"

    @pytest.mark.asyncio
    async def test_skips_when_no_citations(self):
        """Skips when there are no citations."""
        state = ResearchState(
            research_id=1,
            query="Test query",
            citations=[],
        )

        with patch(
            "app.agents.reference_chaser.settings"
        ) as mock_settings:
            mock_settings.research_reference_chase_enabled = True
            mock_settings.research_reference_chase_depth = 2
            result = await chase_references(state)

        assert "agent_steps" in result
        assert result["agent_steps"][0].status == "skipped"

    @pytest.mark.asyncio
    async def test_chases_references_and_adds_citations(self):
        """Successfully chases references and returns new citations."""
        state = ResearchState(
            research_id=1,
            query="climate change effects",
            citations=[
                Citation(
                    id="[1]",
                    url="https://example.com/article1",
                    title="Climate article",
                    snippet="About climate change",
                    source_type=SourceType.WEB,
                    relevance_score=0.9,
                ),
            ],
        )

        mock_refs = [
            ExtractedReference(
                url="https://nature.com/climate-study",
                title="Nature climate study",
                context="A study on climate change effects",
                source_url="https://example.com/article1",
                ref_type="bibliography",
            ),
        ]

        mock_scraped = MagicMock()
        mock_scraped.success = True
        mock_scraped.content = "Detailed content about climate effects..."
        mock_scraped.title = "Nature Climate Study"
        mock_scraped.author = "Dr. Smith"

        with patch(
            "app.agents.reference_chaser.settings"
        ) as mock_settings, patch(
            "app.agents.reference_chaser._extract_refs_for_citation",
            new_callable=AsyncMock,
            return_value=mock_refs,
        ), patch(
            "app.agents.reference_chaser._assess_reference_relevance",
            new_callable=AsyncMock,
            return_value=mock_refs,
        ), patch(
            "app.agents.reference_chaser.scrape_url",
            new_callable=AsyncMock,
            return_value=mock_scraped,
        ):
            mock_settings.research_reference_chase_enabled = True
            mock_settings.research_reference_chase_depth = 1

            result = await chase_references(state)

        assert "citations" in result
        assert len(result["citations"]) >= 1
        new_citation = result["citations"][0]
        assert new_citation.url == "https://nature.com/climate-study"
        assert "agent_steps" in result
