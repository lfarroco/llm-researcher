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
    logger.debug(f"Wikipedia search: {query}")

    results = []

    try:
        # Search for matching pages
        search_results = wikipedia.search(query, results=3)

        for page_title in search_results:
            try:
                page = wikipedia.page(page_title, auto_suggest=False)

                result = WikipediaResult(
                    title=page.title,
                    summary=wikipedia.summary(page_title, sentences=sentences),
                    url=page.url,
                    content=page.content[:3000] if include_content else "",
                )
                results.append(result)

            except wikipedia.DisambiguationError as e:
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
                    except Exception:
                        pass

            except wikipedia.PageError:
                # Page doesn't exist, skip
                continue

    except Exception as e:
        logger.warning(f"Wikipedia search error: {e}")

    logger.debug(f"Wikipedia returned {len(results)} results")
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
