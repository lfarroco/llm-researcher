"""
Chat router - chat and WebSocket endpoints.

Handles conversational interactions with the research assistant
and real-time progress streaming via WebSocket.
"""

import asyncio
import logging
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationMessageResponse,
)
from app.agents.intent_router import route_user_intent
from app.services.chat_handlers import dispatch_intent
from app.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/research/{research_id}/chat",
    response_model=ChatMessageResponse,
    tags=["conversation"],
)
def chat_with_research(
    research_id: int,
    payload: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Chat with the research assistant. Main interaction endpoint.

    The AI classifies the user's intent and routes to the appropriate
    handler (research, question, browse, status, generate, add,
    remove, edit, or general).
    """
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Save user message
    user_message = models.ConversationMessage(
        research_id=research_id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)
    db.commit()

    # Route intent
    logger.info(f"Processing chat message for research {research_id}")
    intent_result = route_user_intent(payload.message)

    # Dispatch to focused handler
    result = dispatch_intent(
        intent=intent_result.intent,
        research=research,
        research_id=research_id,
        message=payload.message,
        entities=intent_result.entities,
        background_tasks=background_tasks,
        db=db,
    )

    # Save assistant response
    assistant_message = models.ConversationMessage(
        research_id=research_id,
        role="assistant",
        content=result.response_text,
        action_taken=result.action_taken,
    )
    db.add(assistant_message)
    db.commit()

    return ChatMessageResponse(
        response=result.response_text,
        action_taken=result.action_taken,
        state_changes=result.state_changes,
        suggestions=result.suggestions,
    )


@router.get(
    "/research/{research_id}/chat/history",
    response_model=List[ConversationMessageResponse],
    tags=["conversation"],
)
def get_chat_history(
    research_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Get conversation history for a research session.

    Returns all messages exchanged between user and assistant.
    """
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    messages = db.query(models.ConversationMessage).filter(
        models.ConversationMessage.research_id == research_id
    ).order_by(
        models.ConversationMessage.timestamp
    ).offset(skip).limit(limit).all()

    return messages


@router.websocket("/ws/research/{research_id}")
async def websocket_research_progress(
    websocket: WebSocket,
    research_id: int,
):
    """
    WebSocket endpoint for real-time research progress updates.

    Streams events as the research progresses:
    - status_change: Research status updates
    - source_added: New source collected
    - finding_created: New finding synthesized
    - error: Error messages
    - completed: Research completed
    """
    await ws_manager.connect(websocket, research_id)
    try:
        await websocket.send_json({
            "event_type": "connected",
            "data": {
                "research_id": research_id,
                "message": "WebSocket connection established",
            },
            "timestamp": asyncio.get_event_loop().time(),
        })

        while True:
            try:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for research {research_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket, research_id)
