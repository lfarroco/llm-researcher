"""
Search agent - executes parallel searches for each sub-query.

This agent takes the sub-queries from the planner and searches
multiple sources (web, arxiv, wikipedia) concurrently.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.config import settings
from app.llm_provider import LLMProviderFactory
from app.memory.research_state import (
    Citation,
    ResearchState,
    SourceType,
    SubQueryResult,
)
from app.tools.web_search import web_search
from app.tools.arxiv_search import arxiv_search, is_academic_query
from app.tools.wikipedia import wikipedia_search
from app.agents.query_expander import expand_query

logger = logging.getLogger(__name__)


class RelevanceScore(BaseModel):
    """Relevance assessment for a single citation."""
    is_relevant: bool = Field(
        description="Whether the source is relevant to the query")
    confidence: float = Field(description="Confidence score (0-1)")
    reason: str = Field(
        description="Brief explanation of relevance assessment")


RELEVANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research quality control expert. Your job is to
assess whether a search result is relevant to a research sub-query.

Guidelines:
1. A source is RELEVANT if it directly addresses the sub-query topic
2. A source is IRRELEVANT if it's about a completely different topic,
   even if it shares some keywords
3. Consider the title and snippet content
4. Be strict - when in doubt, mark as irrelevant

Respond with JSON in this exact format:
{{
    "is_relevant": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}"""),
    ("human", """Sub-query: {sub_query}

Source to evaluate:
Title: {title}
Snippet: {snippet}

Is this source relevant to the sub-query?""")
])


async def assess_relevance(
    sub_query: str, citation: Citation
) -> RelevanceScore:
    """
    Use LLM to assess if a citation is relevant to the sub-query.

    Args:
        sub_query: The research question
        citation: Citation to evaluate

    Returns:
        RelevanceScore indicating if citation is relevant
    """
    try:
        provider = LLMProviderFactory.create_provider(
            provider_type=settings.llm_provider,
            model=settings.llm_model,
            temperature=0.1,  # Low temperature for consistent judgments
            api_key=settings.openai_api_key,
            base_url=settings.ollama_base_url,
        )

        llm = provider.get_llm()
        parser = JsonOutputParser(pydantic_object=RelevanceScore)
        chain = RELEVANCE_PROMPT | llm | parser

        result = await chain.ainvoke({
            "sub_query": sub_query,
            "title": citation.title,
            "snippet": citation.snippet[:500]  # Limit snippet size
        })

        return RelevanceScore(**result)
    except Exception as e:
        logger.warning(f"[RELEVANCE] Failed to assess relevance: {e}")
        # On error, assume relevant to avoid false negatives
        return RelevanceScore(
            is_relevant=True, confidence=0.5, reason="Assessment failed"
        )


async def filter_relevant_citations(
    sub_query: str,
    citations: list[Citation],
    threshold: float = 0.5
) -> list[Citation]:
    """
    Filter citations by relevance to the sub-query using LLM assessment.

    Args:
        sub_query: The research question
        citations: List of citations to filter
        threshold: Minimum confidence score to keep (0-1)

    Returns:
        Filtered list of relevant citations
    """
    if not settings.research_enable_relevance_filter:
        logger.info("[RELEVANCE] Filtering disabled, keeping all citations")
        return citations

    if not citations:
        return []

    logger.info(
        f"[RELEVANCE] Assessing relevance of {len(citations)} citations"
    )
    logger.debug(f"[RELEVANCE] Threshold: {threshold}")

    # Assess all citations in parallel
    assessment_tasks = [
        assess_relevance(sub_query, citation) for citation in citations
    ]
    assessments = await asyncio.gather(
        *assessment_tasks, return_exceptions=True
    )

    # Filter based on relevance
    filtered = []
    for citation, assessment in zip(citations, assessments):
        if isinstance(assessment, Exception):
            logger.warning(
                f"[RELEVANCE] Assessment failed for "
                f"'{citation.title}': {assessment}"
            )
            # Keep citation if assessment fails
            filtered.append(citation)
            continue

        if assessment.is_relevant and assessment.confidence >= threshold:
            logger.debug(
                f"[RELEVANCE] ✓ RELEVANT: '{citation.title[:50]}...' "
                f"(conf={assessment.confidence:.2f})"
            )
            filtered.append(citation)
        else:
            logger.info(
                f"[RELEVANCE] ✗ FILTERED: '{citation.title[:50]}...' "
                f"(conf={assessment.confidence:.2f}) - {assessment.reason}"
            )

    logger.info(
        f"[RELEVANCE] Kept {len(filtered)}/{len(citations)} citations "
        f"after filtering"
    )
    return filtered


