import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app import models
from app.schemas import (
    ResearchCreate,
    ResearchResponse,
    ResearchSourceResponse,
    ResearchSourceCreate,
    ResearchSourceUpdate,
    ResearchDocumentResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    ConversationMessageResponse,
)
from app.agents.orchestrator import run_research_workflow
from app.agents.intent_router import route_user_intent
from app.memory.research_state import Citation

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Global flag to control background worker
_background_worker_running = False
_background_worker_task = None


async def background_task_worker():
    """
    Poll the database for pending research tasks and processes them.
    """
    global _background_worker_running
    logger.info("Background task worker started")

    while _background_worker_running:
        db = next(get_db())
        # Find oldest pending research
        pending_research = db.query(models.Research).filter(
            models.Research.status == "pending"
        ).order_by(models.Research.created_at).first()

        if pending_research:
            logger.info(
                f"Background worker picked up task: id={pending_research.id}")
            # Process in a separate thread to avoid blocking
            await asyncio.to_thread(
                process_research,
                pending_research.id,
                pending_research.query
            )
        else:
            # No pending tasks, wait before checking again
            await asyncio.sleep(2)
        db.close()

    logger.info("Background task worker stopped")


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _background_worker_running, _background_worker_task

    # Database tables are now managed by Alembic migrations
    # Run: docker compose exec app alembic upgrade head
    # Base.metadata.create_all(bind=db_module.engine)

    # Start background worker
    _background_worker_running = True
    _background_worker_task = asyncio.create_task(background_task_worker())
    logger.info("Application startup complete with background worker")

    yield

    # Stop background worker
    logger.info("Shutting down background worker...")
    _background_worker_running = False
    if _background_worker_task:
        await _background_worker_task
    logger.info("Background worker stopped")


app = FastAPI(
    title="LLM Researcher",
    description=(
        "An autonomous researcher agent powered by "
        "LangChain and LangGraph"
    ),
    version="2.0.0",
    lifespan=lifespan,
)


def _save_citations_to_db(
    db: Session,
    research_id: int,
    citations: list[Citation]
):
    """Save citations to the database as ResearchSource records."""
    for citation in citations:
        source = models.ResearchSource(
            research_id=research_id,
            url=citation.url,
            title=citation.title,
            author=citation.author,
            content_snippet=(
                citation.snippet[:2000] if citation.snippet else None
            ),
            source_type=citation.source_type.value,
            relevance_score=citation.relevance_score,
        )
        db.add(source)


def process_research(research_id: int, query: str):
    """
    Background task to run the research workflow.

    This runs the LangGraph workflow and saves results to the database.
    """
    logger.info(f"Starting research task: id={research_id}")
    db = next(get_db())
    # Atomically claim this task by updating status from
    # 'pending' to 'planning' to prevent race conditions
    rows_updated = db.query(models.Research).filter(
        models.Research.id == research_id,
        models.Research.status == "pending"
    ).update({"status": "planning"}, synchronize_session=False)
    db.commit()

    if rows_updated == 0:
        logger.info(
            f"Research id={research_id} already claimed or "
            f"not pending, skipping"
        )
        db.close()
        return

    research = db.query(models.Research).filter(
        models.Research.id == research_id).first()
    if not research:
        logger.warning(f"Research id={research_id} not found in database")
        db.close()
        return

    # Run the async workflow in a new event loop
    logger.debug(f"Running research workflow for id={research_id}")
    final_state = asyncio.run(
        run_research_workflow(research_id, query)
    )

    logger.info(f"Research completed for id={research_id}")

    # Save results
    research.result = final_state.final_document or final_state.draft
    research.status = final_state.status
    research.state_json = final_state.to_dict()

    # Save citations as sources
    _save_citations_to_db(db, research_id, final_state.citations)

    db.commit()
    logger.debug(
        f"Research status updated in database for id={research_id}")
    db.close()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "llm-researcher"}


