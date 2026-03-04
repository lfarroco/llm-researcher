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
