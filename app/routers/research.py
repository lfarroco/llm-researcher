"""
Research router - CRUD endpoints for research tasks.

Handles creating, listing, updating, cancelling, and resuming
research tasks.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    ResearchCreate,
    ResearchResponse,
    ResearchUpdate,
    BatchResearchCreate,
    BatchResearchResponse,
)
from app.rate_limiter import check_research_rate_limit
from app.services.research_service import (
    process_research,
    active_research_tasks,
    cancelled_research_ids,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


@router.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "llm-researcher"}


@router.post(
    "/research",
    response_model=ResearchResponse,
    status_code=201,
)
def create_research(
    payload: ResearchCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new research task."""
    client_ip = request.client.host if request.client else "unknown"
    check_research_rate_limit(client_ip)

    research = models.Research(
        query=payload.query,
        user_notes=payload.user_notes,
        status="pending"
    )
    db.add(research)
    db.commit()
    db.refresh(research)
    background_tasks.add_task(process_research, research.id, research.query)
    return research


@router.post(
    "/research/batch",
    response_model=BatchResearchResponse,
    status_code=201,
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
    client_ip = request.client.host if request.client else "unknown"
    check_research_rate_limit(client_ip)

    if not payload.queries:
        raise HTTPException(
            status_code=400,
            detail="At least one query is required"
        )

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
        db.flush()
        created_research.append(research)

    db.commit()

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


@router.get(
    "/research",
    response_model=List[ResearchResponse],
)
def list_research(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List research projects with optional filtering.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        status: Filter by status (pending, researching, completed, etc.)
        search: Search in query and user_notes fields
    """
    query = db.query(models.Research)

    if status:
        query = query.filter(models.Research.status == status)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.Research.query.ilike(search_pattern))
            | (models.Research.user_notes.ilike(search_pattern))
        )

    return query.order_by(
        models.Research.created_at.desc()
    ).offset(skip).limit(limit).all()


@router.get(
    "/research/{research_id}",
    response_model=ResearchResponse,
)
def get_research(research_id: int, db: Session = Depends(get_db)):
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@router.patch(
    "/research/{research_id}",
    response_model=ResearchResponse,
)
def update_research(
    research_id: int,
    payload: ResearchUpdate,
    db: Session = Depends(get_db),
):
    """
    Update research query, user notes, or tags.

    Allows partial updates - only provided fields will be updated.
    """
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    if payload.query is not None:
        research.query = payload.query

    db.commit()
    db.refresh(research)
    return research


@router.post("/research/{research_id}/cancel")
def cancel_research(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Cancel an ongoing research task.

    Marks the research for cancellation. The workflow will stop
    at the next checkpoint and update status to 'cancelled'.
    """
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    if research.status not in ["pending", "planning", "researching"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel research with status: {research.status}"
        )

    cancelled_research_ids.add(research_id)

    if research_id in active_research_tasks:
        task = active_research_tasks[research_id]
        task.cancel()

    logger.info(f"Research {research_id} marked for cancellation")

    return {
        "research_id": research_id,
        "message": "Research cancellation requested",
        "current_status": research.status,
    }


@router.post("/research/{research_id}/resume")
async def resume_research(
    research_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Resume a cancelled or failed research task.

    Restarts the research workflow from the last checkpoint.
    """
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    if research.status not in ["cancelled", "error", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume research with status: {research.status}"
        )

    research.status = "pending"
    db.commit()

    cancelled_research_ids.discard(research_id)

    background_tasks.add_task(
        process_research, research_id, research.query, resume=True,
    )

    logger.info(f"Research {research_id} queued for resumption")

    return {
        "research_id": research_id,
        "message": "Research resumption queued",
        "status": "pending",
    }


@router.delete("/research/{research_id}", status_code=204)
def delete_research(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Delete a research task and all associated data."""
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")

    # Cancel any active task before deleting
    cancelled_research_ids.add(research_id)
    if research_id in active_research_tasks:
        active_research_tasks[research_id].cancel()

    db.delete(research)
    db.commit()
    logger.info(f"Research {research_id} deleted")
