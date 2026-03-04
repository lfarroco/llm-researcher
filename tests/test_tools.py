"""
Tests for research tools.

These tests demonstrate how to test tools in isolation by:
1. Passing configuration explicitly (no reliance on app.config.settings)
2. Mocking external API calls
3. Testing error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import ToolError, ToolErrorType, ToolResponse, get_setting
from app.tools.web_search import WebSearchResult, web_search
from app.tools.arxiv_search import ArxivResult, arxiv_search, is_academic_query
from app.tools.wikipedia import WikipediaResult, wikipedia_search


class TestBaseTypes:
    """Tests for base tool types."""

    def test_tool_response_ok(self):
        """Test creating a successful response."""
        data = [{"title": "Test", "url": "http://example.com"}]
        response = ToolResponse.ok(data)

        assert response.success is True
        assert response.data == data
        assert response.error is None

    def test_tool_response_fail(self):
        """Test creating a failed response."""
        response = ToolResponse.fail(
            ToolErrorType.RATE_LIMIT,
            "Rate limit exceeded",
            details={"retry_after": 60},
        )

        assert response.success is False
        assert response.data is None
        assert response.error is not None
        assert response.error.error_type == ToolErrorType.RATE_LIMIT
        assert response.error.message == "Rate limit exceeded"
        assert response.error.details == {"retry_after": 60}

    def test_get_setting_explicit_value(self):
        """Test that explicit values take precedence."""
        result = get_setting("my-api-key", "some_setting")
        assert result == "my-api-key"

    def test_get_setting_fallback_to_settings(self):
        """Test fallback to app settings when value is None."""
        # The get_setting function does a lazy import, so we patch the import
        with patch.dict("sys.modules", {"app.config": MagicMock(settings=MagicMock(tavily_api_key="settings-key"))}):
            # Clear any cached import
            import importlib
            import app.tools.base
            importlib.reload(app.tools.base)

            result = app.tools.base.get_setting(None, "tavily_api_key")
            assert result == "settings-key"


class TestWebSearch:
    """Tests for web_search tool."""

    @pytest.mark.asyncio
    async def test_web_search_with_tavily(self):
        """Test web search using Tavily API."""
        mock_response = {
            "results": [
                {
                    "title": "Test Article",
                    "url": "https://example.com/article",
                    "content": "This is a test snippet about the search query.",
                    "score": 0.95,
                },
                {
                    "title": "Another Article",
                    "url": "https://example.com/another",
                    "content": "More content here.",
                    "score": 0.85,
                },
            ]
        }

        # Patch the tavily module that gets imported inside the function
        mock_tavily_module = MagicMock()
        mock_client = MagicMock()
        mock_client.search.return_value = mock_response
        mock_tavily_module.TavilyClient.return_value = mock_client

        with patch.dict("sys.modules", {"tavily": mock_tavily_module}):
            # Pass API key explicitly - no app.config.settings needed!
            results = await web_search(
                "test query",
                max_results=5,
                tavily_api_key="test-api-key",
            )

            assert len(results) == 2
            assert results[0].title == "Test Article"
            assert results[0].url == "https://example.com/article"
            assert results[0].score == 0.95

            # Verify the client was created with the correct API key
            mock_tavily_module.TavilyClient.assert_called_once_with(
                api_key="test-api-key")

    @pytest.mark.asyncio
    async def test_web_search_falls_back_to_duckduckgo(self):
        """Test fallback to DuckDuckGo when no API key is provided."""
        mock_ddg_results = [
            {
                "title": "DDG Result",
                "href": "https://ddg-example.com",
                "body": "DuckDuckGo result snippet",
            }
        ]

        # Patch the duckduckgo_search module
        mock_ddg_module = MagicMock()
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(
            return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text.return_value = mock_ddg_results
        mock_ddg_module.DDGS.return_value = mock_ddgs_instance

        with patch.dict("sys.modules", {"duckduckgo_search": mock_ddg_module}):
            # No API key provided - should use DuckDuckGo
            results = await web_search("test query", tavily_api_key=None)

            assert len(results) == 1
            assert results[0].title == "DDG Result"
            assert results[0].url == "https://ddg-example.com"
            assert results[0].score == 0.5  # DDG default score


class TestArxivSearch:
    """Tests for arxiv_search tool."""

    @pytest.mark.asyncio
    async def test_arxiv_search_returns_results(self):
        """Test ArXiv search returns properly formatted results."""
        from datetime import datetime

        mock_paper = MagicMock()
        mock_paper.title = "Deep Learning for Natural Language Processing"
        mock_paper.authors = [
            MagicMock(name="John Doe"), MagicMock(name="Jane Smith")]
        mock_paper.authors[0].name = "John Doe"
        mock_paper.authors[1].name = "Jane Smith"
        mock_paper.summary = "This paper presents a novel approach..."
        mock_paper.entry_id = "https://arxiv.org/abs/2024.12345"
        mock_paper.pdf_url = "https://arxiv.org/pdf/2024.12345"
        mock_paper.published = datetime(2024, 1, 15)
        mock_paper.categories = ["cs.CL", "cs.LG"]

        with patch("app.tools.arxiv_search.arxiv") as mock_arxiv:
            mock_client = MagicMock()
            mock_client.results.return_value = [mock_paper]
            mock_arxiv.Client.return_value = mock_client
            mock_arxiv.Search.return_value = MagicMock()
            mock_arxiv.SortCriterion.Relevance = "relevance"

            results = await arxiv_search("deep learning NLP", max_results=5)

            assert len(results) == 1
            assert results[0].title == "Deep Learning for Natural Language Processing"
            assert "John Doe" in results[0].authors
            assert results[0].url == "https://arxiv.org/abs/2024.12345"

    def test_is_academic_query_positive(self):
        """Test academic query detection - positive cases."""
        assert is_academic_query("research on neural networks") is True
        assert is_academic_query("machine learning algorithms study") is True
        assert is_academic_query("paper on transformer models") is True
        assert is_academic_query(
            "meta-analysis of diabetes treatments") is True

    def test_is_academic_query_negative(self):
        """Test academic query detection - negative cases."""
        assert is_academic_query("how to cook pasta") is False
        assert is_academic_query("weather in new york") is False
        assert is_academic_query("best restaurants nearby") is False


class TestWikipediaSearch:
    """Tests for wikipedia_search tool."""

    @pytest.mark.asyncio
    async def test_wikipedia_search_returns_results(self):
        """Test Wikipedia search returns properly formatted results."""
        with patch("app.tools.wikipedia.wikipedia") as mock_wiki:
            mock_wiki.search.return_value = [
                "Machine Learning", "Deep Learning"]

            mock_page = MagicMock()
            mock_page.title = "Machine Learning"
            mock_page.url = "https://en.wikipedia.org/wiki/Machine_learning"
            mock_page.content = "Machine learning is a branch of AI..."
            mock_wiki.page.return_value = mock_page
            mock_wiki.summary.return_value = "Machine learning (ML) is a field of study..."

            results = await wikipedia_search("machine learning", sentences=3)

            assert len(results) == 2
            assert results[0].title == "Machine Learning"
            assert "Machine learning" in results[0].summary


class TestWebSearchResult:
    """Tests for WebSearchResult model."""

    def test_web_search_result_creation(self):
        """Test creating a WebSearchResult."""
        result = WebSearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet content",
            score=0.9,
        )

        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet content"
        assert result.score == 0.9

    def test_web_search_result_default_score(self):
        """Test WebSearchResult with default score."""
        result = WebSearchResult(
            title="Test",
            url="https://example.com",
            snippet="Test",
        )
        assert result.score == 0.0


class TestArxivResult:
    """Tests for ArxivResult model."""

    def test_arxiv_result_creation(self):
        """Test creating an ArxivResult."""
        result = ArxivResult(
            title="Test Paper",
            authors=["Author One", "Author Two"],
            summary="This paper investigates...",
            url="https://arxiv.org/abs/2024.12345",
            pdf_url="https://arxiv.org/pdf/2024.12345",
            published="2024-01-15T00:00:00",
            categories=["cs.AI", "cs.LG"],
        )

        assert result.title == "Test Paper"
        assert len(result.authors) == 2
        assert result.categories == ["cs.AI", "cs.LG"]
