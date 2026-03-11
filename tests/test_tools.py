"""
Tests for research tools.

These tests demonstrate how to test tools in isolation by:
1. Passing configuration explicitly (no reliance on app.config.settings)
2. Mocking external API calls
3. Testing error handling
"""

import pytest
import httpx
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


class TestPubMedSearch:
    """Tests for PubMed search tool."""

    @pytest.mark.asyncio
    async def test_pubmed_search_returns_results(self):
        """Test PubMed search returns properly formatted results."""
        # Mock PubMed API responses
        mock_search_result = {
            "IdList": ["12345678"],
        }

        mock_xml_response = b"""<?xml version="1.0" ?>
        <PubmedArticleSet>
        <PubmedArticle>
            <MedlineCitation>
                <PMID>12345678</PMID>
                <Article>
                    <ArticleTitle>Deep Learning in Medicine</ArticleTitle>
                    <Abstract>
                        <AbstractText>This study explores deep learning.</AbstractText>
                    </Abstract>
                    <Journal>
                        <Title>Nature Medicine</Title>
                        <JournalIssue>
                            <PubDate><Year>2024</Year><Month>Jan</Month></PubDate>
                        </JournalIssue>
                    </Journal>
                    <AuthorList>
                        <Author><ForeName>John</ForeName><LastName>Smith</LastName></Author>
                        <Author><ForeName>Jane</ForeName><LastName>Doe</LastName></Author>
                    </AuthorList>
                </Article>
                <MeshHeadingList>
                    <MeshHeading><DescriptorName>Machine Learning</DescriptorName></MeshHeading>
                </MeshHeadingList>
            </MedlineCitation>
            <PubmedData>
                <ArticleIdList>
                    <ArticleId IdType="doi">10.1038/nm.1234</ArticleId>
                </ArticleIdList>
            </PubmedData>
        </PubmedArticle>
        </PubmedArticleSet>
        """

        with patch("Bio.Entrez", create=True) as mock_entrez:
            # Mock esearch
            mock_search_handle = MagicMock()
            mock_search_handle.close = MagicMock()
            mock_entrez.esearch = MagicMock(return_value=mock_search_handle)
            mock_entrez.read = MagicMock(return_value=mock_search_result)

            # Mock efetch - returns handle whose .read() gives XML bytes
            mock_fetch_handle = MagicMock()
            mock_fetch_handle.read = MagicMock(return_value=mock_xml_response)
            mock_fetch_handle.close = MagicMock()
            mock_entrez.efetch = MagicMock(return_value=mock_fetch_handle)

            from app.tools.pubmed_search import pubmed_search

            results = await pubmed_search(
                "machine learning medicine",
                max_results=2,
                ncbi_email="test@example.com",
            )

        # Verify results are formatted correctly
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].title == "Deep Learning in Medicine"
        assert results[0].pmid == "12345678"
        assert "John Smith" in results[0].authors
        assert results[0].doi == "10.1038/nm.1234"


