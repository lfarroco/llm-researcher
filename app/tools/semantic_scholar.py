"""
Semantic Scholar search tool for academic papers.

Uses the Semantic Scholar API to search papers and retrieve
citation data. Free tier allows 100 requests/5 minutes, or use
an API key for higher limits.

When no API key is provided the public unauthenticated endpoint is
used automatically. In that mode requests are throttled to 1 per
second and each request is retried up to 3 times (with exponential
back-off) to cope with the occasional failures that the public API
can return under heavy load.

This module can be tested in isolation by passing api_key explicitly.
"""

import asyncio
import logging
import time
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.tools.base import get_setting

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"

# ---------------------------------------------------------------------------
# Rate-limiting for the unauthenticated public API (1 request per second)
# ---------------------------------------------------------------------------

_unauth_lock = asyncio.Lock()
_last_unauth_request: float = 0.0
_UNAUTH_MIN_INTERVAL: float = 1.0  # seconds

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def _unauth_throttle() -> None:
    """Enforce at most 1 request per second for the unauthenticated API."""
    global _last_unauth_request
    async with _unauth_lock:
        now = time.monotonic()
        elapsed = now - _last_unauth_request
        if elapsed < _UNAUTH_MIN_INTERVAL:
            await asyncio.sleep(_UNAUTH_MIN_INTERVAL - elapsed)
        _last_unauth_request = time.monotonic()


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict,
    headers: dict,
) -> httpx.Response:
    """Make a GET request, retrying on transient errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.get(
                url, params=params, headers=headers, timeout=30.0
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(
                    f"[S2] HTTP {exc.response.status_code} on attempt "
                    f"{attempt + 1}/{_MAX_RETRIES}, retrying in {wait}s…"
                )
                await asyncio.sleep(wait)
                continue
            raise
        except httpx.TimeoutException as exc:
            if attempt < _MAX_RETRIES - 1:
                logger.warning(
                    f"[S2] Timeout on attempt {attempt + 1}/{_MAX_RETRIES}, retrying…"
                )
                await asyncio.sleep(1)
                continue
            raise RuntimeError("Semantic Scholar request timed out") from exc
    raise RuntimeError("Unexpected retry loop exit")  # pragma: no cover


class SemanticScholarResult(BaseModel):
    """A single Semantic Scholar paper result."""

    paper_id: str = Field(description="Semantic Scholar paper ID")
    title: str = Field(description="Paper title")
    authors: list[str] = Field(description="List of author names")
    abstract: str = Field(description="Paper abstract")
    year: Optional[int] = Field(default=None, description="Publication year")
    citation_count: int = Field(default=0, description="Number of citations")
    influential_citation_count: int = Field(
        default=0, description="Number of influential citations"
    )
    url: str = Field(description="Semantic Scholar paper URL")
    venue: Optional[str] = Field(default=None, description="Publication venue")
    open_access_pdf: Optional[str] = Field(
        default=None, description="Open access PDF URL if available"
    )
    doi: Optional[str] = Field(default=None, description="DOI if available")
    arxiv_id: Optional[str] = Field(
        default=None, description="ArXiv ID if available"
    )
    fields_of_study: list[str] = Field(
        default_factory=list, description="Fields of study"
    )
    tldr: Optional[str] = Field(
        default=None, description="AI-generated TLDR summary"
    )


async def semantic_scholar_search(
    query: str,
    max_results: int = 5,
    year_filter: Optional[str] = None,
    fields_of_study: Optional[list[str]] = None,
    open_access_only: bool = False,
    *,
    api_key: Optional[str] = None,
) -> list[SemanticScholarResult]:
    """
    Search Semantic Scholar for academic papers.

    Args:
        query: Search query
        max_results: Maximum number of results (max 100)
        year_filter: Filter by year range, e.g., "2020-2024" or "2020-"
        fields_of_study: Filter by fields, e.g., ["Computer Science", "Medicine"]
        open_access_only: Only return papers with open access PDFs
        api_key: Semantic Scholar API key (falls back to settings if not provided)

    Returns:
        List of SemanticScholarResult objects
    """
    logger.info(f"[S2] Starting search for: '{query[:80]}...'")
    logger.debug(
        f"[S2] Parameters: max_results={max_results}, "
        f"year_filter={year_filter}, fields_of_study={fields_of_study}"
    )

    # Build API request
    fields = (
        "paperId,title,authors,abstract,year,citationCount,"
        "influentialCitationCount,venue,openAccessPdf,externalIds,"
        "fieldsOfStudy,tldr"
    )

    params = {
        "query": query,
        "limit": min(max_results, 100),  # API max is 100
        "fields": fields,
    }

    if year_filter:
        params["year"] = year_filter
    if fields_of_study:
        params["fieldsOfStudy"] = ",".join(fields_of_study)
    if open_access_only:
        params["openAccessPdf"] = ""  # Filter for open access

    # Get API key with fallback to settings
    resolved_api_key = get_setting(api_key, "semantic_scholar_api_key")
    headers = {}
    if resolved_api_key:
        headers["x-api-key"] = resolved_api_key
        logger.debug("[S2] Using Semantic Scholar API key")
    else:
        logger.debug("[S2] No API key – using unauthenticated public API")
        await _unauth_throttle()

    try:
        async with httpx.AsyncClient() as client:
            logger.debug(
                f"[S2] Making request to {SEMANTIC_SCHOLAR_API_BASE}/paper/search")
            response = await _get_with_retry(
                client,
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/search",
                params=params,
                headers=headers,
            )
            data = response.json()

    except httpx.HTTPStatusError as e:
        logger.error(
            f"[S2] HTTP error: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 429:
            raise RuntimeError(
                "Semantic Scholar rate limit exceeded. "
                "Consider using an API key or waiting."
            ) from e
        raise

    papers = data.get("data", [])
    logger.debug(f"[S2] Received {len(papers)} papers from API")

    results = []
    for paper in papers:
        try:
            result = _parse_paper(paper)
            results.append(result)
        except Exception as e:
            logger.warning(f"[S2] Failed to parse paper: {e}")
            continue

    logger.info(f"[S2] Search complete, returning {len(results)} results")
    return results


async def get_paper_details(
    paper_id: str,
    *,
    api_key: Optional[str] = None,
) -> Optional[SemanticScholarResult]:
    """
    Get detailed information about a specific paper.

    Args:
        paper_id: Semantic Scholar paper ID, DOI, or ArXiv ID
        api_key: Semantic Scholar API key (falls back to settings if not provided)

    Returns:
        SemanticScholarResult or None if not found
    """
    logger.info(f"[S2] Fetching details for paper: {paper_id}")

    fields = (
        "paperId,title,authors,abstract,year,citationCount,"
        "influentialCitationCount,venue,openAccessPdf,externalIds,"
        "fieldsOfStudy,tldr"
    )

    resolved_api_key = get_setting(api_key, "semantic_scholar_api_key")
    headers = {}
    if resolved_api_key:
        headers["x-api-key"] = resolved_api_key
    else:
        await _unauth_throttle()

    try:
        async with httpx.AsyncClient() as client:
            response = await _get_with_retry(
                client,
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/{paper_id}",
                params={"fields": fields},
                headers=headers,
            )
            paper = response.json()
            return _parse_paper(paper)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"[S2] Paper not found: {paper_id}")
            return None
        raise


async def get_paper_citations(
    paper_id: str,
    max_results: int = 10,
    *,
    api_key: Optional[str] = None,
) -> list[SemanticScholarResult]:
    """
    Get papers that cite the specified paper.

    Args:
        paper_id: Semantic Scholar paper ID
        max_results: Maximum number of citing papers to return
        api_key: Semantic Scholar API key (falls back to settings if not provided)

    Returns:
        List of citing papers
    """
    logger.info(f"[S2] Fetching citations for paper: {paper_id}")

    fields = "paperId,title,authors,abstract,year,citationCount"

    resolved_api_key = get_setting(api_key, "semantic_scholar_api_key")
    headers = {}
    if resolved_api_key:
        headers["x-api-key"] = resolved_api_key
    else:
        await _unauth_throttle()

    try:
        async with httpx.AsyncClient() as client:
            response = await _get_with_retry(
                client,
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/{paper_id}/citations",
                params={"fields": fields, "limit": max_results},
                headers=headers,
            )
            data = response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"[S2] Failed to get citations: {e}")
        raise

    results = []
    for item in data.get("data", []):
        citing_paper = item.get("citingPaper", {})
        if citing_paper:
            try:
                results.append(_parse_paper(citing_paper))
            except Exception as e:
                logger.warning(f"[S2] Failed to parse citing paper: {e}")
                continue

    return results


async def get_paper_references(
    paper_id: str,
    max_results: int = 10,
    *,
    api_key: Optional[str] = None,
) -> list[SemanticScholarResult]:
    """
    Get papers referenced by the specified paper.

    Args:
        paper_id: Semantic Scholar paper ID
        max_results: Maximum number of referenced papers to return
        api_key: Semantic Scholar API key (falls back to settings if not provided)

    Returns:
        List of referenced papers
    """
    logger.info(f"[S2] Fetching references for paper: {paper_id}")

    fields = "paperId,title,authors,abstract,year,citationCount"

    resolved_api_key = get_setting(api_key, "semantic_scholar_api_key")
    headers = {}
    if resolved_api_key:
        headers["x-api-key"] = resolved_api_key
    else:
        await _unauth_throttle()

    try:
        async with httpx.AsyncClient() as client:
            response = await _get_with_retry(
                client,
                f"{SEMANTIC_SCHOLAR_API_BASE}/paper/{paper_id}/references",
                params={"fields": fields, "limit": max_results},
                headers=headers,
            )
            data = response.json()

    except httpx.HTTPStatusError as e:
        logger.error(f"[S2] Failed to get references: {e}")
        raise

    results = []
    for item in data.get("data", []):
        cited_paper = item.get("citedPaper", {})
        if cited_paper:
            try:
                results.append(_parse_paper(cited_paper))
            except Exception as e:
                logger.warning(f"[S2] Failed to parse referenced paper: {e}")
                continue

    return results


def _parse_paper(paper: dict) -> SemanticScholarResult:
    """Parse a paper response into a structured result."""
    paper_id = paper.get("paperId", "")

    # Parse authors
    authors = []
    for author in paper.get("authors", []):
        name = author.get("name")
        if name:
            authors.append(name)

    # Parse external IDs
    external_ids = paper.get("externalIds", {}) or {}
    doi = external_ids.get("DOI")
    arxiv_id = external_ids.get("ArXiv")

    # Parse open access PDF
    open_access = paper.get("openAccessPdf") or {}
    open_access_pdf = open_access.get("url")

    # Parse TLDR
    tldr_data = paper.get("tldr") or {}
    tldr = tldr_data.get("text")

    return SemanticScholarResult(
        paper_id=paper_id,
        title=paper.get("title", ""),
        authors=authors[:15],  # Limit authors
        abstract=(paper.get("abstract") or "")[:2000],  # Limit length
        year=paper.get("year"),
        citation_count=paper.get("citationCount", 0) or 0,
        influential_citation_count=paper.get(
            "influentialCitationCount", 0) or 0,
        url=f"https://www.semanticscholar.org/paper/{paper_id}",
        venue=paper.get("venue"),
        open_access_pdf=open_access_pdf,
        doi=doi,
        arxiv_id=arxiv_id,
        fields_of_study=paper.get("fieldsOfStudy") or [],
        tldr=tldr,
    )


def is_citation_heavy_query(query: str) -> bool:
    """
    Heuristic to determine if a query would benefit from citation analysis.

    Returns True if the query mentions citations, impact, or influential works.
    """
    citation_keywords = [
        "influential", "highly cited", "impact", "seminal",
        "foundational", "landmark", "breakthrough", "key paper",
        "important work", "citation", "cited", "references",
        "related work", "state of the art", "sota",
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in citation_keywords)
