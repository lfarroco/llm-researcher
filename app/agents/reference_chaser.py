"""
Reference chaser agent - follows references from discovered sources.

After the initial search phase finds citations, this agent examines
promising sources, extracts their references, and follows them
recursively up to a configurable depth. This deepens the research
by discovering sources that the original search might have missed.
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
    ResearchState,
    SourceType,
)
from app.tools.reference_extractor import (
    ExtractedReference,
    extract_references_from_url,
    extract_wikipedia_references,
    extract_academic_references,
)
from app.tools.web_scraper import scrape_url

logger = logging.getLogger(__name__)

# Max references to extract per source
MAX_REFS_PER_SOURCE = 15
# Max references to follow per depth level
MAX_CHASE_PER_LEVEL = 10
# Max total new citations from reference chasing
MAX_TOTAL_NEW_CITATIONS = 20
# Max sources to chase references from at each level
MAX_SOURCES_TO_CHASE = 5


class ReferenceRelevance(BaseModel):
    """LLM assessment of whether a reference is worth following."""

    url: str = Field(description="URL of the reference")
    is_relevant: bool = Field(
        description="Whether the reference is relevant to the research"
    )
    reason: str = Field(description="Brief explanation")


class ReferenceBatchRelevance(BaseModel):
    """Batch relevance assessment results."""

    assessments: list[ReferenceRelevance] = Field(
        description="Relevance assessments for each reference"
    )


REFERENCE_RELEVANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research quality expert. Given a research query
and a list of references extracted from a source, assess which references
are likely to contain valuable information for the research.

Guidelines:
1. A reference is RELEVANT if its URL or title suggests it discusses
   the research topic directly or provides important context/evidence
2. Prefer primary sources, academic papers, reputable news, and
   authoritative references
3. Skip references that seem tangential, off-topic, or low-quality
4. When in doubt, include the reference (we can filter later)
5. Select at most {max_refs} most promising references

Respond with JSON in this exact format:
{{
    "assessments": [
        {{
            "url": "https://...",
            "is_relevant": true/false,
            "reason": "brief explanation"
        }}
    ]
}}

Include an entry for EVERY reference provided."""),
    ("human", """Research query: {query}

Source page: {source_url}

References found on this page:
{references}

Which of these references are relevant to the research query?""")
])


async def _assess_reference_relevance(
    query: str,
    source_url: str,
    references: list[ExtractedReference],
    max_refs: int = MAX_CHASE_PER_LEVEL,
) -> list[ExtractedReference]:
    """
    Use LLM to filter extracted references by relevance to the query.

    Args:
        query: The research query
        source_url: URL of the page references came from
        references: List of extracted references
        max_refs: Maximum number of relevant references to return

    Returns:
        Filtered list of relevant references
    """
    if not references:
        return []

    # Format references for the prompt
    ref_text = "\n".join(
        f"- URL: {ref.url}\n  Title: {ref.title or '(no title)'}\n"
        f"  Context: {ref.context[:150] or '(no context)'}"
        for ref in references[:30]  # Limit input size
    )

    try:
        provider = LLMProviderFactory.create_provider(
            provider_type=settings.llm_provider,
            model=settings.llm_model,
            temperature=0.1,
            api_key=settings.llm_api_key,
            base_url=settings.ollama_base_url,
        )

        llm = provider.get_llm()
        parser = JsonOutputParser(pydantic_object=ReferenceBatchRelevance)
        chain = REFERENCE_RELEVANCE_PROMPT | llm | parser

        result = await rate_limited_llm_call(chain, {
            "query": query,
            "source_url": source_url,
            "references": ref_text,
            "max_refs": max_refs,
        })

        # Build URL -> assessment lookup
        relevant_urls = set()
        assessments = result.get("assessments", [])
        for assessment in assessments:
            if assessment.get("is_relevant", False):
                relevant_urls.add(assessment["url"])

        # Filter references
        filtered = [r for r in references if r.url in relevant_urls]

        logger.info(
            f"[REF_CHASE] LLM filtered {len(references)} references "
            f"to {len(filtered)} relevant ones"
        )
        return filtered[:max_refs]

    except Exception as e:
        logger.warning(f"[REF_CHASE] LLM relevance assessment failed: {e}")
        # On failure, return top references by heuristic
        return references[:max_refs]


