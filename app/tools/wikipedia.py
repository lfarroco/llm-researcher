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


# Titles that cannot be resolved raise PageError ("Page id ... does not match
# any pages"); ambiguous ones raise DisambiguationError ("Scale", "Complex").
# Both are per-page problems and must not discard the other search hits.
LOOKUP_ERRORS = (
    wikipedia.exceptions.PageError,
    wikipedia.exceptions.DisambiguationError,
)


def _fetch_page(
    title: str, sentences: int, include_content: bool = False,
) -> WikipediaResult | None:
    """Fetch one page, returning ``None`` instead of raising.

    When the strict lookup fails we still try an auto-suggesting summary,
    which is usually what the search hit meant.
    """
    try:
        page = wikipedia.page(title, auto_suggest=False)
    except LOOKUP_ERRORS as exc:
        logger.warning(
            "[WIKIPEDIA] Could not resolve '%s' (%s); trying summary "
            "lookup", title, exc,
        )
        return _summary_only_result(title, sentences)

    try:
        summary = wikipedia.summary(title, sentences=sentences)
    except LOOKUP_ERRORS as exc:
        # The page exists but its summary does not (e.g. a redirect loop).
        logger.warning("[WIKIPEDIA] No summary for '%s': %s", title, exc)
        summary = ""

    return WikipediaResult(
        title=page.title,
        summary=summary,
        url=page.url,
        content=page.content[:3000] if include_content else "",
    )


def _summary_only_result(
    title: str, sentences: int
) -> WikipediaResult | None:
    """Best-effort result built from the summary API alone."""
    try:
        summary = wikipedia.summary(
            title, sentences=sentences, auto_suggest=True
        )
        page = wikipedia.page(title, auto_suggest=True)
    except Exception as exc:  # noqa: BLE001 - any lookup failure means skip
        logger.warning("[WIKIPEDIA] Skipping '%s': %s", title, exc)
        return None

    return WikipediaResult(
        title=page.title, summary=summary, url=page.url, content=""
    )


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
        # One unresolvable or ambiguous title must not abort the others.
        result = _fetch_page(page_title, sentences, include_content)
        if result is None:
            continue

        results.append(result)
        logger.debug(f"[WIKIPEDIA] Added result for '{result.title}'")

    if not results and query:
        # Every hit failed; fall back to a summary of the original query.
        logger.warning(
            "[WIKIPEDIA] No page resolved for '%s'; falling back to a "
            "summary lookup", query[:80],
        )
        fallback = _summary_only_result(query, sentences)
        if fallback is not None:
            results.append(fallback)

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
        summary = wikipedia.summary(title, sentences=sentences)
    except LOOKUP_ERRORS as exc:
        logger.warning("[WIKIPEDIA] Page '%s' not available: %s", title, exc)
        return None

    return WikipediaResult(
        title=page.title,
        summary=summary,
        url=page.url,
        content=page.content[:5000],
    )
