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
    logger.debug(
        f"[WEB_SEARCH] Starting web search for query: '{query[:80]}...'")
    logger.debug(f"[WEB_SEARCH] Parameters: max_results={max_results}, "
                 f"include_domains={include_domains}, exclude_domains={exclude_domains}")
    logger.debug(
        f"[WEB_SEARCH] Tavily API key configured: {bool(settings.tavily_api_key)}")

    # Use Tavily first if API key is configured
    if settings.tavily_api_key:
        logger.info("[WEB_SEARCH] Using Tavily API for search")
        results = await _tavily_search(
            query, max_results, include_domains, exclude_domains
        )
        logger.info(
            f"[WEB_SEARCH] Tavily search successful, got {len(results)} results")
        return results

    # Fallback to DuckDuckGo (free, no API key needed)
    logger.info("[WEB_SEARCH] Using DuckDuckGo for search")
    results = await _duckduckgo_search(query, max_results)
    logger.info(
        f"[WEB_SEARCH] DuckDuckGo search successful, got {len(results)} results")
    return results


async def _tavily_search(
    query: str,
    max_results: int,
    include_domains: Optional[list[str]],
    exclude_domains: Optional[list[str]],
) -> list[WebSearchResult]:
    """Search using Tavily API."""
    from tavily import TavilyClient

    logger.debug("[TAVILY] Initializing Tavily client")
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

    logger.debug(f"[TAVILY] Executing search with params: {search_params}")
    response = client.search(**search_params)
    logger.debug(
        f"[TAVILY] Raw response keys: {response.keys() if response else 'None'}")

    results = []
    raw_results = response.get("results", [])
    logger.debug(f"[TAVILY] Processing {len(raw_results)} raw results")

    for i, item in enumerate(raw_results):
        logger.debug(f"[TAVILY] Result {i+1}: title='{item.get('title', '')[:50]}', "
                     f"url='{item.get('url', '')[:60]}', score={item.get('score', 0.0)}")
        results.append(WebSearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", "")[:1000],  # Limit snippet size
            score=item.get("score", 0.0),
        ))

    logger.info(f"[TAVILY] Search complete, returning {len(results)} results")
    return results


async def _duckduckgo_search(
    query: str,
    max_results: int,
) -> list[WebSearchResult]:
    """Search using DuckDuckGo (free fallback)."""
    from duckduckgo_search import DDGS

    logger.debug(f"[DUCKDUCKGO] Starting search for: '{query[:80]}...'")
    logger.debug(f"[DUCKDUCKGO] Requested max_results: {max_results}")

    results = []
    with DDGS() as ddgs:
        logger.debug(
            "[DUCKDUCKGO] DDGS client initialized, executing text search")
        for i, item in enumerate(ddgs.text(query, max_results=max_results)):
            logger.debug(f"[DUCKDUCKGO] Result {i+1}: title='{item.get('title', '')[:50]}', "
                         f"url='{item.get('href', '')[:60]}'")
            results.append(WebSearchResult(
                title=item.get("title", ""),
                url=item.get("href", ""),
                snippet=item.get("body", "")[:1000],
                score=0.5,  # DuckDuckGo doesn't provide scores
            ))

    logger.info(
        f"[DUCKDUCKGO] Search complete, returning {len(results)} results")
    return results