def _classify_citation_source(citation: Citation) -> str:
    """Classify a citation for appropriate reference extraction method."""
    url_lower = citation.url.lower()

    if citation.source_type == SourceType.WIKIPEDIA:
        return "wikipedia"
    if "wikipedia.org" in url_lower:
        return "wikipedia"
    if citation.source_type == SourceType.ARXIV:
        return "academic"
    if "arxiv.org" in url_lower:
        return "academic"
    if citation.source_type == SourceType.SEMANTIC_SCHOLAR:
        return "academic"
    if "semanticscholar.org" in url_lower:
        return "academic"
    if citation.source_type == SourceType.PUBMED:
        return "academic"
    if "pubmed" in url_lower or "ncbi.nlm.nih.gov" in url_lower:
        return "academic"
    if "doi.org" in url_lower:
        return "academic"

    return "web"


def _extract_paper_id(citation: Citation) -> str | None:
    """Try to extract a Semantic Scholar-compatible paper ID from a citation."""
    url = citation.url.lower()

    # ArXiv ID
    arxiv_match = __import__("re").search(
        r'arxiv\.org/abs/(\d+\.\d+)', url
    )
    if arxiv_match:
        return f"ARXIV:{arxiv_match.group(1)}"

    # DOI
    doi_match = __import__("re").search(
        r'doi\.org/(10\.\d{4,}/[^\s]+)', url
    )
    if doi_match:
        return f"DOI:{doi_match.group(1)}"

    # Semantic Scholar paper ID
    s2_match = __import__("re").search(
        r'semanticscholar\.org/paper/([a-f0-9]+)', url
    )
    if s2_match:
        return s2_match.group(1)

    return None


async def _extract_refs_for_citation(
    citation: Citation,
) -> list[ExtractedReference]:
    """Extract references from a single citation based on its type."""
    source_type = _classify_citation_source(citation)
    logger.debug(
        f"[REF_CHASE] Extracting refs from '{citation.title[:50]}' "
        f"(type={source_type})"
    )

    try:
        if source_type == "wikipedia":
            # Extract Wikipedia page title from URL or citation title
            title = citation.title
            if "wikipedia.org/wiki/" in citation.url:
                # Extract title from URL
                import urllib.parse
                path = urllib.parse.urlparse(citation.url).path
                title = urllib.parse.unquote(
                    path.replace("/wiki/", "")
                ).replace("_", " ")
            return await extract_wikipedia_references(title)

        elif source_type == "academic":
            paper_id = _extract_paper_id(citation)
            if paper_id:
                return await extract_academic_references(
                    paper_id, max_refs=MAX_REFS_PER_SOURCE
                )
            # Fallback: scrape the URL for links
            return await extract_references_from_url(
                citation.url, max_refs=MAX_REFS_PER_SOURCE
            )

        else:
            # Generic web page
            return await extract_references_from_url(
                citation.url, max_refs=MAX_REFS_PER_SOURCE
            )

    except Exception as e:
        logger.warning(
            f"[REF_CHASE] Failed to extract refs from "
            f"'{citation.title[:50]}': {e}"
        )
        return []


async def _scrape_and_create_citation(
    ref: ExtractedReference,
    citation_id: int,
) -> Citation | None:
    """Scrape a reference URL and create a Citation from it."""
    try:
        scraped = await scrape_url(ref.url)
        if not scraped.success or not scraped.content:
            logger.debug(
                f"[REF_CHASE] Could not scrape {ref.url}: "
                f"{scraped.error or 'empty content'}"
            )
            return None

        return Citation(
            id=f"[{citation_id}]",
            url=ref.url,
            title=scraped.title or ref.title or ref.url,
            author=scraped.author,
            snippet=scraped.content[:500],
            source_type=SourceType.WEB,
            relevance_score=0.6,  # References get a moderate baseline score
        )
    except Exception as e:
        logger.debug(f"[REF_CHASE] Failed to scrape {ref.url}: {e}")
        return None


