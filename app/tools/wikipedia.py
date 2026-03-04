"""
Wikipedia search tool for background information.

Useful for getting foundational context and definitions.
"""

import logging

import wikipedia
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WikipediaResult(BaseModel):
    """A Wikipedia article result."""

    title: str = Field(description="Article title")
    summary: str = Field(description="Article summary")
    url: str = Field(description="Wikipedia URL")
    content: str = Field(
        default="", description="Full article content (truncated)")


async def wikipedia_search(
    query: str,
    sentences: int = 5,
    include_content: bool = False,
) -> list[WikipediaResult]:
    """
    Search Wikipedia for relevant articles.

    Args:
        query: Search query
        sentences: Number of sentences for summary
        include_content: Whether to include full article content

    Returns:
        List of WikipediaResult objects (usually 1-3 most relevant)
    """
    logger.info(f"[WIKIPEDIA] Starting search for: '{query[:80]}...'")
    logger.debug(
        f"[WIKIPEDIA] Parameters: sentences={sentences}, include_content={include_content}")

    results = []

    # Search for matching pages
    logger.debug("[WIKIPEDIA] Calling wikipedia.search()")
    search_results = wikipedia.search(query, results=3)
    logger.debug(
        f"[WIKIPEDIA] Found {len(search_results)} matching pages: {search_results}")

    for page_title in search_results:
        logger.debug(f"[WIKIPEDIA] Fetching page: '{page_title}'")
        page = wikipedia.page(page_title, auto_suggest=False)
        logger.debug(
            f"[WIKIPEDIA] Successfully fetched page: '{page.title}'")

        result = WikipediaResult(
            title=page.title,
            summary=wikipedia.summary(page_title, sentences=sentences),
            url=page.url,
            content=page.content[:3000] if include_content else "",
        )
        results.append(result)
        logger.debug(f"[WIKIPEDIA] Added result for '{page.title}'")

    logger.info(
        f"[WIKIPEDIA] Search complete, returning {len(results)} results")
    return results


async def get_wikipedia_page(title: str, sentences: int = 10) -> WikipediaResult | None:
    """
    Get a specific Wikipedia page by title.

    Args:
        title: Exact page title
        sentences: Number of sentences for summary

    Returns:
        WikipediaResult or None if not found
    """
    page = wikipedia.page(title, auto_suggest=False)
    return WikipediaResult(
        title=page.title,
        summary=wikipedia.summary(title, sentences=sentences),
        url=page.url,
        content=page.content[:5000],
    )
