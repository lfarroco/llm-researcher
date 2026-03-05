"""
OpenAlex search tool for open scholarly data.

Uses the OpenAlex API to search for papers, authors, institutions,
and other scholarly entities. OpenAlex is free, open-source, and
does not require an API key.

Documentation: https://docs.openalex.org/
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

OPENALEX_API_BASE = "https://api.openalex.org"


class OpenAlexResult(BaseModel):
    """A single OpenAlex work result."""

    openalex_id: str = Field(description="OpenAlex work ID")
    title: str = Field(description="Work title")
    authors: list[str] = Field(
        default_factory=list, description="List of author names"
    )
    abstract: Optional[str] = Field(
        default=None, description="Abstract if available (inverted index)"
    )
    year: Optional[int] = Field(
        default=None, description="Publication year"
    )
    doi: Optional[str] = Field(
        default=None, description="DOI if available"
    )
    url: str = Field(description="OpenAlex landing page URL")
    pdf_url: Optional[str] = Field(
        default=None, description="Best open access PDF URL"
    )
    venue: Optional[str] = Field(
        default=None, description="Publication venue"
    )
    type: str = Field(
        default="unknown", description="Work type"
    )
    cited_by_count: int = Field(
        default=0, description="Citation count"
    )
    is_open_access: bool = Field(
        default=False, description="Whether work is open access"
    )
    topics: list[str] = Field(
        default_factory=list, description="Associated topics"
    )
    concepts: list[str] = Field(
        default_factory=list, description="Associated concepts"
    )


async def openalex_search(
    query: str,
    max_results: int = 5,
    from_year: Optional[int] = None,
    until_year: Optional[int] = None,
    open_access_only: bool = False,
    work_type: Optional[str] = None,
) -> list[OpenAlexResult]:
    """
    Search OpenAlex for scholarly works.

    Args:
        query: Search query (title, abstract, full text)
        max_results: Maximum number of results (max 200)
        from_year: Filter works from this year onwards
        until_year: Filter works until this year
        open_access_only: Only return open access works
        work_type: Filter by type (e.g., "article", "book-chapter")

    Returns:
        List of OpenAlexResult objects
    """
    logger.info(f"[OpenAlex] Starting search for: '{query[:80]}...'")
    logger.debug(
        f"[OpenAlex] Parameters: max_results={max_results}, "
        f"years={from_year}-{until_year}, open_access={open_access_only}"
    )

    # Build API request
    url = f"{OPENALEX_API_BASE}/works"

    params = {
        "search": query,
        "per_page": min(max_results, 200),  # API max is 200
        "page": 1,
    }

    # Build filter string
    filters = []
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    if until_year:
        filters.append(f"to_publication_date:{until_year}-12-31")
    if open_access_only:
        filters.append("is_oa:true")
    if work_type:
        filters.append(f"type:{work_type}")

    if filters:
        params["filter"] = ",".join(filters)

    # Add email for polite pool (faster response)
    params["mailto"] = "research@example.com"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results_list = data.get("results", [])
        logger.info(f"[OpenAlex] Found {len(results_list)} results")

        results = []
        for item in results_list:
            # Extract title
            title = item.get("title", "Untitled")

            # Extract authors
            authors = []
            for authorship in item.get("authorships", []):
                author_data = authorship.get("author", {})
                name = author_data.get("display_name")
                if name:
                    authors.append(name)

            # Extract abstract (OpenAlex uses inverted index)
            abstract = None
            abstract_index = item.get("abstract_inverted_index")
            if abstract_index:
                # Reconstruct abstract from inverted index
                # (simplified - just get first 500 chars worth of words)
                words = []
                for word, positions in list(abstract_index.items())[:100]:
                    words.append(word)
                abstract = " ".join(words)

            # Extract year
            year = item.get("publication_year")

            # Extract DOI
            doi = item.get("doi")
            if doi:
                doi = doi.replace("https://doi.org/", "")

            # Extract best OA location
            pdf_url = None
            oa_location = item.get("best_oa_location")
            if oa_location:
                pdf_url = oa_location.get("pdf_url")

            # Extract venue
            venue = None
            primary_location = item.get("primary_location", {})
            if primary_location:
                source = primary_location.get("source", {})
                venue = source.get("display_name")

            # Extract topics (new OpenAlex feature)
            topics = []
            for topic in item.get("topics", [])[:3]:
                topics.append(topic.get("display_name", ""))

            # Extract concepts (legacy feature)
            concepts = []
            for concept in item.get("concepts", [])[:5]:
                concepts.append(concept.get("display_name", ""))

            result = OpenAlexResult(
                openalex_id=item.get("id", ""),
                title=title,
                authors=authors,
                abstract=abstract,
                year=year,
                doi=doi,
                url=item.get("id", ""),  # OpenAlex ID is the canonical URL
                pdf_url=pdf_url,
                venue=venue,
                type=item.get("type", "unknown"),
                cited_by_count=item.get("cited_by_count", 0),
                is_open_access=item.get("is_oa", False),
                topics=topics,
                concepts=concepts,
            )
            results.append(result)

        return results

    except httpx.HTTPError as e:
        logger.error(f"[OpenAlex] HTTP error: {e}")
        return []
    except Exception as e:
        logger.error(f"[OpenAlex] Unexpected error: {e}")
        return []


async def openalex_lookup_doi(doi: str) -> Optional[OpenAlexResult]:
    """
    Look up a specific work by DOI using OpenAlex.

    Args:
        doi: Digital Object Identifier (e.g., "10.1000/xyz123")

    Returns:
        OpenAlexResult if found, None otherwise
    """
    logger.info(f"[OpenAlex] Looking up DOI: {doi}")

    # Clean DOI
    clean_doi = doi.replace("https://doi.org/", "").replace(
        "http://doi.org/", ""
    )

    url = f"{OPENALEX_API_BASE}/works/doi:{clean_doi}"

    params = {"mailto": "research@example.com"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            item = response.json()

        # Extract data (same logic as search)
        title = item.get("title", "Untitled")

        authors = []
        for authorship in item.get("authorships", []):
            author_data = authorship.get("author", {})
            name = author_data.get("display_name")
            if name:
                authors.append(name)

        abstract = None
        abstract_index = item.get("abstract_inverted_index")
        if abstract_index:
            words = []
            for word in list(abstract_index.keys())[:100]:
                words.append(word)
            abstract = " ".join(words)

        year = item.get("publication_year")

        doi = item.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "")

        pdf_url = None
        oa_location = item.get("best_oa_location")
        if oa_location:
            pdf_url = oa_location.get("pdf_url")

        venue = None
        primary_location = item.get("primary_location", {})
        if primary_location:
            source = primary_location.get("source", {})
            venue = source.get("display_name")

        topics = []
        for topic in item.get("topics", [])[:3]:
            topics.append(topic.get("display_name", ""))

        concepts = []
        for concept in item.get("concepts", [])[:5]:
            concepts.append(concept.get("display_name", ""))

        result = OpenAlexResult(
            openalex_id=item.get("id", ""),
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            doi=doi,
            url=item.get("id", ""),
            pdf_url=pdf_url,
            venue=venue,
            type=item.get("type", "unknown"),
            cited_by_count=item.get("cited_by_count", 0),
            is_open_access=item.get("is_oa", False),
            topics=topics,
            concepts=concepts,
        )

        logger.info(f"[OpenAlex] Successfully retrieved DOI: {doi}")
        return result

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"[OpenAlex] DOI not found: {doi}")
        else:
            logger.error(f"[OpenAlex] HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"[OpenAlex] Unexpected error: {e}")
        return None


# Test function
async def test_openalex():
    """Test function for manual verification."""
    print("Testing OpenAlex search...")

    # Test search
    results = await openalex_search(
        "machine learning neural networks",
        max_results=3,
        from_year=2020,
        open_access_only=True
    )

    print(f"\nFound {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.title}")
        print(f"   Authors: {', '.join(result.authors[:3])}")
        print(f"   Year: {result.year}")
        print(f"   DOI: {result.doi}")
        print(f"   Citations: {result.cited_by_count}")
        print(f"   Open Access: {result.is_open_access}")
        if result.pdf_url:
            print(f"   PDF: {result.pdf_url}")

    # Test DOI lookup
    if results and results[0].doi:
        print(f"\n\nTesting DOI lookup for: {results[0].doi}")
        result = await openalex_lookup_doi(results[0].doi)
        if result:
            print(f"Title: {result.title}")
            print(f"Venue: {result.venue}")
            print(f"Topics: {', '.join(result.topics)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_openalex())
