from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Float, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Research(Base):
    __tablename__ = "research"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(500), nullable=False)
    result = Column(Text, nullable=True)
    status = Column(String(50), default="pending")
    state_json = Column(JSON, nullable=True)  # Serialized ResearchState
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True),
                        default=utcnow, onupdate=utcnow)

    # Relationships
    sources = relationship(
        "ResearchSource",
        back_populates="research",
        cascade="all, delete-orphan"
    )
    conversations = relationship(
        "ConversationMessage",
        back_populates="research",
        cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    """Stores conversation messages between user and AI."""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user|assistant|system
    content = Column(Text, nullable=False)
    action_taken = Column(
        String(100), nullable=True
    )  # search|generate|add|remove|etc
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    research = relationship("Research", back_populates="conversations")


class ResearchSource(Base):
    """Stores individual sources/citations collected during research."""
    __tablename__ = "research_sources"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False)
    url = Column(String(2000), nullable=False)
    title = Column(String(500), nullable=True)
    author = Column(String(200), nullable=True)
    content_snippet = Column(Text, nullable=True)
    source_type = Column(String(50), default="web")  # web|arxiv|wikipedia
    relevance_score = Column(Float, default=0.0)
    accessed_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    research = relationship("Research", back_populates="sources")
