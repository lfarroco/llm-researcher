"""
Tests for app.output.citation_formatter module.

These tests validate citation formatting in APA, MLA, and Chicago styles,
as well as URL validation functionality.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.output.citation_formatter import (
    CitationStyle,
    CitationFormatter,
    format_citation,
    format_references_section,
    validate_citation_url,
    validate_all_citations,
)
from app.memory.research_state import Citation, SourceType


class TestCitationStyle:
    """Tests for CitationStyle enum."""

    def test_all_citation_styles(self):
        """Test all citation style values."""
        assert CitationStyle.APA.value == "apa"
        assert CitationStyle.MLA.value == "mla"
        assert CitationStyle.CHICAGO.value == "chicago"

    def test_citation_style_from_string(self):
        """Test creating CitationStyle from string."""
        style = CitationStyle("mla")
        assert style == CitationStyle.MLA


class TestCitationFormatterHelpers:
    """Tests for CitationFormatter helper methods."""

    def test_parse_date_iso_format(self):
        """Test parsing ISO format date."""
        formatter = CitationFormatter()
        date_string = "2024-01-15T10:30:00+00:00"

        parsed = formatter._parse_date(date_string)

        assert parsed is not None
        assert parsed.year == 2024
        assert parsed.month == 1
        assert parsed.day == 15

    def test_parse_date_with_z_suffix(self):
        """Test parsing date with Z timezone suffix."""
        formatter = CitationFormatter()
        date_string = "2024-01-15T10:30:00Z"

        parsed = formatter._parse_date(date_string)

        assert parsed is not None
        assert parsed.year == 2024

    def test_parse_date_simple_format(self):
        """Test parsing simple YYYY-MM-DD format."""
        formatter = CitationFormatter()
        date_string = "2024-01-15"

        parsed = formatter._parse_date(date_string)

        assert parsed is not None
        assert parsed.year == 2024
        assert parsed.month == 1
        assert parsed.day == 15

    def test_parse_date_invalid(self):
        """Test parsing invalid date returns None."""
        formatter = CitationFormatter()

        assert formatter._parse_date("invalid") is None
        assert formatter._parse_date(None) is None
        assert formatter._parse_date("") is None

    def test_get_domain_from_url(self):
        """Test extracting domain from URL."""
        formatter = CitationFormatter()

        assert formatter._get_domain(
            "https://www.example.com/article") == "example.com"
        assert formatter._get_domain(
            "https://example.com/path") == "example.com"
        assert formatter._get_domain(
            "http://subdomain.example.com") == "subdomain.example.com"

    def test_get_domain_removes_www(self):
        """Test that www. prefix is removed."""
        formatter = CitationFormatter()

        domain = formatter._get_domain("https://www.wikipedia.org/wiki/Test")
        assert domain == "wikipedia.org"

    def test_get_domain_invalid_url(self):
        """Test handling of invalid URLs."""
        formatter = CitationFormatter()

        # Should return original string if parsing fails
        result = formatter._get_domain("not-a-url")
        assert result == "not-a-url"

    def test_format_author_apa_with_first_last(self):
        """Test APA author formatting with first and last name."""
        formatter = CitationFormatter()

        # Format: "Last, First Middle"
        author = "Smith, John David"
        result = formatter._format_author_apa(author)

        assert result == "Smith, J. D."

    def test_format_author_apa_organization(self):
        """Test APA author formatting for organizations."""
        formatter = CitationFormatter()

        # Organizations are returned as-is
        author = "World Health Organization"
        result = formatter._format_author_apa(author)

        assert result == "World Health Organization"

    def test_format_author_apa_no_author(self):
        """Test APA author formatting with None."""
        formatter = CitationFormatter()

        result = formatter._format_author_apa(None)

        assert result == ""


class TestAPACitations:
    """Tests for APA 7th edition citation formatting."""

    def test_format_apa_web_with_author(self):
        """Test APA format for web source with author."""
        citation = Citation(
            id="[1]",
            url="https://www.example.com/article",
            title="Understanding Machine Learning",
            author="Smith, John",
            snippet="...",
            source_type=SourceType.WEB,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_apa(citation)

        # Should include: Author, (Year, Month Day). Title. Domain. URL
        assert "Smith, J." in result
        assert "(2024, January 15)." in result
        assert "Understanding Machine Learning." in result
        assert "example.com." in result
        assert "https://www.example.com/article" in result

    def test_format_apa_web_without_author(self):
        """Test APA format for web source without author."""
        citation = Citation(
            id="[2]",
            url="https://example.com/article",
            title="Climate Change Effects",
            snippet="...",
            source_type=SourceType.WEB,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_apa(citation)

        # Should start with title when no author
        assert result.startswith("Climate Change Effects.")
        assert "(2024, January 15)." in result
        assert "example.com." in result

    def test_format_apa_arxiv_source(self):
        """Test APA format for ArXiv source."""
        citation = Citation(
            id="[3]",
            url="https://arxiv.org/abs/2024.12345",
            title="Deep Learning for NLP",
            author="Doe, Jane",
            snippet="...",
            source_type=SourceType.ARXIV,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_apa(citation)

        assert "Doe, J." in result
        assert "Deep Learning for NLP." in result
        assert "arXiv." in result
        assert "arxiv.org" in result

    def test_format_apa_wikipedia_source(self):
        """Test APA format for Wikipedia source."""
        citation = Citation(
            id="[4]",
            url="https://en.wikipedia.org/wiki/Quantum_computing",
            title="Quantum Computing",
            snippet="...",
            source_type=SourceType.WIKIPEDIA,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_apa(citation)

        assert "Quantum Computing." in result
        assert "Wikipedia." in result

    def test_format_apa_no_date(self):
        """Test APA format when date parsing fails."""
        citation = Citation(
            id="[5]",
            url="https://example.com",
            title="Test Article",
            snippet="...",
            date_accessed="invalid-date",
        )

        result = CitationFormatter.format_apa(citation)

        assert "(n.d.)." in result  # "no date"


class TestMLACitations:
    """Tests for MLA 9th edition citation formatting."""

    def test_format_mla_web_with_author(self):
        """Test MLA format for web source with author."""
        citation = Citation(
            id="[1]",
            url="https://example.com/article",
            title="The Future of AI",
            author="Smith, John",
            snippet="...",
            source_type=SourceType.WEB,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_mla(citation)

        # Should include: Author. "Title." Site, Day Month Year, URL.
        assert "Smith, John." in result
        assert '"The Future of AI."' in result
        assert "example.com," in result
        assert "15 Jan. 2024," in result
        assert "https://example.com/article." in result

    def test_format_mla_web_without_author(self):
        """Test MLA format for web source without author."""
        citation = Citation(
            id="[2]",
            url="https://example.com/article",
            title="Deep Learning Basics",
            snippet="...",
            source_type=SourceType.WEB,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_mla(citation)

        # Should start with title in quotes
        assert result.startswith('"Deep Learning Basics."')
        assert "example.com," in result

    def test_format_mla_arxiv_source(self):
        """Test MLA format for ArXiv source."""
        citation = Citation(
            id="[3]",
            url="https://arxiv.org/abs/2024.12345",
            title="Neural Networks Study",
            author="Doe, Jane",
            snippet="...",
            source_type=SourceType.ARXIV,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_mla(citation)

        assert "Doe, Jane." in result
        assert "arXiv," in result

    def test_format_mla_wikipedia_source(self):
        """Test MLA format for Wikipedia source."""
        citation = Citation(
            id="[4]",
            url="https://en.wikipedia.org/wiki/Machine_learning",
            title="Machine Learning",
            snippet="...",
            source_type=SourceType.WIKIPEDIA,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_mla(citation)

        assert "Wikipedia," in result


class TestChicagoCitations:
    """Tests for Chicago 17th edition citation formatting."""

    def test_format_chicago_web_with_author(self):
        """Test Chicago format for web source with author."""
        citation = Citation(
            id="[1]",
            url="https://example.com/article",
            title="Artificial Intelligence Today",
            author="Smith, John",
            snippet="...",
            source_type=SourceType.WEB,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_chicago(citation)

        # Should include: Author. "Title." Site. Accessed Month Day, Year. URL
        assert "Smith, John." in result
        assert '"Artificial Intelligence Today."' in result
        assert "example.com." in result
        assert "Accessed January 15, 2024." in result
        assert "https://example.com/article" in result

    def test_format_chicago_web_without_author(self):
        """Test Chicago format for web source without author."""
        citation = Citation(
            id="[2]",
            url="https://example.com/article",
            title="Blockchain Technology",
            snippet="...",
            source_type=SourceType.WEB,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_chicago(citation)

        # Should start with title when no author
        assert result.startswith('"Blockchain Technology."')

    def test_format_chicago_arxiv_source(self):
        """Test Chicago format for ArXiv source."""
        citation = Citation(
            id="[3]",
            url="https://arxiv.org/abs/2024.12345",
            title="Quantum Algorithms",
            author="Doe, Jane",
            snippet="...",
            source_type=SourceType.ARXIV,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_chicago(citation)

        assert "arXiv." in result

    def test_format_chicago_wikipedia_source(self):
        """Test Chicago format for Wikipedia source."""
        citation = Citation(
            id="[4]",
            url="https://en.wikipedia.org/wiki/Python",
            title="Python (programming language)",
            snippet="...",
            source_type=SourceType.WIKIPEDIA,
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format_chicago(citation)

        assert "Wikipedia." in result


class TestCitationFormatterGeneric:
    """Tests for generic format() method."""

    def test_format_with_apa_style(self):
        """Test format() method with APA style."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="Test",
            snippet="...",
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format(citation, CitationStyle.APA)

        assert "Test." in result
        assert "example.com." in result

    def test_format_with_mla_style(self):
        """Test format() method with MLA style."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="Test",
            snippet="...",
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format(citation, CitationStyle.MLA)

        assert '"Test."' in result

    def test_format_with_chicago_style(self):
        """Test format() method with Chicago style."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="Test",
            snippet="...",
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = CitationFormatter.format(citation, CitationStyle.CHICAGO)

        assert '"Test."' in result
        assert "Accessed" in result


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_format_citation_function(self):
        """Test format_citation() convenience function."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="Test Article",
            snippet="...",
            date_accessed="2024-01-15T10:00:00+00:00",
        )

        result = format_citation(citation, CitationStyle.APA)

        assert "Test Article." in result
        assert "example.com." in result

    def test_format_references_section_apa(self):
        """Test generating complete references section in APA."""
        citations = [
            Citation(
                id="[1]",
                url="https://example1.com",
                title="First Article",
                snippet="...",
                date_accessed="2024-01-15T10:00:00+00:00",
            ),
            Citation(
                id="[2]",
                url="https://example2.com",
                title="Second Article",
                snippet="...",
                date_accessed="2024-01-15T10:00:00+00:00",
            ),
        ]

        result = format_references_section(citations, CitationStyle.APA)

        assert "## References" in result
        assert "[1]" in result
        assert "[2]" in result
        assert "First Article." in result
        assert "Second Article." in result

    def test_format_references_section_custom_title(self):
        """Test references section with custom title."""
        citations = [
            Citation(
                id="[1]",
                url="https://example.com",
                title="Test",
                snippet="...",
            ),
        ]

        result = format_references_section(
            citations,
            CitationStyle.MLA,
            title="Works Cited"
        )

        assert "## Works Cited" in result

    def test_format_references_section_empty(self):
        """Test references section with no citations."""
        result = format_references_section([], CitationStyle.APA)

        assert result == ""

    def test_format_references_section_sorts_by_id(self):
        """Test that references are sorted by citation ID number."""
        citations = [
            Citation(id="[10]", url="https://example.com",
                     title="Ten", snippet="..."),
            Citation(id="[2]", url="https://example.com",
                     title="Two", snippet="..."),
            Citation(id="[1]", url="https://example.com",
                     title="One", snippet="..."),
            Citation(id="[5]", url="https://example.com",
                     title="Five", snippet="..."),
        ]

        result = format_references_section(citations, CitationStyle.APA)

        # Check that they appear in order
        idx_1 = result.index("[1]")
        idx_2 = result.index("[2]")
        idx_5 = result.index("[5]")
        idx_10 = result.index("[10]")

        assert idx_1 < idx_2 < idx_5 < idx_10


class TestURLValidation:
    """Tests for URL validation functions."""

    @pytest.mark.asyncio
    async def test_validate_citation_url_success(self):
        """Test validating an accessible URL."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="Test",
            snippet="...",
        )

        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.head = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await validate_citation_url(citation)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_citation_url_not_found(self):
        """Test validating a URL that returns 404."""
        citation = Citation(
            id="[1]",
            url="https://example.com/notfound",
            title="Test",
            snippet="...",
        )

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.head = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await validate_citation_url(citation)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_citation_url_exception(self):
        """Test handling of network exceptions."""
        citation = Citation(
            id="[1]",
            url="https://invalid-url",
            title="Test",
            snippet="...",
        )

        mock_session = MagicMock()
        mock_session.head = MagicMock(side_effect=Exception("Network error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await validate_citation_url(citation)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_all_citations(self):
        """Test validating multiple citations."""
        citations = [
            Citation(id="[1]", url="https://good.com",
                     title="Good", snippet="..."),
            Citation(id="[2]", url="https://bad.com",
                     title="Bad", snippet="..."),
        ]

        # Mock different responses for different URLs
        async def mock_validate(citation, timeout):
            if "good.com" in citation.url:
                return True
            return False

        with patch("app.output.citation_formatter.validate_citation_url", side_effect=mock_validate):
            results = await validate_all_citations(citations)

        assert len(results) == 2
        # First should be valid
        assert results[0][0].url == "https://good.com"
        assert results[0][1] is True
        # Second should be invalid
        assert results[1][0].url == "https://bad.com"
        assert results[1][1] is False
