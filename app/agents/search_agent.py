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
from app.llm_provider import LLMProviderFactory, rate_limited_llm_call
from app.memory.research_state import (
    AgentStep,
    Citation,
    ResearchNote,
    ResearchState,
    SubQueryResult,
)
from app.tools.arxiv_search import is_academic_query
from app.tools.registry import get_registry
from app.agents.query_expander import expand_query

logger = logging.getLogger(__name__)


class RelevanceScore(BaseModel):
    """Relevance assessment for a single citation."""
    is_relevant: bool = Field(
        description="Whether the source is relevant to the query")
    confidence: float = Field(description="Confidence score (0-1)")
    reason: str = Field(
        description="Brief explanation of relevance assessment")


class CitationRelevance(RelevanceScore):
    """A relevance assessment tagged with the index of the source it judges."""
    index: int = Field(
        description="Index of the source in the numbered list provided")


class RelevanceBatch(BaseModel):
    """Batch relevance assessment for a page of citations."""
    assessments: list[CitationRelevance] = Field(
        description="One assessment per source in the list")


RELEVANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are screening search results for a research
sub-question. Your job is to drop sources that are clearly about a different
topic, and to keep everything that could contribute evidence.

Guidelines:
1. A source is RELEVANT if it could contribute evidence about ANY part of the
   sub-question - not just if it covers every clause of it.
2. Partial matches count. A source about functional programming languages is
   relevant to a question about functional programming languages in web
   development, even if the excerpt never says "web".
3. Titles and excerpts are short and often imperfect. Some excerpts begin with
   navigation or sign-in boilerplate; judge from the title, the URL, and any
   substantive text that is present.
4. Prefer keeping a plausible source over dropping it: a later synthesis step
   ignores material it cannot use, but nothing can recover a source that was
   discarded here.
