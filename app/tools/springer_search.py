"""
Springer Nature Metadata API search tool.

Uses the Springer Nature Metadata API to search scholarly articles,
book chapters, and related publication metadata.

Docs: https://dev.springernature.com/
"""

import asyncio
import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.tools.base import get_setting

logger = logging.getLogger(__name__)

SPRINGER_API_BASE = "https://api.springernature.com/meta/v2/json"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


class SpringerResult(BaseModel):
    """A single Springer metadata search result."""

    identifier: str = Field(
        default="", description="Springer record identifier")
    title: str = Field(description="Publication title")
    authors: list[str] = Field(
        default_factory=list, description="Author names")
    abstract: str = Field(default="", description="Abstract text if available")
    publication_name: Optional[str] = Field(
        default=None, description="Journal or book title"
    )
    publication_date: Optional[str] = Field(
        default=None, description="Publication date string"
    )
    doi: Optional[str] = Field(default=None, description="DOI if available")
    url: str = Field(description="Landing page URL")
    keywords: list[str] = Field(default_factory=list, description="Keywords")


async def _get_with_retry(
    client: httpx.AsyncClient,
    *,
    params: dict,
) -> httpx.Response:
    """Execute a Springer API request with retry on transient failures."""
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.get(
                SPRINGER_API_BASE,
                params=params,
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
                    "[Springer] HTTP %s on attempt %s/%s; retrying in %ss",
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
                    "[Springer] Timeout on attempt %s/%s; retrying",
                    attempt + 1,
                    _MAX_RETRIES,
                )
                await asyncio.sleep(1)
                continue
            raise RuntimeError("Springer request timed out") from exc

    raise RuntimeError("Springer request failed after retries")


async def springer_search(
    query: str,
    max_results: int = 5,
    *,
    springer_api_key: Optional[str] = None,
) -> list[SpringerResult]:
    """
    Search Springer Nature metadata by free-text query.

    Args:
        query: Search query string.
        max_results: Maximum number of records to request.
        springer_api_key: Explicit API key override. Falls back to settings.

    Returns:
        List of SpringerResult records.
    """
    logger.info("[Springer] Starting search for: '%s...'", query[:80])

    resolved_api_key = get_setting(springer_api_key, "springer_api_key")
    if not resolved_api_key:
        logger.warning(
            "[Springer] Missing springer_api_key; returning no results")
        return []

    params = {
        "q": query,
        "p": min(max_results, 100),
        "api_key": resolved_api_key,
    }

    headers = {
        "User-Agent": "LLM-Researcher/1.0",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(headers=headers) as client:
            response = await _get_with_retry(client, params=params)
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code in (401, 403):
            logger.error(
                "[Springer] Authentication failed (HTTP %s)", status_code)
        else:
            logger.error("[Springer] HTTP error: %s", exc)
        return []
    except Exception as exc:
        logger.error("[Springer] Search failed: %s", exc)
        return []

    records = payload.get("records", [])
    logger.info("[Springer] Found %s records", len(records))

    parsed_results: list[SpringerResult] = []
    for record in records:
        title = record.get("title") or "Untitled"

        creators = record.get("creators") or []
        authors = []
        for creator in creators:
            if isinstance(creator, dict) and creator.get("creator"):
                authors.append(creator["creator"])

        # The API may return multiple URLs; prefer values that look like HTML pages.
        url = ""
        for url_item in record.get("url") or []:
            if not isinstance(url_item, dict):
                continue
            value = url_item.get("value") or ""
            if value:
                url = value
                if value.startswith("http"):
                    break

        abstract = record.get("abstract") or ""
        doi = record.get("doi")
        if not doi:
            identifier = record.get("identifier", "")
            if isinstance(identifier, str) and identifier.startswith("doi:"):
                doi = identifier.replace("doi:", "", 1)

        keywords = record.get("keyword") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        parsed_results.append(
            SpringerResult(
                identifier=record.get("identifier", ""),
                title=title,
                authors=authors,
                abstract=abstract,
                publication_name=record.get("publicationName"),
                publication_date=record.get("publicationDate"),
                doi=doi,
                url=url or f"https://doi.org/{doi}" if doi else "",
                keywords=keywords if isinstance(keywords, list) else [],
            )
        )

    return parsed_results
