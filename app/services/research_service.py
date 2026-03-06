"""
Research service - background task processing and DB persistence.

Extracted from main.py to keep workflow orchestration logic separate
from HTTP endpoint definitions.
"""

import asyncio
import logging
from typing import Dict, Set

from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.agents.orchestrator import run_research_workflow
from app.memory.research_state import Citation, SubQueryResult
from app.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

# Track active research tasks for cancellation
active_research_tasks: Dict[int, asyncio.Task] = {}
cancelled_research_ids: Set[int] = set()


def save_citations_to_db(
    db: Session,
    research_id: int,
    citations: list[Citation],
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


def save_findings_to_db(
    db: Session,
    research_id: int,
    sub_query_results: list[SubQueryResult],
    citations: list[Citation],
):
    """Save sub-query findings to the database as ResearchFinding records.

    Each sub-query that completed successfully becomes a finding,
    with references to the source IDs that support it.
    """
    if not sub_query_results:
        return

    # Build a URL -> source DB ID map for linking findings to sources
    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()
    url_to_source_id = {s.url: s.id for s in sources}

    for sqr in sub_query_results:
        if sqr.status != "complete" or not sqr.citations:
            continue

        # Collect the DB source IDs for citations in this sub-query
        source_ids = []
        for c in sqr.citations:
            sid = url_to_source_id.get(c.url)
            if sid:
                source_ids.append(sid)

        # Build a content summary from the sub-query and its sources
        source_titles = [c.title for c in sqr.citations[:5]]
        content = (
            f"{sqr.sub_query}\n\n"
            f"Supported by {len(sqr.citations)} source(s): "
            + ", ".join(source_titles)
        )

        finding = models.ResearchFinding(
            research_id=research_id,
            content=content,
            source_ids=source_ids,
            created_by="ai",
        )
        db.add(finding)

    logger.debug(
        f"Saved {len([s for s in sub_query_results if s.status == 'complete'])} "
        f"findings for research id={research_id}"
    )


async def process_research_async(research_id: int, query: str):
    """
    Async background task to run the research workflow with progress streaming.

    Runs the LangGraph workflow and saves results to the database.
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
        if research_id in cancelled_research_ids:
            logger.info(f"Research {research_id} was cancelled before start")
            research.status = "cancelled"
            db.commit()
            db.close()
            await ws_manager.broadcast_status_change(
                research_id, "cancelled", "Research was cancelled"
            )
            cancelled_research_ids.discard(research_id)
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
        if research_id in cancelled_research_ids:
            logger.info(f"Research {research_id} was cancelled")
            research.status = "cancelled"
            db.commit()
            db.close()
            await ws_manager.broadcast_status_change(
                research_id, "cancelled", "Research was cancelled"
            )
            cancelled_research_ids.discard(research_id)
            return

        logger.info(f"Research completed for id={research_id}")

        # Save results
        research.result = final_state.final_document or final_state.draft
        research.status = final_state.status
        research.state_json = final_state.to_dict()

        # Save citations as sources
        save_citations_to_db(db, research_id, final_state.citations)

        # Save sub-query results as findings
        save_findings_to_db(
            db, research_id,
            final_state.sub_query_results,
            final_state.citations,
        )

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
        if research_id in active_research_tasks:
            del active_research_tasks[research_id]


def process_research(research_id: int, query: str):
    """
    Synchronous wrapper for process_research_async.
    Used by background task worker.
    """
    asyncio.run(process_research_async(research_id, query))
