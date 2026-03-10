"""
Hypothesis agent - generates and validates research hypotheses.

This agent implements a "thinking" mechanism where the AI:
1. Analyzes initial findings and ponders aspects of the subject
2. Generates hypotheses about what might be true
3. Searches for content supporting/refuting those hypotheses
4. Appends validated findings to the research state

This creates a deeper, more thorough research process beyond
simple query-based search.
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
    AgentStep,
    Citation,
    ResearchNote,
    ResearchState,
    SourceType,
)
from app.tools.web_search import web_search
from app.tools.arxiv_search import arxiv_search, is_academic_query
from app.agents.search_agent import filter_relevant_citations

logger = logging.getLogger(__name__)


class Hypothesis(BaseModel):
    """A research hypothesis to investigate."""
    statement: str = Field(
        description="The hypothesis statement"
    )
    search_query: str = Field(
        description="A search query to find evidence for/against this hypothesis"
    )
    reasoning: str = Field(
        description="Why this hypothesis is worth investigating"
    )
    aspect: str = Field(
        description="The aspect of the topic this hypothesis addresses"
    )


class HypothesesOutput(BaseModel):
    """Output from the hypothesis generation step."""
    observations: str = Field(
        description="Key observations about gaps or areas to explore"
    )
    hypotheses: list[Hypothesis] = Field(
        description="List of hypotheses to investigate"
    )


HYPOTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a critical research analyst. Given a research query and the initial findings collected so far, your job is to:

1. Analyze what has been found and identify gaps, unexplored angles, or areas that need deeper investigation
2. Generate hypotheses about aspects of the topic that haven't been fully covered
3. Create targeted search queries to find evidence for these hypotheses

Think deeply about:
- What aspects of the topic are missing from the current findings?
- What claims in the findings need verification or deeper evidence?
- What related trends, implications, or consequences haven't been explored?
- Are there contrasting viewpoints or counterarguments that should be investigated?

Generate 2-4 hypotheses, each with a specific search query to find supporting evidence.

Respond with JSON in this exact format:
{{
    "observations": "Brief analysis of gaps and areas to explore",
    "hypotheses": [
        {{
            "statement": "Hypothesis statement",
            "search_query": "Specific search query to find evidence",
            "reasoning": "Why this is worth investigating",
            "aspect": "The topic aspect this addresses"
        }}
    ]
}}"""),
    ("human", """Research Query: {query}

Sub-questions investigated:
{sub_queries}

Sources found so far ({num_sources} total):
{sources_summary}

Generate hypotheses to deepen this research.

{notes_context}""")
])


def get_hypothesis_chain():
    """Create the hypothesis generation chain."""
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.5,  # Higher for creative hypothesis generation
        api_key=settings.llm_api_key,
        base_url=settings.ollama_base_url,
    )
    llm = provider.get_llm()
    parser = JsonOutputParser(pydantic_object=HypothesesOutput)
    return HYPOTHESIS_PROMPT | llm | parser


def format_sources_summary(citations: list[Citation]) -> str:
    """Create a concise summary of existing sources for the prompt."""
    if not citations:
        return "No sources found yet."

    lines = []
    for c in citations[:15]:  # Limit to prevent prompt overflow
        line = f"- [{c.source_type.value}] {c.title}"
        if c.snippet:
            line += f"\n  Excerpt: {c.snippet[:150]}..."
        lines.append(line)

    if len(citations) > 15:
        lines.append(f"... and {len(citations) - 15} more sources")

    return "\n".join(lines)


