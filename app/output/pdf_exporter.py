"""
PDF Exporter - converts markdown documents to PDF using Pandoc.

This module provides utilities to export research documents
in various formats (PDF, HTML, DOCX) using pypandoc.
"""

import logging
from enum import Enum
from typing import Optional

try:
    import pypandoc
except ImportError:
    pypandoc = None  # type: ignore

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""
    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"
    MARKDOWN = "md"


def check_pandoc_installed() -> bool:
    """
    Check if pandoc is installed and available.

    Returns:
        True if pandoc is available, False otherwise
    """
    if pypandoc is None:
        logger.error("pypandoc package not installed")
        return False

    try:
        pypandoc.get_pandoc_version()
        return True
    except OSError:
        logger.error("Pandoc executable not found in system PATH")
        return False


def export_markdown_to_format(
    markdown_content: str,
    output_format: ExportFormat = ExportFormat.PDF,
    extra_args: Optional[list[str]] = None,
    metadata: Optional[dict[str, str]] = None
) -> bytes:
    """
    Convert markdown content to specified format using Pandoc.

    Args:
        markdown_content: The markdown text to convert
        output_format: Target format (PDF, HTML, DOCX, etc.)
        extra_args: Additional pandoc command-line arguments
        metadata: Document metadata (title, author, date)

    Returns:
        Binary content of the converted document

    Raises:
        RuntimeError: If pandoc is not installed
        ValueError: If conversion fails
    """
    if not check_pandoc_installed():
        raise RuntimeError(
            "Pandoc is not installed. Please install pandoc: "
            "https://pandoc.org/installing.html"
        )

    logger.info(f"Converting markdown to {output_format.value}")

    # Default pandoc arguments for better output
    default_args = []

    if output_format == ExportFormat.PDF:
        # PDF-specific options
        default_args.extend([
            '--pdf-engine=pdflatex',
            '--variable=geometry:margin=1in',
            '--variable=fontsize=11pt',
            '--variable=linkcolor=blue',
            '--number-sections',
            '--toc',  # Table of contents
            '--toc-depth=2',
        ])
    elif output_format == ExportFormat.HTML:
        # HTML-specific options
        default_args.extend([
            '--standalone',
            '--self-contained',
            (
                '--css=https://cdn.jsdelivr.net/npm/'
                'github-markdown-css/github-markdown.min.css'
            ),
        ])
    elif output_format == ExportFormat.DOCX:
        # DOCX-specific options
        default_args.extend([
            '--reference-doc=default',  # Use default template
        ])

    # Merge with custom args
    if extra_args:
        default_args.extend(extra_args)

    # Add metadata if provided
    if metadata:
        for key, value in metadata.items():
            default_args.append(f'--metadata={key}:{value}')

    try:
        # pypandoc.convert_text returns string for some formats, bytes for PDF
        output = pypandoc.convert_text(
            markdown_content,
            output_format.value,
            format='md',
            extra_args=default_args,
        )

        # Ensure we return bytes
        if isinstance(output, str):
            return output.encode('utf-8')
        return output

    except Exception as e:
        logger.error(
            f"Failed to convert markdown to {output_format.value}: {e}")
        raise ValueError(f"Pandoc conversion failed: {str(e)}")


def export_research_to_pdf(
    markdown_content: str,
    title: str,
    author: str = "LLM Researcher",
    date: Optional[str] = None
) -> bytes:
    """
    Export research document to PDF with proper formatting.

    Args:
        markdown_content: The research document in markdown
        title: Document title
        author: Document author
        date: Document date (defaults to current date)

    Returns:
        PDF content as bytes
    """
    metadata = {
        'title': title,
        'author': author,
    }

    if date:
        metadata['date'] = date

    return export_markdown_to_format(
        markdown_content,
        output_format=ExportFormat.PDF,
        metadata=metadata
    )


def export_research_to_html(
    markdown_content: str,
    title: str,
    author: str = "LLM Researcher"
) -> bytes:
    """
    Export research document to HTML with proper formatting.

    Args:
        markdown_content: The research document in markdown
        title: Document title
        author: Document author

    Returns:
        HTML content as bytes
    """
    metadata = {
        'title': title,
        'author': author,
    }

    return export_markdown_to_format(
        markdown_content,
        output_format=ExportFormat.HTML,
        metadata=metadata
    )


def export_research_to_docx(
    markdown_content: str,
    title: str,
    author: str = "LLM Researcher"
) -> bytes:
    """
    Export research document to DOCX with proper formatting.

    Args:
        markdown_content: The research document in markdown
        title: Document title
        author: Document author

    Returns:
        DOCX content as bytes
    """
    metadata = {
        'title': title,
        'author': author,
    }

    return export_markdown_to_format(
        markdown_content,
        output_format=ExportFormat.DOCX,
        metadata=metadata
    )
