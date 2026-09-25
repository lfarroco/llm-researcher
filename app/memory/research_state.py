"""
Research state models for tracking progress across the research pipeline.

This module defines the state that flows through the LangGraph workflow
and is persisted to the database for resumption.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A message in the user-AI conversation."""

    role: str = Field(description="Message role: user|assistant|system")
    content: str = Field(description="Message content")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of message"
    )
    action_taken: Optional[str] = Field(
        default=None,
        description=(
            "Action triggered by this message "
            "(e.g., 'search', 'generate')"
        )
    )


class AIReasoning(BaseModel):
    """Log entry of AI reasoning/decision-making."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of reasoning"
    )
    step: str = Field(description="Name of the step or decision point")
    reasoning: str = Field(description="Explanation of the AI's reasoning")
    decision: Optional[str] = Field(
        default=None,
        description="Decision made (if applicable)"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context or data"
    )


class SourceType(str, Enum):
    """Types of sources that can be cited."""
    WEB = "web"
    ARXIV = "arxiv"
    WIKIPEDIA = "wikipedia"
    PUBMED = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    SPRINGER = "springer"
    ELSEVIER = "elsevier"


class Citation(BaseModel):
    """A citation/reference collected during research."""

    id: str = Field(description="Citation marker, e.g., '[1]'")
    url: str = Field(description="Source URL")
    title: str = Field(description="Page or article title")
    author: Optional[str] = Field(
        default=None, description="Author if available")
    date_accessed: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp when source was accessed"
    )
    snippet: str = Field(description="Relevant excerpt from the source")
    source_type: SourceType = Field(
        default=SourceType.WEB, description="Type of source")
    relevance_score: float = Field(
        default=0.0, description="Search relevance score")


class SubQueryResult(BaseModel):
    """Result of searching for a single sub-query."""

    sub_query: str = Field(description="The sub-question being answered")
    answer: str = Field(
        default="", description="Synthesized answer to the sub-query")
    citations: list[Citation] = Field(
        default_factory=list, description="Citations for this answer")
    status: str = Field(default="pending",
                        description="pending|searching|complete|failed")
    error: Optional[str] = Field(
        default=None, description="Error message if failed")


class AgentStep(BaseModel):
    """A step taken by the research agent, for debugging/transparency."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of this step"
    )
    step_type: str = Field(
        description=(
            "Type of step: planning|searching|relevance_filter|"
            "thinking|hypothesis|synthesis|formatting|summary|error"
        )
    )
    title: str = Field(
        description="Short title of what happened"
    )
    description: str = Field(
        default="",
        description="Detailed description of the step"
    )
    status: str = Field(
        default="completed",
        description="Status: running|completed|skipped|error"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional data (e.g., counts, queries, scores)"
    )


class ResearchNote(BaseModel):
    """A note written by an agent or user during research.

    Notes serve as the research's evolving memory — a shared cognitive
    workspace where agents and users record important context for
    downstream steps.
    """

    agent: str = Field(
        description=(
            "Who wrote this note: "
            "planner|search|hypothesis|synthesis|user"
        )
    )
    content: str = Field(
        description="The note content"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp when the note was created"
    )


class EvidenceSpan(BaseModel):
    """A quotable passage of a source's full text.

    Snippets are what search engines return; evidence is what the paper
    actually says. Synthesis is grounded in these spans so claims can be
    attributed to a passage rather than to an abstract-length blurb.
    """

    source_id: int = Field(description="Database ID of the owning source")
    citation_id: str = Field(
        default="", description="Citation marker, e.g. '[1]', when known"
    )
    title: str = Field(default="", description="Source title")
    url: str = Field(default="", description="Source URL")
    text: str = Field(description="The passage text")
    chunk_index: int = Field(default=0, description="Position in the source")
    section: Optional[str] = Field(
        default=None, description="Section heading the passage came from"
    )


