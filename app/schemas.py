from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class ResearchCreate(BaseModel):
    """Request to create a new research task."""
    query: str = Field(description="Research query/topic to investigate")


class ResearchResponse(BaseModel):
    """Response for a research task."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    result: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ResearchSourceResponse(BaseModel):
    """Response for a research source/citation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    content_snippet: Optional[str] = None
    source_type: str
    relevance_score: float
    accessed_at: datetime
    user_notes: Optional[str] = None
    tags: Optional[list[str]] = None


class ResearchSourceCreate(BaseModel):
    """Request to manually add a source to a research project."""
    url: str = Field(description="URL of the source")
    title: Optional[str] = Field(
        default=None, description="Title of the source"
    )
    author: Optional[str] = Field(
        default=None, description="Author(s) of the source"
    )
    content_snippet: Optional[str] = Field(
        default=None,
        description="Brief excerpt or summary"
    )
    source_type: str = Field(
        default="web",
        description="Type of source (web, arxiv, wikipedia, etc.)"
    )
    relevance_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relevance score (0-1)"
    )
    user_notes: Optional[str] = Field(
        default=None,
        description="User's notes about this source"
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Tags for categorization"
    )


class ResearchSourceUpdate(BaseModel):
    """Request to update a source's user-editable fields."""
    user_notes: Optional[str] = Field(
        default=None,
        description="User's notes about this source"
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Tags for categorization"
    )
    title: Optional[str] = Field(
        default=None, description="Update source title"
    )
    relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Update relevance score (0-1)"
    )


class ResearchDocumentResponse(BaseModel):
    """Full research document with citations."""
    id: int
    query: str
    document: Optional[str] = None
    status: str
    sources: list[ResearchSourceResponse] = []
    created_at: datetime
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    """Request to send a message to the research assistant."""
    message: str = Field(
        description="User's message or command to the research assistant"
    )


class ChatMessageResponse(BaseModel):
    """Response from the research assistant."""
    response: str = Field(description="AI's response to the user")
    action_taken: Optional[str] = Field(
        default=None,
        description="Action performed (e.g., search, add, remove, generate)"
    )
    state_changes: Optional[dict] = Field(
        default=None,
        description="Changes made to knowledge base or research state"
    )
    suggestions: Optional[list[str]] = Field(
        default=None,
        description="Optional follow-up suggestions"
    )


class ConversationMessageResponse(BaseModel):
    """Response for a single conversation message."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    action_taken: Optional[str] = None
    timestamp: datetime


class ResearchFindingCreate(BaseModel):
    """Request to create a new finding."""
    content: str = Field(description="The finding text/content")
    source_ids: Optional[list[int]] = Field(
        default=None,
        description="IDs of sources supporting this finding"
    )


class ResearchFindingUpdate(BaseModel):
    """Request to update a finding."""
    content: Optional[str] = Field(
        default=None,
        description="Updated finding text"
    )
    source_ids: Optional[list[int]] = Field(
        default=None,
        description="Updated list of source IDs"
    )


class ResearchFindingResponse(BaseModel):
    """Response for a research finding."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    source_ids: Optional[list[int]] = None
    created_by: str
    created_at: datetime
    updated_at: datetime


class ResearchStateResponse(BaseModel):
    """Response for AI research state."""
    status: str = Field(
        description="Current research status"
    )
    current_plan: Optional[dict] = Field(
        default=None,
        description="Current research plan breakdown"
    )
    pending_queries: list[str] = Field(
        default=[],
        description="Queries not yet researched"
    )
    completed_queries: list[str] = Field(
        default=[],
        description="Queries that have been researched"
    )
    reasoning_log: list[dict] = Field(
        default=[],
        description="AI decision history"
    )
    last_activity: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last activity"
    )
    source_count: int = Field(
        default=0,
        description="Number of sources in knowledge base"
    )
    finding_count: int = Field(
        default=0,
        description="Number of findings created"
    )


class ResearchPlanResponse(BaseModel):
    """Response for research plan."""
    query: str = Field(description="Main research query")
    refined_question: Optional[str] = Field(
        default=None,
        description="Clarified research question"
    )
    sub_queries: list[str] = Field(
        default=[],
        description="Decomposed sub-questions"
    )
    progress: dict = Field(
        default={},
        description="Progress on each sub-query"
    )
    outline: Optional[str] = Field(
        default=None,
        description="Document outline structure"
    )


class ResearchPlanUpdate(BaseModel):
    """Request to update research plan."""
    add_queries: Optional[list[str]] = Field(
        default=None,
        description="New queries to add to the research plan"
    )
    remove_queries: Optional[list[str]] = Field(
        default=None,
        description="Queries to remove from the plan"
    )
    refined_question: Optional[str] = Field(
        default=None,
        description="Update the refined research question"
    )


class BatchResearchCreate(BaseModel):
    """Request to create multiple research tasks."""
    queries: list[str] = Field(
        description="List of research queries to process"
    )


class BatchResearchResponse(BaseModel):
    """Response for batch research creation."""
    created_count: int = Field(
        description="Number of research tasks created"
    )
    research_ids: list[int] = Field(
        description="IDs of created research tasks"
    )
    research_items: list[ResearchResponse] = Field(
        description="Full details of created research tasks"
    )
