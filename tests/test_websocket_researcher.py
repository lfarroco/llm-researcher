"""
Tests for websocket_manager and researcher modules.

These tests validate WebSocket connection management and the basic
researcher chain functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.websocket_manager import ConnectionManager
from app.researcher import get_researcher_chain, run_research


class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    @pytest.fixture
    def manager(self):
        """Create a ConnectionManager instance for testing."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_websocket(self, manager):
        """Test connecting a WebSocket."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        research_id = 1

        await manager.connect(mock_websocket, research_id)

        # Verify accept was called
        mock_websocket.accept.assert_called_once()

        # Verify connection is registered
        assert research_id in manager.active_connections
        assert mock_websocket in manager.active_connections[research_id]

    @pytest.mark.asyncio
    async def test_connect_multiple_websockets(self, manager):
        """Test connecting multiple WebSockets for same research."""
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        research_id = 1

        await manager.connect(mock_ws1, research_id)
        await manager.connect(mock_ws2, research_id)

        # Both should be registered
        assert len(manager.active_connections[research_id]) == 2
        assert mock_ws1 in manager.active_connections[research_id]
        assert mock_ws2 in manager.active_connections[research_id]

    @pytest.mark.asyncio
    async def test_disconnect_websocket(self, manager):
        """Test disconnecting a WebSocket."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        research_id = 1

        # Connect then disconnect
        await manager.connect(mock_websocket, research_id)
        await manager.disconnect(mock_websocket, research_id)

        # Connection should be removed
        assert research_id not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_one_of_multiple(self, manager):
        """Test disconnecting one WebSocket when multiple are connected."""
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        research_id = 1

        await manager.connect(mock_ws1, research_id)
        await manager.connect(mock_ws2, research_id)
        await manager.disconnect(mock_ws1, research_id)

        # Only ws2 should remain
        assert len(manager.active_connections[research_id]) == 1
        assert mock_ws2 in manager.active_connections[research_id]
        assert mock_ws1 not in manager.active_connections[research_id]

    @pytest.mark.asyncio
    async def test_send_event_to_connected_websockets(self, manager):
        """Test sending an event to connected WebSockets."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        research_id = 1

        await manager.connect(mock_websocket, research_id)

        # Send event
        event_data = {"message": "Test event"}
        await manager.send_event(research_id, "test_event", event_data)

        # Verify send_json was called
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]

        assert call_args["event_type"] == "test_event"
        assert call_args["data"] == event_data
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_send_event_with_custom_timestamp(self, manager):
        """Test sending an event with custom timestamp."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        research_id = 1

        await manager.connect(mock_websocket, research_id)

        custom_time = datetime(2024, 1, 15, 10, 30, 0)
        await manager.send_event(
            research_id,
            "test_event",
            {"data": "test"},
            timestamp=custom_time
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "2024-01-15" in call_args["timestamp"]

    @pytest.mark.asyncio
    async def test_send_event_to_nonexistent_research(self, manager):
        """Test sending event to research with no connections."""
        # Should not raise exception
        await manager.send_event(999, "test_event", {"data": "test"})

    @pytest.mark.asyncio
    async def test_send_event_handles_send_failure(self, manager):
        """Test that failed sends are handled gracefully."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock(
            side_effect=Exception("Send failed")
        )
        research_id = 1

        await manager.connect(mock_websocket, research_id)

        # Should not raise exception, but should clean up
        await manager.send_event(research_id, "test_event", {"data": "test"})

        # Connection should be cleaned up after failure
        assert research_id not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_event_to_multiple_websockets(self, manager):
        """Test sending event to multiple connected WebSockets."""
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()

        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        research_id = 1

        await manager.connect(mock_ws1, research_id)
        await manager.connect(mock_ws2, research_id)

        await manager.send_event(research_id, "broadcast", {"msg": "hello"})

        # Both should receive the event
        mock_ws1.send_json.assert_called_once()
        mock_ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_status_change(self, manager):
        """Test broadcasting status change."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        research_id = 1

        await manager.connect(mock_websocket, research_id)
        await manager.broadcast_status_change(
            research_id,
            "searching",
            "Searching for information"
        )

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["event_type"] == "status_change"
        assert call_args["data"]["status"] == "searching"
        assert call_args["data"]["message"] == "Searching for information"

    @pytest.mark.asyncio
    async def test_broadcast_source_added(self, manager):
        """Test broadcasting source added event."""
        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()
        research_id = 1

        await manager.connect(mock_websocket, research_id)

        source = {
            "id": 1,
            "title": "Test Article",
            "url": "https://example.com",
        }

        await manager.broadcast_source_added(research_id, source)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["event_type"] == "source_added"
        assert call_args["data"]["source"] == source

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, manager):
        """Test handling concurrent connection operations."""
        research_id = 1
        websockets = []

        # Create multiple WebSocket mocks
        for i in range(10):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            websockets.append(ws)

        # Connect all concurrently
        await asyncio.gather(
            *[manager.connect(ws, research_id) for ws in websockets]
        )

        # All should be registered
        assert len(manager.active_connections[research_id]) == 10

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_websocket(self, manager):
        """Test disconnecting a WebSocket that was never connected."""
        mock_websocket = AsyncMock()

        # Should not raise exception
        await manager.disconnect(mock_websocket, 999)

    @pytest.mark.asyncio
    async def test_multiple_research_ids(self, manager):
        """Test managing WebSockets for multiple research projects."""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws3 = AsyncMock()
        ws3.accept = AsyncMock()

        await manager.connect(ws1, research_id=1)
        await manager.connect(ws2, research_id=2)
        await manager.connect(ws3, research_id=1)

        # Research 1 should have 2 connections
        assert len(manager.active_connections[1]) == 2
        # Research 2 should have 1 connection
        assert len(manager.active_connections[2]) == 1


