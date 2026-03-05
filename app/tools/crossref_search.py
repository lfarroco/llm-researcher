"""
Crossref search tool for DOI and metadata lookup.

Uses the Crossref API to search for academic papers, books, and other
scholarly content via DOI or metadata search. Crossref is free and
does not require an API key.

Documentation: https://api.crossref.org
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org"


class CrossrefResult(BaseModel):
    """A single Crossref result."""

    doi: str = Field(description="Digital Object Identifier (DOI)")
    title: str = Field(description="Work title")
    authors: list[str] = Field(
        default_factory=list, description="List of author names"
    )
    abstract: Optional[str] = Field(
        default=None, description="Abstract if available"
    )
    year: Optional[int] = Field(
        default=None, description="Publication year"
    )
    publisher: Optional[str] = Field(
        default=None, description="Publisher name"
    )
    container_title: Optional[str] = Field(
        default=None, description="Journal/book title"
    )
    url: str = Field(description="DOI URL")
    type: str = Field(
        default="unknown", description="Work type (e.g., journal-article)"
    )
    issue: Optional[str] = Field(
        default=None, description="Issue number"
    )
    volume: Optional[str] = Field(
        default=None, description="Volume number"
    )
    page: Optional[str] = Field(
        default=None, description="Page range"
    )
    issn: Optional[list[str]] = Field(
        default=None, description="ISSN identifiers"
    )
    isbn: Optional[list[str]] = Field(
        default=None, description="ISBN identifiers"
    )
    reference_count: int = Field(
        default=0, description="Number of references"
    )
    is_referenced_by_count: int = Field(
        default=0, description="Citation count"
    )


async def crossref_search(
    query: str,
    max_results: int = 5,
    work_type: Optional[str] = None,
    from_year: Optional[int] = None,
    until_year: Optional[int] = None,
) -> list[CrossrefResult]:
    """
    Search Crossref for scholarly works.

    Args:
        query: Search query (title, author, keywords)
        max_results: Maximum number of results (max 100)
        work_type: Filter by type (e.g., "journal-article", "book-chapter")
        from_year: Filter works from this year onwards
        until_year: Filter works until this year

    Returns:
        List of CrossrefResult objects
    """
    logger.info(f"[Crossref] Starting search for: '{query[:80]}...'")
    logger.debug(
        f"[Crossref] Parameters: max_results={max_results}, "
        f"type={work_type}, years={from_year}-{until_year}"
    )

    # Build API request
    url = f"{CROSSREF_API_BASE}/works"

    params = {
        "query": query,
        "rows": min(max_results, 100),  # API max is 100
        "select": (
            "DOI,title,author,abstract,published,publisher,"
            "container-title,type,issue,volume,page,ISSN,ISBN,"
            "reference-count,is-referenced-by-count"
        ),
    }

    # Add filters
    filters = []
    if work_type:
        filters.append(f"type:{work_type}")
    if from_year:
        filters.append(f"from-pub-date:{from_year}")
    if until_year:
        filters.append(f"until-pub-date:{until_year}")

    if filters:
        params["filter"] = ",".join(filters)

    headers = {
        "User-Agent": "LLM-Researcher/1.0 (mailto:research@example.com)"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        items = data.get("message", {}).get("items", [])
        logger.info(f"[Crossref] Found {len(items)} results")

        results = []
        for item in items:
            # Extract title (Crossref returns list of titles)
            title_list = item.get("title", [])
            title = title_list[0] if title_list else "Untitled"

            # Extract authors
            authors = []
            for author in item.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                if given and family:
                    authors.append(f"{given} {family}")
                elif family:
                    authors.append(family)

            # Extract year
            year = None
            published = item.get("published", {})
            if "date-parts" in published and published["date-parts"]:
                date_parts = published["date-parts"][0]
                if date_parts:
                    year = date_parts[0]

            # Extract container title (journal/book)
            container_list = item.get("container-title", [])
            container = container_list[0] if container_list else None

            # Build DOI URL
            doi = item.get("DOI", "")
            url = f"https://doi.org/{doi}" if doi else ""

            result = CrossrefResult(
                doi=doi,
                title=title,
                authors=authors,
                abstract=item.get("abstract"),
                year=year,
                publisher=item.get("publisher"),
                container_title=container,
                url=url,
                type=item.get("type", "unknown"),
                issue=item.get("issue"),
                volume=item.get("volume"),
                page=item.get("page"),
                issn=item.get("ISSN"),
                isbn=item.get("ISBN"),
                reference_count=item.get("reference-count", 0),
                is_referenced_by_count=item.get(
                    "is-referenced-by-count", 0
                ),
            )
            results.append(result)

        return results

    except httpx.HTTPError as e:
        logger.error(f"[Crossref] HTTP error: {e}")
        return []
    except Exception as e:
        logger.error(f"[Crossref] Unexpected error: {e}")
        return []


async def crossref_lookup_doi(doi: str) -> Optional[CrossrefResult]:
    """
    Look up a specific work by DOI.

    Args:
        doi: Digital Object Identifier (e.g., "10.1000/xyz123")

    Returns:
        CrossrefResult if found, None otherwise
    """
    logger.info(f"[Crossref] Looking up DOI: {doi}")

    # Clean DOI (remove https://doi.org/ prefix if present)
    clean_doi = doi.replace(
        "https://doi.org/", "").replace("http://doi.org/", "")

    url = f"{CROSSREF_API_BASE}/works/{clean_doi}"

    headers = {
        "User-Agent": "LLM-Researcher/1.0 (mailto:research@example.com)"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        item = data.get("message", {})

        # Extract data (same logic as search)
        title_list = item.get("title", [])
        title = title_list[0] if title_list else "Untitled"

        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)

        year = None
        published = item.get("published", {})
        if "date-parts" in published and published["date-parts"]:
            date_parts = published["date-parts"][0]
            if date_parts:
                year = date_parts[0]

        container_list = item.get("container-title", [])
        container = container_list[0] if container_list else None

        result = CrossrefResult(
            doi=item.get("DOI", doi),
            title=title,
            authors=authors,
            abstract=item.get("abstract"),
            year=year,
            publisher=item.get("publisher"),
            container_title=container,
            url=f"https://doi.org/{clean_doi}",
            type=item.get("type", "unknown"),
            issue=item.get("issue"),
            volume=item.get("volume"),
            page=item.get("page"),
            issn=item.get("ISSN"),
            isbn=item.get("ISBN"),
            reference_count=item.get("reference-count", 0),
            is_referenced_by_count=item.get("is-referenced-by-count", 0),
        )

        logger.info(f"[Crossref] Successfully retrieved DOI: {doi}")
        return result

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"[Crossref] DOI not found: {doi}")
        else:
            logger.error(f"[Crossref] HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"[Crossref] Unexpected error: {e}")
        return None


# Test function
async def test_crossref():
    """Test function for manual verification."""
    print("Testing Crossref search...")

    # Test search
    results = await crossref_search(
        "machine learning transformers",
        max_results=3,
        work_type="journal-article",
        from_year=2020
    )

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.title}")
        print(f"   Authors: {', '.join(result.authors[:3])}")
        print(f"   Year: {result.year}")
        print(f"   DOI: {result.doi}")
        print(f"   Citations: {result.is_referenced_by_count}")

    # Test DOI lookup
    if results:
        print(f"\n\nTesting DOI lookup for: {results[0].doi}")
        result = await crossref_lookup_doi(results[0].doi)
        if result:
            print(f"Title: {result.title}")
            print(f"Container: {result.container_title}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_crossref())
