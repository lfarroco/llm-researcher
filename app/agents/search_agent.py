"""
Search agent - executes parallel searches for each sub-query.

This agent takes the sub-queries from the planner and searches
multiple sources (web, arxiv, wikipedia) concurrently.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.memory.research_state import (
    Citation,
    ResearchState,
    SourceType,
    SubQueryResult,
)
from app.tools.web_search import web_search
from app.tools.arxiv_search import arxiv_search, is_academic_query
from app.tools.wikipedia import wikipedia_search

logger = logging.getLogger(__name__)


async def search_for_subquery(
    sub_query: str,
    include_academic: bool = False,
    include_wikipedia: bool = True,
) -> SubQueryResult:
    """
    Search all relevant sources for a single sub-query.

    Args:
        sub_query: The question to research
        include_academic: Whether to search ArXiv
        include_wikipedia: Whether to search Wikipedia

    Returns:
        SubQueryResult with citations
    """
    logger.debug(f"Searching for: {sub_query}")

    citations = []
    errors = []

    # Prepare search tasks
    tasks = []
    task_types = []

    # Always search web
    tasks.append(web_search(sub_query, max_results=5))
    task_types.append("web")

    # Conditionally add ArXiv
    if include_academic or is_academic_query(sub_query):
        tasks.append(arxiv_search(sub_query, max_results=3))
        task_types.append("arxiv")

    # Conditionally add Wikipedia
    if include_wikipedia:
        tasks.append(wikipedia_search(sub_query, sentences=5))
        task_types.append("wikipedia")

    # Execute all searches concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    citation_id = 1
    for result, source_type in zip(results, task_types):
        if isinstance(result, Exception):
            errors.append(f"{source_type} search failed: {str(result)}")
            continue

        for item in result:
            # Convert to Citation based on source type
            if source_type == "web":
                citations.append(Citation(
                    id=f"[{citation_id}]",
                    url=item.url,
                    title=item.title,
                    snippet=item.snippet,
                    source_type=SourceType.WEB,
                    relevance_score=item.score,
                ))
            elif source_type == "arxiv":
                citations.append(Citation(
                    id=f"[{citation_id}]",
                    url=item.url,
                    title=item.title,
                    author=", ".join(item.authors[:3]),  # First 3 authors
                    snippet=item.summary[:500],
                    source_type=SourceType.ARXIV,
                    relevance_score=0.8,  # ArXiv results are generally relevant
                ))
            elif source_type == "wikipedia":
                citations.append(Citation(
                    id=f"[{citation_id}]",
                    url=item.url,
                    title=item.title,
                    snippet=item.summary,
                    source_type=SourceType.WIKIPEDIA,
                    relevance_score=0.7,
                ))

            citation_id += 1

    return SubQueryResult(
        sub_query=sub_query,
        citations=citations,
        status="complete" if citations else "failed",
        error="; ".join(errors) if errors and not citations else None,
    )


async def execute_searches(state: ResearchState) -> dict[str, Any]:
    """
    Search node for LangGraph workflow.

    Executes parallel searches for all sub-queries.

    Args:
        state: Current research state with sub_queries populated

    Returns:
        State updates with citations and sub_query_results
    """
    logger.info(f"Executing searches for {len(state.sub_queries)} sub-queries")

    # Check if we should include academic sources
    include_academic = is_academic_query(state.query)

    # Search all sub-queries in parallel
    tasks = [
        search_for_subquery(sq, include_academic=include_academic)
        for sq in state.sub_queries
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect all citations and results
    all_citations = []
    sub_query_results = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Search failed for sub-query {i}: {result}")
            errors.append(f"Search failed: {str(result)}")
            sub_query_results.append(SubQueryResult(
                sub_query=state.sub_queries[i],
                status="failed",
                error=str(result),
            ))
        else:
            sub_query_results.append(result)
            all_citations.extend(result.citations)

    # Deduplicate citations by URL and reassign IDs
    seen_urls = set()
    unique_citations = []
    for citation in all_citations:
        if citation.url not in seen_urls:
            seen_urls.add(citation.url)
            citation.id = f"[{len(unique_citations) + 1}]"
            unique_citations.append(citation)

    # Limit to max sources
    unique_citations = unique_citations[:settings.research_max_sources]

    logger.info(f"Collected {len(unique_citations)} unique citations")

    return {
        "citations": unique_citations,
        "sub_query_results": sub_query_results,
        "status": "synthesizing",
        "current_step": f"Found {len(unique_citations)} sources. Synthesizing findings.",
        "errors": errors,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
