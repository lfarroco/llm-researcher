"""
Citation formatter - formats citations in APA, MLA, and Chicago styles.

This module provides utilities to format citations and generate reference
sections in various academic citation styles.
"""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from app.memory.research_state import Citation, SourceType

logger = logging.getLogger(__name__)


class CitationStyle(str, Enum):
    """Supported citation styles."""
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"


class CitationFormatter:
    """
    Formats citations in various academic styles.

    Supports APA (7th edition), MLA (9th edition), and Chicago (17th edition).
    """

    @staticmethod
    def _parse_date(date_string: str) -> Optional[datetime]:
        """Parse an ISO date string into a datetime object."""
        try:
            # Handle ISO format with timezone
            if "T" in date_string:
                return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
            return datetime.strptime(date_string, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _get_domain(url: str) -> str:
        """Extract the domain from a URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return url

    @staticmethod
    def _format_author_apa(author: Optional[str]) -> str:
        """
        Format author name for APA style.
        Expected format: "Last, F. M." or "Organization Name"
        """
        if not author:
            return ""

        # Check if it's likely an organization (no comma, multiple words)
        if "," not in author and " " in author:
            return author

        # Split by comma for "Last, First" format
        parts = author.split(",")
        if len(parts) >= 2:
            last_name = parts[0].strip()
            first_names = parts[1].strip().split()
            initials = " ".join(f"{name[0]}." for name in first_names if name)
            return f"{last_name}, {initials}"

        return author

    @staticmethod
    def _format_author_mla(author: Optional[str]) -> str:
        """
        Format author name for MLA style.
        Expected format: "Last, First Middle"
        """
        if not author:
            return ""
        return author

    @staticmethod
    def _format_author_chicago(author: Optional[str]) -> str:
        """
        Format author name for Chicago style.
        Same as MLA for bibliography entries.
        """
        if not author:
            return ""
        return author

    @classmethod
    def format_apa(cls, citation: Citation) -> str:
        """
        Format a citation in APA 7th edition style.

        Format:
        Author, A. A. (Year, Month Day). Title. Site Name. URL

        For web sources without author:
        Title. (Year, Month Day). Site Name. URL
        """
        parts = []

        # Author
        author_str = cls._format_author_apa(citation.author)
        if author_str:
            parts.append(author_str)

        # Date
        date_obj = cls._parse_date(citation.date_accessed)
        if date_obj:
            date_str = f"({date_obj.year}, {date_obj.strftime('%B')} {date_obj.day})"
        else:
            date_str = "(n.d.)"

        if author_str:
            parts.append(date_str + ".")
        else:
            # Title first, then date
            parts.append(f"{citation.title}.")
            parts.append(date_str + ".")

        # Title (if author exists)
        if author_str:
            parts.append(f"{citation.title}.")

        # Source type specific additions
        domain = cls._get_domain(citation.url)
        if citation.source_type == SourceType.ARXIV:
            parts.append("arXiv.")
        elif citation.source_type == SourceType.WIKIPEDIA:
            parts.append("Wikipedia.")
        else:
            parts.append(f"{domain}.")

        # URL
        parts.append(citation.url)

        return " ".join(parts)

    @classmethod
    def format_mla(cls, citation: Citation) -> str:
        """
        Format a citation in MLA 9th edition style.

        Format:
        Author. "Title." Website Name, Publisher, Day Month Year, URL.

        For web sources without author:
        "Title." Website Name, Day Month Year, URL.
        """
        parts = []

        # Author
        author_str = cls._format_author_mla(citation.author)
        if author_str:
            parts.append(f"{author_str}.")

        # Title in quotes
        parts.append(f'"{citation.title}."')

        # Website/Source name
        if citation.source_type == SourceType.ARXIV:
            parts.append("arXiv,")
        elif citation.source_type == SourceType.WIKIPEDIA:
            parts.append("Wikipedia,")
        else:
            domain = cls._get_domain(citation.url)
            parts.append(f"{domain},")

        # Date
        date_obj = cls._parse_date(citation.date_accessed)
        if date_obj:
            date_str = f"{date_obj.day} {date_obj.strftime('%b')}. {date_obj.year},"
            parts.append(date_str)

        # URL
        parts.append(f"{citation.url}.")

        return " ".join(parts)

    @classmethod
    def format_chicago(cls, citation: Citation) -> str:
        """
        Format a citation in Chicago 17th edition style (Notes-Bibliography).

        Bibliography format:
        Author. "Title." Source Name. Last modified/Accessed Date. URL.

        For web sources without author:
        "Title." Source Name. Accessed Date. URL.
        """
        parts = []

        # Author
        author_str = cls._format_author_chicago(citation.author)
        if author_str:
            parts.append(f"{author_str}.")

        # Title in quotes
        parts.append(f'"{citation.title}."')

        # Source name
        if citation.source_type == SourceType.ARXIV:
            parts.append("arXiv.")
        elif citation.source_type == SourceType.WIKIPEDIA:
            parts.append("Wikipedia.")
        else:
            domain = cls._get_domain(citation.url)
            parts.append(f"{domain}.")

        # Accessed date
        date_obj = cls._parse_date(citation.date_accessed)
        if date_obj:
            date_str = f"Accessed {date_obj.strftime('%B')} {date_obj.day}, {date_obj.year}."
            parts.append(date_str)

        # URL
        parts.append(citation.url)

        return " ".join(parts)

    @classmethod
    def format(cls, citation: Citation, style: CitationStyle = CitationStyle.APA) -> str:
        """
        Format a citation in the specified style.

        Args:
            citation: The citation to format
            style: Citation style (APA, MLA, or Chicago)

        Returns:
            Formatted citation string
        """
        formatters = {
            CitationStyle.APA: cls.format_apa,
            CitationStyle.MLA: cls.format_mla,
            CitationStyle.CHICAGO: cls.format_chicago,
        }
        return formatters[style](citation)


def format_citation(citation: Citation, style: CitationStyle = CitationStyle.APA) -> str:
    """
    Convenience function to format a single citation.

    Args:
        citation: The citation to format
        style: Citation style (default: APA)

    Returns:
        Formatted citation string
    """
    return CitationFormatter.format(citation, style)


def format_references_section(
    citations: list[Citation],
    style: CitationStyle = CitationStyle.APA,
    title: str = "References"
) -> str:
    """
    Generate a complete references section with all citations.

    Args:
        citations: List of citations to include
        style: Citation style (default: APA)
        title: Section title (default: "References")

    Returns:
        Formatted references section as markdown
    """
    if not citations:
        return ""

    # Sort citations by their ID number
    def sort_key(c: Citation) -> int:
        # Extract number from "[1]" format
        match = re.search(r'\[(\d+)\]', c.id)
        return int(match.group(1)) if match else 0

    sorted_citations = sorted(citations, key=sort_key)

    lines = [f"## {title}", ""]
    for citation in sorted_citations:
        formatted = CitationFormatter.format(citation, style)
        lines.append(f"{citation.id} {formatted}")
        lines.append("")

    return "\n".join(lines)


async def validate_citation_url(citation: Citation, timeout: float = 5.0) -> bool:
    """
    Validate that a citation URL is accessible.

    Args:
        citation: The citation to validate
        timeout: Request timeout in seconds

    Returns:
        True if URL is accessible, False otherwise
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(
                citation.url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=True
            ) as response:
                return response.status < 400
    except Exception as e:
        logger.warning(f"Failed to validate URL {citation.url}: {e}")
        return False


async def validate_all_citations(
    citations: list[Citation],
    timeout: float = 5.0
) -> list[tuple[Citation, bool]]:
    """
    Validate all citation URLs.

    Args:
        citations: List of citations to validate
        timeout: Request timeout per URL

    Returns:
        List of (citation, is_valid) tuples
    """
    import asyncio

    results = []
    for citation in citations:
        is_valid = await validate_citation_url(citation, timeout)
        results.append((citation, is_valid))
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.1)

    return results
