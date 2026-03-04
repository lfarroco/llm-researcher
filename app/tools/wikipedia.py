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

    try:
        # Search for matching pages
        logger.debug("[WIKIPEDIA] Calling wikipedia.search()")
        search_results = wikipedia.search(query, results=3)
        logger.debug(
            f"[WIKIPEDIA] Found {len(search_results)} matching pages: {search_results}")

        for page_title in search_results:
            logger.debug(f"[WIKIPEDIA] Fetching page: '{page_title}'")
            try:
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

            except wikipedia.DisambiguationError as e:
                logger.debug(
                    f"[WIKIPEDIA] Disambiguation page for '{page_title}', options: {e.options[:3]}")
                # If disambiguation page, try the first option
                if e.options:
                    try:
                        page = wikipedia.page(e.options[0], auto_suggest=False)
                        result = WikipediaResult(
                            title=page.title,
                            summary=wikipedia.summary(
                                e.options[0], sentences=sentences),
                            url=page.url,
                            content=page.content[:3000] if include_content else "",
                        )
                        results.append(result)
                        logger.debug(
                            f"[WIKIPEDIA] Added result from disambiguation: '{page.title}'")
                    except Exception as inner_e:
                        logger.debug(
                            f"[WIKIPEDIA] Failed to fetch disambiguation option: {inner_e}")

            except wikipedia.PageError as e:
                logger.debug(
                    f"[WIKIPEDIA] Page not found for '{page_title}': {e}")
                continue

    except Exception as e:
        logger.warning(f"[WIKIPEDIA] Search error: {e}", exc_info=True)

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
    try:
        page = wikipedia.page(title, auto_suggest=False)
        return WikipediaResult(
            title=page.title,
            summary=wikipedia.summary(title, sentences=sentences),
            url=page.url,
            content=page.content[:5000],
        )
    except Exception as e:
        logger.warning(f"Failed to get Wikipedia page '{title}': {e}")
        return None
