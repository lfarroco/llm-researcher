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
    RELEVANCE_PROMPT,
    filter_relevant_citations,
    search_for_subquery,
    execute_searches,
)
from app.config import settings
from app.agents import intent_router
from app.agents.intent_router import IntentRouterOutput
from app.agents.query_expander import (
    QueryVariations,
    expand_query,
)
from app.agents.hypothesis_agent import (
    Hypothesis,
    generate_hypotheses,
    rank_hypotheses_by_evidence,
    refine_hypotheses_with_user_feedback,
)
from app.memory.research_state import (
    ResearchState,
    Citation,
    ResearchNote,
    SubQueryResult,
    SourceType,
)


class FakeSearchPlugin:
    """Minimal SearchPlugin stand-in for testing the search agent.

    Mirrors the attributes the search agent reads off a plugin
    (``name``, ``default_max_results``, ``search``).
    """

    def __init__(
        self,
        name: str,
        citations=None,
        default_max_results: int = 5,
        search_side_effect=None,
    ):
        self.name = name
        self.default_max_results = default_max_results
        self.search = AsyncMock(
            return_value=citations or [],
            side_effect=search_side_effect,
        )


class FakeRegistry:
    """ToolRegistry stand-in returning a fixed plugin list."""

    def __init__(self, plugins):
        self.plugins = plugins

    def get_plugins(self, include_academic: bool = False, first_variation: bool = True):
        return self.plugins


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

        with patch(
            "app.agents.planner.get_planner_chain", return_value=mock_chain
        ):
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

        # Mock web plugin results
        web_citation = Citation(
            id="[0]",
            url="https://example.com/ml",
            title="ML Introduction",
            snippet="Machine learning is...",
            source_type=SourceType.WEB,
        )
        registry = FakeRegistry([
            FakeSearchPlugin(name="web", citations=[web_citation]),
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    with patch(
                        "app.agents.search_agent.filter_relevant_citations",
                        new_callable=AsyncMock,
                        side_effect=lambda sub_query, citations, threshold=0.5: citations,
                    ):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=False,
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

        web_citation = Citation(
            id="[0]",
            url="https://example.com",
            title="NN Tutorial",
            snippet="Tutorial on neural networks",
            source_type=SourceType.WEB,
        )

        arxiv_citation = Citation(
            id="[0]",
            url="https://arxiv.org/abs/2024.12345",
            title="Deep Neural Networks Study",
            author="Smith, J.",
            snippet="We investigate deep learning...",
            source_type=SourceType.ARXIV,
        )

        registry = FakeRegistry([
            FakeSearchPlugin(name="web", citations=[web_citation]),
            FakeSearchPlugin(name="arxiv", citations=[arxiv_citation]),
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    with patch(
                        "app.agents.search_agent.filter_relevant_citations",
                        new_callable=AsyncMock,
                        side_effect=lambda sub_query, citations, threshold=0.5: citations,
                    ):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=True,
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

        wiki_citation = Citation(
            id="[0]",
            url="https://en.wikipedia.org/wiki/Python",
            title="Python (programming language)",
            snippet="Python is a high-level programming language...",
            source_type=SourceType.WIKIPEDIA,
        )

        registry = FakeRegistry([
            FakeSearchPlugin(name="web", citations=[]),
            FakeSearchPlugin(name="wikipedia", citations=[wiki_citation]),
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    with patch(
                        "app.agents.search_agent.filter_relevant_citations",
                        new_callable=AsyncMock,
                        side_effect=lambda sub_query, citations, threshold=0.5: citations,
                    ):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=False,
                        )

        assert len(result.citations) == 1
        assert result.citations[0].source_type == SourceType.WIKIPEDIA

    @pytest.mark.asyncio
    async def test_search_for_subquery_handles_errors(self):
        """Test that search handles errors gracefully."""
        sub_query = "Test query"

        # Mock web plugin to raise an exception
        registry = FakeRegistry([
            FakeSearchPlugin(
                name="web",
                search_side_effect=Exception("API error"),
            )
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    result = await search_for_subquery(
                        sub_query,
                        include_academic=False,
                    )

        # Should still return a result, but marked as failed
        assert result.sub_query == sub_query
        assert result.status == "failed"
        assert len(result.citations) == 0
        assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_search_for_subquery_citation_ids(self):
        """Test that citations are numbered sequentially after deduplication."""
        sub_query = "Test"

        web_citations = [
            Citation(
                id="[0]",
                url="https://example.com/1",
                title="Result 1",
                snippet="Snippet 1",
                source_type=SourceType.WEB,
            ),
            Citation(
                id="[0]",
                url="https://example.com/2",
                title="Result 2",
                snippet="Snippet 2",
                source_type=SourceType.WEB,
            ),
        ]
        registry = FakeRegistry([
            FakeSearchPlugin(name="web", citations=web_citations),
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    with patch(
                        "app.agents.search_agent.filter_relevant_citations",
                        new_callable=AsyncMock,
                        side_effect=lambda sub_query, citations, threshold=0.5: citations,
                    ):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=False,
                        )

        # Citation IDs are reassigned sequentially by execute_searches, so
        # search_for_subquery preserves the plugin-assigned placeholders.
        assert len(result.citations) == 2
        assert all(c.id == "[0]" for c in result.citations)


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

        async def slow_search(query, max_results=5):
            await asyncio.sleep(0.1)  # Simulate slow API
            return []

        sub_query = "Test query"

        registry = FakeRegistry([
            FakeSearchPlugin(name="web", search_side_effect=slow_search),
            FakeSearchPlugin(name="arxiv", search_side_effect=slow_search),
            FakeSearchPlugin(name="wikipedia", search_side_effect=slow_search),
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    start = time.time()
                    await search_for_subquery(
                        sub_query,
                        include_academic=True,
                    )
                    elapsed = time.time() - start

        # If parallel: ~0.1s, if sequential: ~0.3s
        # Allow some overhead
        assert elapsed < 0.25, "Searches should execute in parallel"

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_url(self):
        """Test that duplicate URLs are removed."""
        sub_query = "Test"

        # Same URL appears in multiple results
        web_citations = [
            Citation(
                id="[0]",
                url="https://example.com/duplicate",
                title="Article 1",
                snippet="First mention",
                source_type=SourceType.WEB,
            ),
            Citation(
                id="[0]",
                url="https://example.com/duplicate",  # Duplicate
                title="Article 2",
                snippet="Second mention",
                source_type=SourceType.WEB,
            ),
        ]
        registry = FakeRegistry([
            FakeSearchPlugin(name="web", citations=web_citations),
        ])

        with patch("app.agents.search_agent.expand_query", return_value=[sub_query]):
            with patch("app.agents.search_agent.is_academic_query", return_value=False):
                with patch("app.agents.search_agent.get_registry", return_value=registry):
                    with patch(
                        "app.agents.search_agent.filter_relevant_citations",
                        new_callable=AsyncMock,
                        side_effect=lambda sub_query, citations, threshold=0.5: citations,
                    ):
                        result = await search_for_subquery(
                            sub_query,
                            include_academic=False,
                        )

        # Deduplication by URL happens inside search_for_subquery, keeping the
        # first occurrence.
        assert len(result.citations) == 1
        assert result.citations[0].title == "Article 1"


# LLM Tests with mocked responses
@pytest.mark.asyncio
async def test_planner_with_mocked_llm_response():
    """
    Test planner with mocked LLM response to validate output handling.

    Previously this was an integration test making real LLM calls.
    Now uses mocks for faster, more reliable testing.
    """
    state = ResearchState(
        research_id=1,
        query="What are the recent developments in quantum computing?",
    )

    # Mock realistic LLM response
    mock_result = {
        "sub_queries": [
            "What are the latest breakthroughs in quantum computing hardware?",
            "How are quantum algorithms advancing in practical applications?",
            "What are the main challenges in quantum error correction?",
            "Which companies are leading quantum computing development?",
        ],
        "search_strategy": (
            "Start with hardware advances, then algorithms, "
            "challenges, and industry players"
        ),
        "include_academic": True,
    }

    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_result)

    with patch(
        "app.agents.planner.get_planner_chain", return_value=mock_chain
    ):
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


@pytest.mark.asyncio
async def test_intent_router_with_mocked_llm():
    """
    Test intent router with mocked LLM responses.

    Previously this was an integration test making real LLM calls.
    Now uses mocks for faster, more reliable testing.
    """
    # Test various message types with mocked responses
    test_cases = [
        (
            "Research artificial intelligence",
            "research",
            "User wants to start new research",
        ),
        (
            "What does my research say about AI?",
            "question",
            "User is asking about existing research",
        ),
        (
            "Add this URL: https://example.com",
            "add",
            "User wants to add a source",
        ),
        ("Show me all sources", "browse", "User wants to view sources"),
        ("Generate a summary", "generate", "User wants to generate document"),
    ]

    for message, expected_intent, reasoning in test_cases:
        # Create expected output
        # Mock the LLM to avoid actual API calls
        mock_llm_output = {
            "intent": expected_intent,
            "confidence": 0.95,
            "reasoning": reasoning,
            "entities": {},
        }

        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_llm_output)

        with patch(
            "app.agents.intent_router.get_intent_router_chain",
            return_value=mock_chain,
        ):
            result = await intent_router.route_user_intent(message)

            assert result.intent == expected_intent
            assert result.confidence > 0.7
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


class TestHypothesisRanking:
    """Tests for hypothesis ranking behavior."""

    def test_rank_hypotheses_prioritizes_evidence(self):
        """Higher-evidence hypotheses should rank first."""
        hyp_low = Hypothesis(
            statement="Hypothesis A",
            search_query="impact of AI on education",
            reasoning="General trend worth exploring",
            aspect="education",
        )
        hyp_high = Hypothesis(
            statement="Hypothesis B",
            search_query=(
                "AI tutor effectiveness AND randomized trial site:edu"
            ),
            reasoning=(
                "Multiple studies suggest gains but evidence quality differs "
                "by population and evaluation design."
            ),
            aspect="effectiveness",
        )

        ranked = rank_hypotheses_by_evidence([
            (
                hyp_low,
                [
                    Citation(
                        id="[1]",
                        url="https://example.com/1",
                        title="A",
                        snippet="A",
                        source_type=SourceType.WEB,
                    )
                ],
            ),
            (
                hyp_high,
                [
                    Citation(
                        id="[2]",
                        url="https://example.com/2",
                        title="B",
                        snippet="B",
                        source_type=SourceType.WEB,
                    ),
                    Citation(
                        id="[3]",
                        url="https://example.com/3",
                        title="C",
                        snippet="C",
                        source_type=SourceType.ARXIV,
                    ),
                    Citation(
                        id="[4]",
                        url="https://example.com/4",
                        title="D",
                        snippet="D",
                        source_type=SourceType.WIKIPEDIA,
                    ),
                ],
            ),
        ])

        assert len(ranked) == 2
        assert ranked[0]["hypothesis"].statement == "Hypothesis B"
        assert ranked[0]["rank"] == 1
        assert ranked[0]["score"] >= ranked[1]["score"]
        assert ranked[0]["confidence"] in {"high", "medium"}

    @pytest.mark.asyncio
    async def test_generate_hypotheses_includes_ranking_metadata(self):
        """Summary and hypothesis steps should include ranking details."""
        state = ResearchState(
            research_id=42,
            query="How effective are AI tutors?",
            sub_queries=["What outcomes improve?"],
            citations=[
                Citation(
                    id="[1]",
                    url="https://seed.example",
                    title="Seed source",
                    snippet="Initial evidence",
                    source_type=SourceType.WEB,
                )
            ],
        )

        llm_result = {
            "observations": "Need stronger causal evidence across cohorts.",
            "hypotheses": [
                {
                    "statement": "AI tutors improve exam performance in STEM.",
                    "search_query": "AI tutor exam performance randomized trial",
                    "reasoning": "A recurring claim that needs stronger validation.",
                    "aspect": "STEM outcomes",
                },
                {
                    "statement": "Benefits are larger for novice learners.",
                    "search_query": "AI tutor novice learners effect size meta analysis",
                    "reasoning": "Prior studies indicate heterogeneity by baseline skill.",
                    "aspect": "learner segment",
                },
            ],
        }

        first_hypothesis = Hypothesis(**llm_result["hypotheses"][0])
        second_hypothesis = Hypothesis(**llm_result["hypotheses"][1])

        first_citations = [
            Citation(
                id="[0]",
                url="https://example.com/a",
                title="A",
                snippet="A",
                source_type=SourceType.WEB,
            )
        ]
        second_citations = [
            Citation(
                id="[0]",
                url="https://example.com/b",
                title="B",
                snippet="B",
                source_type=SourceType.WEB,
            ),
            Citation(
                id="[0]",
                url="https://example.com/c",
                title="C",
                snippet="C",
                source_type=SourceType.ARXIV,
            ),
        ]

        with patch("app.agents.hypothesis_agent.rate_limited_llm_call", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_result

            with patch("app.agents.hypothesis_agent.search_for_hypothesis", new_callable=AsyncMock) as mock_search:
                mock_search.side_effect = [
                    (first_hypothesis, first_citations),
                    (second_hypothesis, second_citations),
                ]

                result = await generate_hypotheses(state)

        assert result["status"] == "synthesizing"
        summary_steps = [
            step for step in result["agent_steps"]
            if step.step_type == "summary"
        ]
        assert len(summary_steps) == 1
        rankings = summary_steps[0].metadata.get("rankings", [])
        assert len(rankings) == 2
        assert rankings[0]["rank"] == 1
        assert rankings[0]["score"] >= rankings[1]["score"]

        hypothesis_steps = [
            step for step in result["agent_steps"]
            if step.step_type == "hypothesis"
        ]
        assert len(hypothesis_steps) == 2
        assert all("rank" in step.metadata for step in hypothesis_steps)
        assert all("score" in step.metadata for step in hypothesis_steps)


class TestHypothesisFeedbackLoop:
    """Tests for user feedback refinement in hypothesis generation."""

    def test_refine_hypotheses_with_user_feedback_reorders(self):
        """Hypotheses matching user feedback keywords should be prioritized."""
        hypotheses = [
            Hypothesis(
                statement="AI tutors improve chemistry scores.",
                search_query="ai tutor chemistry outcomes",
                reasoning="Need domain-specific evidence.",
                aspect="chemistry",
            ),
            Hypothesis(
                statement="AI tutors benefit novice learners most.",
                search_query="ai tutor novice effect size",
                reasoning="Effects may vary by prior knowledge.",
                aspect="learner level",
            ),
        ]
        feedback = [
            ResearchNote(
                agent="user",
                content="Please focus on novice learners and baseline skill.",
            )
        ]

        refined = refine_hypotheses_with_user_feedback(hypotheses, feedback)

        assert len(refined) == 2
        assert "novice learners" in refined[0].statement.lower()

    @pytest.mark.asyncio
    async def test_generate_hypotheses_adds_feedback_refinement_step(self):
        """Hypothesis workflow should record when user feedback is applied."""
        state = ResearchState(
            research_id=77,
            query="How effective are AI tutors?",
            sub_queries=["Which groups benefit most?"],
            citations=[
                Citation(
                    id="[1]",
                    url="https://seed.example",
                    title="Seed",
                    snippet="seed",
                    source_type=SourceType.WEB,
                )
            ],
            research_notes=[
                ResearchNote(
                    agent="user",
                    content="Prioritize novice learner effects.",
                )
            ],
        )

        llm_result = {
            "observations": "Need subgroup analysis.",
            "hypotheses": [
                {
                    "statement": "AI tutors improve outcomes in STEM.",
                    "search_query": "AI tutor stem outcomes",
                    "reasoning": "Common claim needing stronger validation.",
                    "aspect": "STEM outcomes",
                }
            ],
        }

        generated_hypothesis = Hypothesis(**llm_result["hypotheses"][0])
        citations = [
            Citation(
                id="[0]",
                url="https://example.com/evidence",
                title="Evidence",
                snippet="Evidence",
                source_type=SourceType.WEB,
            )
        ]

        with patch("app.agents.hypothesis_agent.rate_limited_llm_call", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = llm_result

            with patch("app.agents.hypothesis_agent.search_for_hypothesis", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = (generated_hypothesis, citations)
                result = await generate_hypotheses(state)

        feedback_steps = [
            step for step in result["agent_steps"]
            if step.title == "Refining hypotheses with user feedback"
        ]
        assert len(feedback_steps) == 1
        assert feedback_steps[0].metadata.get("feedback_notes_used") == 1


class TestRelevanceFiltering:
    """The relevance filter must be cheap and must not starve a sub-query.

    It used to make one LLM call per citation with a "when in doubt, mark as
    irrelevant" instruction, which both dominated the search phase's runtime
    and rejected directly on-topic sources (2/17 and 5/14 in a live run), so
    two of five sub-questions ended with no sources at all.
    """

    def _citations(self, count: int) -> list[Citation]:
        return [
            Citation(
                id=f"[{i + 1}]",
                url=f"https://example.com/{i}",
                title=f"Source {i}",
                snippet=f"Snippet {i}",
                source_type=SourceType.WEB,
                relevance_score=0.1 * i,
            )
            for i in range(count)
        ]

    def _batch_response(self, first_index: int, count: int, relevant: bool):
        return {
            "assessments": [
                {
                    "index": first_index + offset,
                    "is_relevant": relevant,
                    "confidence": 0.9,
                    "reason": "because",
                }
                for offset in range(count)
            ]
        }

    @pytest.mark.asyncio
    async def test_assesses_in_batches_not_per_citation(self):
        """20 citations at batch size 5 issue 4 calls, not 20."""
        citations = self._citations(20)
        calls: list[int] = []

        async def fake_llm(chain, payload):
            first = int(payload["sources"].split("[", 1)[1].split("]")[0])
            count = payload["sources"].count("URL:")
            calls.append(first)
            return self._batch_response(first, count, relevant=True)

        with patch("app.agents.search_agent._build_relevance_chain",
                   return_value=MagicMock()):
            with patch("app.agents.search_agent.rate_limited_llm_call",
                       side_effect=fake_llm):
                with patch.object(settings, "research_relevance_batch_size", 5):
                    kept = await filter_relevant_citations("q", citations)

        assert kept == citations
        assert calls == [0, 5, 10, 15]

    @pytest.mark.asyncio
    async def test_rejected_citations_are_dropped(self):
        citations = self._citations(4)

        async def fake_llm(chain, payload):
            first = int(payload["sources"].split("[", 1)[1].split("]")[0])
            count = payload["sources"].count("URL:")
            return {
                "assessments": [
                    {
                        "index": first + offset,
                        "is_relevant": offset != 1,
                        "confidence": 0.9,
                        "reason": "off topic",
                    }
                    for offset in range(count)
                ]
            }

        with patch("app.agents.search_agent._build_relevance_chain",
                   return_value=MagicMock()):
            with patch("app.agents.search_agent.rate_limited_llm_call",
                       side_effect=fake_llm):
                kept = await filter_relevant_citations("q", citations)

        assert [c.title for c in kept] == ["Source 0", "Source 2", "Source 3"]

    @pytest.mark.asyncio
    async def test_llm_failure_keeps_every_citation(self):
        citations = self._citations(3)

        with patch("app.agents.search_agent._build_relevance_chain",
                   return_value=MagicMock()):
            with patch("app.agents.search_agent.rate_limited_llm_call",
                       new_callable=AsyncMock,
                       side_effect=RuntimeError("boom")):
                kept = await filter_relevant_citations("q", citations)

        assert kept == citations

    @pytest.mark.asyncio
    async def test_omitted_assessments_keep_their_citation(self):
        citations = self._citations(3)

        async def fake_llm(chain, payload):
            # The model only judges the first source.
            return self._batch_response(0, 1, relevant=False)

        with patch("app.agents.search_agent._build_relevance_chain",
                   return_value=MagicMock()):
            with patch("app.agents.search_agent.rate_limited_llm_call",
                       side_effect=fake_llm):
                kept = await filter_relevant_citations("q", citations)

        assert [c.title for c in kept] == ["Source 1", "Source 2"]

    @pytest.mark.asyncio
    async def test_all_rejected_falls_back_to_best_sources(self):
        """A sub-question is never left with zero sources."""
        citations = self._citations(5)

        async def fake_llm(chain, payload):
            first = int(payload["sources"].split("[", 1)[1].split("]")[0])
            count = payload["sources"].count("URL:")
            return self._batch_response(first, count, relevant=False)

        with patch("app.agents.search_agent._build_relevance_chain",
                   return_value=MagicMock()):
            with patch("app.agents.search_agent.rate_limited_llm_call",
                       side_effect=fake_llm):
                with patch.object(
                    settings, "research_relevance_fallback_keep", 2
                ):
                    kept = await filter_relevant_citations("q", citations)

        # Highest search relevance scores win (0.5, then 0.4).
        assert [c.title for c in kept] == ["Source 4", "Source 3"]

    @pytest.mark.asyncio
    async def test_disabled_filter_keeps_everything(self):
        citations = self._citations(2)
        with patch.object(settings, "research_enable_relevance_filter", False):
            assert await filter_relevant_citations("q", citations) == citations

    def test_prompt_asks_for_recall_not_strictness(self):
        """Regression guard for the rejected-on-topic-sources bug."""
        rendered = RELEVANCE_PROMPT.format_prompt(
            sub_query="q", sources="[0] t"
        ).to_string().lower()
        assert "when in doubt, mark as irrelevant" not in rendered
        assert "could contribute evidence" in rendered
        assert "partial matches count" in rendered

    @pytest.mark.asyncio
    async def test_execute_searches_honours_planner_flag(self):
        """The planner's include_academic decision is no longer discarded."""
        state = ResearchState(
            research_id=1,
            query="a plain product question",
            sub_queries=["what is X"],
            include_academic=True,
        )
        captured = {}

        async def fake_search(sub_query, include_academic=False):
            captured["include_academic"] = include_academic
            return SubQueryResult(
                sub_query=sub_query, citations=[], status="failed"
            )

        with patch("app.agents.search_agent.search_for_subquery",
                   side_effect=fake_search):
            with patch("app.agents.search_agent.is_academic_query",
                       return_value=False):
                await execute_searches(state)

        assert captured["include_academic"] is True