async def search_for_subquery(
    sub_query: str,
    include_academic: bool = False,
    include_wikipedia: bool = True,
) -> SubQueryResult:
    """
    Search all relevant sources for a single sub-query.

    Generates query variations and searches with each to improve coverage.

    Args:
        sub_query: The question to research
        include_academic: Whether to search ArXiv
        include_wikipedia: Whether to search Wikipedia

    Returns:
        SubQueryResult with citations
    """
    logger.info(
        f"[SEARCH] Starting search for sub-query: '{sub_query[:60]}...'"
    )
    logger.debug(f"[SEARCH] Full sub-query: {sub_query}")
    logger.debug(
        f"[SEARCH] include_academic={include_academic}, "
        f"include_wikipedia={include_wikipedia}"
    )

    # Generate query variations for improved search coverage
    logger.debug("[SEARCH] Generating query variations")
    query_variations = await expand_query(
        sub_query,
        num_variations=settings.research_query_variations
    )
    logger.info(
        f"[SEARCH] Using {len(query_variations)} query variations "
        f"(1 original + {len(query_variations) - 1} expanded)"
    )
    for i, q in enumerate(query_variations):
        logger.debug(f"[SEARCH] Query {i+1}: '{q}'")

    citations = []
    errors = []

    # Search each query variation
    for query_idx, current_query in enumerate(query_variations, 1):
        logger.debug(
            f"[SEARCH] Searching with variation {query_idx}/"
            f"{len(query_variations)}: '{current_query[:50]}...'"
        )

        # Prepare search tasks for this query variation
        tasks = []
        task_types = []

        # Always search web
        logger.debug(
            f"[SEARCH] Adding web search task for variation {query_idx}"
        )
        tasks.append(web_search(current_query, max_results=5))
        task_types.append("web")

        # Conditionally add ArXiv
        if include_academic or is_academic_query(current_query):
            logger.debug(
                f"[SEARCH] Adding ArXiv search task for variation {query_idx} "
                "(academic query detected)"
            )
            tasks.append(arxiv_search(current_query, max_results=3))
            task_types.append("arxiv")

        # Conditionally add Wikipedia
        # (only for first variation to avoid duplicates)
        if include_wikipedia and query_idx == 1:
            logger.debug(
                f"[SEARCH] Adding Wikipedia search task "
                f"for variation {query_idx}"
            )
            tasks.append(wikipedia_search(current_query, sentences=5))
            task_types.append("wikipedia")

        logger.debug(
            f"[SEARCH] Executing {len(tasks)} search tasks for variation "
            f"{query_idx}: {task_types}"
        )

        # Execute all searches for this variation concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(
            f"[SEARCH] All search tasks completed for variation {query_idx}"
        )

        citation_id_base = len(citations) + 1
        for result, source_type in zip(results, task_types):
            if isinstance(result, Exception):
                error_msg = (
                    f"{source_type} search failed for variation {query_idx}: "
                    f"{str(result)}"
                )
                logger.error(f"[SEARCH] {error_msg}", exc_info=result)
                errors.append(error_msg)
                continue

            logger.debug(
                f"[SEARCH] Processing {len(result)} results from "
                f"{source_type} (variation {query_idx})"
            )
            for item in result:
                # Convert to Citation based on source type
                if source_type == "web":
                    citations.append(Citation(
                        id=f"[{citation_id_base}]",
                        url=item.url,
                        title=item.title,
                        snippet=item.snippet,
                        source_type=SourceType.WEB,
                        relevance_score=item.score,
                    ))
                elif source_type == "arxiv":
                    citations.append(Citation(
                        id=f"[{citation_id_base}]",
                        url=item.url,
                        title=item.title,
                        author=", ".join(item.authors[:3]),  # First 3
                        snippet=item.summary[:500],
                        source_type=SourceType.ARXIV,
                        relevance_score=0.8,  # Generally relevant
                    ))
                elif source_type == "wikipedia":
                    citations.append(Citation(
                        id=f"[{citation_id_base}]",
                        url=item.url,
                        title=item.title,
                        snippet=item.summary,
                        source_type=SourceType.WIKIPEDIA,
                        relevance_score=0.7,
                    ))

                citation_id_base += 1

    # Deduplicate citations by URL before filtering
    logger.debug(
        f"[SEARCH] Deduplicating {len(citations)} citations "
        f"from all variations"
    )
    seen_urls = {}
    unique_citations = []
    for citation in citations:
        if citation.url not in seen_urls:
            seen_urls[citation.url] = citation
            unique_citations.append(citation)
        else:
            logger.debug(
                f"[SEARCH] Skipping duplicate URL: {citation.url[:60]}"
            )

    logger.info(
        f"[SEARCH] After deduplication: {len(unique_citations)} unique "
        f"citations (was {len(citations)})"
    )

    logger.info(
        f"[SEARCH] Sub-query search complete: "
        f"{len(unique_citations)} unique citations, {len(errors)} errors"
    )
    if errors:
        logger.warning(f"[SEARCH] Errors encountered: {errors}")

    # Filter citations by relevance to the ORIGINAL sub-query
    if unique_citations:
        logger.debug(
            f"[SEARCH] Filtering citations for relevance to original query: "
            f"'{sub_query[:60]}...'"
        )
        unique_citations = await filter_relevant_citations(
            sub_query,
            unique_citations,
            threshold=settings.research_relevance_threshold
        )
        logger.info(
            f"[SEARCH] After relevance filtering: "
            f"{len(unique_citations)} citations remain"
        )

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
    logger.info(
        f"[SEARCH] Starting parallel search for all "
        f"{len(state.sub_queries)} sub-queries"
    )
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
            logger.error(
                f"[SEARCH] Sub-query {i+1} failed: {result}", exc_info=result)
            errors.append(f"Search failed: {str(result)}")
            sub_query_results.append(SubQueryResult(
                sub_query=state.sub_queries[i],
                status="failed",
                error=str(result),
            ))
        else:
            logger.debug(
                f"[SEARCH] Sub-query {i+1} returned "
                f"{len(result.citations)} citations"
            )
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

    logger.debug(
        f"[SEARCH] After deduplication: "
        f"{len(unique_citations)} unique citations"
    )

    # Limit to max sources
    if len(unique_citations) > settings.research_max_sources:
        logger.debug(
            f"[SEARCH] Limiting to {settings.research_max_sources} "
            f"citations (was {len(unique_citations)})"
        )
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
        "current_step": (
            f"Found {len(unique_citations)} sources. "
            f"Synthesizing findings."
        ),
        "errors": errors,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
