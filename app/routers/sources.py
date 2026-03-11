"""
Sources router - CRUD endpoints for research sources.

Handles creating, listing, updating, and deleting research sources
(citations in the knowledge base).
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    ResearchSourceResponse,
    ResearchSourceCreate,
    ResearchSourceUpdate,
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
    "/research/{research_id}/sources",
    response_model=List[ResearchSourceResponse],
)
def get_research_sources(
    research_id: int,
    source_type: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get sources with optional filtering and sorting.

    Args:
        research_id: ID of the research project
        source_type: Filter by source type (web, arxiv, wikipedia, etc.)
        tag: Filter by tag (sources that have this tag)
        search: Search in title, author, or content snippet
        sort_by: Sort field (accessed_at, title)
        sort_order: Sort order (asc, desc)
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
    """
    _get_research_or_404(research_id, db)

    query = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    )

    if source_type:
        query = query.filter(
            models.ResearchSource.source_type == source_type
        )

    if tag:
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy import cast
        query = query.filter(
            cast(models.ResearchSource.tags, JSONB).contains([tag])
        )

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.ResearchSource.title.ilike(search_pattern))
            | (models.ResearchSource.author.ilike(search_pattern))
            | (models.ResearchSource.content_snippet.ilike(search_pattern))
        )

    # Apply sorting
    if sort_by == "title":
        order_column = models.ResearchSource.title
    else:  # default to accessed_at
        order_column = models.ResearchSource.accessed_at

    if sort_order == "asc":
        query = query.order_by(order_column.asc())
    else:  # default to desc
        query = query.order_by(order_column.desc())

    return query.offset(skip).limit(limit).all()


@router.post(
    "/research/{research_id}/sources",
    response_model=ResearchSourceResponse,
    status_code=201,
)
def add_research_source(
    research_id: int,
    payload: ResearchSourceCreate,
    db: Session = Depends(get_db),
):
    """Manually add a source to the research knowledge base."""
    _get_research_or_404(research_id, db)

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


@router.patch(
    "/research/{research_id}/sources/{source_id}",
    response_model=ResearchSourceResponse,
)
def update_research_source(
    research_id: int,
    source_id: int,
    payload: ResearchSourceUpdate,
    db: Session = Depends(get_db),
):
    """Update a source's notes, tags, title, or relevance score."""
    _get_research_or_404(research_id, db)

    source = db.query(models.ResearchSource).filter(
        models.ResearchSource.id == source_id,
        models.ResearchSource.research_id == research_id,
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)
    return source


@router.delete(
    "/research/{research_id}/sources/{source_id}",
    status_code=204,
)
def delete_research_source(
    research_id: int,
    source_id: int,
    db: Session = Depends(get_db),
):
    """Remove a source from the research knowledge base."""
    _get_research_or_404(research_id, db)

    source = db.query(models.ResearchSource).filter(
        models.ResearchSource.id == source_id,
        models.ResearchSource.research_id == research_id,
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    db.delete(source)
    db.commit()
    return None
