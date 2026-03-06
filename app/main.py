"""
LLM Researcher - FastAPI Application Entry Point.

This module sets up the FastAPI app, registers routers, and manages
the background task worker. All endpoint logic is delegated to
dedicated router modules in app/routers/.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import get_db
from app import models
from app.services.research_service import process_research

# Import routers
from app.routers import research as research_router
from app.routers import sources as sources_router
from app.routers import findings as findings_router
from app.routers import state as state_router
from app.routers import exports as exports_router
from app.routers import chat as chat_router

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
            await asyncio.to_thread(
                process_research,
                pending_research.id,
                pending_research.query
            )
        else:
            await asyncio.sleep(2)
        db.close()

    logger.info("Background task worker stopped")


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _background_worker_running, _background_worker_task

    # Database tables are now managed by Alembic migrations
    # Run: docker compose exec app alembic upgrade head

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

# Register all routers
app.include_router(research_router.router)
app.include_router(sources_router.router)
app.include_router(findings_router.router)
app.include_router(state_router.router)
app.include_router(exports_router.router)
app.include_router(chat_router.router)
