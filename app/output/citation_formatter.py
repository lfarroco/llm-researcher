"""
Citation formatter - formats citations in APA, MLA, and Chicago styles.

This module provides utilities to format citations and generate reference
sections in various academic citation styles using citeproc-py and CSL.
"""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from citeproc import CitationStylesStyle, CitationStylesBibliography
from citeproc import Citation as CiteProc_Citation
from citeproc import CitationItem
from citeproc.source.json import CiteProcJSON

from app.memory.research_state import Citation, SourceType

logger = logging.getLogger(__name__)


class CitationStyle(str, Enum):
    """Supported citation styles."""
    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"


# CSL style XML content (simplified versions - in production, use full CSL files)
CSL_STYLES = {
    CitationStyle.APA: """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0" demote-non-dropping-particle="never">
  <info>
    <title>American Psychological Association 7th edition</title>
    <id>http://www.zotero.org/styles/apa</id>
  </info>
  <macro name="author">
    <names variable="author">
      <name name-as-sort-order="all" and="symbol" sort-separator=", " initialize-with=". " delimiter=", " delimiter-precedes-last="always"/>
    </names>
  </macro>
  <macro name="issued">
    <date variable="issued">
      <date-part name="year"/>
    </date>
  </macro>
  <bibliography hanging-indent="true" et-al-min="8" et-al-use-first="6" et-al-use-last="true" entry-spacing="0" line-spacing="2">
    <sort>
      <key macro="author"/>
      <key macro="issued" sort="ascending"/>
    </sort>
    <layout>
      <text macro="author" suffix=". "/>
      <text macro="issued" prefix="(" suffix="). "/>
      <text variable="title" font-style="italic" suffix=". "/>
      <text variable="URL"/>
    </layout>
  </bibliography>
</style>""",
    CitationStyle.MLA: """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">
  <info>
    <title>Modern Language Association 9th edition</title>
    <id>http://www.zotero.org/styles/mla</id>
  </info>
  <macro name="author">
    <names variable="author">
      <name name-as-sort-order="first" and="text" sort-separator=", " delimiter=", " delimiter-precedes-last="always"/>
    </names>
  </macro>
  <bibliography hanging-indent="true" et-al-min="3" et-al-use-first="1" line-spacing="2" entry-spacing="0">
    <sort>
      <key macro="author"/>
      <key variable="title"/>
    </sort>
    <layout>
      <text macro="author" suffix=". "/>
      <text variable="title" quotes="true" suffix=". "/>
      <text variable="container-title" font-style="italic" suffix=", "/>
      <date variable="issued">
        <date-part name="day" suffix=" "/>
        <date-part name="month" form="short" suffix=" "/>
        <date-part name="year" suffix=", "/>
      </date>
      <text variable="URL" suffix="."/>
    </layout>
  </bibliography>
</style>""",
    CitationStyle.CHICAGO: """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="note" version="1.0">
  <info>
    <title>Chicago Manual of Style 17th edition (note)</title>
    <id>http://www.zotero.org/styles/chicago-note-bibliography</id>
  </info>
  <macro name="author">
    <names variable="author">
      <name name-as-sort-order="first" and="text" sort-separator=", " delimiter=", "/>
    </names>
  </macro>
  <bibliography hanging-indent="true" et-al-min="11" et-al-use-first="7" subsequent-author-substitute="———" entry-spacing="0">
    <sort>
      <key macro="author"/>
      <key variable="title"/>
    </sort>
    <layout>
      <text macro="author" suffix=". "/>
      <text variable="title" quotes="true" suffix=". "/>
      <text variable="container-title" font-style="italic" suffix=". "/>
      <text value="Accessed "/>
      <date variable="accessed">
        <date-part name="month" suffix=" "/>
        <date-part name="day" suffix=", "/>
        <date-part name="year" suffix=". "/>
      </date>
      <text variable="URL" suffix="."/>
    </layout>
  </bibliography>
</style>"""
}


