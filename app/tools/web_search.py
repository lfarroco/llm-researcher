"""
Web search tool using Tavily API with DuckDuckGo fallback.

Tavily is preferred as it returns structured results with snippets
that work well for citation extraction.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class WebSearchResult(BaseModel):
    """A single web search result."""

    title: str = Field(description="Page title")
    url: str = Field(description="Page URL")
    snippet: str = Field(description="Relevant text snippet")
    score: float = Field(default=0.0, description="Relevance score")


async def web_search(
    query: str,
    max_results: int = 5,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> list[WebSearchResult]:
    """
    Search the web for information.

    Uses Tavily API if available, falls back to DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum number of results to return
        include_domains: Only search these domains (optional)
        exclude_domains: Exclude these domains (optional)

    Returns:
        List of WebSearchResult objects
    """

    # Try Tavily first if API key is configured
    if settings.tavily_api_key:
        try:
            return await _tavily_search(
                query, max_results, include_domains, exclude_domains
            )
        except Exception as e:
            logger.warning(
                f"Tavily search failed, falling back to DuckDuckGo: {e}")

    # Fallback to DuckDuckGo (free, no API key needed)
    return await _duckduckgo_search(query, max_results)


async def _tavily_search(
    query: str,
    max_results: int,
    include_domains: Optional[list[str]],
    exclude_domains: Optional[list[str]],
) -> list[WebSearchResult]:
    """Search using Tavily API."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key)

    search_params = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",  # Better results with more context
        "include_answer": False,
    }

    if include_domains:
        search_params["include_domains"] = include_domains
    if exclude_domains:
        search_params["exclude_domains"] = exclude_domains

    logger.debug(f"Tavily search: {query}")
    response = client.search(**search_params)

    results = []
    for item in response.get("results", []):
        results.append(WebSearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", "")[:1000],  # Limit snippet size
            score=item.get("score", 0.0),
        ))

    logger.debug(f"Tavily returned {len(results)} results")
    return results


async def _duckduckgo_search(
    query: str,
    max_results: int,
) -> list[WebSearchResult]:
    """Search using DuckDuckGo (free fallback)."""
    from duckduckgo_search import DDGS

    logger.debug(f"DuckDuckGo search: {query}")

    results = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=max_results):
            results.append(WebSearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", "")[:1000],
                score=0.5,  # DuckDuckGo doesn't provide scores
            ))

    logger.debug(f"DuckDuckGo returned {len(results)} results")
    return results
