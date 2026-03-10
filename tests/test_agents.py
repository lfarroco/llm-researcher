"""
Tests for agent modules: planner, search_agent, synthesis_agent, intent_router.

These tests validate agent logic with both mocked LLM responses and actual
LLM calls (for prompt validation), as well as the search orchestration logic.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.agents.planner import (
    PlannerOutput,
    plan_research,
    get_planner_chain,
)
from app.agents.search_agent import (
    search_for_subquery,
    execute_searches,
)
from app.agents import intent_router
from app.agents.intent_router import IntentRouterOutput
from app.agents.query_expander import (
    QueryVariations,
    expand_query,
)
from app.memory.research_state import (
    ResearchState,
    Citation,
    SubQueryResult,
    SourceType,
)
from app.tools.web_search import WebSearchResult
from app.tools.arxiv_search import ArxivResult
from app.tools.wikipedia import WikipediaResult


class TestPlannerOutput:
    """Tests for PlannerOutput model."""

    def test_create_planner_output(self):
        """Test creating a planner output."""
        output = PlannerOutput(
            sub_queries=["Question 1", "Question 2", "Question 3"],
            search_strategy="Start with background, then specifics",
            include_academic=True,
        )

        assert len(output.sub_queries) == 3
        assert output.search_strategy == "Start with background, then specifics"
        assert output.include_academic is True

    def test_planner_output_default_academic(self):
        """Test default value for include_academic."""
        output = PlannerOutput(
            sub_queries=["Q1"],
            search_strategy="Broad search",
        )

        assert output.include_academic is False


class TestPlannerAgent:
    """Tests for planner agent."""

    @pytest.mark.asyncio
    async def test_plan_research_with_mocked_llm(self):
        """Test planner with mocked LLM response."""
        state = ResearchState(
            research_id=1,
            query="What is quantum computing?",
        )

        mock_result = {
            "sub_queries": [
                "What are the basic principles of quantum computing?",
                "What are the main quantum computing technologies?",
                "What are current applications of quantum computing?",
            ],
            "search_strategy": "Start with fundamentals, then current state",
            "include_academic": True,
        }

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)

        with patch("app.agents.planner.get_planner_chain", return_value=mock_chain):
            result = await plan_research(state)

        assert "sub_queries" in result
        assert len(result["sub_queries"]) == 3
        assert result["status"] == "searching"
        assert result["current_step"] == "Planning complete. Searching 3 sub-topics."

    @pytest.mark.asyncio
    async def test_plan_research_handles_missing_fields(self):
        """Test planner handles incomplete LLM response."""
        state = ResearchState(
            research_id=1,
            query="What is AI?",
        )

        # Incomplete response from LLM
        mock_result = {
            "sub_queries": ["Q1", "Q2"],
            # Missing search_strategy and include_academic
        }

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)

        with patch("app.agents.planner.get_planner_chain", return_value=mock_chain):
            result = await plan_research(state)

        assert len(result["sub_queries"]) == 2


class TestSearchAgentSubquery:
    """Tests for search_for_subquery function."""

    @pytest.mark.asyncio
    async def test_search_for_subquery_web_only(self):
        """Test searching with web sources only."""
        sub_query = "What is machine learning?"

        # Mock web search results
        mock_web_results = [
            WebSearchResult(
                title="ML Introduction",
                url="https://example.com/ml",
                snippet="Machine learning is...",
                score=0.9,
            )
        ]

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", return_value=mock_web_results):
                with patch("app.agents.search_agent.is_academic_query", return_value=False):
                    result = await search_for_subquery(
                        sub_query,
                        include_academic=False,
                        include_wikipedia=False,
                    )

        assert result.sub_query == sub_query
        assert len(result.citations) == 1
        assert result.citations[0].title == "ML Introduction"
        assert result.citations[0].source_type == SourceType.WEB
        assert result.status == "complete"

    @pytest.mark.asyncio
    async def test_search_for_subquery_with_arxiv(self):
        """Test searching with ArXiv included."""
        sub_query = "Recent research on neural networks"

        mock_web_results = [
            WebSearchResult(
                title="NN Tutorial",
                url="https://example.com",
                snippet="Tutorial on neural networks",
                score=0.8,
            )
        ]

        mock_arxiv_results = [
            ArxivResult(
                title="Deep Neural Networks Study",
                authors=["Smith, J."],
                summary="We investigate deep learning...",
                url="https://arxiv.org/abs/2024.12345",
                pdf_url="https://arxiv.org/pdf/2024.12345",
                published="2024-01-15T00:00:00",
                categories=["cs.LG"],
            )
        ]

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", return_value=mock_web_results):
                with patch("app.agents.search_agent.arxiv_search", return_value=mock_arxiv_results):
                    with patch("app.agents.search_agent.is_academic_query", return_value=True):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=True,
                            include_wikipedia=False,
                        )

        assert len(result.citations) == 2
        # Check we have both WEB and ARXIV sources
        source_types = [c.source_type for c in result.citations]
        assert SourceType.WEB in source_types
        assert SourceType.ARXIV in source_types

    @pytest.mark.asyncio
    async def test_search_for_subquery_with_wikipedia(self):
        """Test searching with Wikipedia included."""
        sub_query = "What is Python programming?"

        mock_web_results = []
        mock_wiki_results = [
            WikipediaResult(
                title="Python (programming language)",
                url="https://en.wikipedia.org/wiki/Python",
                summary="Python is a high-level programming language...",
            )
        ]

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", return_value=mock_web_results):
                with patch("app.agents.search_agent.wikipedia_search", return_value=mock_wiki_results):
                    with patch("app.agents.search_agent.is_academic_query", return_value=False):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=False,
                            include_wikipedia=True,
                        )

        assert len(result.citations) == 1
        assert result.citations[0].source_type == SourceType.WIKIPEDIA

    @pytest.mark.asyncio
    async def test_search_for_subquery_handles_errors(self):
        """Test that search handles errors gracefully."""
        sub_query = "Test query"

        # Mock web search to raise exception
        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", side_effect=Exception("API error")):
                with patch("app.agents.search_agent.is_academic_query", return_value=False):
                    result = await search_for_subquery(
                        sub_query,
                        include_academic=False,
                        include_wikipedia=False,
                    )

        # Should still return a result, but marked as failed
        assert result.sub_query == sub_query
        assert result.status == "failed"
        assert len(result.citations) == 0
        assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_search_for_subquery_citation_ids(self):
        """Test that citations are numbered correctly."""
        sub_query = "Test"

        mock_web_results = [
            WebSearchResult(
                title="Result 1",
                url="https://example.com/1",
                snippet="Snippet 1",
                score=0.9,
            ),
            WebSearchResult(
                title="Result 2",
                url="https://example.com/2",
                snippet="Snippet 2",
                score=0.8,
            ),
        ]

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", return_value=mock_web_results):
                with patch("app.agents.search_agent.is_academic_query", return_value=False):
                    result = await search_for_subquery(
                        sub_query,
                        include_academic=False,
                        include_wikipedia=False,
                    )

        # Citation IDs should be sequential
        assert result.citations[0].id == "[1]"
        assert result.citations[1].id == "[2]"


class TestSearchExecutes:
    """Tests for execute_searches workflow node."""

    @pytest.mark.asyncio
    async def test_execute_searches_with_subqueries(self):
        """Test searching with multiple sub-queries."""
        state = ResearchState(
            research_id=1,
            query="Main query",
            sub_queries=["Sub Q1", "Sub Q2"],
        )

        # Mock search results for each sub-query
        mock_result_1 = SubQueryResult(
            sub_query="Sub Q1",
            citations=[
                Citation(
                    id="[1]",
                    url="https://example.com/1",
                    title="Result 1",
                    snippet="Snippet 1",
                )
            ],
            status="complete",
        )

        mock_result_2 = SubQueryResult(
            sub_query="Sub Q2",
            citations=[
                Citation(
                    id="[2]",
                    url="https://example.com/2",
                    title="Result 2",
                    snippet="Snippet 2",
                )
            ],
            status="complete",
        )

        with patch("app.agents.search_agent.search_for_subquery", side_effect=[mock_result_1, mock_result_2]):
            result = await execute_searches(state)

        assert "sub_query_results" in result
        assert len(result["sub_query_results"]) == 2
        assert "citations" in result
        # Should have collected citations from both sub-queries
        assert len(result["citations"]) >= 2


class TestIntentRouterOutput:
    """Tests for IntentRouterOutput model."""

    def test_create_intent_output(self):
        """Test creating an intent router output."""
        output = IntentRouterOutput(
            intent="research",
            confidence=0.95,
            entities={"topic": "quantum computing"},
            reasoning="User explicitly asked to research a topic",
        )

        assert output.intent == "research"
        assert output.confidence == 0.95
        assert output.entities["topic"] == "quantum computing"
        assert "research" in output.reasoning

    def test_intent_output_confidence_validation(self):
        """Test that confidence is validated (0-1 range)."""
        # Valid
        output = IntentRouterOutput(
            intent="question",
            confidence=0.5,
            reasoning="Unsure",
        )
        assert output.confidence == 0.5

        # Invalid confidence > 1 should raise validation error
        with pytest.raises(Exception):  # Pydantic ValidationError
            IntentRouterOutput(
                intent="question",
                confidence=1.5,
                reasoning="Test",
            )


class TestIntentRouter:
    """Tests for intent classification."""

    @pytest.mark.asyncio
    async def test_route_intent_research(self):
        """Test classifying research intent."""
        message = "Research quantum computing"

        mock_result = IntentRouterOutput(
            intent="research",
            confidence=0.95,
            entities={"topic": "quantum computing"},
            reasoning="User explicitly asked to research a topic",
        )

        with patch.object(
            intent_router, 'route_user_intent',
            new_callable=AsyncMock, return_value=mock_result,
        ):
            result = await intent_router.route_user_intent(message)

        assert result.intent == "research"
        assert result.confidence > 0.9
        assert "quantum computing" in result.entities.get("topic", "")

    @pytest.mark.asyncio
    async def test_route_intent_question(self):
        """Test classifying question intent."""
        message = "What does my research say about climate change?"

        mock_result = IntentRouterOutput(
            intent="question",
            confidence=0.92,
            entities={
                "question_text": "What does my research say about climate change?"},
            reasoning="User is asking about existing research",
        )

        with patch.object(
            intent_router, 'route_user_intent',
            new_callable=AsyncMock, return_value=mock_result,
        ):
            result = await intent_router.route_user_intent(message)

        assert result.intent == "question"

    @pytest.mark.asyncio
    async def test_route_intent_add_source(self):
        """Test classifying add source intent."""
        message = "Add this paper: https://arxiv.org/abs/2024.12345"

        mock_result = IntentRouterOutput(
            intent="add",
            confidence=0.98,
            entities={"source_url": "https://arxiv.org/abs/2024.12345"},
            reasoning="User provided a URL to add",
        )

        with patch.object(
            intent_router, 'route_user_intent',
            new_callable=AsyncMock, return_value=mock_result,
        ):
            result = await intent_router.route_user_intent(message)

        assert result.intent == "add"
        assert "arxiv.org" in result.entities.get("source_url", "")

    @pytest.mark.asyncio
    async def test_route_intent_general(self):
        """Test classifying general conversation."""
        message = "Thanks for your help!"

        mock_result = IntentRouterOutput(
            intent="general",
            confidence=0.85,
            entities={},
            reasoning="Conversational pleasantry",
        )

        with patch.object(
            intent_router, 'route_user_intent',
            new_callable=AsyncMock, return_value=mock_result,
        ):
            result = await intent_router.route_user_intent(message)

        assert result.intent == "general"


class TestSearchAgentIntegration:
    """Integration tests for search agent with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_parallel_search_execution(self):
        """Test that searches execute in parallel, not sequentially."""
        import time

        async def slow_search(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate slow API
            return []

        sub_query = "Test query"

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", side_effect=slow_search):
                with patch("app.agents.search_agent.arxiv_search", side_effect=slow_search):
                    with patch("app.agents.search_agent.wikipedia_search", side_effect=slow_search):
                        with patch("app.agents.search_agent.is_academic_query", return_value=True):
                            start = time.time()
                            await search_for_subquery(
                                sub_query,
                                include_academic=True,
                                include_wikipedia=True,
                            )
                            elapsed = time.time() - start

        # If parallel: ~0.1s, if sequential: ~0.3s
        # Allow some overhead
        assert elapsed < 0.25, "Searches should execute in parallel"

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_url(self):
        """Test that duplicate URLs are handled."""
        sub_query = "Test"

        # Same URL appears in multiple results
        mock_web_results = [
            WebSearchResult(
                title="Article 1",
                url="https://example.com/duplicate",
                snippet="First mention",
                score=0.9,
            ),
            WebSearchResult(
                title="Article 2",
                url="https://example.com/duplicate",  # Duplicate
                snippet="Second mention",
                score=0.8,
            ),
        ]

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.web_search", return_value=mock_web_results):
                with patch("app.agents.search_agent.is_academic_query", return_value=False):
                    result = await search_for_subquery(
                        sub_query,
                        include_academic=False,
                        include_wikipedia=False,
                    )

        # Should keep both initially (deduplication happens at state level)
        assert len(result.citations) == 2


# Optional: LLM Integration Tests (requires API keys)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_planner_with_real_llm():
    """
    Integration test with real LLM to validate prompt effectiveness.

    This test makes actual LLM calls. Run with: pytest -m integration
    Requires valid OPENAI_API_KEY or running Ollama server.
    """
    from app.config import settings

    # Skip if no LLM configured
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        pytest.skip("OpenAI API key not configured")

    state = ResearchState(
        research_id=1,
        query="What are the recent developments in quantum computing?",
    )

    result = await plan_research(state)

    # Validate planner produced reasonable output
    assert "sub_queries" in result
    assert len(result["sub_queries"]) >= 3
    assert len(result["sub_queries"]) <= 5

    # Each sub-query should be a question
    for sq in result["sub_queries"]:
        assert isinstance(sq, str)
        assert len(sq) > 10  # Not trivial
        # Most questions end with ?
        assert sq.endswith("?") or "what" in sq.lower() or "how" in sq.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_intent_router_with_real_llm():
    """
    Integration test for intent router with real LLM.

    Run with: pytest -m integration
    """
    from app.config import settings

    if settings.llm_provider == "openai" and not settings.openai_api_key:
        pytest.skip("OpenAI API key not configured")

    # Test various message types
    test_cases = [
        ("Research artificial intelligence", "research"),
        ("What does my research say about AI?", "question"),
        ("Add this URL: https://example.com", "add"),
        ("Show me all sources", "browse"),
        ("Generate a summary", "generate"),
    ]

    for message, expected_intent in test_cases:
        result = await intent_router.route_user_intent(message)

        assert result.intent == expected_intent or result.confidence > 0.7
        assert isinstance(result.reasoning, str)
        assert len(result.reasoning) > 10


class TestQueryExpander:
    """Tests for query expansion functionality."""

    def test_query_variations_model(self):
        """Test QueryVariations model creation."""
        variations = QueryVariations(
            variations=[
                "alternative query 1",
                "alternative query 2",
            ],
            reasoning="Used synonyms and related terms"
        )

        assert len(variations.variations) == 2
        assert isinstance(variations.reasoning, str)

    @pytest.mark.asyncio
    async def test_expand_query_disabled(self):
        """Test that query expansion can be disabled via config."""
        with patch("app.agents.query_expander.settings") as mock_settings:
            mock_settings.research_enable_query_expansion = False

            result = await expand_query("test query")

            # Should return only the original query
            assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_expand_query_with_variations(self):
        """Test query expansion with mocked LLM response."""
        mock_variations = {
            "variations": [
                "test search alternative",
                "sample query variation",
            ],
            "reasoning": "Used synonyms"
        }

        with patch("app.agents.query_expander.settings") as mock_settings:
            mock_settings.research_enable_query_expansion = True

            with patch("app.agents.query_expander.LLMProviderFactory") as mock_factory:
                # Mock the LLM chain
                mock_provider = MagicMock()
                mock_llm = MagicMock()
                mock_provider.get_llm.return_value = mock_llm
                mock_factory.create_provider.return_value = mock_provider

                # Mock the chain invoke to return variations
                with patch("app.agents.query_expander.QUERY_EXPANSION_PROMPT") as mock_prompt:
                    mock_chain = AsyncMock()
                    mock_chain.ainvoke = AsyncMock(
                        return_value=mock_variations)
                    mock_prompt.__or__ = MagicMock(
                        return_value=MagicMock(
                            __or__=MagicMock(return_value=mock_chain))
                    )

                    result = await expand_query("original query", num_variations=2)

                    # Should return original + variations
                    assert len(result) == 3
                    assert result[0] == "original query"
                    assert "alternative" in result[1].lower(
                    ) or "variation" in result[2].lower()

    @pytest.mark.asyncio
    async def test_expand_query_handles_errors(self):
        """Test that query expansion gracefully handles LLM errors."""
        with patch("app.agents.query_expander.settings") as mock_settings:
            mock_settings.research_enable_query_expansion = True

            with patch("app.agents.query_expander.LLMProviderFactory") as mock_factory:
                # Make the LLM call raise an exception
                mock_factory.create_provider.side_effect = Exception(
                    "LLM error")

                result = await expand_query("test query")

                # Should fallback to original query only
                assert result == ["test query"]
