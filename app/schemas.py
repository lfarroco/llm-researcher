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