class CitationFormatter:
    """
    Formats citations in various academic styles using citeproc-py and CSL.

    Supports APA (7th edition), MLA (9th edition), and Chicago (17th edition).
    """

    @staticmethod
    def _parse_date(date_string: str) -> Optional[datetime]:
        """Parse an ISO date string into a datetime object."""
        try:
            # Handle ISO format with timezone
            if "T" in date_string:
                cleaned = date_string.replace("Z", "+00:00")
                return datetime.fromisoformat(cleaned)
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
    def _citation_to_csl_json(citation: Citation) -> dict:
        """
        Convert a Citation object to CSL JSON format.

        CSL JSON is the standard format for bibliographic data used by citeproc-py.
        """
        # Extract numeric ID from citation.id (e.g., "[1]" -> "1")
        match = re.search(r'\[(\d+)\]', citation.id)
        csl_id = match.group(1) if match else citation.id.strip("[]")

        # Parse date
        date_obj = CitationFormatter._parse_date(citation.date_accessed)
        date_parts = None
        if date_obj:
            date_parts = [[date_obj.year, date_obj.month, date_obj.day]]

        # Determine type based on source
        item_type = "webpage"
        if citation.source_type == SourceType.ARXIV:
            item_type = "article"
        elif citation.source_type == SourceType.WIKIPEDIA:
            item_type = "entry-encyclopedia"

        # Build CSL JSON
        csl_data = {
            "id": csl_id,
            "type": item_type,
            "title": citation.title,
            "URL": citation.url,
        }

        # Add author if present (convert to CSL name format)
        if citation.author:
            # Handle "Last, First" format
            if "," in citation.author:
                parts = citation.author.split(",", 1)
                csl_data["author"] = [{
                    "family": parts[0].strip(),
                    "given": parts[1].strip() if len(parts) > 1 else ""
                }]
            else:
                # Organization or single name
                csl_data["author"] = [{"literal": citation.author}]

        # Add dates
        if date_parts:
            csl_data["issued"] = {"date-parts": date_parts}
            csl_data["accessed"] = {"date-parts": date_parts}

        # Add container/publisher based on source type
        if citation.source_type == SourceType.WIKIPEDIA:
            csl_data["container-title"] = "Wikipedia"
        elif citation.source_type == SourceType.ARXIV:
            csl_data["container-title"] = "arXiv"
        else:
            domain = CitationFormatter._get_domain(citation.url)
            csl_data["container-title"] = domain

        return csl_data

    @classmethod
    def format(
        cls,
        citation: Citation,
        style: CitationStyle = CitationStyle.APA
    ) -> str:
        """
        Format a citation in the specified style using citeproc-py.

        Args:
            citation: The citation to format
            style: Citation style (APA, MLA, or Chicago)

        Returns:
            Formatted citation string
        """
        try:
            # Convert to CSL JSON format
            csl_data = cls._citation_to_csl_json(citation)
            csl_id = csl_data["id"]

            # Create citation source
            bib_source = CiteProcJSON([csl_data])

            # Load CSL style
            style_xml = CSL_STYLES[style]
            bib_style = CitationStylesStyle(style_xml, validate=False)

            # Create bibliography
            bibliography = CitationStylesBibliography(
                bib_style, bib_source, None)

            # Register citation
            citation_item = CitationItem(csl_id)
            bibliography.register(CiteProc_Citation([citation_item]))

            # Generate bibliography
            for item in bibliography.bibliography():
                # Remove HTML tags and clean up
                result = str(item)
                result = re.sub(r'<[^>]+>', '', result)
                result = re.sub(r'\s+', ' ', result).strip()
                return result

            # Fallback if citeproc fails
            return cls._format_fallback(citation, style)

        except Exception as e:
            logger.warning(
                f"citeproc-py formatting failed: {e}, using fallback")
            return cls._format_fallback(citation, style)

    @classmethod
    def _format_fallback(cls, citation: Citation, style: CitationStyle) -> str:
        """Simple fallback formatting if citeproc-py fails."""
        parts = []

        if citation.author:
            parts.append(f"{citation.author}.")

        if style == CitationStyle.MLA or style == CitationStyle.CHICAGO:
            parts.append(f'"{citation.title}."')
        else:
            parts.append(f"{citation.title}.")

        domain = cls._get_domain(citation.url)
        parts.append(f"{domain}.")

        date_obj = cls._parse_date(citation.date_accessed)
        if date_obj:
            if style == CitationStyle.APA:
                parts.append(f"({date_obj.year}).")
            else:
                parts.append(f"Accessed {date_obj.strftime('%B %d, %Y')}.")

        parts.append(citation.url)

        return " ".join(parts)


def format_citation(
    citation: Citation,
    style: CitationStyle = CitationStyle.APA
) -> str:
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


async def validate_citation_url(
    citation: Citation,
    timeout: float = 5.0
) -> bool:
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
