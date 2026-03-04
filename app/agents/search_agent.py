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
    logger.info(
        f"[SEARCH] Starting search for sub-query: '{sub_query[:60]}...'")
    logger.debug(f"[SEARCH] Full sub-query: {sub_query}")
    logger.debug(
        f"[SEARCH] include_academic={include_academic}, include_wikipedia={include_wikipedia}")

    citations = []
    errors = []

    # Prepare search tasks
    tasks = []
    task_types = []

    # Always search web
    logger.debug("[SEARCH] Adding web search task")
    tasks.append(web_search(sub_query, max_results=5))
    task_types.append("web")

    # Conditionally add ArXiv
    if include_academic or is_academic_query(sub_query):
        logger.debug(
            "[SEARCH] Adding ArXiv search task (academic query detected)")
        tasks.append(arxiv_search(sub_query, max_results=3))
        task_types.append("arxiv")

    # Conditionally add Wikipedia
    if include_wikipedia:
        logger.debug("[SEARCH] Adding Wikipedia search task")
        tasks.append(wikipedia_search(sub_query, sentences=5))
        task_types.append("wikipedia")

    logger.info(
        f"[SEARCH] Executing {len(tasks)} search tasks in parallel: {task_types}")

    # Execute all searches concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    logger.debug("[SEARCH] All search tasks completed")

    citation_id = 1
    for result, source_type in zip(results, task_types):
        if isinstance(result, Exception):
            error_msg = f"{source_type} search failed: {str(result)}"
            logger.error(f"[SEARCH] {error_msg}", exc_info=result)
            errors.append(error_msg)
            continue

        logger.debug(
            f"[SEARCH] Processing {len(result)} results from {source_type}")
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

    logger.info(
        f"[SEARCH] Sub-query search complete: {len(citations)} citations, {len(errors)} errors")
    if errors:
        logger.warning(f"[SEARCH] Errors encountered: {errors}")

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
    logger.info("[SEARCH] ========== STARTING SEARCH PHASE ==========")
    logger.info(f"[SEARCH] Research ID: {state.research_id}")
    logger.info(f"[SEARCH] Number of sub-queries: {len(state.sub_queries)}")
    for i, sq in enumerate(state.sub_queries):
        logger.debug(f"[SEARCH] Sub-query {i+1}: {sq}")

    # Check if we should include academic sources
    include_academic = is_academic_query(state.query)
    logger.debug(f"[SEARCH] Include academic sources: {include_academic}")

    # Search all sub-queries in parallel
    logger.info(f"[SEARCH] Starting parallel search for all {len(state.sub_queries)} sub-queries")
    tasks = [
        search_for_subquery(sq, include_academic=include_academic)
        for sq in state.sub_queries
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    logger.debug("[SEARCH] All parallel searches completed")

    # Collect all citations and results
    all_citations = []
    sub_query_results = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"[SEARCH] Sub-query {i+1} failed: {result}", exc_info=result)
            errors.append(f"Search failed: {str(result)}")
            sub_query_results.append(SubQueryResult(
                sub_query=state.sub_queries[i],
                status="failed",
                error=str(result),
            ))
        else:
            logger.debug(f"[SEARCH] Sub-query {i+1} returned {len(result.citations)} citations")
            sub_query_results.append(result)
            all_citations.extend(result.citations)

    logger.info(f"[SEARCH] Total citations collected: {len(all_citations)}")

    # Deduplicate citations by URL and reassign IDs
    logger.debug("[SEARCH] Deduplicating citations by URL")
    seen_urls = set()
    unique_citations = []
    for citation in all_citations:
        if citation.url not in seen_urls:
            seen_urls.add(citation.url)
            citation.id = f"[{len(unique_citations) + 1}]"
            unique_citations.append(citation)
    
    logger.debug(f"[SEARCH] After deduplication: {len(unique_citations)} unique citations")

    # Limit to max sources
    if len(unique_citations) > settings.research_max_sources:
        logger.debug(f"[SEARCH] Limiting to {settings.research_max_sources} citations (was {len(unique_citations)})")
    unique_citations = unique_citations[:settings.research_max_sources]

    logger.info("[SEARCH] ========== SEARCH PHASE COMPLETE ==========")
    logger.info(f"[SEARCH] Final citation count: {len(unique_citations)}")
    logger.info(f"[SEARCH] Errors: {len(errors)}")
    if errors:
        for err in errors:
            logger.warning(f"[SEARCH] Error: {err}")

    return {
        "citations": unique_citations,
        "sub_query_results": sub_query_results,
        "status": "synthesizing",
        "current_step": f"Found {len(unique_citations)} sources. Synthesizing findings.",
        "errors": errors,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
