"""
WebSocket connection manager for real-time updates.

Manages WebSocket connections for research progress streaming.
"""

import asyncio
import logging
from typing import Dict, Set
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for research progress streaming."""

    def __init__(self):
        # Map of research_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, research_id: int):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if research_id not in self.active_connections:
                self.active_connections[research_id] = set()
            self.active_connections[research_id].add(websocket)
        logger.info(
            f"WebSocket connected for research {research_id}. "
            f"Total connections: "
            f"{len(self.active_connections.get(research_id, set()))}"
        )

    async def disconnect(self, websocket: WebSocket, research_id: int):
        """Remove a WebSocket connection."""
        async with self._lock:
            if research_id in self.active_connections:
                self.active_connections[research_id].discard(websocket)
                if not self.active_connections[research_id]:
                    del self.active_connections[research_id]
        logger.info(f"WebSocket disconnected for research {research_id}")

    async def send_event(
        self,
        research_id: int,
        event_type: str,
        data: dict,
        timestamp: datetime = None
    ):
        """Send an event to all connections for a research project."""
        if research_id not in self.active_connections:
            return

        if timestamp is None:
            timestamp = datetime.utcnow()

        message = {
            "event_type": event_type,
            "data": data,
            "timestamp": timestamp.isoformat(),
        }

        disconnected = set()
        async with self._lock:
            connections = self.active_connections.get(
                research_id, set()).copy()

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(
                    f"Failed to send to WebSocket for research {research_id}: {e}"
                )
                disconnected.add(websocket)

        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                if research_id in self.active_connections:
                    self.active_connections[research_id] -= disconnected
                    if not self.active_connections[research_id]:
                        del self.active_connections[research_id]

    async def broadcast_status_change(
        self, research_id: int, status: str, message: str = None
    ):
        """Send a status change event."""
        await self.send_event(
            research_id,
            "status_change",
            {"status": status, "message": message}
        )

    async def broadcast_source_added(
        self, research_id: int, source: dict
    ):
        """Send a source added event."""
        await self.send_event(
            research_id,
            "source_added",
            {"source": source}
        )

    async def broadcast_finding_created(
        self, research_id: int, finding: dict
    ):
        """Send a finding created event."""
        await self.send_event(
            research_id,
            "finding_created",
            {"finding": finding}
        )

    async def broadcast_progress(
        self,
        research_id: int,
        current: int,
        total: int,
        message: str = None
    ):
        """Send a progress update."""
        await self.send_event(
            research_id,
            "progress",
            {
                "current": current,
                "total": total,
                "percentage": (current / total * 100) if total > 0 else 0,
                "message": message
            }
        )

    async def broadcast_error(
        self, research_id: int, error: str
    ):
        """Send an error event."""
        await self.send_event(
            research_id,
            "error",
            {"error": error}
        )

    async def broadcast_completion(
        self, research_id: int, result: dict
    ):
        """Send a completion event."""
        await self.send_event(
            research_id,
            "completed",
            {"result": result}
        )

    def get_connection_count(self, research_id: int) -> int:
        """Get the number of active connections for a research project."""
        return len(self.active_connections.get(research_id, set()))


# Global connection manager instance
manager = ConnectionManager()
