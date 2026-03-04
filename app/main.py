import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.database import Base, get_db
import app.database as db_module
from app import models
from app.schemas import (
    ResearchCreate,
    ResearchResponse,
    ResearchSourceResponse,
    ResearchDocumentResponse,
)
from app.agents.orchestrator import run_research_workflow
from app.memory.research_state import Citation

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=db_module.engine)
    yield


app = FastAPI(
    title="LLM Researcher",
    description="An autonomous researcher agent powered by LangChain and LangGraph",
    version="2.0.0",
    lifespan=lifespan,
)


def _save_citations_to_db(db: Session, research_id: int, citations: list[Citation]):
    """Save citations to the database as ResearchSource records."""
    for citation in citations:
        source = models.ResearchSource(
            research_id=research_id,
            url=citation.url,
            title=citation.title,
            author=citation.author,
            content_snippet=citation.snippet[:
                                             2000] if citation.snippet else None,
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
    try:
        research = db.query(models.Research).filter(
            models.Research.id == research_id).first()
        if not research:
            logger.warning(f"Research id={research_id} not found in database")
            return

        try:
            # Update status to show we're starting
            research.status = "planning"
            db.commit()

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

        except Exception as e:
            logger.error(
                f"Research failed for id={research_id}: {str(e)}", exc_info=True)
            research.result = f"Research failed: {str(e)}"
            research.status = "failed"

        db.commit()
        logger.debug(
            f"Research status updated in database for id={research_id}")

    finally:
        db.close()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "llm-researcher"}


@app.post("/research", response_model=ResearchResponse, status_code=201, tags=["research"])
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


@app.get("/research", response_model=List[ResearchResponse], tags=["research"])
def list_research(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.query(models.Research).offset(skip).limit(limit).all()


@app.get("/research/{research_id}", response_model=ResearchResponse, tags=["research"])
def get_research(research_id: int, db: Session = Depends(get_db)):
    research = db.query(models.Research).filter(
        models.Research.id == research_id).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research


@app.get("/research/{research_id}/sources", response_model=List[ResearchSourceResponse], tags=["research"])
def get_research_sources(research_id: int, db: Session = Depends(get_db)):
    """Get all sources/citations collected during research."""
    research = db.query(models.Research).filter(
        models.Research.id == research_id).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research.sources


@app.get("/research/{research_id}/document", response_model=ResearchDocumentResponse, tags=["research"])
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
