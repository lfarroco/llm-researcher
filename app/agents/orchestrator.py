"""
LangGraph orchestrator - coordinates the research workflow.

This module defines the state machine that coordinates the research agents:
Planner -> Search -> Hypothesis -> Synthesis -> Format
"""

import logging
from typing import Optional

from langgraph.graph import StateGraph, END

from app.memory.research_state import ResearchState
from app.agents.planner import plan_research
from app.agents.search_agent import execute_searches
from app.agents.reference_chaser import chase_references
from app.agents.hypothesis_agent import generate_hypotheses
from app.agents.synthesis_agent import synthesize_findings, format_final_document

logger = logging.getLogger(__name__)


def should_continue_after_search(state: ResearchState) -> str:
    """
    Conditional edge: decide whether to run hypothesis investigation or fail.
    """
    logger.debug("[ORCHESTRATOR] Evaluating post-search condition")
    logger.debug(
        f"[ORCHESTRATOR] Citations count: {len(state.citations) if state.citations else 0}")
    logger.debug(
        f"[ORCHESTRATOR] Errors count: {len(state.errors) if state.errors else 0}")

    if state.citations:
        logger.info(
            f"[ORCHESTRATOR] Post-search decision: HYPOTHESIZE (has {len(state.citations)} citations)")
        return "hypothesize"
    elif state.errors:
        logger.warning(
            "[ORCHESTRATOR] Post-search decision: FAIL (has errors, no citations)")
        return "fail"
    else:
        logger.info(
            "[ORCHESTRATOR] Post-search decision: HYPOTHESIZE (no citations but will try)")
        return "hypothesize"  # Try hypothesis even with no citations


def should_continue_after_synthesis(state: ResearchState) -> str:
    """
    Conditional edge: decide whether to format or fail.
    """
    logger.debug("[ORCHESTRATOR] Evaluating post-synthesis condition")
    logger.debug(
        f"[ORCHESTRATOR] Draft length: {len(state.draft) if state.draft else 0}")

    if state.draft:
        logger.info("[ORCHESTRATOR] Post-synthesis decision: FORMAT")
        return "format"
    else:
        logger.warning(
            "[ORCHESTRATOR] Post-synthesis decision: FAIL (no draft)")
        return "fail"


async def handle_failure(state: ResearchState) -> dict:
    """
    Failure handler node.
    """
    logger.error("[ORCHESTRATOR] ========== WORKFLOW FAILED ==========")
    logger.error(f"[ORCHESTRATOR] Research ID: {state.research_id}")
    logger.error(f"[ORCHESTRATOR] Query: {state.query[:100]}")
    logger.error(f"[ORCHESTRATOR] Status at failure: {state.status}")
    logger.error(f"[ORCHESTRATOR] Errors: {state.errors}")

    error_list = "\n".join(f"- {e}" for e in state.errors)
    return {
        "status": "failed",
        "current_step": "Research failed",
        "final_document": f"Research failed.\n\nErrors:\n{error_list}",
    }


def create_research_graph() -> StateGraph:
    """
    Create the research workflow graph.

    Workflow:
        plan -> search -> hypothesize -> synthesize -> format -> END
                    |                                    |
                    +-> fail <---------------------------+

    Returns:
        Compiled StateGraph
    """
    # Create the graph with our state schema
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("plan", plan_research)
    workflow.add_node("search", execute_searches)
    workflow.add_node("chase_references", chase_references)
    workflow.add_node("hypothesize", generate_hypotheses)
    workflow.add_node("synthesize", synthesize_findings)
    workflow.add_node("format", format_final_document)
    workflow.add_node("fail", handle_failure)

    # Add edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "search")

    # Conditional edge after search -> reference chasing
    workflow.add_conditional_edges(
        "search",
        should_continue_after_search,
        {
            "hypothesize": "chase_references",
            "fail": "fail",
        }
    )

    # After reference chasing, proceed to hypothesis investigation
    workflow.add_edge("chase_references", "hypothesize")

    # After hypothesis investigation, proceed to synthesis
    workflow.add_edge("hypothesize", "synthesize")

    # Conditional edge after synthesis
    workflow.add_conditional_edges(
        "synthesize",
        should_continue_after_synthesis,
        {
            "format": "format",
            "fail": "fail",
        }
    )

    # Terminal edges
    workflow.add_edge("format", END)
    workflow.add_edge("fail", END)

    return workflow.compile()


async def run_research_workflow(
    research_id: int,
    query: str,
    config: Optional[dict] = None,
) -> ResearchState:
    """
    Execute the complete research workflow.

    Args:
        research_id: Database ID for the research task
        query: The research query
        config: Optional LangGraph config (for checkpointing, callbacks, etc.)

    Returns:
        Final ResearchState with results
    """
    logger.info("[ORCHESTRATOR] ========================================")
    logger.info("[ORCHESTRATOR] STARTING RESEARCH WORKFLOW")
    logger.info("[ORCHESTRATOR] ========================================")
    logger.info(f"[ORCHESTRATOR] Research ID: {research_id}")
    logger.info(f"[ORCHESTRATOR] Query: '{query[:100]}...'")
    logger.debug(f"[ORCHESTRATOR] Full query: {query}")
    logger.debug(f"[ORCHESTRATOR] Config: {config}")

    # Create initial state
    logger.debug("[ORCHESTRATOR] Creating initial state")
    initial_state = ResearchState(
        research_id=research_id,
        query=query,
    )
    logger.debug(
        f"[ORCHESTRATOR] Initial state created with status='{initial_state.status}'")

    # Create and run the graph
    logger.debug("[ORCHESTRATOR] Creating research graph")
    graph = create_research_graph()
    logger.debug("[ORCHESTRATOR] Graph compiled, starting execution")

    # Run the workflow
    logger.info("[ORCHESTRATOR] Invoking graph workflow...")
    final_state = await graph.ainvoke(
        initial_state,
        config=config or {},
    )
    logger.debug("[ORCHESTRATOR] Graph execution completed")

    final_status = final_state.get('status', 'unknown') if isinstance(
        final_state, dict) else final_state.status

    logger.info("[ORCHESTRATOR] ========================================")
    logger.info("[ORCHESTRATOR] RESEARCH WORKFLOW COMPLETE")
    logger.info("[ORCHESTRATOR] ========================================")
    logger.info(f"[ORCHESTRATOR] Final status: {final_status}")

    if isinstance(final_state, dict):
        logger.debug(
            f"[ORCHESTRATOR] Final state keys: {list(final_state.keys())}")
        logger.debug(
            f"[ORCHESTRATOR] Citations count: {len(final_state.get('citations', []))}")
        logger.debug(
            f"[ORCHESTRATOR] Final doc length: {len(final_state.get('final_document', '') or '')}")

    # Convert back to ResearchState if needed
    if isinstance(final_state, dict):
        logger.debug("[ORCHESTRATOR] Converting dict to ResearchState")
        return ResearchState.model_validate(final_state)

    return final_state