class TestResearcher:
    """Tests for researcher module."""

    def test_get_researcher_chain(self):
        """Test creating researcher chain."""
        with patch("app.researcher.LLMProviderFactory.create_provider") as mock_factory:
            mock_provider = MagicMock()
            mock_llm = MagicMock()
            mock_provider.get_llm.return_value = mock_llm
            mock_factory.return_value = mock_provider

            chain = get_researcher_chain()

            # Verify factory was called
            mock_factory.assert_called_once()
            # Verify provider's get_llm was called
            mock_provider.get_llm.assert_called_once()

    def test_run_research_with_mocked_llm(self):
        """Test run_research with mocked LLM response."""
        query = "What is quantum computing?"

        mock_response = MagicMock()
        mock_response.content = "Quantum computing is a type of computation..."

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("app.researcher.get_researcher_chain", return_value=mock_chain):
            result = run_research(query)

        assert isinstance(result, str)
        assert "Quantum computing" in result
        mock_chain.invoke.assert_called_once_with({"query": query})

    def test_run_research_handles_long_query(self):
        """Test that long queries are handled correctly."""
        long_query = "A" * 500  # Very long query

        mock_response = MagicMock()
        mock_response.content = "Response to long query"

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("app.researcher.get_researcher_chain", return_value=mock_chain):
            result = run_research(long_query)

        assert result == "Response to long query"


class TestConnectionManagerEdgeCases:
    """Additional edge case tests for ConnectionManager."""

    @pytest.mark.asyncio
    async def test_send_event_cleans_up_failed_connections(self):
        """Test that failed connections are cleaned up during send."""
        manager = ConnectionManager()

        # Create one working and one failing WebSocket
        working_ws = AsyncMock()
        working_ws.accept = AsyncMock()
        working_ws.send_json = AsyncMock()

        failing_ws = AsyncMock()
        failing_ws.accept = AsyncMock()
        failing_ws.send_json = AsyncMock(side_effect=Exception("Failed"))

        research_id = 1

        await manager.connect(working_ws, research_id)
        await manager.connect(failing_ws, research_id)

        # Send event
        await manager.send_event(research_id, "test", {"data": "test"})

        # Working WebSocket should still be connected
        assert working_ws in manager.active_connections[research_id]
        # Failing WebSocket should be removed
        assert failing_ws not in manager.active_connections[research_id]

    @pytest.mark.asyncio
    async def test_concurrent_send_events(self):
        """Test sending multiple events concurrently."""
        manager = ConnectionManager()

        mock_websocket = AsyncMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()

        research_id = 1
        await manager.connect(mock_websocket, research_id)

        # Send multiple events concurrently
        await asyncio.gather(
            manager.send_event(research_id, "event1", {"data": 1}),
            manager.send_event(research_id, "event2", {"data": 2}),
            manager.send_event(research_id, "event3", {"data": 3}),
        )

        # Should have been called 3 times
        assert mock_websocket.send_json.call_count == 3


# Test with mocked LLM instead of integration test
def test_run_research_with_mocked_llm():
    """
    Test run_research with mocked LLM response.

    Previously this was an integration test making real LLM calls.
    Now uses mocks for faster, more reliable testing.
    """
    query = "What is the capital of France?"

    # Mock the LLM response
    mock_response = MagicMock()
    mock_response.content = (
        "The capital of France is Paris. Paris is the largest city in France and "
        "serves as the country's political, economic, and cultural center. "
        "It has been the capital since the late 10th century."
    )

    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(return_value=mock_response)

    with patch("app.researcher.get_researcher_chain", return_value=mock_chain):
        result = run_research(query)

    assert isinstance(result, str)
    assert len(result) > 10
    # Should mention Paris
    assert "paris" in result.lower()
