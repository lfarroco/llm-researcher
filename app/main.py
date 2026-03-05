import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Set

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
    ResearchFindingCreate,
    ResearchFindingUpdate,
    ResearchFindingResponse,
    ResearchStateResponse,
    ResearchPlanResponse,
    ResearchPlanUpdate,
    BatchResearchCreate,
    BatchResearchResponse,
)
from app.agents.orchestrator import run_research_workflow
from app.agents.intent_router import route_user_intent
from app.memory.research_state import Citation
from app.websocket_manager import manager as ws_manager
from app.rate_limiter import check_research_rate_limit

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# Global flag to control background worker
_background_worker_running = False
_background_worker_task = None

# Track active research tasks for cancellation
_active_research_tasks: Dict[int, asyncio.Task] = {}
_cancelled_research_ids: Set[int] = set()


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


async def process_research_async(research_id: int, query: str):
    """
    Async background task to run the research workflow with progress streaming.

    This runs the LangGraph workflow and saves results to the database.
    Emits WebSocket events for progress tracking.
    """
    logger.info(f"Starting research task: id={research_id}")

    try:
        # Broadcast status change
        await ws_manager.broadcast_status_change(
            research_id, "planning", "Initializing research workflow"
        )

        db = next(get_db())

        # Atomically claim this task
        rows_updated = db.query(models.Research).filter(
            models.Research.id == research_id,
            models.Research.status == "pending"
        ).update({"status": "planning"}, synchronize_session=False)
        db.commit()

        if rows_updated == 0:
            logger.info(
                f"Research id={research_id} already claimed or not pending"
            )
            db.close()
            return

        research = db.query(models.Research).filter(
            models.Research.id == research_id
        ).first()
        if not research:
            logger.warning(f"Research id={research_id} not found")
            db.close()
            return

        # Check for cancellation
        if research_id in _cancelled_research_ids:
            logger.info(f"Research {research_id} was cancelled before start")
            research.status = "cancelled"
            db.commit()
            db.close()
            await ws_manager.broadcast_status_change(
                research_id, "cancelled", "Research was cancelled"
            )
            _cancelled_research_ids.discard(research_id)
            return

        # Update status to researching
        research.status = "researching"
        db.commit()
        await ws_manager.broadcast_status_change(
            research_id, "researching", "Running research workflow"
        )

        # Run the async workflow
        logger.debug(f"Running research workflow for id={research_id}")
        final_state = await run_research_workflow(research_id, query)

        # Check for cancellation after workflow
        if research_id in _cancelled_research_ids:
            logger.info(f"Research {research_id} was cancelled")
            research.status = "cancelled"
            db.commit()
            db.close()
            await ws_manager.broadcast_status_change(
                research_id, "cancelled", "Research was cancelled"
            )
            _cancelled_research_ids.discard(research_id)
            return

        logger.info(f"Research completed for id={research_id}")

        # Save results
        research.result = final_state.final_document or final_state.draft
        research.status = final_state.status
        research.state_json = final_state.to_dict()

        # Save citations as sources
        _save_citations_to_db(db, research_id, final_state.citations)

        db.commit()

        # Broadcast completion
        await ws_manager.broadcast_completion(
            research_id,
            {
                "status": research.status,
                "sources_count": len(final_state.citations),
                "has_document": bool(research.result)
            }
        )

        logger.debug(f"Research status updated for id={research_id}")
        db.close()

    except Exception as e:
        logger.error(f"Error in research {research_id}: {e}")
        await ws_manager.broadcast_error(research_id, str(e))
        try:
            db = next(get_db())
            research = db.query(models.Research).filter(
                models.Research.id == research_id
            ).first()
            if research:
                research.status = "error"
                db.commit()
            db.close()
        except Exception:
            pass
    finally:
        # Clean up task tracking
        if research_id in _active_research_tasks:
            del _active_research_tasks[research_id]


