"""
Elsevier Scopus search tool.

Uses the Elsevier Search API (Scopus index) to search scholarly metadata.
An API key is required.

Docs: https://dev.elsevier.com/sc_search_tips.html
"""

import asyncio
import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.tools.base import get_setting

logger = logging.getLogger(__name__)

ELSEVIER_SCOPUS_API_BASE = "https://api.elsevier.com/content/search/scopus"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


class ElsevierResult(BaseModel):
    """A single Elsevier Scopus search result."""

    eid: str = Field(default="", description="Scopus EID")
    title: str = Field(description="Publication title")
    authors: list[str] = Field(
        default_factory=list, description="Author names"
    )
    abstract: str = Field(default="", description="Abstract text if available")
    publication_name: Optional[str] = Field(
        default=None, description="Journal or source title"
    )
    cover_date: Optional[str] = Field(
        default=None, description="Publication date"
    )
    doi: Optional[str] = Field(default=None, description="DOI if available")
    url: str = Field(description="Result URL")
    citedby_count: int = Field(default=0, description="Citation count")


async def _get_with_retry(
    client: httpx.AsyncClient,
    *,
    params: dict,
    headers: dict,
) -> httpx.Response:
    """Execute an Elsevier API request with retry on transient failures."""
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.get(
                ELSEVIER_SCOPUS_API_BASE,
                params=params,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code in _RETRYABLE_STATUS_CODES
                and attempt < _MAX_RETRIES - 1
            ):
                wait_seconds = 2 ** attempt
                logger.warning(
                    "[Elsevier] HTTP %s on attempt %s/%s; retrying in %ss",
                    exc.response.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
                continue
            raise
        except httpx.TimeoutException as exc:
            if attempt < _MAX_RETRIES - 1:
                logger.warning(
                    "[Elsevier] Timeout on attempt %s/%s; retrying",
                    attempt + 1,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(1)
                continue
            raise RuntimeError("Elsevier request timed out") from exc

    raise RuntimeError("Elsevier request failed after retries")


def _extract_url(entry: dict) -> str:
    """Extract a best-effort URL from an Elsevier entry."""
    direct_url = entry.get("prism:url")
    if isinstance(direct_url, str) and direct_url:
        return direct_url

    for link in entry.get("link", []):
        if not isinstance(link, dict):
            continue
        href = link.get("@href")
        if not isinstance(href, str) or not href:
            continue
        ref = (link.get("@ref") or "").lower()
        if ref in {"scopus", "self", "scopus-citedby"}:
            return href

    return ""


def _extract_authors(entry: dict) -> list[str]:
    """Extract authors from entry fields used by Scopus API."""
    authors: list[str] = []

    for author in entry.get("author", []):
        if not isinstance(author, dict):
            continue
        name = author.get("authname")
        if isinstance(name, str) and name:
            authors.append(name)

    if not authors:
        creator = entry.get("dc:creator")
        if isinstance(creator, str) and creator:
            authors = [creator]

    return authors


async def elsevier_search(
    query: str,
    max_results: int = 5,
    *,
    elsevier_api_key: Optional[str] = None,
) -> list[ElsevierResult]:
    """
    Search Elsevier Scopus metadata by free-text query.

    Args:
        query: Search query string.
        max_results: Maximum number of records to request.
        elsevier_api_key: Explicit API key override. Falls back to settings.

    Returns:
        List of ElsevierResult records.
    """
    logger.info("[Elsevier] Starting search for: '%s...'", query[:80])

    resolved_api_key = get_setting(elsevier_api_key, "elsevier_api_key")
    if not resolved_api_key:
        logger.warning(
            "[Elsevier] Missing elsevier_api_key; returning no results"
        )
        return []

    params = {
        "query": query,
        "count": min(max_results, 25),
        "start": 0,
    }
    headers = {
        "X-ELS-APIKey": resolved_api_key,
        "Accept": "application/json",
        "User-Agent": "LLM-Researcher/1.0",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await _get_with_retry(
                client,
                params=params,
                headers=headers,
            )
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in (401, 403):
            logger.error(
                "[Elsevier] Authentication failed (HTTP %s)",
                status_code,
            )
        else:
            logger.error("[Elsevier] HTTP error: %s", exc)
        return []
    except Exception as exc:
        logger.error("[Elsevier] Search failed: %s", exc)
        return []

    entries = payload.get("search-results", {}).get("entry", [])
    logger.info("[Elsevier] Found %s entries", len(entries))

    results: list[ElsevierResult] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        title = entry.get("dc:title") or "Untitled"
        doi = entry.get("prism:doi")
        abstract = entry.get("dc:description") or ""
        url = _extract_url(entry)
        authors = _extract_authors(entry)

        cited_by_raw = entry.get("citedby-count", 0)
        try:
            cited_by = int(cited_by_raw)
        except (TypeError, ValueError):
            cited_by = 0

        if not url and doi:
            url = f"https://doi.org/{doi}"

        results.append(
            ElsevierResult(
                eid=entry.get("eid", ""),
                title=title,
                authors=authors,
                abstract=abstract,
                publication_name=entry.get("prism:publicationName"),
                cover_date=entry.get("prism:coverDate"),
                doi=doi,
                url=url,
                citedby_count=cited_by,
            )
        )

    return results
