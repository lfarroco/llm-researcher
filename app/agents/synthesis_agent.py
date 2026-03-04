"""
Synthesis agent - combines research findings into a coherent document.

This agent takes all the citations and sub-query results and produces
a well-structured research document with inline citations.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.llm_provider import LLMProviderFactory
from app.memory.research_state import ResearchState, Citation

logger = logging.getLogger(__name__)


SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert research writer. Your task is to synthesize research findings into a comprehensive, well-structured document.

Guidelines:
1. Create a clear, logical structure with sections and subsections
2. Include inline citations using the format [1], [2], etc.
3. Each major claim should be supported by at least one citation
4. Write in a formal, academic tone
5. Include an introduction and conclusion
6. Be thorough but concise - aim for clarity
7. Synthesize information across sources, don't just summarize each one

IMPORTANT: Use ONLY the citation numbers provided in the sources. Do not invent citations."""),
    ("human", """Research Query: {query}

Sub-questions investigated:
{sub_queries}

Sources and findings:
{sources}

Please write a comprehensive research document that answers the query using the provided sources.""")
])


def format_sources_for_prompt(citations: list[Citation]) -> str:
    """Format citations for the synthesis prompt."""
    formatted = []
    for citation in citations:
        source_info = f"{citation.id} {citation.title}"
        if citation.author:
            source_info += f" by {citation.author}"
        source_info += f"\nURL: {citation.url}"
        source_info += f"\nExcerpt: {citation.snippet[:400]}..."
        formatted.append(source_info)

    return "\n\n---\n\n".join(formatted)


def get_synthesis_chain():
    """Create the synthesis chain."""
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.4,  # Balanced for coherent but informative writing
        api_key=settings.openai_api_key,
        base_url=settings.ollama_base_url,
    )

    llm = provider.get_llm()
    return SYNTHESIS_PROMPT | llm


async def synthesize_findings(state: ResearchState) -> dict[str, Any]:
    """
    Synthesis node for LangGraph workflow.

    Takes citations and produces a draft document with inline citations.

    Args:
        state: Current research state with citations populated

    Returns:
        State updates with draft document
    """
    logger.info("[SYNTHESIS] ========== STARTING SYNTHESIS PHASE ==========")
    logger.info(f"[SYNTHESIS] Research ID: {state.research_id}")
    logger.info(f"[SYNTHESIS] Number of citations: {len(state.citations)}")
    logger.info(f"[SYNTHESIS] Number of sub-queries: {len(state.sub_queries)}")
    logger.debug(f"[SYNTHESIS] Query: {state.query}")

    if not state.citations:
        logger.warning("[SYNTHESIS] No citations to synthesize - aborting")
        return {
            "draft": "No sources were found for this research query.",
            "status": "formatting",
            "current_step": "No sources found",
            "errors": ["No citations collected during search phase"],
        }

    try:
        logger.debug("[SYNTHESIS] Creating synthesis chain")
        logger.debug(
            f"[SYNTHESIS] Using LLM provider: {settings.llm_provider}, model: {settings.llm_model}")
        chain = get_synthesis_chain()

        # Prepare inputs
        sub_queries_text = "\n".join(f"- {sq}" for sq in state.sub_queries)
        sources_text = format_sources_for_prompt(state.citations)

        logger.debug(
            f"[SYNTHESIS] Sub-queries text length: {len(sub_queries_text)} chars")
        logger.debug(
            f"[SYNTHESIS] Sources text length: {len(sources_text)} chars")
        logger.debug("[SYNTHESIS] Invoking LLM for document synthesis...")

        # Generate the document
        response = await chain.ainvoke({
            "query": state.query,
            "sub_queries": sub_queries_text,
            "sources": sources_text,
        })

        draft = response.content if hasattr(
            response, 'content') else str(response)

        logger.info("[SYNTHESIS] Draft document generated successfully")
        logger.info(f"[SYNTHESIS] Draft length: {len(draft)} characters")
        logger.debug(f"[SYNTHESIS] Draft preview: {draft[:200]}...")

        return {
            "draft": draft,
            "status": "formatting",
            "current_step": "Draft complete. Formatting citations.",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(
            f"[SYNTHESIS] Synthesis failed with error: {e}", exc_info=True)
        return {
            "draft": "",
            "status": "failed",
            "current_step": "Synthesis failed",
            "errors": [f"Synthesis error: {str(e)}"],
        }


async def format_final_document(state: ResearchState) -> dict[str, Any]:
    """
    Final formatting node - adds references section.

    Args:
        state: Current research state with draft populated

    Returns:
        State updates with final_document
    """
    logger.info("[FORMAT] ========== STARTING FORMAT PHASE ==========")
    logger.info(f"[FORMAT] Research ID: {state.research_id}")
    logger.info(
        f"[FORMAT] Draft length: {len(state.draft) if state.draft else 0} chars")
    logger.info(f"[FORMAT] Number of citations: {len(state.citations)}")

    if not state.draft:
        logger.error("[FORMAT] No draft to format - marking as failed")
        return {
            "final_document": "Research failed to produce results.",
            "status": "failed",
        }

    logger.debug(
        "[FORMAT] Building final document with header and references")

    # Build the final document
    document_parts = [
        f"# Research Report: {state.query}\n",
        f"*Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
        "\n---\n\n",
        state.draft,
        "\n\n---\n\n",
        "## References\n\n",
    ]

    # Add references section
    logger.debug(f"[FORMAT] Adding {len(state.citations)} references")
    for i, citation in enumerate(state.citations):
        ref_line = f"{citation.id} "
        if citation.author:
            ref_line += f"{citation.author}. "
        ref_line += f'"{citation.title}." '
        ref_line += f"Retrieved from {citation.url} "
        ref_line += f"on {citation.date_accessed[:10]}.\n\n"
        document_parts.append(ref_line)
        logger.debug(
            f"[FORMAT] Added reference {i+1}: {citation.title[:40]}...")

    final_document = "".join(document_parts)

    logger.info("[FORMAT] ========== FORMAT PHASE COMPLETE ==========")
    logger.info(
        f"[FORMAT] Final document length: {len(final_document)} characters")
    logger.debug(f"[FORMAT] Final document preview: {final_document[:300]}...")

    return {
        "final_document": final_document,
        "status": "complete",
        "current_step": "Research complete",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