5. Mark a source IRRELEVANT only when it is clearly about a different subject
   (for example a generic "best programming languages" listicle that never
   mentions the sub-question's topic at all).

Respond with JSON in this exact format:
{{
    "assessments": [
        {{"index": 0, "is_relevant": true, "confidence": 0.0-1.0,
          "reason": "brief explanation"}}
    ]
}}

Include exactly one entry for EVERY numbered source."""),
    ("human", """Sub-query: {sub_query}

Sources to evaluate:
{sources}

Which of these sources could contribute evidence for the sub-query?""")
])


def _format_relevance_candidates(
    citations: list[Citation],
    first_index: int,
) -> str:
    """Render a numbered source list for the batch relevance prompt."""
    blocks = []
    for offset, citation in enumerate(citations):
        snippet = " ".join((citation.snippet or "").split())[:400]
        block = (
            f"[{first_index + offset}] {citation.title}\n"
            f"URL: {citation.url}"
        )
        if snippet:
            block += f"\nExcerpt: {snippet}"
        blocks.append(block)
    return "\n\n".join(blocks)


async def assess_relevance_batch(
    sub_query: str,
    citations: list[Citation],
    first_index: int = 0,
) -> dict[int, RelevanceScore]:
    """Assess a page of citations in a single LLM call.

    Args:
        sub_query: The research question the sources are judged against.
        citations: Sources to assess.
        first_index: Index of the first citation, used to key the results so
            several batches can be merged without ambiguity.

    Returns:
        Mapping of source index to its assessment. Indices the model omitted
        are absent from the mapping; callers keep those sources.
    """
    chain = _build_relevance_chain()
    result = await rate_limited_llm_call(chain, {
        "sub_query": sub_query,
        "sources": _format_relevance_candidates(citations, first_index),
    })

    assessments: dict[int, RelevanceScore] = {}
    for item in (result or {}).get("assessments", []):
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int):
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        assessments[index] = RelevanceScore(
            is_relevant=bool(item.get("is_relevant", False)),
            confidence=confidence,
            reason=str(item.get("reason", "")),
        )
    return assessments


def _build_relevance_chain():
    """Create the retrieval chain used to batch-assess citations."""
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.1,  # Low temperature for consistent judgments
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    llm = provider.get_llm()
    parser = JsonOutputParser(pydantic_object=RelevanceBatch)
    return RELEVANCE_PROMPT | llm | parser


async def filter_relevant_citations(
    sub_query: str,
    citations: list[Citation],
    threshold: float = 0.5
) -> list[Citation]:
    """
    Filter citations by relevance to the sub-query using LLM assessment.

    Citations are assessed in batches (``research_relevance_batch_size`` per
    call) instead of one call each, which keeps the phase to a handful of
    requests. A citation is kept when the model marks it relevant with
    confidence at or above ``threshold``; citations the model skipped, or that
    could not be assessed at all, are kept so a model or parsing failure never
    silently shrinks the evidence base.

    If filtering would remove *every* candidate for a sub-query, the
    highest-scoring few are kept instead (``research_relevance_fallback_keep``)
    so no sub-question is ever left with zero sources.

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

    batch_size = max(1, int(settings.research_relevance_batch_size))
    # (first_index, batch)
    batches = [
        (start, citations[start:start + batch_size])
        for start in range(0, len(citations), batch_size)
    ]
    logger.info(
        f"[RELEVANCE] Assessing {len(citations)} citations in "
        f"{len(batches)} batched call(s) (batch size {batch_size})"
    )

    results = await asyncio.gather(
        *(
            assess_relevance_batch(sub_query, batch, first_index=start)
            for start, batch in batches
        ),
        return_exceptions=True,
    )

    kept: list[Citation] = []
    rejected = 0
    for (start, batch), assessment in zip(batches, results):
        if isinstance(assessment, Exception):
            logger.warning(
                f"[RELEVANCE] Batch at index {start} failed "
                f"({assessment}); keeping its {len(batch)} citations"
            )
            kept.extend(batch)
            continue

        for offset, citation in enumerate(batch):
            judged = assessment.get(start + offset)
            if judged is None:
                # The model skipped this source; keep it rather than lose it.
                logger.debug(
                    f"[RELEVANCE] No assessment for "
                    f"'{citation.title[:50]}'; keeping it"
                )
                kept.append(citation)
                continue
            if judged.is_relevant and judged.confidence >= threshold:
                logger.debug(
                    f"[RELEVANCE] ✓ RELEVANT: '{citation.title[:50]}...' "
                    f"(conf={judged.confidence:.2f})"
                )
                kept.append(citation)
            else:
                rejected += 1
                logger.debug(
                    f"[RELEVANCE] ✗ FILTERED: '{citation.title[:50]}...' "
                    f"(conf={judged.confidence:.2f}) - {judged.reason}"
                )

    fallback_keep = max(0, int(settings.research_relevance_fallback_keep))
    if not kept and citations and fallback_keep > 0:
        ranked = sorted(
            citations,
            key=lambda c: c.relevance_score or 0.0,
            reverse=True,
        )[:fallback_keep]
        logger.warning(
            f"[RELEVANCE] Filtering rejected all {len(citations)} citation(s) "
            f"for '{sub_query[:60]}...'; keeping the top {len(ranked)} by "
            f"search relevance so the sub-question is not left empty"
        )
        return ranked

    logger.info(
        f"[RELEVANCE] Kept {len(kept)}/{len(citations)} citations "
        f"after filtering ({rejected} rejected)"
    )
    return kept


async def search_for_subquery(
    sub_query: str,
    include_academic: bool = False,
) -> SubQueryResult:
    """
    Search all relevant sources for a single sub-query.

    Generates query variations and searches with each to improve coverage.
    Which sources are queried is determined by the global ToolRegistry; add
    or remove plugins there rather than modifying this function.

    Args:
        sub_query: The question to research
        include_academic: Whether to include academic sources (e.g. ArXiv)

    Returns:
        SubQueryResult with citations
    """
    logger.info(
        f"[SEARCH] Starting search for sub-query: '{sub_query[:60]}...'"
    )
    logger.debug(f"[SEARCH] Full sub-query: {sub_query}")
    logger.debug(f"[SEARCH] include_academic={include_academic}")

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

    registry = get_registry()

    # Search each query variation
    for query_idx, current_query in enumerate(query_variations, 1):
        logger.debug(
            f"[SEARCH] Searching with variation {query_idx}/"
            f"{len(query_variations)}: '{current_query[:50]}...'"
        )

        include_academic_for_variation = (
            include_academic or is_academic_query(current_query)
        )
        plugins = registry.get_plugins(
            include_academic=include_academic_for_variation,
            first_variation=(query_idx == 1),
        )
        plugin_names = [p.name for p in plugins]
        logger.debug(
            f"[SEARCH] Plugins for variation {query_idx}: {plugin_names}"
        )

        # Execute all plugin searches concurrently
        tasks = [
            p.search(current_query, max_results=p.default_max_results)
            for p in plugins
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug(
            f"[SEARCH] All search tasks completed for variation {query_idx}"
        )

        for plugin, result in zip(plugins, results):
            if isinstance(result, Exception):
                error_msg = (
                    f"{plugin.name} search failed for variation {query_idx}: "
                    f"{str(result)}"
                )
                logger.error(f"[SEARCH] {error_msg}", exc_info=result)
                errors.append(error_msg)
                continue

            logger.debug(
                f"[SEARCH] {len(result)} results from "
                f"{plugin.name} (variation {query_idx})"
            )
            citations.extend(result)

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
        citations=unique_citations,
        status="complete" if unique_citations else "failed",
        error="; ".join(errors) if errors and not unique_citations else None,
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

    # Check if we should include academic sources. The planner's own decision
    # (state.include_academic) is authoritative when it asked for academic
    # sources; the keyword heuristic is the fallback for states that predate
    # the flag or for callers that build a state by hand.
    include_academic = bool(state.include_academic) or is_academic_query(
        state.query
    )
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

    # Build agent steps for each sub-query search
    steps = []
    for sqr in sub_query_results:
        steps.append(AgentStep(
            step_type="searching",
            title=f"Searched: {sqr.sub_query[:40]}...",
            description=(
                f"Found {len(sqr.citations)} sources for: {sqr.sub_query}"
            ),
            status="completed" if sqr.status == "complete" else "error",
            metadata={
                "sub_query": sqr.sub_query,
                "citations_found": len(sqr.citations),
                "error": sqr.error,
            },
        ))

    steps.append(AgentStep(
        step_type="summary",
        title="Search phase complete",
        description=(
            f"Collected {len(unique_citations)} unique sources "
            f"from {len(state.sub_queries)} sub-queries. "
            f"{len(errors)} errors encountered."
        ),
        status="completed",
        metadata={
            "total_citations": len(unique_citations),
            "total_errors": len(errors),
        },
    ))

    # Write research notes about search outcomes
    notes = [
        ResearchNote(
            agent="search",
            content=(
                f"Search phase collected "
                f"{len(unique_citations)} unique sources "
                f"across {len(state.sub_queries)} sub-queries. "
                f"{len(errors)} errors encountered."
            ),
        ),
    ]
    for sqr in sub_query_results:
        if sqr.status == "failed":
            notes.append(ResearchNote(
                agent="search",
                content=(
                    f"Search failed for: {sqr.sub_query}. "
                    f"Error: {sqr.error}"
                ),
            ))
        elif not sqr.citations:
            notes.append(ResearchNote(
                agent="search",
                content=f"No sources found for: {sqr.sub_query}",
            ))

    return {
        "citations": unique_citations,
        "sub_query_results": sub_query_results,
        "status": "synthesizing",
        "current_step": (
            f"Found {len(unique_citations)} sources. "
            f"Synthesizing findings."
        ),
        "errors": errors,
        "agent_steps": steps,
        "research_notes": notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
