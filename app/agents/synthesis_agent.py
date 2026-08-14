"""
Synthesis agent - combines research findings into a coherent document.

This agent takes all the citations and sub-query results and produces
a well-structured research document with inline citations.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.llm_provider import LLMProviderFactory, rate_limited_llm_call
from app.memory.research_state import (
    AgentStep, ResearchNote, ResearchState, Citation,
)

logger = logging.getLogger(__name__)


SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert research writer. Your task is to synthesize research findings into a comprehensive, well-structured document.

Guidelines:
1. Create a clear, logical structure with sections and subsections
2. Include inline citations using the format [1], [2], etc.
3. Each major claim should be supported by at least one citation
4. Write in a formal, academic tone
5. Include an introduction and conclusion
6. Be thorough and detailed. Expand every section with multiple paragraphs, specific data points, and concrete examples drawn from the sources. Prioritize depth and completeness over brevity.
7. Synthesize information across sources, don't just summarize each one
8. Write as an authoritative research document. Do NOT refer to "provided sources", "the sources", "the provided corpus", "the available evidence", or similar meta-references to the material you were given. Instead, present findings directly and cite them naturally.
9. Only cite sources that are directly relevant to the claims you are making. Prioritize sources with higher relevance scores; skip sources with low relevance scores or that are off-topic. It is fine not to cite every source.
10. Write a report of approximately {word_target} words - aim for at least 80% of this target and do not finish early. Structure the report as follows: an Introduction (~150 words); one dedicated section per sub-question investigated (5 sections, each ~350-450 words); a cross-cutting analysis section (~200 words); and a Conclusion (~150 words). Inside each section, write several paragraphs that cover key findings with inline citations, supporting data points, concrete examples, and implications. Before finishing, estimate how many words you have written; if you are short of the target, keep expanding sections with additional analysis and detail until you reach it.
11. Cite at least 12 distinct sources. For each source you cite, include at least one sentence describing what that source specifically contributes, so cited sources are meaningfully discussed rather than merely listed.

IMPORTANT: Use ONLY the citation numbers provided in the sources. Do not invent citations. Do NOT include a "References" section in your response - the reference list is appended separately."""),
    ("human", """Research Query: {query}

Sub-questions investigated:
{sub_queries}

Sources and findings:
{sources}

{notes_context}

Write a comprehensive research document that answers the query. Present your findings authoritatively without referring to the research process or the sources as a collection.""")
])


def format_sources_for_prompt(citations: list[Citation]) -> str:
    """Format citations for the synthesis prompt.

    Each source is annotated with its relevance score (0-1) so the writer
    can prioritize the most relevant material. Excerpts are capped at
    ``research_synthesis_excerpt_chars`` characters.
    """
    excerpt_chars = settings.research_synthesis_excerpt_chars
    formatted = []
    for citation in citations:
        source_info = f"{citation.id} {citation.title}"
        if citation.author:
            source_info += f" by {citation.author}"
        source_info += f"\nURL: {citation.url}"
        source_info += (
            f"\nRelevance score: {citation.relevance_score:.2f}"
            " (0-1, higher = more relevant)"
        )
        snippet = (citation.snippet or "").strip()
        if snippet:
            source_info += f"\nExcerpt: {snippet[:excerpt_chars]}..."
        formatted.append(source_info)

    return "\n\n---\n\n".join(formatted)


_REFERENCES_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s+references?|\*\*references?\*\*|references?:)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_model_written_references(draft: str) -> tuple[str, bool]:
    """Remove a "References" section the LLM may have written.

    The formatter appends the canonical reference list separately, so any
    references written by the model are stripped to avoid duplication.

    Returns:
        The cleaned draft and whether a references section was removed.
    """
    match = _REFERENCES_HEADING_RE.search(draft)
    if not match:
        return draft, False
    cleaned = draft[:match.start()].rstrip()
    logger.info("[FORMAT] Removed LLM-written References section from draft")
    return cleaned, True


