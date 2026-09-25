from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Float, JSON,
    UniqueConstraint, Index,
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
    # User's notes about this research
    user_notes = Column(Text, nullable=True)
    # Tags for categorizing the research
    tags = Column(JSON, nullable=True)
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
    findings = relationship(
        "ResearchFinding",
        back_populates="research",
        cascade="all, delete-orphan"
    )
    notes = relationship(
        "ResearchNote",
        back_populates="research",
        cascade="all, delete-orphan",
        order_by="ResearchNote.created_at",
    )
    evidence = relationship(
        "ResearchEvidence",
        back_populates="research",
        cascade="all, delete-orphan",
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
    __table_args__ = (
        # A source is identified by its normalized URL/DOI within one
        # research item. This makes collection idempotent: re-running or
        # resuming a research merges into the existing knowledge base
        # instead of inserting duplicates.
        UniqueConstraint(
            "research_id", "dedupe_key", name="uq_research_sources_identity"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False)
    url = Column(String(2000), nullable=False)
    # Normalized identity (lowercased URL or doi:<value>). Never user-facing;
    # see app/services/source_identity.py for the normalization rules.
    dedupe_key = Column(String(2000), nullable=True, index=True)
    title = Column(String(500), nullable=True)
    author = Column(String(200), nullable=True)
    content_snippet = Column(Text, nullable=True)
    source_type = Column(String(50), default="web")  # web|arxiv|wikipedia
    relevance_score = Column(Float, default=0.0)
    # Marker this source carries in the generated document ("[3]" -> 3) when
    # the report cites it. Assigned when the document is finalized so the API
    # and the report agree on which source a citation number points to.
    citation_marker = Column(Integer, nullable=True)
    accessed_at = Column(DateTime(timezone=True), default=utcnow)
    user_notes = Column(Text, nullable=True)  # User's notes on this source
    tags = Column(JSON, nullable=True)  # List of tags for categorization
    # Full-text retrieval state for this source (see research_fulltext_* settings)
    full_text_status = Column(
        String(20), nullable=True
    )  # None|fetched|unavailable|failed
    full_text_parser = Column(String(50), nullable=True)  # grobid|pdfplumber|pypdf2
    full_text_chars = Column(Integer, nullable=True)
    full_text_fetched_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    research = relationship("Research", back_populates="sources")
    evidence = relationship(
        "ResearchEvidence",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class ResearchEvidence(Base):
    """A quotable span of a source's full text.

    Evidence is what makes a report auditable: synthesis is grounded in these
    spans rather than in search-result snippets, and each span keeps its
    character offsets so a claim can later be bound back to the exact passage
    that supports it (see docs/HARNESS_FEASIBILITY.md §8.4).
    """

    __tablename__ = "research_evidence"
    __table_args__ = (
        Index("ix_research_evidence_source_index", "source_id", "chunk_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False)
    source_id = Column(
        Integer, ForeignKey("research_sources.id"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False)
    # Offsets into the parsed full text, so a span can be re-located.
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    # Which parsed section this span came from, when known.
    section = Column(String(300), nullable=True)
    # Sub-query this evidence was retrieved for, when known.
    sub_query = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    research = relationship("Research", back_populates="evidence")
    source = relationship("ResearchSource", back_populates="evidence")


class ResearchFinding(Base):
    """Stores synthesized findings from research, linked to sources."""
    __tablename__ = "research_findings"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False)
    content = Column(Text, nullable=False)
    # List of source IDs supporting this finding
    source_ids = Column(JSON, nullable=True)
    created_by = Column(String(50), default="user")  # user|ai
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    research = relationship("Research", back_populates="findings")


class ResearchNote(Base):
    """Agent/user notes that serve as the research's evolving memory.

    Notes are read and written by agents throughout the workflow,
    acting as a shared cognitive workspace ("the notes are the
    research brain" — Feynman).
    """
    __tablename__ = "research_notes"

    id = Column(Integer, primary_key=True, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False)
    agent = Column(
        String(50), nullable=False
    )  # planner|search|hypothesis|synthesis|user
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    research = relationship("Research", back_populates="notes")


class AppSetting(Base):
    """Persistent runtime override for application settings."""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    value_type = Column(String(20), nullable=False, default="string")
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