def merge_lists(left: list, right: list) -> list:
    """Reducer function to merge lists in state updates."""
    return left + right


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer function to merge dicts in state updates."""
    return {**left, **right}


class ResearchState(BaseModel):
    """
    Main state object that flows through the LangGraph research workflow.

    This state is **execution context**, not the durable record of truth. The
    knowledge base (sources, findings, notes) lives in the database and is the
    canonical store; this object is serialized to ``Research.state_json``
    after each node purely so a run can be resumed. Nothing here is
    authoritative, and losing it never loses research data.
    """

    # Core identifiers
    research_id: int = Field(description="Database ID of the research task")
    query: str = Field(description="Original research query from user")

    # Planning phase outputs
    sub_queries: Annotated[list[str], merge_lists] = Field(
        default_factory=list,
        description="Sub-questions derived from the main query"
    )
    include_academic: bool = Field(
        default=False,
        description=(
            "Planner's decision on whether to query academic sources "
            "(arXiv, Springer, ...). Consumed by the search phase."
        )
    )

    # Search phase outputs
    citations: Annotated[list[Citation], merge_lists] = Field(
        default_factory=list,
        description="All citations collected during research"
    )
    sub_query_results: Annotated[list[SubQueryResult], merge_lists] = Field(
        default_factory=list,
        description="Results for each sub-query"
    )

    # Full-text grounding: quotable passages retrieved from parsed PDFs.
    # Populated after search and consumed by synthesis, which prefers these
    # over search-result snippets when they are available.
    evidence: Annotated[list[EvidenceSpan], merge_lists] = Field(
        default_factory=list,
        description="Full-text evidence passages supporting the citations"
    )

    # Synthesis phase outputs
    outline: Optional[str] = Field(
        default=None,
        description="Document outline/structure"
    )
    draft: Optional[str] = Field(
        default=None,
        description="Current draft of the research document"
    )
    final_document: Optional[str] = Field(
        default=None,
        description="Final document with formatted citations"
    )

    # Workflow tracking
    status: str = Field(
        default="planning",
        description=(
            "Current phase: planning|searching|synthesizing|"
            "formatting|complete|failed"
        )
    )
    current_step: str = Field(
        default="",
        description="Description of current activity"
    )
    errors: Annotated[list[str], merge_lists] = Field(
        default_factory=list,
        description="Errors encountered during research"
    )

    # Interactive conversation
    conversation_history: Annotated[
        list[ConversationMessage], merge_lists
    ] = Field(
        default_factory=list,
        description="History of user-AI conversation messages"
    )
    ai_reasoning: Annotated[list[AIReasoning], merge_lists] = Field(
        default_factory=list,
        description="Log of AI decision-making for transparency"
    )
    agent_steps: Annotated[list[AgentStep], merge_lists] = Field(
        default_factory=list,
        description="Steps taken by the agent for debugging/transparency"
    )
    user_notes: Annotated[dict[str, str], merge_dicts] = Field(
        default_factory=dict,
        description=(
            "User annotations on sources/findings "
            "(key: item_id, value: note)"
        )
    )

    # Research notes — the research's evolving brain
    research_notes: Annotated[list[ResearchNote], merge_lists] = Field(
        default_factory=list,
        description=(
            "Notes written by agents and users during research, "
            "serving as shared cognitive memory across workflow stages"
        )
    )

    # Metadata
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When research was started"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Last update timestamp"
    )

    def get_all_citations(self) -> list[Citation]:
        """Get deduplicated list of all citations.

        Deduplicates by normalized source identity rather than raw URL
        string, so ``http``/``https``, ``www.``, tracking parameters and
        DOI-resolver variants of the same paper collapse to one citation.
        """
        # Imported lazily: app.services.source_identity is dependency-free,
        # but this keeps app.memory importable without the services package.
        from app.services.source_identity import source_identity

        seen: set[str] = set()
        unique_citations = []
        for citation in self.citations:
            key = source_identity(citation.url, title=citation.title)
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)
        return unique_citations

    def to_dict(self) -> dict:
        """Convert state to dictionary for JSON storage."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchState":
        """Create state from dictionary."""
        return cls.model_validate(data)