async def search_for_hypothesis(
    hypothesis: Hypothesis,
    include_academic: bool = False,
    existing_urls: set[str] | None = None,
) -> tuple[Hypothesis, list[Citation]]:
    """
    Search for evidence supporting a hypothesis.

    Args:
        hypothesis: The hypothesis to investigate
        include_academic: Whether to search ArXiv
        existing_urls: URLs already in the citation list (for dedup)

    Returns:
        Tuple of (hypothesis, new_citations)
    """
    logger.info(
        f"[HYPOTHESIS] Searching for: '{hypothesis.search_query[:60]}...'"
    )
    logger.debug(
        f"[HYPOTHESIS] Hypothesis: {hypothesis.statement[:80]}"
    )

    citations = []
    existing_urls = existing_urls or set()

    # Search web
    try:
        web_results = await web_search(
            hypothesis.search_query, max_results=3
        )
        for item in web_results:
            if item.url not in existing_urls:
                citations.append(Citation(
                    id="[0]",  # Will be reassigned later
                    url=item.url,
                    title=item.title,
                    snippet=item.snippet,
                    source_type=SourceType.WEB,
                    relevance_score=item.score,
                ))
    except Exception as e:
        logger.warning(
            f"[HYPOTHESIS] Web search failed for hypothesis: {e}"
        )

    # Search ArXiv if academic
    if include_academic or is_academic_query(hypothesis.search_query):
        try:
            arxiv_results = await arxiv_search(
                hypothesis.search_query, max_results=2
            )
            for item in arxiv_results:
                if item.url not in existing_urls:
                    citations.append(Citation(
                        id="[0]",
                        url=item.url,
                        title=item.title,
                        author=", ".join(item.authors[:3]),
                        snippet=item.summary[:500],
                        source_type=SourceType.ARXIV,
                        relevance_score=0.8,
                    ))
        except Exception as e:
            logger.warning(
                f"[HYPOTHESIS] ArXiv search failed for hypothesis: {e}"
            )

    # Filter by relevance to the hypothesis statement
    if citations:
        citations = await filter_relevant_citations(
            hypothesis.statement,
            citations,
            threshold=settings.research_relevance_threshold
        )

    logger.info(
        f"[HYPOTHESIS] Found {len(citations)} relevant new sources "
        f"for hypothesis: '{hypothesis.statement[:50]}...'"
    )

    return hypothesis, citations


