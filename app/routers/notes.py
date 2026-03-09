"""
Notes router - CRUD endpoints for research notes.

Research notes act as the evolving memory / cognitive workspace
shared by all agents and the user during a research workflow.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    ResearchNoteCreate,
    ResearchNoteUpdate,
    ResearchNoteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"])


def _get_research_or_404(
    research_id: int, db: Session
) -> models.Research:
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@router.get(
    "/research/{research_id}/notes",
    response_model=List[ResearchNoteResponse],
)
def get_research_notes(
    research_id: int,
    agent: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """Get all notes for a research project, optionally filtered."""
    _get_research_or_404(research_id, db)
    query = db.query(models.ResearchNote).filter(
        models.ResearchNote.research_id == research_id
    )
    if agent:
        query = query.filter(models.ResearchNote.agent == agent)
    if category:
        query = query.filter(models.ResearchNote.category == category)
    return query.order_by(models.ResearchNote.created_at).all()


@router.post(
    "/research/{research_id}/notes",
    response_model=ResearchNoteResponse,
    status_code=201,
)
def create_research_note(
    research_id: int,
    note: ResearchNoteCreate,
    db: Session = Depends(get_db),
):
    """Create a new research note (typically from the user)."""
    _get_research_or_404(research_id, db)
    db_note = models.ResearchNote(
        research_id=research_id,
        agent=note.agent,
        category=note.category,
        content=note.content,
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


@router.patch(
    "/research/{research_id}/notes/{note_id}",
    response_model=ResearchNoteResponse,
)
def update_research_note(
    research_id: int,
    note_id: int,
    update: ResearchNoteUpdate,
    db: Session = Depends(get_db),
):
    """Update an existing research note."""
    _get_research_or_404(research_id, db)
    db_note = db.query(models.ResearchNote).filter(
        models.ResearchNote.id == note_id,
        models.ResearchNote.research_id == research_id,
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")

    if update.content is not None:
        db_note.content = update.content
    if update.category is not None:
        db_note.category = update.category
    db.commit()
    db.refresh(db_note)
    return db_note


@router.delete(
    "/research/{research_id}/notes/{note_id}",
    status_code=204,
)
def delete_research_note(
    research_id: int,
    note_id: int,
    db: Session = Depends(get_db),
):
    """Delete a research note."""
    _get_research_or_404(research_id, db)
    db_note = db.query(models.ResearchNote).filter(
        models.ResearchNote.id == note_id,
        models.ResearchNote.research_id == research_id,
    ).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(db_note)
    db.commit()
