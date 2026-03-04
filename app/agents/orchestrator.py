"""
LangGraph orchestrator - coordinates the research workflow.

This module defines the state machine that coordinates the research agents:
Planner -> Search -> Synthesis -> Format
"""

import logging
from typing import Optional

from langgraph.graph import StateGraph, END

from app.memory.research_state import ResearchState
from app.agents.planner import plan_research
from app.agents.search_agent import execute_searches
from app.agents.synthesis_agent import synthesize_findings, format_final_document

logger = logging.getLogger(__name__)


def should_continue_after_search(state: ResearchState) -> str:
    """
    Conditional edge: decide whether to synthesize or fail.
    """
    if state.citations:
        return "synthesize"
    elif state.errors:
        return "fail"
    else:
        return "synthesize"  # Try to synthesize even with no citations


def should_continue_after_synthesis(state: ResearchState) -> str:
    """
    Conditional edge: decide whether to format or fail.
    """
    if state.draft:
        return "format"
    else:
        return "fail"


async def handle_failure(state: ResearchState) -> dict:
    """
    Failure handler node.
    """
    logger.error(f"Research workflow failed: {state.errors}")
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
        plan -> search -> synthesize -> format -> END
                    |                      |
                    +-> fail <-------------+

    Returns:
        Compiled StateGraph
    """
    # Create the graph with our state schema
    workflow = StateGraph(ResearchState)

    # Add nodes
    workflow.add_node("plan", plan_research)
    workflow.add_node("search", execute_searches)
    workflow.add_node("synthesize", synthesize_findings)
    workflow.add_node("format", format_final_document)
    workflow.add_node("fail", handle_failure)

    # Add edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "search")

    # Conditional edge after search
    workflow.add_conditional_edges(
        "search",
        should_continue_after_search,
        {
            "synthesize": "synthesize",
            "fail": "fail",
        }
    )

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
    logger.info(f"Starting research workflow for: {query[:100]}...")

    # Create initial state
    initial_state = ResearchState(
        research_id=research_id,
        query=query,
    )

    # Create and run the graph
    graph = create_research_graph()

    # Run the workflow
    final_state = await graph.ainvoke(
        initial_state,
        config=config or {},
    )

    logger.info(
        f"Research workflow complete. Status: {final_state.get('status', 'unknown')}")

    # Convert back to ResearchState if needed
    if isinstance(final_state, dict):
        return ResearchState.model_validate(final_state)

    return final_state
