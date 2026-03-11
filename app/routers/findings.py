"""
Findings router - CRUD endpoints for research findings.

Handles creating, listing, updating, and deleting research findings
(synthesized results linked to sources).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    ResearchFindingCreate,
    ResearchFindingUpdate,
    ResearchFindingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


def _get_research_or_404(
    research_id: int, db: Session
) -> models.Research:
    """Fetch research by ID or raise 404."""
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@router.get(
    "/research/{research_id}/findings",
    response_model=List[ResearchFindingResponse],
)
def get_research_findings(
    research_id: int,
    source_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get findings with optional filtering and sorting.

    Args:
        research_id: ID of the research project
        source_id: Filter by findings that reference this source
        search: Search in finding content
        sort_by: Sort field (created_at)
        sort_order: Sort order (asc, desc)
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
    """
    _get_research_or_404(research_id, db)

    query = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    )

    if source_id:
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy import cast
        query = query.filter(
            cast(models.ResearchFinding.source_ids, JSONB).contains([source_id])
        )

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            models.ResearchFinding.content.ilike(search_pattern)
        )

    # Apply sorting (only created_at for now)
    if sort_order == "asc":
        query = query.order_by(models.ResearchFinding.created_at.asc())
    else:  # default to desc
        query = query.order_by(models.ResearchFinding.created_at.desc())

    return query.offset(skip).limit(limit).all()


@router.post(
    "/research/{research_id}/findings",
    response_model=ResearchFindingResponse,
    status_code=201,
)
def create_research_finding(
    research_id: int,
    payload: ResearchFindingCreate,
    db: Session = Depends(get_db),
):
    """Create a new finding in the research knowledge base."""
    _get_research_or_404(research_id, db)

    if payload.source_ids:
        for source_id in payload.source_ids:
            source = db.query(models.ResearchSource).filter(
                models.ResearchSource.id == source_id,
                models.ResearchSource.research_id == research_id,
            ).first()
            if not source:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Source ID {source_id} not found in this research"
                    ),
                )

    finding = models.ResearchFinding(
        research_id=research_id,
        content=payload.content,
        source_ids=payload.source_ids,
        created_by="user",
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get(
    "/research/{research_id}/findings/{finding_id}",
    response_model=ResearchFindingResponse,
)
def get_research_finding(
    research_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
):
    """Get a specific finding by ID."""
    _get_research_or_404(research_id, db)

    finding = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.id == finding_id,
        models.ResearchFinding.research_id == research_id,
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    return finding


@router.patch(
    "/research/{research_id}/findings/{finding_id}",
    response_model=ResearchFindingResponse,
)
def update_research_finding(
    research_id: int,
    finding_id: int,
    payload: ResearchFindingUpdate,
    db: Session = Depends(get_db),
):
    """Update a finding's content or linked sources."""
    _get_research_or_404(research_id, db)

    finding = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.id == finding_id,
        models.ResearchFinding.research_id == research_id,
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if payload.source_ids is not None:
        for source_id in payload.source_ids:
            source = db.query(models.ResearchSource).filter(
                models.ResearchSource.id == source_id,
                models.ResearchSource.research_id == research_id,
            ).first()
            if not source:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Source ID {source_id} not found in this research"
                    ),
                )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(finding, field, value)

    db.commit()
    db.refresh(finding)
    return finding


@router.delete(
    "/research/{research_id}/findings/{finding_id}",
    status_code=204,
)
def delete_research_finding(
    research_id: int,
    finding_id: int,
    db: Session = Depends(get_db),
):
    """Delete a finding from the research knowledge base."""
    _get_research_or_404(research_id, db)

    finding = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.id == finding_id,
        models.ResearchFinding.research_id == research_id,
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    db.delete(finding)
    db.commit()
    return None