def get_synthesis_chain():
    """Create the synthesis chain."""
    provider = LLMProviderFactory.create_provider(
        provider_type=settings.llm_provider,
        model=settings.llm_model,
        temperature=0.4,  # Balanced for coherent but informative writing
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
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

    logger.debug("[SYNTHESIS] Creating synthesis chain")
    logger.debug(
        f"[SYNTHESIS] Using LLM provider: {settings.llm_provider}, model: {settings.llm_model}")
    chain = get_synthesis_chain()

    # Prepare inputs
    sub_queries_text = "\n".join(f"- {sq}" for sq in state.sub_queries)
    sources_text = format_sources_for_prompt(state.citations)

    # Build notes context so synthesis can leverage agent observations
    notes_context = ""
    if state.research_notes:
        notes_lines = []
        for note in state.research_notes:
            notes_lines.append(
                f"[{note.agent}] {note.content}"
            )
        notes_context = (
            "Research notes and observations from the investigation:\n"
            + "\n".join(notes_lines)
            + "\n\nUse these notes to guide emphasis, structure, "
            "and which gaps to acknowledge."
        )

    logger.debug(
        f"[SYNTHESIS] Sub-queries text length: {len(sub_queries_text)} chars")
    logger.debug(
        f"[SYNTHESIS] Sources text length: {len(sources_text)} chars")
    logger.debug("[SYNTHESIS] Invoking LLM for document synthesis...")

    # Generate the document
    response = await rate_limited_llm_call(chain, {
        "query": state.query,
        "sub_queries": sub_queries_text,
        "sources": sources_text,
        "notes_context": notes_context,
        "word_target": settings.research_report_word_target,
    })

    draft = response.content if hasattr(
        response, 'content') else str(response)

    # DeepSeek thinking mode returns its chain-of-thought in
    # reasoning_content (preserved into additional_kwargs by the
    # DeepSeekChatOpenAI subclass). Surface it for transparency.
    reasoning = ""
    if hasattr(response, "additional_kwargs"):
        reasoning = response.additional_kwargs.get(
            "reasoning_content") or ""

    logger.info("[SYNTHESIS] Draft document generated successfully")
    logger.info(f"[SYNTHESIS] Draft length: {len(draft)} characters")
    logger.info(f"[SYNTHESIS] Model reasoning length: {len(reasoning)} chars")
    logger.debug(f"[SYNTHESIS] Draft preview: {draft[:200]}...")

    step = AgentStep(
        step_type="synthesis",
        title="Research document synthesized",
        description=(
            f"Generated {len(draft)} character draft from "
            f"{len(state.citations)} sources."
        ),
        status="completed",
        metadata={
            "draft_length": len(draft),
            "sources_used": len(state.citations),
            "model_reasoning_chars": len(reasoning),
            "model_reasoning": reasoning[:2000] if reasoning else "",
        },
    )

    synthesis_note = ResearchNote(
        agent="synthesis",
        content=(
            f"Synthesized {len(state.citations)} sources into a "
            f"{len(draft)}-character draft document."
        ),
    )

    return {
        "draft": draft,
        "status": "formatting",
        "current_step": "Draft complete. Formatting citations.",
        "agent_steps": [step],
        "research_notes": [synthesis_note],
        "updated_at": datetime.now(timezone.utc).isoformat(),
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

    # Remove any "References" section the model wrote itself - the canonical
    # reference list is appended below, so a model-written one would duplicate.
    draft, removed_model_references = strip_model_written_references(
        state.draft)

    # Parse which citation IDs are actually used in the draft text
    cited_ids = set(re.findall(r'\[(\d+)\]', draft))
    logger.info(
        f"[FORMAT] Found {len(cited_ids)} unique citation IDs used in draft: {sorted(cited_ids)}")
    logger.info(
        f"[FORMAT] Total citations available: {len(state.citations)}")

    # Filter citations to only those actually referenced in the text
    cited_citations = []
    skipped_citations = []
    for citation in state.citations:
        # Extract numeric ID from citation.id (e.g., "[1]" -> "1")
        match = re.search(r'\[(\d+)\]', citation.id)
        if match and match.group(1) in cited_ids:
            cited_citations.append(citation)
        else:
            skipped_citations.append(citation)

    if skipped_citations:
        logger.info(
            f"[FORMAT] Filtered out {len(skipped_citations)} uncited references:")
        for sc in skipped_citations:
            logger.info(f"[FORMAT]   - {sc.id} {sc.title[:60]}")

    # Build the final document
    document_parts = [
        f"# Research Report: {state.query}\n",
        f"*Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
        "\n---\n\n",
        draft,
        "\n\n---\n\n",
        "## References\n\n",
    ]

    # Add only cited references
    logger.debug(f"[FORMAT] Adding {len(cited_citations)} cited references")
    for i, citation in enumerate(cited_citations):
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

    step = AgentStep(
        step_type="formatting",
        title="Document formatted",
        description=(
            f"Formatted final document with {len(cited_citations)} cited references. "
            f"Filtered out {len(skipped_citations)} uncited sources."
            + (
                " Removed a References section written by the model."
                if removed_model_references else ""
            )
        ),
        status="completed",
        metadata={
            "cited_references": len(cited_citations),
            "filtered_references": len(skipped_citations),
            "document_length": len(final_document),
            "removed_model_references": removed_model_references,
            "skipped_titles": [
                sc.title[:60] for sc in skipped_citations
            ],
        },
    )

    return {
        "final_document": final_document,
        "status": "complete",
        "current_step": "Research complete",
        "agent_steps": [step],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
