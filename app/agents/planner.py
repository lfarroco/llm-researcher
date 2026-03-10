"""
Planner agent - decomposes research queries into sub-questions.

This is the first step in the research workflow. It analyzes the user's
query and breaks it down into specific, searchable sub-questions.
"""

import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.config import settings
from app.llm_provider import LLMProviderFactory, rate_limited_llm_call
from app.memory.research_state import AgentStep, ResearchNote, ResearchState

logger = logging.getLogger(__name__)


class PlannerOutput(BaseModel):
    """Output schema for the planner."""

    sub_queries: list[str] = Field(
        description="List of specific sub-questions to research"
    )
    search_strategy: str = Field(
        description="Brief description of research approach"
    )
    include_academic: bool = Field(
        default=False,
        description="Whether to include academic sources (ArXiv)"
    )


PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a research planning expert. Your job is to break down a complex research query into specific, searchable sub-questions.

Guidelines:
1. Create 3-5 focused sub-questions that together will comprehensively answer the main query
2. Each sub-question should be specific and searchable
3. Consider different aspects: background, current state, key players, trends, challenges
4. If the topic is technical/scientific, set include_academic to true
5. Order sub-questions logically (background first, then specifics)

Respond with JSON in this exact format:
{{
    "sub_queries": ["question 1", "question 2", ...],
    "search_strategy": "brief description of approach",
    "include_academic": true/false
}}"""),
    ("human", "Research query: {query}")
])


def get_planner_chain():
    """Create the planner chain."""
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.3,  # Slightly higher for creative decomposition
        api_key=settings.llm_api_key,
        base_url=settings.ollama_base_url,
    )

    llm = provider.get_llm()
    parser = JsonOutputParser(pydantic_object=PlannerOutput)

    return PLANNER_PROMPT | llm | parser


async def plan_research(state: ResearchState) -> dict[str, Any]:
    """
    Planner node for LangGraph workflow.

    Takes the initial query and produces sub-questions for parallel research.

    Args:
        state: Current research state

    Returns:
        State updates with sub_queries and status
    """
    logger.info("[PLANNER] ========== STARTING PLANNING PHASE ==========")
    logger.info(f"[PLANNER] Research ID: {state.research_id}")
    logger.info(f"[PLANNER] Query: '{state.query[:100]}...'")
    logger.debug(f"[PLANNER] Full query: {state.query}")
    logger.debug(
        f"[PLANNER] Using LLM provider: {settings.llm_provider}, model: {settings.llm_model}")

    logger.debug("[PLANNER] Creating planner chain")
    chain = get_planner_chain()

    logger.debug("[PLANNER] Invoking LLM for query decomposition")
    result = await rate_limited_llm_call(chain, {"query": state.query})
    logger.debug(f"[PLANNER] LLM response received: {result}")

    sub_queries = result.get("sub_queries", [])
    search_strategy = result.get("search_strategy", "Not specified")
    include_academic = result.get("include_academic", False)

    logger.debug(f"[PLANNER] Parsed sub_queries: {sub_queries}")
    logger.debug(f"[PLANNER] Search strategy: {search_strategy}")
    logger.debug(f"[PLANNER] Include academic sources: {include_academic}")

    # Ensure we have at least some sub-queries
    if not sub_queries:
        logger.warning(
            "[PLANNER] No sub-queries generated, falling back to original query")
        sub_queries = [state.query]  # Fallback to original query

    logger.info(
        f"[PLANNER] Successfully generated {len(sub_queries)} sub-queries")
    for i, sq in enumerate(sub_queries):
        logger.info(f"[PLANNER]   {i+1}. {sq}")

    # Build agent step for transparency
    step = AgentStep(
        step_type="planning",
        title="Research plan created",
        description=(
            f"Decomposed query into {len(sub_queries)} sub-questions. "
            f"Strategy: {search_strategy}"
        ),
        status="completed",
        metadata={
            "sub_queries": sub_queries,
            "search_strategy": search_strategy,
            "include_academic": include_academic,
        },
    )

    # Write research notes capturing the plan and strategy
    notes = [
        ResearchNote(
            agent="planner",
            category="instruction",
            content=(
                f"Research strategy: {search_strategy}. "
                f"Decomposed into {len(sub_queries)} sub-questions. "
                f"Academic sources: {'yes' if include_academic else 'no'}."
            ),
        ),
    ]
    for sq in sub_queries:
        notes.append(ResearchNote(
            agent="planner",
            category="instruction",
            content=f"Investigate: {sq}",
        ))

    return {
        "sub_queries": sub_queries,
        "status": "searching",
        "current_step": f"Planning complete. Searching {len(sub_queries)} sub-topics.",
        "agent_steps": [step],
        "research_notes": notes,
    }
