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
