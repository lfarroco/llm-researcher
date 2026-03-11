"""
Integration tests for LLM Researcher system.

Tests the complete workflow with mocked external dependencies:
- LLM calls are mocked
- Database operations use in-memory test database
- External API calls (Tavily, ArXiv, etc.) are mocked

This provides fast, reliable testing while still validating
the full integration of components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Research, ResearchSource, ResearchFinding


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_db():
    """Create a fresh test database for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client with mocked database and disabled rate limiting."""
    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiting for tests
    with patch("app.routers.research.check_research_rate_limit"):
        with patch("app.rate_limiter.check_research_rate_limit"):
            with TestClient(app) as test_client:
                yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def mock_llm_responses():
    """Mock LLM responses for chat and research operations."""
    return {
        "chat_response": (
            "I'll help you research transformer models. "
            "Let me search for the latest developments."
        ),
        "status_response": (
            "Your research has 3 sources collected so far, "
            "including papers from ArXiv and blog posts."
        ),
        "browse_response": (
            "Here are your sources:\n"
            "1. [arxiv] Attention Is All You Need\n"
            "2. [web] Transformer Architecture Explained\n"
            "3. [arxiv] Recent Advances in Transformers"
        ),
        "planner_output": {
            "sub_queries": [
                "What are the key innovations in transformer architecture?",
                "How do transformers handle attention mechanisms?",
                "What are recent improvements to transformer models?",
            ],
            "search_strategy": "Search academic papers first, then blogs",
            "include_academic": True,
        },
    }


@pytest.fixture
def mock_search_results():
    """Mock search results from various sources."""
    from app.tools.web_search import WebSearchResult
    from app.tools.arxiv_search import ArxivResult

    return {
        "web": [
            WebSearchResult(
                title="Understanding Transformers",
                url="https://example.com/transformers",
                snippet="A comprehensive guide to transformer models.",
                source="example.com",
            ),
        ],
        "arxiv": [
            ArxivResult(
                title="Attention Is All You Need",
                authors=["Vaswani, A.", "et al."],
                summary=(
                    "The dominant sequence transduction models are "
                    "based on complex RNNs or CNNs."
                ),
                url="https://arxiv.org/abs/1706.03762",
                pdf_url="https://arxiv.org/pdf/1706.03762.pdf",
                published="2017-06-12",
                categories=["cs.CL", "cs.LG"],
            ),
        ],
    }


class TestResearchWorkflow:
    """Test the complete research workflow."""

    def test_create_research_project(self, client):
        """Test creating a new research project."""
        response = client.post(
            "/research",
            json={"query": "What are the latest developments in transformers?"}
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["query"] == "What are the latest developments in transformers?"
        assert data["status"] == "pending"

    def test_list_research_projects(self, client):
        """Test listing research projects."""
        # Create a project first
        client.post(
            "/research",
            json={"query": "Test query"}
        )

        response = client.get("/research")
        assert response.status_code == 200
        projects = response.json()
        assert len(projects) > 0

    def test_get_research_project(self, client):
        """Test retrieving a specific research project."""
        # Create a project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Get the project
        response = client.get(f"/research/{research_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == research_id
        assert data["query"] == "Test query"

    @patch("app.services.chat_handlers.dispatch_intent")
    @patch("app.agents.intent_router.route_user_intent")
    @patch("app.agents.orchestrator.run_research_workflow")
    def test_trigger_research_via_chat(
        self, mock_workflow, mock_intent, mock_dispatch, client, mock_llm_responses
    ):
        """Test triggering research through chat interface."""
        # Create a project
        create_response = client.post(
            "/research",
            json={"query": "Transformer models"}
        )
        research_id = create_response.json()["id"]

        # Mock intent router to return "research" intent
        from app.agents.intent_router import IntentRouterOutput
        from app.services.chat_handlers import ChatResult

        mock_intent.return_value = IntentRouterOutput(
            intent="research",
            confidence=0.95,
            reasoning="User wants to start research",
            entities={},
        )

        # Mock dispatch result
        mock_dispatch.return_value = ChatResult(
            response_text=mock_llm_responses["chat_response"],
            action_taken="research_started",
            state_changes={"status": "searching"},
            suggestions=[],
        )

        # Mock workflow execution
        mock_workflow.return_value = None  # Async workflow runs in background

        # Send chat message
        response = client.post(
            f"/research/{research_id}/chat",
            json={"message": "Research transformer architecture"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "transformer" in data["response"].lower(
        ) or "research" in data["response"].lower()


class TestSourceManagement:
    """Test source management operations."""

    @patch("app.agents.search_agent.web_search")
    @patch("app.agents.search_agent.arxiv_search")
    def test_get_sources(
        self, mock_arxiv, mock_web, client, mock_search_results
    ):
        """Test retrieving sources for a research project."""
        # Create a project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Add a source manually first
        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test",
                "title": "Test Source",
                "author": "Test Author",
                "content_snippet": "Test content",
                "source_type": "web",
            }
        )

        # Get sources
        response = client.get(f"/research/{research_id}/sources")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) > 0

    def test_add_source_manually(self, client):
        """Test manually adding a source to research."""
        # Create a project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Add source
        response = client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://arxiv.org/abs/1706.03762",
                "title": "Attention Is All You Need",
                "author": "Vaswani et al.",
                "content_snippet": "The dominant sequence transduction models...",
                "source_type": "arxiv",
                "relevance_score": 0.95,
                "user_notes": "Seminal transformer paper",
                "tags": ["transformer", "attention", "foundational"],
            }
        )

        assert response.status_code == 201
        source = response.json()
        assert source["title"] == "Attention Is All You Need"
        assert "transformer" in source["tags"]
        assert source["relevance_score"] == 0.95

    def test_update_source_notes(self, client):
        """Test updating source notes and tags."""
        # Create project and source
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        source_response = client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test",
                "title": "Test Source",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "web",
                "tags": ["test"],
            }
        )
        source_id = source_response.json()["id"]

        # Update source
        response = client.patch(
            f"/research/{research_id}/sources/{source_id}",
            json={
                "user_notes": "Updated notes",
                "tags": ["test", "updated"],
            }
        )

        assert response.status_code == 200
        updated = response.json()
        assert updated["user_notes"] == "Updated notes"
        assert "updated" in updated["tags"]

    def test_filter_sources_by_type(self, client):
        """Test filtering sources by type."""
        # Create project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Add sources of different types
        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://arxiv.org/test1",
                "title": "ArXiv Paper",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "arxiv",
            }
        )
        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test2",
                "title": "Web Source",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "web",
            }
        )

        # Filter by arxiv
        response = client.get(
            f"/research/{research_id}/sources",
            params={"source_type": "arxiv"}
        )
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 1
        assert sources[0]["source_type"] == "arxiv"

    def test_search_sources(self, client):
        """Test searching sources by text."""
        # Create project and sources
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/attention",
                "title": "Understanding Attention Mechanisms",
                "author": "Author",
                "content_snippet": "Attention is key to transformers",
                "source_type": "web",
            }
        )

        # Search for "attention"
        response = client.get(
            f"/research/{research_id}/sources",
            params={"search": "attention"}
        )
        assert response.status_code == 200
        results = response.json()
        assert len(results) > 0


class TestFindingsManagement:
    """Test research findings operations."""

    def test_create_finding(self, client):
        """Test creating a research finding."""
        # Create project and source
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        source_response = client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test",
                "title": "Test Source",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "web",
            }
        )
        source_id = source_response.json()["id"]

        # Create finding
        response = client.post(
            f"/research/{research_id}/findings",
            json={
                "content": "Transformers use self-attention mechanisms.",
                "source_ids": [source_id],
            }
        )

        assert response.status_code == 201
        finding = response.json()
        assert "id" in finding
        assert "Transformers" in finding["content"]

    def test_list_findings(self, client):
        """Test listing research findings."""
        # Create project and finding
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        client.post(
            f"/research/{research_id}/findings",
            json={
                "content": "Test finding",
                "source_ids": [],
            }
        )

        # List findings
        response = client.get(f"/research/{research_id}/findings")
        assert response.status_code == 200
        findings = response.json()
        assert len(findings) > 0

    def test_update_finding(self, client):
        """Test updating a research finding."""
        # Create project and finding
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        finding_response = client.post(
            f"/research/{research_id}/findings",
            json={
                "content": "Original content",
                "source_ids": [],
            }
        )
        finding_id = finding_response.json()["id"]

        # Update finding
        response = client.patch(
            f"/research/{research_id}/findings/{finding_id}",
            json={
                "content": "Updated content with more details",
            }
        )

        assert response.status_code == 200
        updated = response.json()
        assert updated["content"] == "Updated content with more details"


class TestStateAndPlanManagement:
    """Test research state and plan management."""

    def test_get_research_state(self, client):
        """Test retrieving research state."""
        # Create project with some data
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Add a source and finding
        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test",
                "title": "Test",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "web",
            }
        )
        client.post(
            f"/research/{research_id}/findings",
            json={
                "content": "Test finding",
                "source_ids": [],
            }
        )

        # Get state
        response = client.get(f"/research/{research_id}/state")
        assert response.status_code == 200
        state = response.json()
        assert "status" in state
        assert state["source_count"] >= 1
        assert state["finding_count"] >= 1

    @patch("app.agents.planner.get_planner_chain")
    def test_get_research_plan(self, mock_planner, client, mock_llm_responses):
        """Test retrieving research plan."""
        # Create project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Mock planner
        mock_chain = AsyncMock()
        mock_chain.ainvoke = AsyncMock(
            return_value=mock_llm_responses["planner_output"]
        )
        mock_planner.return_value = mock_chain

        # Get plan
        response = client.get(f"/research/{research_id}/plan")
        assert response.status_code == 200
        plan = response.json()
        assert "query" in plan

    def test_update_research_plan(self, client):
        """Test updating research plan."""
        # Create project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Update plan
        response = client.patch(
            f"/research/{research_id}/plan",
            json={
                "add_queries": [
                    "What are the computational requirements?",
                    "How do transformers scale?",
                ],
                "refined_question": "What are the key aspects of transformers?",
            }
        )

        assert response.status_code == 200
        updated_plan = response.json()
        assert "refined_question" in updated_plan


class TestChatInterface:
    """Test chat interface operations."""

    @patch("app.services.chat_handlers.dispatch_intent")
    @patch("app.agents.intent_router.route_user_intent")
    def test_chat_status_check(
        self, mock_intent, mock_dispatch, client, mock_llm_responses
    ):
        """Test checking status via chat."""
        # Create project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Mock intent and dispatch
        from app.agents.intent_router import IntentRouterOutput
        from app.services.chat_handlers import ChatResult

        mock_intent.return_value = IntentRouterOutput(
            intent="status",
            confidence=0.9,
            reasoning="User wants status",
            entities={},
        )
        mock_dispatch.return_value = ChatResult(
            response_text=mock_llm_responses["status_response"],
            action_taken="status_provided",
            state_changes={},
            suggestions=[],
        )

        # Send status check message
        response = client.post(
            f"/research/{research_id}/chat",
            json={"message": "Show me the current status"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "sources" in data["response"].lower()

    def test_get_chat_history(self, client):
        """Test retrieving chat history."""
        # Create project
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Get history (should be empty initially)
        response = client.get(f"/research/{research_id}/chat/history")
        assert response.status_code == 200
        history = response.json()
        assert isinstance(history, list)

    @patch("app.services.chat_handlers.dispatch_intent")
    @patch("app.agents.intent_router.route_user_intent")
    def test_chat_browse_sources(
        self, mock_intent, mock_dispatch, client, mock_llm_responses
    ):
        """Test browsing sources via chat."""
        # Create project with sources
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test",
                "title": "Test Source",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "web",
            }
        )

        # Mock intent and dispatch
        from app.agents.intent_router import IntentRouterOutput
        from app.services.chat_handlers import ChatResult

        mock_intent.return_value = IntentRouterOutput(
            intent="browse",
            confidence=0.9,
            reasoning="User wants to see sources",
            entities={},
        )
        mock_dispatch.return_value = ChatResult(
            response_text=mock_llm_responses["browse_response"],
            action_taken="sources_listed",
            state_changes={},
            suggestions=[],
        )

        # Browse sources
        response = client.post(
            f"/research/{research_id}/chat",
            json={"message": "Show me all the sources"}
        )

        assert response.status_code == 200


class TestDocumentGeneration:
    """Test document generation."""

    def test_get_research_document(self, client):
        """Test retrieving the full research document."""
        # Create project with data
        create_response = client.post(
            "/research",
            json={"query": "Test query"}
        )
        research_id = create_response.json()["id"]

        # Add source and finding
        client.post(
            f"/research/{research_id}/sources",
            json={
                "url": "https://example.com/test",
                "title": "Test Source",
                "author": "Author",
                "content_snippet": "Content",
                "source_type": "web",
            }
        )
        client.post(
            f"/research/{research_id}/findings",
            json={
                "content": "Test finding",
                "source_ids": [],
            }
        )

        # Get document
        response = client.get(f"/research/{research_id}/document")
        assert response.status_code == 200
        document = response.json()
        assert "sources" in document
        assert "status" in document
