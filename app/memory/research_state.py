"""
Research state models for tracking progress across the research pipeline.

This module defines the state that flows through the LangGraph workflow
and is persisted to the database for resumption.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Types of sources that can be cited."""
    WEB = "web"
    ARXIV = "arxiv"
    WIKIPEDIA = "wikipedia"


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


def merge_lists(left: list, right: list) -> list:
    """Reducer function to merge lists in state updates."""
    return left + right


def merge_dicts(left: dict, right: dict) -> dict:
    """Reducer function to merge dicts in state updates."""
    return {**left, **right}


class ResearchState(BaseModel):
    """
    Main state object that flows through the LangGraph research workflow.

    This state is persisted to PostgreSQL via LangGraph checkpointing,
    allowing research to be paused and resumed.
    """

    # Core identifiers
    research_id: int = Field(description="Database ID of the research task")
    query: str = Field(description="Original research query from user")

    # Planning phase outputs
    sub_queries: Annotated[list[str], merge_lists] = Field(
        default_factory=list,
        description="Sub-questions derived from the main query"
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
        description="Current phase: planning|searching|synthesizing|formatting|complete|failed"
    )
    current_step: str = Field(
        default="",
        description="Description of current activity"
    )
    errors: Annotated[list[str], merge_lists] = Field(
        default_factory=list,
        description="Errors encountered during research"
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
        """Get deduplicated list of all citations."""
        seen_urls = set()
        unique_citations = []
        for citation in self.citations:
            if citation.url not in seen_urls:
                seen_urls.add(citation.url)
                unique_citations.append(citation)
        return unique_citations

    def to_dict(self) -> dict:
        """Convert state to dictionary for JSON storage."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchState":
        """Create state from dictionary."""
        return cls.model_validate(data)
