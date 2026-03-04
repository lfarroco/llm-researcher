"""
Web scraper for extracting full content from URLs.

Uses trafilatura for clean text extraction from web pages.
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Request configuration
REQUEST_TIMEOUT = 15.0
MAX_CONTENT_LENGTH = 50000  # 50KB limit for content
USER_AGENT = (
    "Mozilla/5.0 (compatible; LLMResearcher/1.0; +https://github.com/lfarroco/llm-researcher)"
)


class ScrapedContent(BaseModel):
    """Extracted content from a web page."""

    url: str = Field(description="Source URL")
    title: str = Field(default="", description="Page title")
    content: str = Field(description="Extracted text content")
    author: Optional[str] = Field(default=None, description="Author if found")
    date: Optional[str] = Field(
        default=None, description="Publication date if found")
    success: bool = Field(
        default=True, description="Whether extraction succeeded")
    error: Optional[str] = Field(
        default=None, description="Error message if failed")


async def scrape_url(url: str) -> ScrapedContent:
    """
    Scrape and extract clean text content from a URL.

    Uses trafilatura for content extraction, which handles:
    - Removing boilerplate (ads, navigation, footers)
    - Extracting main article content
    - Finding metadata (author, date, title)

    Args:
        url: URL to scrape

    Returns:
        ScrapedContent object with extracted text
    """
    import trafilatura

    logger.debug(f"Scraping URL: {url}")

    # Fetch the page
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        response.raise_for_status()
        html = response.text

    # Extract content using trafilatura
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=True,
        output_format="txt",
    )

    if not extracted:
        return ScrapedContent(
            url=url,
            content="",
            success=False,
            error="Failed to extract content from page",
        )

    # Extract metadata
    metadata = trafilatura.extract_metadata(html)

    # Truncate content if too long
    content = extracted[:MAX_CONTENT_LENGTH]
    if len(extracted) > MAX_CONTENT_LENGTH:
        content += "\n\n[Content truncated...]"

    return ScrapedContent(
        url=url,
        title=metadata.title if metadata else "",
        content=content,
        author=metadata.author if metadata else None,
        date=metadata.date if metadata else None,
        success=True,
    )


async def scrape_multiple(urls: list[str]) -> list[ScrapedContent]:
    """
    Scrape multiple URLs concurrently.

    Args:
        urls: List of URLs to scrape

    Returns:
        List of ScrapedContent objects
    """
    import asyncio

    tasks = [scrape_url(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scraped = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            scraped.append(ScrapedContent(
                url=url,
                content="",
                success=False,
                error=str(result),
            ))
        else:
            scraped.append(result)

    return scraped
