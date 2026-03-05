"""
Tests for app.memory.research_state module.

These tests validate all Pydantic models and state management logic
in isolation.
"""

import pytest
from datetime import datetime, timezone

from app.memory.research_state import (
    ConversationMessage,
    AIReasoning,
    SourceType,
    Citation,
    SubQueryResult,
    ResearchState,
    merge_lists,
    merge_dicts,
)


class TestConversationMessage:
    """Tests for ConversationMessage model."""

    def test_create_user_message(self):
        """Test creating a user message."""
        msg = ConversationMessage(
            role="user",
            content="What is quantum computing?",
        )

        assert msg.role == "user"
        assert msg.content == "What is quantum computing?"
        assert msg.timestamp is not None
        assert msg.action_taken is None

    def test_create_assistant_message_with_action(self):
        """Test creating an assistant message with action."""
        msg = ConversationMessage(
            role="assistant",
            content="I'll search for information about quantum computing.",
            action_taken="search",
        )

        assert msg.role == "assistant"
        assert msg.action_taken == "search"

    def test_timestamp_is_iso_format(self):
        """Test that timestamp is in ISO format."""
        msg = ConversationMessage(role="system", content="Starting research")

        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(msg.timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)

    def test_custom_timestamp(self):
        """Test setting a custom timestamp."""
        custom_time = "2024-01-15T10:30:00+00:00"
        msg = ConversationMessage(
            role="user",
            content="Test",
            timestamp=custom_time,
        )

        assert msg.timestamp == custom_time


class TestAIReasoning:
    """Tests for AIReasoning model."""

    def test_create_reasoning_entry(self):
        """Test creating an AI reasoning log entry."""
        reasoning = AIReasoning(
            step="plan_decomposition",
            reasoning="Breaking down query into 3 sub-questions",
            decision="Create sub-queries: Q1, Q2, Q3",
            metadata={"num_subqueries": 3},
        )

        assert reasoning.step == "plan_decomposition"
        assert reasoning.reasoning == "Breaking down query into 3 sub-questions"
        assert reasoning.decision == "Create sub-queries: Q1, Q2, Q3"
        assert reasoning.metadata["num_subqueries"] == 3
        assert reasoning.timestamp is not None

    def test_reasoning_without_decision(self):
        """Test reasoning log without explicit decision."""
        reasoning = AIReasoning(
            step="evaluating_sources",
            reasoning="Checking source credibility",
        )

        assert reasoning.decision is None
        assert reasoning.metadata == {}


class TestSourceType:
    """Tests for SourceType enum."""

    def test_all_source_types(self):
        """Test all source type values."""
        assert SourceType.WEB.value == "web"
        assert SourceType.ARXIV.value == "arxiv"
        assert SourceType.WIKIPEDIA.value == "wikipedia"
        assert SourceType.PUBMED.value == "pubmed"
        assert SourceType.SEMANTIC_SCHOLAR.value == "semantic_scholar"

    def test_source_type_from_string(self):
        """Test creating SourceType from string."""
        source = SourceType("arxiv")
        assert source == SourceType.ARXIV


class TestCitation:
    """Tests for Citation model."""

    def test_create_web_citation(self):
        """Test creating a web citation."""
        citation = Citation(
            id="[1]",
            url="https://example.com/article",
            title="Test Article",
            author="John Doe",
            snippet="This is a relevant excerpt from the article.",
            source_type=SourceType.WEB,
            relevance_score=0.95,
        )

        assert citation.id == "[1]"
        assert citation.url == "https://example.com/article"
        assert citation.title == "Test Article"
        assert citation.author == "John Doe"
        assert citation.source_type == SourceType.WEB
        assert citation.relevance_score == 0.95
        assert citation.date_accessed is not None

    def test_create_arxiv_citation(self):
        """Test creating an ArXiv citation."""
        citation = Citation(
            id="[2]",
            url="https://arxiv.org/abs/2024.12345",
            title="Deep Learning for NLP",
            author="Jane Smith",
            snippet="We propose a novel architecture...",
            source_type=SourceType.ARXIV,
        )

        assert citation.source_type == SourceType.ARXIV
        assert "arxiv.org" in citation.url

    def test_citation_default_values(self):
        """Test citation with default values."""
        citation = Citation(
            id="[3]",
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
        )

        assert citation.author is None
        assert citation.source_type == SourceType.WEB
        assert citation.relevance_score == 0.0

    def test_citation_custom_date(self):
        """Test citation with custom access date."""
        custom_date = "2024-01-15T10:30:00+00:00"
        citation = Citation(
            id="[4]",
            url="https://example.com",
            title="Test",
            snippet="Test",
            date_accessed=custom_date,
        )

        assert citation.date_accessed == custom_date


