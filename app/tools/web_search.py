"""
Web search tool using Tavily API with DuckDuckGo fallback.

Tavily is preferred as it returns structured results with snippets
that work well for citation extraction.

This module can be tested in isolation by passing api_key explicitly.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.tools.base import get_setting

logger = logging.getLogger(__name__)


# Navigation / sign-in / cookie chrome that search APIs splice onto the front
# of a page's real text. A live run produced BibTeX entries whose "abstract"
# was entirely sign-in chrome, which then poisoned the relevance assessment.
#
# STRONG phrases are chrome wherever they appear; WEAK ones are ordinary words
# that are only chrome when followed by a separator, so "Home robots are
# changing manufacturing" is left alone while "Home | Example" is stripped.
CHROME_PHRASES_STRONG = (
    "skip to main content",
    "skip to content",
    "sign in",
    "sign up",
    "log in",
    "create account",
    "create an account",
    "accept all cookies",
    "accept cookies",
    "we use cookies",
    "enable javascript",
    "you need to enable javascript",
)

CHROME_PHRASES_WEAK = (
    "home",
    "menu",
    "navigation",
    "share",
    "subscribe",
    "dismiss",
    "advertisement",
    "sponsored",
    "cookie policy",
)

# Separators that may follow a chrome phrase. A bare space is allowed only for
# the unambiguous multiword phrases.
_SEPARATORS = "|·•›»-–—:,.\n\r\t"
_TRAILING_CHROME_CHARS = " \t\n\r|·•›»-–—:,."


def strip_leading_boilerplate(text: str) -> str:
    """Remove leading navigation/sign-in/cookie chrome from a snippet.

    Stripping is iterative because banners stack ("Sign in | Menu | Article").
    Returns the text with whitespace collapsed.
    """
    if not text:
        return ""

    cleaned = text.strip()
    changed = True
    while changed and cleaned:
        changed = False
        lowered = cleaned.lower()

        for phrase in CHROME_PHRASES_STRONG:
            if lowered.startswith(phrase):
                cleaned = cleaned[len(phrase):].lstrip(_TRAILING_CHROME_CHARS)
                changed = True
                break

        if changed:
            continue

        for phrase in CHROME_PHRASES_WEAK:
            if not lowered.startswith(phrase):
                continue
            remainder = cleaned[len(phrase):].lstrip(" \t\n\r")
            # Require a punctuation separator or end of text. A following
            # *word* means this is probably the first word of real content
            # ("Home robots ...", "Share prices fell ...").
            if remainder and remainder[0] not in _SEPARATORS:
                continue
            cleaned = remainder.lstrip(_TRAILING_CHROME_CHARS)
            changed = True
            break

    return " ".join(cleaned.split())


def site_label(url: str) -> str:
    """The registrable-ish site name for a URL ("www.medium.com" -> "medium")."""
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(".")[0] if host else ""


def title_from_url(url: str) -> str:
    """Derive a human-readable title from a URL's last path segment."""
    path = urlparse(url).path.rstrip("/")
    if not path:
        return ""
    slug = path.rsplit("/", 1)[-1]
    slug = re.sub(r"\.(html?|php|aspx?|jsp)$", "", slug, flags=re.I)
    slug = re.sub(r"[-_+]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    if not slug or slug.isdigit():
        return ""
    # Preserve already-capitalised words (acronyms) but capitalise the rest.
    return " ".join(
        word if word[:1].isupper() else word.capitalize()
        for word in slug.split()
    )


def improve_title(title: str, url: str) -> str:
    """Replace a missing or site-name-only title with one derived from the URL.

    Search results frequently carry the publisher's name as the title ("Medium")
    which is useless as a reference title and produces BibTeX keys like
    ``@misc{Unknown2026Medium}``.
    """
    cleaned = (title or "").strip()
    normalized = re.sub(r"[^a-z0-9]", "", cleaned.lower())
    if cleaned and normalized and normalized != site_label(url):
        return cleaned

    derived = title_from_url(url)
    return derived or cleaned


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
    *,
    tavily_api_key: Optional[str] = None,
) -> list[WebSearchResult]:
    """
    Search the web for information.

    Uses Tavily API if available, falls back to DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum number of results to return
        include_domains: Only search these domains (optional)
        exclude_domains: Exclude these domains (optional)
        tavily_api_key: Tavily API key (falls back to settings if not provided)

    Returns:
        List of WebSearchResult objects
    """
    logger.debug(
        f"[WEB_SEARCH] Starting web search for query: '{query[:80]}...'")
    logger.debug(f"[WEB_SEARCH] Parameters: max_results={max_results}, "
                 f"include_domains={include_domains}, exclude_domains={exclude_domains}")

    # Get API key with fallback to settings
    api_key = get_setting(tavily_api_key, "tavily_api_key")
    logger.debug(f"[WEB_SEARCH] Tavily API key configured: {bool(api_key)}")

    # Use Tavily first if API key is configured
    if api_key:
        logger.info("[WEB_SEARCH] Using Tavily API for search")
        results = await _tavily_search(
            query, max_results, include_domains, exclude_domains, api_key
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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
async def _tavily_search(
    query: str,
    max_results: int,
    include_domains: Optional[list[str]],
    exclude_domains: Optional[list[str]],
    api_key: str,
) -> list[WebSearchResult]:
    """Search using Tavily API with automatic retries."""
    from tavily import TavilyClient

    logger.debug("[TAVILY] Initializing Tavily client")
    client = TavilyClient(api_key=api_key)

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
        url = item.get("url", "")
        results.append(WebSearchResult(
            title=improve_title(item.get("title", ""), url),
            url=url,
            snippet=strip_leading_boilerplate(
                item.get("content", "")
            )[:1000],  # Limit snippet size
            score=item.get("score", 0.0),
        ))

    logger.info(f"[TAVILY] Search complete, returning {len(results)} results")
    return results


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)
async def _duckduckgo_search(
    query: str,
    max_results: int,
) -> list[WebSearchResult]:
    """Search using DuckDuckGo (free fallback) with automatic retries."""
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
            url = item.get("href", "")
            results.append(WebSearchResult(
                title=improve_title(item.get("title", ""), url),
                url=url,
                snippet=strip_leading_boilerplate(item.get("body", ""))[:1000],
                score=0.5,  # DuckDuckGo doesn't provide scores
            ))

    logger.info(
        f"[DUCKDUCKGO] Search complete, returning {len(results)} results")
    return results
