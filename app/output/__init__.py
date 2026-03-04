"""
Output module for document generation and citation formatting.
"""

from app.output.citation_formatter import (
    CitationStyle,
    CitationFormatter,
    format_citation,
    format_references_section,
)

__all__ = [
    "CitationStyle",
    "CitationFormatter",
    "format_citation",
    "format_references_section",
]
