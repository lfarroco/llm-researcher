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


# Global flag to control background worker
_background_worker_running = False
_background_worker_task = None


async def background_task_worker():
    """
    Continuously polls the database for pending research tasks and processes them.
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

    Base.metadata.create_all(bind=db_module.engine)

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
    # Atomically claim this task by updating status from 'pending' to 'planning'
    # This prevents race conditions between multiple workers
    rows_updated = db.query(models.Research).filter(
        models.Research.id == research_id,
        models.Research.status == "pending"
    ).update({"status": "planning"}, synchronize_session=False)
    db.commit()

    if rows_updated == 0:
        logger.info(
            f"Research id={research_id} already claimed or not pending, skipping")
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
