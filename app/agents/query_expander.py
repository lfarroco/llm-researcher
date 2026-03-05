"""
Query expander - generates variations of search queries.

This module creates alternative phrasings, synonyms, and related terms
for search queries to improve search coverage and find more relevant sources.
"""

import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.config import settings
from app.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)


class QueryVariations(BaseModel):
    """Output schema for query variations."""

    variations: list[str] = Field(
        description="List of alternative query phrasings"
    )
    reasoning: str = Field(
        description="Brief explanation of variation strategy"
    )


QUERY_EXPANSION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a search query optimization expert. 
Your job is to generate alternative phrasings of a search query 
to maximize search coverage.

Guidelines:
1. Generate 2-3 variations of the original query
2. Use synonyms, related terms, and alternative phrasings
3. Keep variations focused on the same topic (don't drift)
4. Consider formal vs informal language
5. Include commonly used abbreviations or expansions
6. Keep each variation concise (5-15 words)
7. Make variations meaningfully different from each other

Examples:
Query: "What are the health benefits of meditation?"
Variations:
- "meditation positive effects wellbeing health"
- "mindfulness practice health advantages benefits"
- "how does meditation improve physical mental health"

Query: "machine learning model interpretability techniques"
Variations:
- "explaining ML model predictions interpretability"
- "explainable AI XAI methods techniques"
- "neural network transparency interpretability"

Respond with JSON in this exact format:
{{
    "variations": ["variation 1", "variation 2", "variation 3"],
    "reasoning": "brief explanation of strategy"
}}"""),
    ("human", "Generate search query variations for: {query}")
])


async def expand_query(query: str, num_variations: int = 2) -> list[str]:
    """
    Generate multiple variations of a search query.

    Args:
        query: Original search query
        num_variations: Number of variations to generate (default: 2)

    Returns:
        List of query variations (including original query)
    """
    if not settings.research_enable_query_expansion:
        logger.debug(
            "[QUERY_EXPANSION] Query expansion disabled, "
            "returning original query only"
        )
        return [query]

    logger.info(f"[QUERY_EXPANSION] Expanding query: '{query[:60]}...'")
    logger.debug(f"[QUERY_EXPANSION] Generating {num_variations} variations")

    try:
        provider = LLMProviderFactory.create_provider(
            provider_type=settings.llm_provider,
            model=settings.llm_model,
            temperature=0.7,  # Higher temperature for creative variations
            api_key=settings.openai_api_key,
            base_url=settings.ollama_base_url,
        )

        llm = provider.get_llm()
        parser = JsonOutputParser(pydantic_object=QueryVariations)
        chain = QUERY_EXPANSION_PROMPT | llm | parser

        result = await chain.ainvoke({"query": query})
        logger.debug(f"[QUERY_EXPANSION] LLM response: {result}")

        variations = result.get("variations", [])
        reasoning = result.get("reasoning", "")

        logger.info(
            f"[QUERY_EXPANSION] Generated {len(variations)} variations"
        )
        logger.debug(f"[QUERY_EXPANSION] Strategy: {reasoning}")

        # Limit to requested number
        variations = variations[:num_variations]

        for i, var in enumerate(variations, 1):
            logger.debug(f"[QUERY_EXPANSION] Variation {i}: '{var}'")

        # Always include the original query first
        all_queries = [query] + variations

        logger.info(
            f"[QUERY_EXPANSION] Returning {len(all_queries)} total queries "
            f"(1 original + {len(variations)} variations)"
        )

        return all_queries

    except Exception as e:
        logger.error(
            f"[QUERY_EXPANSION] Failed to generate variations: {e}",
            exc_info=True
        )
        # Fallback to original query on error
        logger.warning(
            "[QUERY_EXPANSION] Falling back to original query only"
        )
        return [query]