async def chase_references_for_level(
    query: str,
    citations: list[Citation],
    existing_urls: set[str],
    depth: int,
    max_depth: int,
) -> list[Citation]:
    """
    Chase references one level deep from the given citations.

    Args:
        query: The research query for relevance filtering
        citations: Citations to extract references from
        existing_urls: URLs already in the research (to avoid duplicates)
        depth: Current depth level (1-indexed)
        max_depth: Maximum depth to chase

    Returns:
        List of new citations discovered from references
    """
    if depth > max_depth:
        logger.info(f"[REF_CHASE] Reached max depth ({max_depth}), stopping")
        return []

    logger.info(
        f"[REF_CHASE] === Depth {depth}/{max_depth} === "
        f"Chasing references from {len(citations)} citations"
    )

    # Select the most promising citations to chase
    # Prefer higher relevance scores and diverse source types
    sorted_citations = sorted(
        citations, key=lambda c: c.relevance_score, reverse=True
    )
    citations_to_chase = sorted_citations[:MAX_SOURCES_TO_CHASE]

    logger.info(
        f"[REF_CHASE] Selected {len(citations_to_chase)} citations to chase"
    )

    # Extract references from each selected citation in parallel
    extract_tasks = [
        _extract_refs_for_citation(c) for c in citations_to_chase
    ]
    all_ref_lists = await asyncio.gather(
        *extract_tasks, return_exceptions=True
    )

    # Collect all extracted references
    all_refs: list[ExtractedReference] = []
    for citation, ref_list in zip(citations_to_chase, all_ref_lists):
        if isinstance(ref_list, Exception):
            logger.warning(
                f"[REF_CHASE] Failed to extract refs from "
                f"'{citation.title[:40]}': {ref_list}"
            )
            continue
        # Filter out already-known URLs
        new_refs = [r for r in ref_list if r.url not in existing_urls]
        all_refs.extend(new_refs)

    if not all_refs:
        logger.info("[REF_CHASE] No new references found at this depth")
        return []

    # Deduplicate by URL
    seen = set()
    unique_refs = []
    for ref in all_refs:
        if ref.url not in seen:
            seen.add(ref.url)
            unique_refs.append(ref)
    all_refs = unique_refs

    logger.info(
        f"[REF_CHASE] Found {len(all_refs)} unique new references "
        f"at depth {depth}"
    )

    # Use LLM to filter for relevance
    relevant_refs = await _assess_reference_relevance(
        query=query,
        source_url="(multiple sources)",
        references=all_refs,
        max_refs=MAX_CHASE_PER_LEVEL,
    )

    if not relevant_refs:
        logger.info("[REF_CHASE] No relevant references after LLM filtering")
        return []

    logger.info(
        f"[REF_CHASE] {len(relevant_refs)} references passed "
        f"relevance filter at depth {depth}"
    )

    # Scrape each relevant reference to create citations
    citation_id_start = 1000 + (depth * 100)  # Temp IDs, will be reassigned
    scrape_tasks = [
        _scrape_and_create_citation(ref, citation_id_start + i)
        for i, ref in enumerate(relevant_refs)
    ]
    scrape_results = await asyncio.gather(
        *scrape_tasks, return_exceptions=True
    )

    new_citations = []
    for result in scrape_results:
        if isinstance(result, Exception):
            continue
        if result is not None:
            new_citations.append(result)
            existing_urls.add(result.url)

    logger.info(
        f"[REF_CHASE] Created {len(new_citations)} new citations "
        f"at depth {depth}"
    )

    # If we haven't hit max depth and we found new citations,
    # recurse one level deeper
    if depth < max_depth and new_citations:
        deeper_citations = await chase_references_for_level(
            query=query,
            citations=new_citations,
            existing_urls=existing_urls,
            depth=depth + 1,
            max_depth=max_depth,
        )
        new_citations.extend(deeper_citations)

    return new_citations