def process_research(research_id: int, query: str):
    """
    Synchronous wrapper for process_research_async.
    Used by background task worker.
    """
    asyncio.run(process_research_async(research_id, query))


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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new research task."""
    # Check rate limit
    client_ip = request.client.host if request.client else "unknown"
    check_research_rate_limit(client_ip)

    research = models.Research(query=payload.query, status="pending")
    db.add(research)
    db.commit()
    db.refresh(research)
    background_tasks.add_task(process_research, research.id, research.query)
    return research


@app.post(
    "/research/batch",
    response_model=BatchResearchResponse,
    status_code=201,
    tags=["research"]
)
def create_batch_research(
    payload: BatchResearchCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create multiple research tasks at once.

    Useful for processing multiple queries simultaneously.
    Each query will be processed independently.
    """
    # Check rate limit
    client_ip = request.client.host if request.client else "unknown"
    check_research_rate_limit(client_ip)

    if not payload.queries:
        raise HTTPException(
            status_code=400,
            detail="At least one query is required"
        )

    # Limit batch size
    max_batch_size = 10
    if len(payload.queries) > max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size cannot exceed {max_batch_size} queries"
        )

    created_research = []

    for query in payload.queries:
        research = models.Research(query=query, status="pending")
        db.add(research)
        db.flush()  # Get ID without committing
        created_research.append(research)

    db.commit()

    # Refresh all and queue for processing
    for research in created_research:
        db.refresh(research)
        background_tasks.add_task(
            process_research, research.id, research.query
        )

    logger.info(
        f"Created batch of {len(created_research)} research tasks"
    )

    return BatchResearchResponse(
        created_count=len(created_research),
        research_ids=[r.id for r in created_research],
        research_items=[
            ResearchResponse.model_validate(r) for r in created_research
        ]
    )


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
    "/research/{research_id}/findings",
    response_model=List[ResearchFindingResponse],
    tags=["research"]
)
def get_research_findings(
    research_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all findings for a research project."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    findings = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).order_by(
        models.ResearchFinding.created_at.desc()
    ).offset(skip).limit(limit).all()

    return findings


@app.post(
    "/research/{research_id}/findings",
    response_model=ResearchFindingResponse,
    status_code=201,
    tags=["research"]
)
def create_research_finding(
    research_id: int,
    payload: ResearchFindingCreate,
    db: Session = Depends(get_db)
):
    """Create a new finding in the research knowledge base."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Validate that source_ids exist if provided
    if payload.source_ids:
        for source_id in payload.source_ids:
            source = db.query(models.ResearchSource).filter(
                models.ResearchSource.id == source_id,
                models.ResearchSource.research_id == research_id
            ).first()
            if not source:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source ID {source_id} not found in this research"
                )

    # Create finding
    finding = models.ResearchFinding(
        research_id=research_id,
        content=payload.content,
        source_ids=payload.source_ids,
        created_by="user"
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@app.get(
    "/research/{research_id}/findings/{finding_id}",
    response_model=ResearchFindingResponse,
    tags=["research"]
)
def get_research_finding(
    research_id: int,
    finding_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific finding by ID."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    finding = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.id == finding_id,
        models.ResearchFinding.research_id == research_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    return finding


@app.patch(
    "/research/{research_id}/findings/{finding_id}",
    response_model=ResearchFindingResponse,
    tags=["research"]
)
def update_research_finding(
    research_id: int,
    finding_id: int,
    payload: ResearchFindingUpdate,
    db: Session = Depends(get_db)
):
    """Update a finding's content or linked sources."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Find the finding
    finding = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.id == finding_id,
        models.ResearchFinding.research_id == research_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Validate source_ids if provided
    if payload.source_ids is not None:
        for source_id in payload.source_ids:
            source = db.query(models.ResearchSource).filter(
                models.ResearchSource.id == source_id,
                models.ResearchSource.research_id == research_id
            ).first()
            if not source:
                raise HTTPException(
                    status_code=400,
                    detail=f"Source ID {source_id} not found in this research"
                )

    # Update fields
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(finding, field, value)

    db.commit()
    db.refresh(finding)
    return finding


@app.delete(
    "/research/{research_id}/findings/{finding_id}",
    status_code=204,
    tags=["research"]
)
def delete_research_finding(
    research_id: int,
    finding_id: int,
    db: Session = Depends(get_db)
):
    """Delete a finding from the research knowledge base."""
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Find and delete the finding
    finding = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.id == finding_id,
        models.ResearchFinding.research_id == research_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    db.delete(finding)
    db.commit()
    return None


@app.get(
    "/research/{research_id}/state",
    response_model=ResearchStateResponse,
    tags=["research"]
)
def get_research_state(
    research_id: int,
    db: Session = Depends(get_db)
):
    """Get the current AI state for a research project.

    Returns current status, pending/completed queries, reasoning log,
    and statistics about the knowledge base.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Parse state from JSON
    state_data = research.state_json or {}

    # Count sources and findings
    source_count = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).count()

    finding_count = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).count()

    # Extract sub-queries and findings from state
    sub_queries = state_data.get("sub_queries", [])
    findings = state_data.get("findings", {})

    # Determine which queries are completed (have findings)
    completed_queries = [q for q in sub_queries if q in findings]
    pending_queries = [q for q in sub_queries if q not in findings]

    # Extract reasoning log (AI decision history)
    reasoning_log = state_data.get("ai_reasoning", [])

    # Build current plan
    current_plan = None
    if sub_queries:
        current_plan = {
            "main_query": state_data.get("query", research.query),
            "refined_question": state_data.get("refined_question"),
            "total_queries": len(sub_queries),
            "completed": len(completed_queries),
            "pending": len(pending_queries),
            "outline": state_data.get("outline")
        }

    return ResearchStateResponse(
        status=research.status,
        current_plan=current_plan,
        pending_queries=pending_queries,
        completed_queries=completed_queries,
        reasoning_log=reasoning_log,
        last_activity=research.updated_at,
        source_count=source_count,
        finding_count=finding_count
    )


@app.get(
    "/research/{research_id}/plan",
    response_model=ResearchPlanResponse,
    tags=["research"]
)
def get_research_plan(
    research_id: int,
    db: Session = Depends(get_db)
):
    """Get the research plan with progress details.

    Returns the main query, refined question, sub-queries with
    progress tracking, and document outline.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Parse state from JSON
    state_data = research.state_json or {}

    # Extract plan components
    sub_queries = state_data.get("sub_queries", [])
    findings = state_data.get("findings", {})

    # Build progress map
    progress = {}
    for query in sub_queries:
        if query in findings:
            progress[query] = {
                "status": "completed",
                "finding": findings[query][:200] + "..." if len(
                    findings[query]
                ) > 200 else findings[query]
            }
        else:
            progress[query] = {
                "status": "pending",
                "finding": None
            }

    return ResearchPlanResponse(
        query=state_data.get("query", research.query),
        refined_question=state_data.get("refined_question"),
        sub_queries=sub_queries,
        progress=progress,
        outline=state_data.get("outline")
    )