async def generate_hypotheses(state: ResearchState) -> dict[str, Any]:
    """
    Hypothesis generation node for LangGraph workflow.

    Analyzes current findings and generates hypotheses for deeper
    investigation. Searches for evidence and adds new citations.

    Args:
        state: Current research state after initial search

    Returns:
        State updates with new citations and agent steps
    """
    logger.info(
        "[HYPOTHESIS] ========== STARTING HYPOTHESIS PHASE =========="
    )
    logger.info(f"[HYPOTHESIS] Research ID: {state.research_id}")
    logger.info(
        f"[HYPOTHESIS] Current citations: {len(state.citations)}"
    )

    steps = []

    # Record the start of hypothesis thinking
    steps.append(AgentStep(
        step_type="thinking",
        title="Analyzing findings for gaps",
        description=(
            f"Reviewing {len(state.citations)} sources collected so far "
            f"to identify gaps and unexplored angles."
        ),
        status="running",
    ))

    if not state.citations:
        logger.warning(
            "[HYPOTHESIS] No citations to analyze - skipping hypothesis phase"
        )
        steps[-1].status = "skipped"
        steps[-1].description = "No initial sources to analyze."
        return {
            "status": "synthesizing",
            "current_step": "No sources for hypothesis generation. Moving to synthesis.",
            "agent_steps": steps,
        }

    # Generate hypotheses
    chain = get_hypothesis_chain()

    sub_queries_text = "\n".join(f"- {sq}" for sq in state.sub_queries)
    sources_summary = format_sources_summary(state.citations)

    # Build notes context for the hypothesis agent
    notes_context = ""
    if state.research_notes:
        notes_lines = []
        for note in state.research_notes:
            notes_lines.append(
                f"[{note.agent}/{note.category}] {note.content}"
            )
        notes_context = (
            "Research notes from prior stages:\n"
            + "\n".join(notes_lines)
        )

    try:
        result = await chain.ainvoke({
            "query": state.query,
            "sub_queries": sub_queries_text,
            "num_sources": len(state.citations),
            "sources_summary": sources_summary,
            "notes_context": notes_context,
        })
    except Exception as e:
        logger.error(f"[HYPOTHESIS] Failed to generate hypotheses: {e}")
        steps[-1].status = "error"
        steps[-1].description = f"Hypothesis generation failed: {str(e)[:100]}"
        return {
            "status": "synthesizing",
            "current_step": "Hypothesis generation failed. Moving to synthesis.",
            "agent_steps": steps,
        }

    observations = result.get("observations", "")
    hypotheses_data = result.get("hypotheses", [])

    logger.info(
        f"[HYPOTHESIS] Generated {len(hypotheses_data)} hypotheses"
    )
    logger.info(f"[HYPOTHESIS] Observations: {observations[:200]}")

    steps[-1].status = "completed"
    steps[-1].description = observations
    steps[-1].metadata = {
        "hypotheses_count": len(hypotheses_data),
    }

    # Parse hypotheses
    hypotheses = []
    for h in hypotheses_data:
        try:
            hypotheses.append(Hypothesis(**h) if isinstance(h, dict) else h)
        except Exception as e:
            logger.warning(f"[HYPOTHESIS] Failed to parse hypothesis: {e}")

    if not hypotheses:
        logger.warning("[HYPOTHESIS] No valid hypotheses generated")
        return {
            "status": "synthesizing",
            "current_step": "No hypotheses generated. Moving to synthesis.",
            "agent_steps": steps,
        }

    # Collect existing URLs for deduplication
    existing_urls = {c.url for c in state.citations}

    # Record hypothesis investigation steps
    for h in hypotheses:
        steps.append(AgentStep(
            step_type="hypothesis",
            title=f"Investigating: {h.aspect}",
            description=h.statement,
            status="running",
            metadata={
                "search_query": h.search_query,
                "reasoning": h.reasoning,
            },
        ))

    # Search for all hypotheses in parallel
    include_academic = is_academic_query(state.query)
    search_tasks = [
        search_for_hypothesis(h, include_academic, existing_urls)
        for h in hypotheses
    ]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # Process results
    new_citations = []
    for i, result in enumerate(results):
        step_idx = i + 1  # +1 because first step is the analysis step

        if isinstance(result, Exception):
            logger.error(
                f"[HYPOTHESIS] Search failed for hypothesis {i+1}: {result}"
            )
            if step_idx < len(steps):
                steps[step_idx].status = "error"
                steps[step_idx].description += (
                    f" | Search failed: {str(result)[:100]}"
                )
            continue

        hypothesis, citations = result

        if step_idx < len(steps):
            steps[step_idx].status = "completed"
            steps[step_idx].metadata["sources_found"] = len(citations)

        if citations:
            logger.info(
                f"[HYPOTHESIS] Hypothesis '{hypothesis.aspect}' "
                f"validated with {len(citations)} new sources"
            )
            # Update existing_urls to avoid duplicates across hypotheses
            for c in citations:
                if c.url not in existing_urls:
                    existing_urls.add(c.url)
                    new_citations.append(c)
        else:
            logger.info(
                f"[HYPOTHESIS] Hypothesis '{hypothesis.aspect}' "
                f"- no new supporting evidence found"
            )
            if step_idx < len(steps):
                steps[step_idx].description += " | No new evidence found."

    # Reassign citation IDs for the new citations
    next_id = len(state.citations) + 1
    for citation in new_citations:
        citation.id = f"[{next_id}]"
        next_id += 1

    logger.info(
        "[HYPOTHESIS] ========== HYPOTHESIS PHASE COMPLETE =========="
    )
    logger.info(
        f"[HYPOTHESIS] Added {len(new_citations)} new citations "
        f"from hypothesis investigation"
    )

    # Summary step
    steps.append(AgentStep(
        step_type="summary",
        title="Hypothesis investigation complete",
        description=(
            f"Investigated {len(hypotheses)} hypotheses, "
            f"found {len(new_citations)} new relevant sources."
        ),
        status="completed",
        metadata={
            "hypotheses_investigated": len(hypotheses),
            "new_sources_found": len(new_citations),
        },
    ))

    # Write research notes capturing hypothesis insights
    notes = []
    if observations:
        notes.append(ResearchNote(
            agent="hypothesis",
            category="pattern",
            content=f"Hypothesis analysis observations: {observations}",
        ))
    for hyp in hypotheses:
        if new_citations:
            notes.append(ResearchNote(
                agent="hypothesis",
                category="observation",
                content=(
                    f"Investigated hypothesis on '{hyp.aspect}': "
                    f"{hyp.statement}. Reasoning: {hyp.reasoning}"
                ),
            ))
        else:
            notes.append(ResearchNote(
                agent="hypothesis",
                category="gap",
                content=(
                    f"Could not find evidence for hypothesis on "
                    f"'{hyp.aspect}': {hyp.statement}"
                ),
            ))

    return {
        "citations": new_citations,
        "status": "synthesizing",
        "current_step": (
            f"Hypothesis investigation complete. "
            f"Found {len(new_citations)} additional sources. "
            f"Synthesizing all findings."
        ),
        "agent_steps": steps,
        "research_notes": notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
