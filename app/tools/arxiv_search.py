"""
ArXiv search tool for academic papers.

Useful for research queries that benefit from scientific/academic sources.
"""

import logging

import arxiv
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ArxivResult(BaseModel):
    """A single ArXiv paper result."""

    title: str = Field(description="Paper title")
    authors: list[str] = Field(description="List of author names")
    summary: str = Field(description="Paper abstract/summary")
    url: str = Field(description="ArXiv URL")
    pdf_url: str = Field(description="Direct PDF URL")
    published: str = Field(description="Publication date")
    categories: list[str] = Field(
        default_factory=list, description="ArXiv categories")


async def arxiv_search(
    query: str,
    max_results: int = 5,
    sort_by: str = "relevance",
) -> list[ArxivResult]:
    """
    Search ArXiv for academic papers.

    Args:
        query: Search query (supports ArXiv query syntax)
        max_results: Maximum number of results
        sort_by: Sort order - "relevance", "lastUpdatedDate", or "submittedDate"

    Returns:
        List of ArxivResult objects
    """
    logger.info(f"[ARXIV] Starting search for: '{query[:80]}...'")
    logger.debug(
        f"[ARXIV] Parameters: max_results={max_results}, sort_by={sort_by}")

    # Map sort options
    sort_criterion = {
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
        "submittedDate": arxiv.SortCriterion.SubmittedDate,
    }.get(sort_by, arxiv.SortCriterion.Relevance)

    logger.debug("[ARXIV] Initializing arxiv client and search")
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=sort_criterion,
    )

    results = []
    logger.debug("[ARXIV] Fetching results from ArXiv API")
    for i, paper in enumerate(client.results(search)):
        logger.debug(f"[ARXIV] Result {i+1}: title='{paper.title[:50]}', "
                     f"authors={len(paper.authors)}, categories={paper.categories}")
        results.append(ArxivResult(
            title=paper.title,
            authors=[author.name for author in paper.authors],
            summary=paper.summary[:1500],  # Limit summary length
            url=paper.entry_id,
            pdf_url=paper.pdf_url or "",
            published=paper.published.isoformat() if paper.published else "",
            categories=paper.categories,
        ))

    logger.info(
        f"[ARXIV] Search complete, returning {len(results)} results")
    return results


def is_academic_query(query: str) -> bool:
    """
    Heuristic to determine if a query would benefit from academic sources.

    Returns True if the query contains academic-related keywords.
    """
    academic_keywords = [
        "research", "study", "paper", "journal", "theory",
        "hypothesis", "experiment", "analysis", "scientific",
        "algorithm", "method", "approach", "framework",
        "model", "dataset", "benchmark", "evaluation",
        "literature", "review", "survey", "meta-analysis",
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in academic_keywords)