@app.patch(
    "/research/{research_id}/plan",
    response_model=ResearchPlanResponse,
    tags=["research"]
)
def update_research_plan(
    research_id: int,
    payload: ResearchPlanUpdate,
    db: Session = Depends(get_db)
):
    """Update the research plan by adding/removing queries.

    Allows users to manually adjust the research direction
    by modifying the list of sub-queries to investigate.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Parse existing state
    state_data = research.state_json or {}
    sub_queries = state_data.get("sub_queries", [])

    # Apply updates
    if payload.add_queries:
        # Add new queries that don't already exist
        for query in payload.add_queries:
            if query not in sub_queries:
                sub_queries.append(query)

    if payload.remove_queries:
        # Remove specified queries
        for query in payload.remove_queries:
            if query in sub_queries:
                sub_queries.remove(query)

    if payload.refined_question is not None:
        state_data["refined_question"] = payload.refined_question

    # Update state
    state_data["sub_queries"] = sub_queries
    research.state_json = state_data

    db.commit()
    db.refresh(research)

    # Return updated plan using the get endpoint logic
    return get_research_plan(research_id, db)


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


@app.websocket("/ws/research/{research_id}")
async def websocket_research_progress(
    websocket: WebSocket,
    research_id: int
):
    """
    WebSocket endpoint for real-time research progress updates.

    Streams events as the research progresses:
    - status_change: Research status updates
    - source_added: New source collected
    - finding_created: New finding synthesized
    - progress: Progress percentage updates
    - error: Error messages
    - completed: Research completed

    Example usage (JavaScript):
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/research/1');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data.event_type, data.data);
    };
    ```
    """
    await ws_manager.connect(websocket, research_id)
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "event_type": "connected",
            "data": {
                "research_id": research_id,
                "message": "WebSocket connection established"
            },
            "timestamp": asyncio.get_event_loop().time()
        })

        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for any client messages (like ping/pong)
                data = await websocket.receive_text()
                # Echo back or handle as needed
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"WebSocket error for research {research_id}: {e}")
    finally:
        await ws_manager.disconnect(websocket, research_id)


@app.post(
    "/research/{research_id}/cancel",
    tags=["research"]
)
def cancel_research(
    research_id: int,
    db: Session = Depends(get_db)
):
    """
    Cancel an ongoing research task.

    Marks the research for cancellation. The workflow will stop
    at the next checkpoint and update status to 'cancelled'.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Check if research is in a cancellable state
    if research.status not in ["pending", "planning", "researching"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel research with status: {research.status}"
        )

    # Mark for cancellation
    _cancelled_research_ids.add(research_id)

    # If there's an active task, try to cancel it
    if research_id in _active_research_tasks:
        task = _active_research_tasks[research_id]
        task.cancel()

    logger.info(f"Research {research_id} marked for cancellation")

    return {
        "research_id": research_id,
        "message": "Research cancellation requested",
        "current_status": research.status
    }


@app.post(
    "/research/{research_id}/resume",
    tags=["research"]
)
async def resume_research(
    research_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Resume a cancelled or failed research task.

    Restarts the research workflow from the last checkpoint.
    """
    # Verify research exists
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Check if research can be resumed
    if research.status not in ["cancelled", "error"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume research with status: {research.status}"
        )

    # Reset status to pending
    research.status = "pending"
    db.commit()

    # Remove from cancelled set if present
    _cancelled_research_ids.discard(research_id)

    # Add to background tasks
    background_tasks.add_task(process_research, research_id, research.query)

    logger.info(f"Research {research_id} queued for resumption")

    return {
        "research_id": research_id,
        "message": "Research resumption queued",
        "status": "pending"
    }