class TestSubQueryResult:
    """Tests for SubQueryResult model."""

    def test_create_pending_subquery(self):
        """Test creating a pending sub-query."""
        result = SubQueryResult(sub_query="What is machine learning?")

        assert result.sub_query == "What is machine learning?"
        assert result.answer == ""
        assert result.citations == []
        assert result.status == "pending"
        assert result.error is None

    def test_create_complete_subquery(self):
        """Test creating a completed sub-query with results."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="ML Intro",
            snippet="Machine learning is...",
        )

        result = SubQueryResult(
            sub_query="What is machine learning?",
            answer="Machine learning is a branch of AI...",
            citations=[citation],
            status="complete",
        )

        assert result.status == "complete"
        assert result.answer != ""
        assert len(result.citations) == 1

    def test_create_failed_subquery(self):
        """Test creating a failed sub-query."""
        result = SubQueryResult(
            sub_query="What is X?",
            status="failed",
            error="Search API rate limit exceeded",
        )

        assert result.status == "failed"
        assert result.error == "Search API rate limit exceeded"


class TestMergeFunctions:
    """Tests for merge reducer functions."""

    def test_merge_lists(self):
        """Test merging two lists."""
        left = [1, 2, 3]
        right = [4, 5]

        result = merge_lists(left, right)

        assert result == [1, 2, 3, 4, 5]
        # Original lists should be unchanged
        assert left == [1, 2, 3]
        assert right == [4, 5]

    def test_merge_empty_lists(self):
        """Test merging with empty lists."""
        assert merge_lists([], [1, 2]) == [1, 2]
        assert merge_lists([1, 2], []) == [1, 2]
        assert merge_lists([], []) == []

    def test_merge_dicts(self):
        """Test merging two dictionaries."""
        left = {"a": 1, "b": 2}
        right = {"c": 3, "d": 4}

        result = merge_dicts(left, right)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_merge_dicts_with_overlap(self):
        """Test merging dicts with overlapping keys (right wins)."""
        left = {"a": 1, "b": 2}
        right = {"b": 99, "c": 3}

        result = merge_dicts(left, right)

        assert result == {"a": 1, "b": 99, "c": 3}

    def test_merge_empty_dicts(self):
        """Test merging with empty dicts."""
        assert merge_dicts({}, {"a": 1}) == {"a": 1}
        assert merge_dicts({"a": 1}, {}) == {"a": 1}
        assert merge_dicts({}, {}) == {}


class TestResearchState:
    """Tests for ResearchState model."""

    def test_create_minimal_state(self):
        """Test creating state with minimal required fields."""
        state = ResearchState(
            research_id=1,
            query="What is quantum computing?",
        )

        assert state.research_id == 1
        assert state.query == "What is quantum computing?"
        assert state.sub_queries == []
        assert state.citations == []
        assert state.status == "planning"
        assert state.created_at is not None

    def test_create_full_state(self):
        """Test creating a complete research state."""
        citation = Citation(
            id="[1]",
            url="https://example.com",
            title="Test",
            snippet="Test snippet",
        )

        subquery_result = SubQueryResult(
            sub_query="What is X?",
            answer="X is...",
            citations=[citation],
            status="complete",
        )

        state = ResearchState(
            research_id=42,
            query="Main query",
            sub_queries=["Sub Q1", "Sub Q2"],
            citations=[citation],
            sub_query_results=[subquery_result],
            outline="# Introduction\n# Body\n# Conclusion",
            draft="This is a draft document...",
            status="synthesizing",
        )

        assert state.research_id == 42
        assert len(state.sub_queries) == 2
        assert len(state.citations) == 1
        assert len(state.sub_query_results) == 1
        assert state.outline is not None
        assert state.draft is not None

    def test_state_with_conversation(self):
        """Test state with conversation history."""
        msg1 = ConversationMessage(role="user", content="Start research")
        msg2 = ConversationMessage(
            role="assistant",
            content="Starting...",
            action_taken="search",
        )

        state = ResearchState(
            research_id=1,
            query="Test",
            conversation_history=[msg1, msg2],
        )

        assert len(state.conversation_history) == 2
        assert state.conversation_history[0].role == "user"

    def test_state_with_ai_reasoning(self):
        """Test state with AI reasoning logs."""
        reasoning = AIReasoning(
            step="planning",
            reasoning="Analyzing query complexity",
            decision="Create 3 sub-queries",
        )

        state = ResearchState(
            research_id=1,
            query="Test",
            ai_reasoning=[reasoning],
        )

        assert len(state.ai_reasoning) == 1
        assert state.ai_reasoning[0].step == "planning"

    def test_state_with_user_notes(self):
        """Test state with user notes."""
        state = ResearchState(
            research_id=1,
            query="Test",
            user_notes={
                "source_1": "Very relevant for section 2",
                "source_2": "Contains useful statistics",
            },
        )

        assert len(state.user_notes) == 2
        assert "Very relevant" in state.user_notes["source_1"]

    def test_state_with_errors(self):
        """Test state with errors."""
        state = ResearchState(
            research_id=1,
            query="Test",
            errors=[
                "Tavily API rate limit exceeded",
                "ArXiv search timed out",
            ],
            status="failed",
        )

        assert len(state.errors) == 2
        assert state.status == "failed"

    def test_get_all_citations_deduplicates(self):
        """Test that get_all_citations removes duplicates by URL."""
        citation1 = Citation(
            id="[1]",
            url="https://example.com",
            title="Article 1",
            snippet="Snippet 1",
        )
        citation2 = Citation(
            id="[2]",
            url="https://example.com",  # Same URL
            title="Article 1 Duplicate",
            snippet="Snippet 2",
        )
        citation3 = Citation(
            id="[3]",
            url="https://different.com",
            title="Article 2",
            snippet="Snippet 3",
        )

        state = ResearchState(
            research_id=1,
            query="Test",
            citations=[citation1, citation2, citation3],
        )

        unique = state.get_all_citations()

        assert len(unique) == 2  # Only 2 unique URLs
        urls = [c.url for c in unique]
        assert "https://example.com" in urls
        assert "https://different.com" in urls

    def test_get_all_citations_empty(self):
        """Test get_all_citations with no citations."""
        state = ResearchState(research_id=1, query="Test")

        unique = state.get_all_citations()

        assert unique == []

    def test_to_dict_conversion(self):
        """Test converting state to dictionary."""
        state = ResearchState(
            research_id=1,
            query="Test query",
            sub_queries=["Q1", "Q2"],
            status="complete",
        )

        data = state.to_dict()

        assert isinstance(data, dict)
        assert data["research_id"] == 1
        assert data["query"] == "Test query"
        assert data["sub_queries"] == ["Q1", "Q2"]
        assert data["status"] == "complete"

    def test_from_dict_conversion(self):
        """Test creating state from dictionary."""
        data = {
            "research_id": 42,
            "query": "What is AI?",
            "sub_queries": ["Q1", "Q2", "Q3"],
            "citations": [],
            "sub_query_results": [],
            "status": "searching",
            "current_step": "Searching web",
            "errors": [],
            "conversation_history": [],
            "ai_reasoning": [],
            "user_notes": {},
            "created_at": "2024-01-15T10:00:00+00:00",
            "updated_at": "2024-01-15T10:30:00+00:00",
        }

        state = ResearchState.from_dict(data)

        assert state.research_id == 42
        assert state.query == "What is AI?"
        assert len(state.sub_queries) == 3
        assert state.status == "searching"

    def test_state_roundtrip(self):
        """Test converting state to dict and back."""
        original = ResearchState(
            research_id=99,
            query="Original query",
            sub_queries=["A", "B", "C"],
            status="complete",
        )

        data = original.to_dict()
        reconstructed = ResearchState.from_dict(data)

        assert reconstructed.research_id == original.research_id
        assert reconstructed.query == original.query
        assert reconstructed.sub_queries == original.sub_queries
        assert reconstructed.status == original.status

    def test_annotated_fields_merge_behavior(self):
        """Test that annotated fields use merge functions correctly."""
        # This tests the Pydantic model definition, not runtime behavior
        # Just verify the fields exist and have default factories
        state = ResearchState(research_id=1, query="Test")

        # These should all be mutable defaults via factories
        assert isinstance(state.sub_queries, list)
        assert isinstance(state.citations, list)
        assert isinstance(state.sub_query_results, list)
        assert isinstance(state.conversation_history, list)
        assert isinstance(state.ai_reasoning, list)
        assert isinstance(state.user_notes, dict)
        assert isinstance(state.errors, list)

    def test_status_flow(self):
        """Test valid status transitions."""
        state = ResearchState(research_id=1, query="Test")

        # Initial status
        assert state.status == "planning"

        # Simulate workflow progression
        state.status = "searching"
        assert state.status == "searching"

        state.status = "synthesizing"
        assert state.status == "synthesizing"

        state.status = "formatting"
        assert state.status == "formatting"

        state.status = "complete"
        assert state.status == "complete"

    def test_current_step_tracking(self):
        """Test current_step field for progress tracking."""
        state = ResearchState(
            research_id=1,
            query="Test",
            current_step="Decomposing query into sub-questions",
        )

        assert "Decomposing query" in state.current_step

        state.current_step = "Searching ArXiv for papers"
        assert "ArXiv" in state.current_step