@app.post(
    "/research",
    response_model=ResearchResponse,
    status_code=201,
    tags=["research"]
)
def create_research(
    payload: ResearchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    research = models.Research(query=payload.query, status="pending")
    db.add(research)
    db.commit()
    db.refresh(research)
    background_tasks.add_task(process_research, research.id, research.query)
    return research


@app.get(
    "/research",
    response_model=List[ResearchResponse],
    tags=["research"]
)
def list_research(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    return db.query(models.Research).offset(skip).limit(limit).all()


@app.get(
    "/research/{research_id}",
    response_model=ResearchResponse,
    tags=["research"]
)
def get_research(research_id: int, db: Session = Depends(get_db)):
    research = db.query(models.Research).filter(
        models.Research.id == research_id).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@app.get(
    "/research/{research_id}/sources",
    response_model=List[ResearchSourceResponse],
    tags=["research"]
)
def get_research_sources(
    research_id: int,
    source_type: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get sources with optional filtering.

    Args:
        research_id: ID of the research project
        source_type: Filter by source type (web, arxiv, wikipedia, etc.)
        tag: Filter by tag (sources that have this tag)
        search: Search in title, author, or content snippet
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
    """
    research = db.query(models.Research).filter(
        models.Research.id == research_id).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Build query with filters
    query = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    )

    if source_type:
        query = query.filter(models.ResearchSource.source_type == source_type)

    if tag:
        # Filter sources that have this tag in their tags JSON array
        # Using PostgreSQL's @> operator to check if JSON contains value
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy import cast
        query = query.filter(
            cast(models.ResearchSource.tags, JSONB).contains([tag])
        )

    if search:
        # Search in title, author, or content snippet
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.ResearchSource.title.ilike(search_pattern)) |
            (models.ResearchSource.author.ilike(search_pattern)) |
            (models.ResearchSource.content_snippet.ilike(search_pattern))
        )

    return query.offset(skip).limit(limit).all()


@app.post(
    "/research/{research_id}/sources",
    response_model=ResearchSourceResponse,
    status_code=201,
    tags=["research"]
)
def add_research_source(
    research_id: int,
    payload: ResearchSourceCreate,
    db: Session = Depends(get_db)
):
    """Manually add a source to the research knowledge base."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Create new source
    source = models.ResearchSource(
        research_id=research_id,
        url=payload.url,
        title=payload.title,
        author=payload.author,
        content_snippet=payload.content_snippet,
        source_type=payload.source_type,
        relevance_score=payload.relevance_score,
        user_notes=payload.user_notes,
        tags=payload.tags,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@app.patch(
    "/research/{research_id}/sources/{source_id}",
    response_model=ResearchSourceResponse,
    tags=["research"]
)
def update_research_source(
    research_id: int,
    source_id: int,
    payload: ResearchSourceUpdate,
    db: Session = Depends(get_db)
):
    """Update a source's notes, tags, title, or relevance score."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Find source
    source = db.query(models.ResearchSource).filter(
        models.ResearchSource.id == source_id,
        models.ResearchSource.research_id == research_id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Update fields (only if provided in payload)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)
    return source


@app.delete(
    "/research/{research_id}/sources/{source_id}",
    status_code=204,
    tags=["research"]
)
def delete_research_source(
    research_id: int,
    source_id: int,
    db: Session = Depends(get_db)
):
    """Remove a source from the research knowledge base."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Find and delete source
    source = db.query(models.ResearchSource).filter(
        models.ResearchSource.id == source_id,
        models.ResearchSource.research_id == research_id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    db.delete(source)
    db.commit()
    return None


@app.get(
    "/research/{research_id}/document",
    response_model=ResearchDocumentResponse,
    tags=["research"]
)
def get_research_document(research_id: int, db: Session = Depends(get_db)):
    """Get the full research document with all sources."""
    research = db.query(models.Research).filter(
        models.Research.id == research_id).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    return ResearchDocumentResponse(
        id=research.id,
        query=research.query,
        document=research.result,
        status=research.status,
        sources=[ResearchSourceResponse.model_validate(
            s) for s in research.sources],
        created_at=research.created_at,
        updated_at=research.updated_at,
    )


@app.post(
    "/research/{research_id}/chat",
    response_model=ChatMessageResponse,
    tags=["conversation"]
)
def chat_with_research(
    research_id: int,
    payload: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Chat with the research assistant. Main interaction endpoint.

    This endpoint handles all user interactions with the research assistant,
    including research requests, questions, knowledge base management, etc.
    The AI will classify the intent and route to the appropriate handler.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Save user message
    user_message = models.ConversationMessage(
        research_id=research_id,
        role="user",
        content=payload.message
    )
    db.add(user_message)
    db.commit()

    # Route intent
    logger.info(f"Processing chat message for research {research_id}")
    intent_result = route_user_intent(payload.message)

    # Execute action based on intent
    response_text = ""
    action_taken = None
    state_changes = {}
    suggestions = []

    if intent_result.intent == "research":
        # Extract topic from entities
        topic = intent_result.entities.get("topic", payload.message)

        # Trigger research workflow in background
        background_tasks.add_task(process_research, research_id, topic)

        response_text = (
            f"I'll start researching '{topic}' for you. "
            f"This will involve searching multiple sources and "
            f"collecting relevant information. "
            f"I'll update your knowledge base as I find new sources."
        )
        action_taken = "research_initiated"
        state_changes = {"status": "researching", "new_query": topic}
        suggestions = [
            "Check research status",
            "View collected sources",
            "Ask me questions about the findings"
        ]

        # Update research status
        research.status = "researching"
        db.commit()

    elif intent_result.intent == "question":
        # Query existing knowledge base
        question = intent_result.entities.get(
            "question_text", payload.message
        )

        # For now, provide a basic response
        # TODO: Implement RAG-based answering from knowledge base
        source_count = len(research.sources)
        if source_count > 0:
            response_text = (
                f"I found {source_count} source(s) in your knowledge base. "
                "Based on the collected research, I'll analyze the "
                "information and provide an answer. "
                "(Note: Full RAG implementation coming soon)"
            )
            action_taken = "question_answered"
        else:
            response_text = (
                "I don't have any sources in the knowledge base yet "
                "for this research. Would you like me to research "
                "this topic first?"
            )
            action_taken = "question_no_sources"
            suggestions = [f"Research {question}"]

    elif intent_result.intent == "browse":
        # Show knowledge base items
        sources = db.query(models.ResearchSource).filter(
            models.ResearchSource.research_id == research_id
        ).all()

        if sources:
            response_text = (
                f"I found {len(sources)} source(s) in your knowledge base:\n\n"
            )
            for i, source in enumerate(sources[:5], 1):
                response_text += (
                    f"{i}. [{source.source_type}] {source.title}\n"
                    f"   URL: {source.url}\n\n"
                )
            if len(sources) > 5:
                response_text += f"... and {len(sources) - 5} more sources."
        else:
            response_text = (
                "Your knowledge base is currently empty. "
                "Start by asking me to research a topic or "
                "manually add sources."
            )
        action_taken = "browse_sources"

    elif intent_result.intent == "status":
        # Show research state
        response_text = (
            f"**Research Status**\n\n"
            f"Query: {research.query}\n"
            f"Status: {research.status}\n"
            f"Sources collected: {len(research.sources)}\n"
            f"Conversations: {len(research.conversations)}\n"
            f"Created: {research.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        )
        action_taken = "status_check"
        suggestions = [
            "View all sources",
            "Continue research",
            "Generate a summary"
        ]

    elif intent_result.intent == "generate":
        # Generate document from knowledge base
        format_type = intent_result.entities.get("format", "summary")

        if len(research.sources) == 0:
            response_text = (
                "I can't generate a document yet because your "
                "knowledge base is empty. "
                "Please add sources or research a topic first."
            )
            action_taken = "generate_failed_no_sources"
        else:
            response_text = (
                f"I'll generate a {format_type} from your knowledge base. "
                f"This will synthesize information from "
                f"{len(research.sources)} source(s). "
                f"(Note: Full generation implementation coming soon)"
            )
            action_taken = "generate_initiated"
            state_changes = {"generating": format_type}

    elif intent_result.intent == "add":
        # User wants to manually add a source
        response_text = (
            "I can help you add sources to your knowledge base. "
            "Please provide the URL or reference. "
            "(Note: Manual source addition coming soon)"
        )
        action_taken = "add_source_requested"

    elif intent_result.intent == "remove":
        # User wants to remove a source
        response_text = (
            "I can help you remove sources from your knowledge base. "
            "(Note: Source removal coming soon)"
        )
        action_taken = "remove_source_requested"

    elif intent_result.intent == "edit":
        # User wants to edit knowledge base items
        response_text = (
            "I can help you edit items in your knowledge base. "
            "(Note: Editing functionality coming soon)"
        )
        action_taken = "edit_requested"

    else:  # general or unknown intent
        response_text = (
            "I'm your research assistant. I can help you:\n\n"
            "• Research topics and collect sources\n"
            "• Answer questions about your research\n"
            "• Browse and manage your knowledge base\n"
            "• Generate documents from your research\n\n"
            "What would you like to do?"
        )
        action_taken = "general_help"
        suggestions = [
            "Research a topic",
            "Show my sources",
            "Check status"
        ]

    # Save assistant response
    assistant_message = models.ConversationMessage(
        research_id=research_id,
        role="assistant",
        content=response_text,
        action_taken=action_taken
    )
    db.add(assistant_message)
    db.commit()

    return ChatMessageResponse(
        response=response_text,
        action_taken=action_taken,
        state_changes=state_changes if state_changes else None,
        suggestions=suggestions if suggestions else None
    )


@app.get(
    "/research/{research_id}/chat/history",
    response_model=List[ConversationMessageResponse],
    tags=["conversation"]
)
def get_chat_history(
    research_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get conversation history for a research session.

    Returns all messages exchanged between user and assistant.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Get messages
    messages = db.query(models.ConversationMessage).filter(
        models.ConversationMessage.research_id == research_id
    ).order_by(
        models.ConversationMessage.timestamp
    ).offset(skip).limit(limit).all()

    return messages