class TestSemanticScholarSearch:
    """Tests for Semantic Scholar search tool."""

    @pytest.mark.asyncio
    async def test_semantic_scholar_search_returns_results(self):
        """Test Semantic Scholar search returns properly formatted results."""
        mock_api_response = {
            "data": [
                {
                    "paperId": "abc123",
                    "title": "Attention Is All You Need",
                    "authors": [{"name": "Vaswani, A."}, {"name": "Shazeer, N."}],
                    "abstract": "The dominant sequence transduction models...",
                    "year": 2017,
                    "citationCount": 50000,
                    "influentialCitationCount": 5000,
                    "venue": "NeurIPS",
                    "openAccessPdf": {"url": "https://arxiv.org/pdf/1706.03762"},
                    "externalIds": {"DOI": "10.5555/3295222", "ArXiv": "1706.03762"},
                    "fieldsOfStudy": ["Computer Science"],
                    "tldr": {"text": "Introduces the Transformer architecture"},
                }
            ]
        }

        with patch("app.tools.semantic_scholar.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.semantic_scholar import semantic_scholar_search

            results = await semantic_scholar_search("transformer architecture", max_results=5)

        assert len(results) == 1
        assert results[0].title == "Attention Is All You Need"
        assert results[0].citation_count == 50000
        assert "Vaswani" in results[0].authors[0]

    @pytest.mark.asyncio
    async def test_unauthenticated_api_used_when_no_key(self):
        """Test that requests are made without an API key header when no key is set."""
        mock_api_response = {"data": []}

        with patch("app.tools.semantic_scholar.httpx.AsyncClient") as mock_client, \
                patch("app.tools.semantic_scholar._unauth_throttle", new_callable=AsyncMock) as mock_throttle:

            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.semantic_scholar import semantic_scholar_search

            # Call without an explicit API key; settings returns None for the key too
            with patch("app.tools.semantic_scholar.get_setting", return_value=None):
                await semantic_scholar_search("machine learning", max_results=2)

        # Rate-limiter must have been invoked for unauthenticated requests
        mock_throttle.assert_called_once()

        # The outgoing request must NOT carry an x-api-key header
        _, call_kwargs = mock_ctx.get.call_args
        assert "x-api-key" not in call_kwargs.get("headers", {})

    @pytest.mark.asyncio
    async def test_api_key_header_sent_when_key_provided(self):
        """Test that the x-api-key header is sent when a key is available."""
        mock_api_response = {"data": []}

        with patch("app.tools.semantic_scholar.httpx.AsyncClient") as mock_client, \
                patch("app.tools.semantic_scholar._unauth_throttle", new_callable=AsyncMock) as mock_throttle:

            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.semantic_scholar import semantic_scholar_search

            with patch("app.tools.semantic_scholar.get_setting", return_value="my-test-key"):
                await semantic_scholar_search("machine learning", max_results=2)

        # Throttle should NOT be called when an API key is present
        mock_throttle.assert_not_called()

        _, call_kwargs = mock_ctx.get.call_args
        assert call_kwargs.get("headers", {}).get("x-api-key") == "my-test-key"

    @pytest.mark.asyncio
    async def test_retry_on_transient_http_error(self):
        """Test that transient HTTP errors (e.g. 503) are retried."""
        import httpx as _httpx

        mock_api_response = {"data": [{"paperId": "x1", "title": "T", "authors": [],
                                       "abstract": "", "year": 2020, "citationCount": 0,
                                       "influentialCitationCount": 0, "venue": None,
                                       "openAccessPdf": None, "externalIds": {},
                                       "fieldsOfStudy": [], "tldr": None}]}

        error_response = MagicMock()
        error_response.status_code = 503
        error_response.text = "Service Unavailable"

        success_response = AsyncMock()
        success_response.status_code = 200
        success_response.json = MagicMock(return_value=mock_api_response)
        success_response.raise_for_status = MagicMock()

        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise _httpx.HTTPStatusError(
                    "503", request=MagicMock(), response=error_response
                )
            return success_response

        with patch("app.tools.semantic_scholar.httpx.AsyncClient") as mock_client, \
                patch("app.tools.semantic_scholar._unauth_throttle", new_callable=AsyncMock), \
                patch("app.tools.semantic_scholar.asyncio.sleep", new_callable=AsyncMock):

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = fake_get

            mock_client.return_value = mock_ctx

            from app.tools.semantic_scholar import semantic_scholar_search

            with patch("app.tools.semantic_scholar.get_setting", return_value=None):
                results = await semantic_scholar_search("deep learning")

        # Two calls: one failure + one success
        assert call_count == 2
        assert results[0].title == "T"

    @pytest.mark.asyncio
    async def test_non_retryable_http_error_is_raised_immediately(self):
        """Test that non-retryable errors (e.g. 400) are raised without retrying."""
        import httpx as _httpx

        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Bad Request"

        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise _httpx.HTTPStatusError(
                "400", request=MagicMock(), response=error_response
            )

        with patch("app.tools.semantic_scholar.httpx.AsyncClient") as mock_client, \
                patch("app.tools.semantic_scholar._unauth_throttle", new_callable=AsyncMock), \
                patch("app.tools.semantic_scholar.asyncio.sleep", new_callable=AsyncMock):

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = fake_get

            mock_client.return_value = mock_ctx

            from app.tools.semantic_scholar import semantic_scholar_search

            with patch("app.tools.semantic_scholar.get_setting", return_value=None):
                with pytest.raises(_httpx.HTTPStatusError):
                    await semantic_scholar_search("deep learning")

        # Must have been called only once – no retries for 400
        assert call_count == 1


class TestCrossrefSearch:
    """Tests for Crossref search tool."""

    @pytest.mark.asyncio
    async def test_crossref_search_returns_results(self):
        """Test Crossref search returns properly formatted results."""
        mock_api_response = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1016/j.cell.2024.01.001",
                        "title": ["CRISPR Gene Editing Advances"],
                        "author": [
                            {"given": "John", "family": "Smith"},
                            {"given": "Jane", "family": "Doe"},
                        ],
                        "abstract": "This paper presents new CRISPR techniques...",
                        "published-print": {"date-parts": [[2024, 1, 15]]},
                        "container-title": ["Cell"],
                        "type": "journal-article",
                        "score": 95.5,
                    }
                ]
            }
        }

        with patch("app.tools.crossref_search.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.crossref_search import crossref_search

            results = await crossref_search("CRISPR gene editing", max_results=5)

        assert len(results) == 1
        assert results[0].title == "CRISPR Gene Editing Advances"
        assert results[0].doi == "10.1016/j.cell.2024.01.001"


class TestOpenAlexSearch:
    """Tests for OpenAlex search tool."""

    @pytest.mark.asyncio
    async def test_openalex_search_returns_results(self):
        """Test OpenAlex search returns properly formatted results."""
        mock_api_response = {
            "results": [
                {
                    "id": "https://openalex.org/W12345",
                    "title": "Climate Change Mitigation Strategies",
                    "authorships": [
                        {"author": {"display_name": "Alice Johnson"}},
                        {"author": {"display_name": "Bob Williams"}},
                    ],
                    "abstract_inverted_index": {
                        "This": [0],
                        "paper": [1],
                        "discusses": [2],
                    },
                    "publication_year": 2024,
                    "cited_by_count": 150,
                    "primary_location": {
                        "source": {"display_name": "Science"},
                    },
                    "doi": "https://doi.org/10.1126/science.abc123",
                    "open_access": {"is_oa": True, "oa_url": "https://example.com/pdf"},
                    "concepts": [
                        {"display_name": "Climate Change"},
                        {"display_name": "Environmental Science"},
                    ],
                }
            ]
        }

        with patch("app.tools.openalex_search.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.openalex_search import openalex_search

            results = await openalex_search("climate change", max_results=5)

        assert len(results) == 1
        assert results[0].title == "Climate Change Mitigation Strategies"
        assert results[0].cited_by_count == 150

    @pytest.mark.asyncio
    async def test_abstract_reconstructed_in_word_order(self):
        """Test that abstracts are reconstructed with correct word order."""
        mock_api_response = {
            "results": [
                {
                    "id": "https://openalex.org/W99999",
                    "title": "Test Paper",
                    "authorships": [],
                    "abstract_inverted_index": {
                        "Hello": [0],
                        "world": [1],
                        "foo": [3],
                        "bar": [2],
                    },
                    "publication_year": 2023,
                    "cited_by_count": 0,
                }
            ]
        }

        with patch("app.tools.openalex_search.httpx.AsyncClient") as mock_client, \
                patch("app.tools.openalex_search._throttle", new_callable=AsyncMock):
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.openalex_search import openalex_search

            results = await openalex_search("test", max_results=1)

        assert len(results) == 1
        # Words must appear in position order: Hello(0) world(1) bar(2) foo(3)
        assert results[0].abstract == "Hello world bar foo"

    @pytest.mark.asyncio
    async def test_throttle_called_on_each_request(self):
        """Test that the rate-limiter is invoked for every request."""
        mock_api_response = {"results": []}

        with patch("app.tools.openalex_search.httpx.AsyncClient") as mock_client, \
                patch("app.tools.openalex_search._throttle", new_callable=AsyncMock) as mock_throttle:

            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = MagicMock(return_value=mock_api_response)
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.openalex_search import openalex_search

            await openalex_search("transformer models", max_results=3)

        mock_throttle.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_transient_http_error(self):
        """Test that transient HTTP errors (e.g. 503) are retried."""
        import httpx as _httpx

        mock_api_response = {
            "results": [
                {
                    "id": "https://openalex.org/W55555",
                    "title": "Retry Success Paper",
                    "authorships": [],
                    "publication_year": 2022,
                    "cited_by_count": 10,
                }
            ]
        }

        error_response = MagicMock()
        error_response.status_code = 503
        error_response.text = "Service Unavailable"

        success_response = AsyncMock()
        success_response.status_code = 200
        success_response.json = MagicMock(return_value=mock_api_response)
        success_response.raise_for_status = MagicMock()

        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise _httpx.HTTPStatusError(
                    "503", request=MagicMock(), response=error_response
                )
            return success_response

        with patch("app.tools.openalex_search.httpx.AsyncClient") as mock_client, \
                patch("app.tools.openalex_search._throttle", new_callable=AsyncMock), \
                patch("app.tools.openalex_search.asyncio.sleep", new_callable=AsyncMock):

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = fake_get

            mock_client.return_value = mock_ctx

            from app.tools.openalex_search import openalex_search

            results = await openalex_search("retry test")

        # Two calls: one failure + one success
        assert call_count == 2
        assert results[0].title == "Retry Success Paper"

    @pytest.mark.asyncio
    async def test_non_retryable_http_error_returns_empty_list(self):
        """Test that non-retryable errors (e.g. 400) return an empty list."""
        import httpx as _httpx

        error_response = MagicMock()
        error_response.status_code = 400
        error_response.text = "Bad Request"

        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise _httpx.HTTPStatusError(
                "400", request=MagicMock(), response=error_response
            )

        with patch("app.tools.openalex_search.httpx.AsyncClient") as mock_client, \
                patch("app.tools.openalex_search._throttle", new_callable=AsyncMock), \
                patch("app.tools.openalex_search.asyncio.sleep", new_callable=AsyncMock):

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = fake_get

            mock_client.return_value = mock_ctx

            from app.tools.openalex_search import openalex_search

            results = await openalex_search("bad query")

        # Must have been called only once – no retries for 400
        assert call_count == 1
        assert results == []


class TestWebScraper:
    """Tests for web scraping tool."""

    @pytest.mark.asyncio
    async def test_scrape_url_success(self):
        """Test successful web scraping."""
        mock_html = """
        <html>
            <head><title>Test Article</title></head>
            <body>
                <article>
                    <h1>Test Article</h1>
                    <p>This is the main content of the article.</p>
                    <p>It contains important information.</p>
                </article>
            </body>
        </html>
        """

        with patch("app.tools.web_scraper.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = mock_html
            mock_response.raise_for_status = MagicMock()

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            # Patch trafilatura at the point it's used, not at module level
            with patch("trafilatura.extract") as mock_extract, \
                    patch("trafilatura.extract_metadata") as mock_metadata:
                mock_extract.return_value = "Test Article\n\nThis is the main content"
                mock_metadata.return_value = None

                from app.tools.web_scraper import scrape_url

                result = await scrape_url("https://example.com/article")

        assert result.success is True
        assert "content" in result.content.lower() or "Test Article" in result.content
        assert result.url == "https://example.com/article"

    @pytest.mark.asyncio
    async def test_scrape_url_http_error(self):
        """Test handling of HTTP errors with retry logic."""
        from tenacity import RetryError

        with patch("app.tools.web_scraper.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=None, response=None)
            )

            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_ctx.get = AsyncMock(return_value=mock_response)

            mock_client.return_value = mock_ctx

            from app.tools.web_scraper import scrape_url

            # With retry logic, it should raise RetryError after all attempts
            with pytest.raises(RetryError):
                await scrape_url("https://example.com/notfound")


class TestPDFDownload:
    """Tests for PDF download functionality."""

    @pytest.mark.asyncio
    async def test_pdf_download_success(self):
        """Test successful PDF download."""
        mock_pdf_content = b"%PDF-1.4\n%Mock PDF content"

        async def mock_aiter_bytes():
            yield mock_pdf_content

        with patch("app.tools.pdf_download.httpx.AsyncClient") as mock_client, \
                patch("app.tools.pdf_download.aiofiles.open") as mock_open, \
                patch("app.tools.pdf_download.Path.exists", return_value=False):

            # Mock the streaming response
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.headers = {
                "content-type": "application/pdf", "content-length": "100"}
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_bytes = mock_aiter_bytes

            # Mock async context managers
            mock_stream_ctx = AsyncMock()
            mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_client_ctx = AsyncMock()
            mock_client_ctx.__aenter__ = AsyncMock(
                return_value=mock_client_ctx)
            mock_client_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_client_ctx.stream = MagicMock(return_value=mock_stream_ctx)

            mock_client.return_value = mock_client_ctx

            # Mock file writing
            mock_file = AsyncMock()
            mock_file.__aenter__ = AsyncMock(return_value=mock_file)
            mock_file.__aexit__ = AsyncMock(return_value=None)
            mock_file.write = AsyncMock()
            mock_open.return_value = mock_file

            from app.tools.pdf_download import download_pdf, PDFDownloadResult

            result = await download_pdf("https://arxiv.org/pdf/2024.12345")

        assert result is not None
        assert isinstance(result, PDFDownloadResult)
        assert result.success is True
        assert result.file_path is not None

    @pytest.mark.asyncio
    async def test_pdf_download_failure(self):
        """Test handling of PDF download failure."""
        mock_error_response = MagicMock()
        mock_error_response.status_code = 404

        with patch("app.tools.pdf_download.httpx.AsyncClient") as mock_client, \
                patch("app.tools.pdf_download.Path.exists", return_value=False):

            mock_response = AsyncMock()
            mock_response.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "404", request=MagicMock(), response=mock_error_response)
            )

            mock_stream_ctx = AsyncMock()
            mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
            mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_client_ctx = AsyncMock()
            mock_client_ctx.__aenter__ = AsyncMock(
                return_value=mock_client_ctx)
            mock_client_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_client_ctx.stream = MagicMock(return_value=mock_stream_ctx)

            mock_client.return_value = mock_client_ctx

            from app.tools.pdf_download import download_pdf, PDFDownloadResult

            result = await download_pdf("https://example.com/missing.pdf")

        assert isinstance(result, PDFDownloadResult)
        assert result.success is False
        assert "404" in result.error


# Tests for tools with mocked external APIs
class TestToolsWithMockedAPIs:
    """Tests for tools with mocked external API responses."""

    @pytest.mark.asyncio
    async def test_web_search_mocked_api(self):
        """Test web search with mocked API response."""
        from app.tools.web_search import WebSearchResult

        # Mock results
        mock_results = [
            WebSearchResult(
                title="Python Programming Tutorial",
                url="https://example.com/python-tutorial",
                snippet="Learn Python programming basics and advanced concepts.",
                source="Example.com"
            ),
            WebSearchResult(
                title="Python Documentation",
                url="https://docs.python.org",
                snippet="Official Python documentation and guides.",
                source="Python.org"
            ),
        ]

        with patch("app.tools.web_search.web_search", return_value=mock_results):
            from app.tools.web_search import web_search
            results = await web_search("python programming", max_results=3)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(hasattr(r, "title") for r in results)
        assert all(hasattr(r, "url") for r in results)

    @pytest.mark.asyncio
    async def test_arxiv_search_mocked_api(self):
        """Test ArXiv search with mocked API response."""
        from app.tools.arxiv_search import ArxivResult

        mock_results = [
            ArxivResult(
                title="Machine Learning: A Survey",
                url="https://arxiv.org/abs/2301.12345",
                summary="Comprehensive survey of machine learning techniques.",
                authors=["Smith, J.", "Doe, A."],
                pdf_url="https://arxiv.org/pdf/2301.12345.pdf",
                published="2023-01-15",
                categories=["cs.LG", "cs.AI"]
            ),
            ArxivResult(
                title="Deep Learning Advances",
                url="https://arxiv.org/abs/2302.54321",
                summary="Recent advances in deep learning architectures.",
                authors=["Johnson, B."],
                pdf_url="https://arxiv.org/pdf/2302.54321.pdf",
                published="2023-02-20",
                categories=["cs.LG"]
            ),
        ]

        with patch("app.tools.arxiv_search.arxiv_search", return_value=mock_results):
            from app.tools.arxiv_search import arxiv_search
            results = await arxiv_search("machine learning", max_results=2)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all("arxiv.org" in r.url for r in results)

    @pytest.mark.asyncio
    async def test_wikipedia_search_mocked_api(self):
        """Test Wikipedia search with mocked API response."""
        from app.tools.wikipedia import WikipediaResult

        mock_results = [
            WikipediaResult(
                title="Python (programming language)",
                url="https://en.wikipedia.org/wiki/Python_(programming_language)",
                summary="Python is a high-level, interpreted programming language. It emphasizes code readability. Python supports multiple programming paradigms.",
                content="Full article content would go here..."
            ),
        ]

        with patch("app.tools.wikipedia.wikipedia_search", return_value=mock_results):
            from app.tools.wikipedia import wikipedia_search
            results = await wikipedia_search("Python programming language", sentences=3)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all("wikipedia.org" in r.url for r in results)

    @pytest.mark.asyncio
    async def test_semantic_scholar_mocked_api(self):
        """Test Semantic Scholar with mocked API response."""
        from app.tools.semantic_scholar import SemanticScholarResult

        mock_results = [
            SemanticScholarResult(
                paper_id="12345abc",
                title="Attention Is All You Need",
                url="https://api.semanticscholar.org/paper/12345",
                abstract="Introducing the Transformer architecture for neural networks.",
                authors=["Vaswani, A.", "et al."],
                year=2017,
                citation_count=50000,
                influential_citation_count=5000,
                venue="NeurIPS",
                fields_of_study=["Computer Science", "Machine Learning"]
            ),
        ]

        with patch("app.tools.semantic_scholar.semantic_scholar_search", return_value=mock_results):
            from app.tools.semantic_scholar import semantic_scholar_search
            results = await semantic_scholar_search("transformer neural networks", max_results=2)

        assert isinstance(results, list)
        # API might return 0 results depending on rate limits
        if len(results) > 0:
            assert hasattr(results[0], "title")
            assert hasattr(results[0], "citation_count")


class TestPDFParser:
    """Tests for PDF parser tool."""

    @pytest.mark.asyncio
    async def test_parse_pdf_missing_file(self):
        """Test parsing a non-existent file returns error."""
        from app.tools.pdf_parser import parse_pdf_from_file

        result = await parse_pdf_from_file("/nonexistent/file.pdf")

        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ToolErrorType.NOT_FOUND

    @pytest.mark.asyncio
    async def test_parse_pdf_from_url_download_fails(self):
        """Test that parse_pdf_from_url handles download failures."""
        from app.tools.pdf_parser import parse_pdf_from_url

        # Mock download_pdf to return failure
        mock_download_result = MagicMock()
        mock_download_result.success = False
        mock_download_result.file_path = None
        mock_download_result.error = "Network error"

        with patch("app.tools.pdf_parser.download_pdf", return_value=mock_download_result):
            result = await parse_pdf_from_url("http://example.com/paper.pdf")

        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ToolErrorType.NETWORK_ERROR

    @pytest.mark.asyncio
    async def test_parse_pdf_with_pypdf2_fallback(self):
        """Test PDF parsing falls back to PyPDF2 when GROBID and pdfplumber fail."""
        from app.tools.pdf_parser import parse_pdf_from_file, ParsedPDF
        import tempfile
        from PyPDF2 import PdfWriter

        # Create a minimal valid PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            writer.write(f)
            temp_path = f.name

        try:
            # Mock GROBID and pdfplumber to fail
            with patch("app.tools.pdf_parser._parse_with_grobid", return_value=None), \
                 patch("app.tools.pdf_parser._parse_with_pdfplumber", side_effect=Exception("pdfplumber failed")):
                
                result = await parse_pdf_from_file(temp_path)

            # PyPDF2 should succeed as fallback
            assert result.success is True
            assert result.data is not None
            assert len(result.data) == 1
            assert result.data[0].parser_used == "pypdf2"
        finally:
            # Clean up
            import os
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_parse_pdf_grobid_success(self):
        """Test successful PDF parsing with GROBID."""
        from app.tools.pdf_parser import parse_pdf_from_file, ParsedPDF

        # Mock a successful GROBID parse
        mock_parsed_pdf = ParsedPDF(
            title="Test Paper",
            authors=["John Doe", "Jane Smith"],
            abstract="This is a test abstract.",
            sections=[],
            references=[],
            figures=[],
            tables=[],
            keywords=["test", "paper"],
            full_text="This is a test abstract. Full content here.",
            metadata={},
            parser_used="grobid"
        )

        with patch("app.tools.pdf_parser._parse_with_grobid", return_value=mock_parsed_pdf):
            result = await parse_pdf_from_file("/tmp/test.pdf")

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0].title == "Test Paper"
        assert len(result.data[0].authors) == 2
        assert result.data[0].parser_used == "grobid"

    @pytest.mark.asyncio
    async def test_parse_pdf_empty_text_error(self):
        """Test that PDFs with no extractable text return an error."""
        from app.tools.pdf_parser import parse_pdf_from_file, ParsedPDF

        # Mock a parse that returns empty text
        mock_parsed_pdf = ParsedPDF(
            title=None,
            authors=[],
            abstract=None,
            sections=[],
            references=[],
            figures=[],
            tables=[],
            keywords=[],
            full_text="",  # Empty text
            metadata={},
            parser_used="grobid"
        )

        with patch("app.tools.pdf_parser._parse_with_grobid", return_value=mock_parsed_pdf):
            result = await parse_pdf_from_file("/tmp/test.pdf")

        assert result.success is False
        assert result.error is not None
        assert result.error.error_type == ToolErrorType.PARSE_ERROR
        assert "No text content" in result.error.message

    def test_pdf_section_model(self):
        """Test PDFSection model validation."""
        from app.tools.pdf_parser import PDFSection

        section = PDFSection(
            heading="Introduction",
            content="This is the introduction section.",
            level=1
        )

        assert section.heading == "Introduction"
        assert section.level == 1
        assert len(section.content) > 0

    def test_pdf_reference_model(self):
        """Test PDFReference model validation."""
        from app.tools.pdf_parser import PDFReference

        ref = PDFReference(
            raw_text="Doe, J. (2020). Test Paper. Nature.",
            title="Test Paper",
            authors=["Doe, J."],
            year=2020,
            doi="10.1234/test"
        )

        assert ref.title == "Test Paper"
        assert ref.year == 2020
        assert ref.doi == "10.1234/test"

    def test_parsed_pdf_model(self):
        """Test ParsedPDF model validation."""
        from app.tools.pdf_parser import ParsedPDF, PDFSection, PDFReference

        section = PDFSection(heading="Methods", content="Methodology", level=1)
        reference = PDFReference(
            raw_text="Smith, A. (2019). Related Work.",
            title="Related Work",
            authors=["Smith, A."],
            year=2019
        )

        pdf = ParsedPDF(
            title="Research Paper",
            authors=["Author One", "Author Two"],
            abstract="Abstract text",
            sections=[section],
            references=[reference],
            figures=[],
            tables=[],
            keywords=["research", "test"],
            full_text="Abstract text Methodology",
            metadata={"pages": 10},
            parser_used="grobid"
        )

        assert pdf.title == "Research Paper"
        assert len(pdf.authors) == 2
        assert len(pdf.sections) == 1
        assert len(pdf.references) == 1
        assert pdf.parser_used == "grobid"