async def chase_references(state: ResearchState) -> dict[str, Any]:
    """
    Reference chasing node for LangGraph workflow.

    Takes citations from the search phase, extracts references from
    the most promising ones, filters for relevance, and adds new
    citations to the research state.

    Args:
        state: Current research state with citations from search

    Returns:
        State updates with additional citations from reference chasing
    """
    logger.info(
        "[REF_CHASE] ========== STARTING REFERENCE CHASING =========="
    )
    logger.info(f"[REF_CHASE] Research ID: {state.research_id}")
    logger.info(
        f"[REF_CHASE] Existing citations: {len(state.citations)}"
    )

    # Check if reference chasing is enabled
    if not settings.research_reference_chase_enabled:
        logger.info("[REF_CHASE] Reference chasing is disabled, skipping")
        return {
            "agent_steps": [AgentStep(
                step_type="summary",
                title="Reference chasing skipped",
                description="Reference chasing is disabled in settings",
                status="skipped",
            )],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    max_depth = settings.research_reference_chase_depth
    if max_depth < 1:
        logger.info("[REF_CHASE] Chase depth is 0, skipping")
        return {
            "agent_steps": [AgentStep(
                step_type="summary",
                title="Reference chasing skipped",
                description="Chase depth is set to 0",
                status="skipped",
            )],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    if not state.citations:
        logger.info("[REF_CHASE] No citations to chase references from")
        return {
            "agent_steps": [AgentStep(
                step_type="summary",
                title="Reference chasing skipped",
                description="No citations available to chase",
                status="skipped",
            )],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Track existing URLs to avoid duplicates
    existing_urls = {c.url for c in state.citations}

    # Chase references
    steps = [AgentStep(
        step_type="searching",
        title="Chasing references",
        description=(
            f"Following references from {len(state.citations)} sources "
            f"up to depth {max_depth}"
        ),
        status="running",
        metadata={
            "existing_citations": len(state.citations),
            "max_depth": max_depth,
        },
    )]

    try:
        new_citations = await chase_references_for_level(
            query=state.query,
            citations=state.citations,
            existing_urls=existing_urls,
            depth=1,
            max_depth=max_depth,
        )
    except Exception as e:
        logger.error(f"[REF_CHASE] Reference chasing failed: {e}")
        steps.append(AgentStep(
            step_type="error",
            title="Reference chasing failed",
            description=f"Error during reference chasing: {str(e)}",
            status="error",
        ))
        return {
            "agent_steps": steps,
            "errors": [f"Reference chasing failed: {str(e)}"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Limit total new citations
    if len(new_citations) > MAX_TOTAL_NEW_CITATIONS:
        logger.info(
            f"[REF_CHASE] Limiting new citations from "
            f"{len(new_citations)} to {MAX_TOTAL_NEW_CITATIONS}"
        )
        new_citations = new_citations[:MAX_TOTAL_NEW_CITATIONS]

    # Reassign citation IDs to continue sequence
    existing_count = len(state.citations)
    for i, citation in enumerate(new_citations):
        citation.id = f"[{existing_count + i + 1}]"

    logger.info(
        "[REF_CHASE] ========== REFERENCE CHASING COMPLETE =========="
    )
    logger.info(f"[REF_CHASE] New citations found: {len(new_citations)}")

    steps.append(AgentStep(
        step_type="summary",
        title="Reference chasing complete",
        description=(
            f"Discovered {len(new_citations)} additional sources by "
            f"following references up to depth {max_depth}. "
            f"Total citations now: {existing_count + len(new_citations)}"
        ),
        status="completed",
        metadata={
            "new_citations": len(new_citations),
            "total_citations": existing_count + len(new_citations),
            "max_depth": max_depth,
        },
    ))

    return {
        "citations": new_citations,
        "agent_steps": steps,
        "current_step": (
            f"Found {len(new_citations)} additional sources from references. "
            f"Total: {existing_count + len(new_citations)} sources."
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
