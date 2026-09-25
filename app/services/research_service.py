"""
Research service - background task processing and DB persistence.

Extracted from main.py to keep workflow orchestration logic separate
from HTTP endpoint definitions.

Persistence here is **idempotent and additive**: the knowledge base is the
durable record of truth, and ``Research.state_json`` is disposable execution
context. Saving the same citation, finding, or agent note twice is a no-op, and
nothing user-authored is ever deleted by running or resuming a workflow.
"""

import asyncio
import hashlib
import logging
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.agents.orchestrator import run_research_workflow
from app.memory.research_state import (
    Citation, ResearchNote, ResearchState, SubQueryResult,
)
from app.services.source_identity import source_identity
from app.services.citation_numbering import renumber_document
from app.services.fulltext import collect_fulltext_evidence
from app.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

# Track active research tasks for cancellation
active_research_tasks: Dict[int, asyncio.Task] = {}
cancelled_research_ids: Set[int] = set()

# A note authored by a human is never rewritten or deduplicated by the
# pipeline. Every other agent value is agent-generated and therefore safe to
# reconcile on re-run.
USER_NOTE_AGENT = "user"


def _content_digest(text: str) -> str:
    """Stable digest of normalized text, used to de-duplicate agent output."""
    collapsed = " ".join((text or "").split()).lower()
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()[:32]


def get_existing_sources_by_identity(
    db: Session,
    research_id: int,
) -> Dict[str, models.ResearchSource]:
    """Return ``dedupe_key -> ResearchSource`` for one research item.

    Rows written before the identity column existed have no key; they are
    keyed on the fly from their URL/title so legacy data still merges.
    """
    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    by_key: Dict[str, models.ResearchSource] = {}
    for source in sources:
        key = source.dedupe_key or source_identity(source.url, title=source.title)
        # Keep the earliest row if duplicates already exist in legacy data;
        # never overwrite an established identity.
        by_key.setdefault(key, source)
    return by_key


def save_citations_to_db(
    db: Session,
    research_id: int,
    citations: list[Citation],
    markers_by_identity: Optional[Dict[str, int]] = None,
) -> Dict[str, models.ResearchSource]:
    """Merge citations into the knowledge base and return them by identity.

    Existing sources are **enriched**, not replaced: a later, better result for
    a source we already have can fill in a missing title/author or raise the
    relevance score, but it cannot clear fields or touch user notes and tags.

    Args:
        markers_by_identity: Optional ``source_identity -> citation marker``
            map from :func:`app.services.citation_numbering.renumber_document`.
            When given, each row's ``citation_marker`` is set to the number the
            finished document uses for it (``None`` for sources the report does
            not cite), which keeps the document and the API in agreement. When
            omitted, existing markers are left untouched.

    Returns:
        Mapping of ``dedupe_key`` to the persisted source row, for callers
        that need to link findings or evidence to sources.
    """
    by_key = get_existing_sources_by_identity(db, research_id)
    merged: Dict[str, models.ResearchSource] = {}

    for citation in citations:
        key = source_identity(citation.url, title=citation.title)
        existing = by_key.get(key)

        snippet = citation.snippet[:2000] if citation.snippet else None

        marker = (
            markers_by_identity.get(key)
            if markers_by_identity is not None
            else None
        )

        if existing is None:
            source = models.ResearchSource(
                research_id=research_id,
                url=citation.url,
                dedupe_key=key,
                title=citation.title,
                author=citation.author,
                content_snippet=snippet,
                source_type=citation.source_type.value,
                relevance_score=citation.relevance_score,
                citation_marker=marker,
            )
            db.add(source)
            by_key[key] = source
            merged[key] = source
            continue

        # The marker belongs to the document that was just finalized, so it is
        # replaced rather than preserved (a re-run may cite a different set).
        if markers_by_identity is not None:
            existing.citation_marker = marker

        # Enrich only. Never blank out data we already hold, and never touch
        # user_notes / tags, which belong to the user.
        if citation.title and not existing.title:
            existing.title = citation.title
        if citation.author and not existing.author:
            existing.author = citation.author
        if snippet and len(snippet) > len(existing.content_snippet or ""):
            existing.content_snippet = snippet
        if citation.relevance_score and (
            citation.relevance_score > (existing.relevance_score or 0.0)
        ):
            existing.relevance_score = citation.relevance_score

        merged[key] = existing

    # Flush so newly added rows get their primary keys before callers use them.
    db.flush()
    return merged


def save_findings_to_db(
    db: Session,
    research_id: int,
    sub_query_results: list[SubQueryResult],
    citations: list[Citation],
    sources_by_identity: Optional[Dict[str, models.ResearchSource]] = None,
) -> None:
    """Merge sub-query findings into the database.

    Findings are identified by their sub-query text, so re-running a research
    updates the existing finding (including its evidence links) rather than
    appending a duplicate. Findings authored by a user are left alone.
    """
    if not sub_query_results:
        return

    # Prefer the identity map produced by save_citations_to_db: it is
    # conflict-free, unlike the URL-keyed dict this used to build.
    if sources_by_identity is None:
        sources_by_identity = get_existing_sources_by_identity(db, research_id)

    value_by_key = {key: src.id for key, src in sources_by_identity.items()}

    existing_findings = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id,
        models.ResearchFinding.created_by != "user",
    ).all()
    finding_by_digest = {
        _content_digest(f.content): f for f in existing_findings
    }

    saved = 0
    for sqr in sub_query_results:
        if sqr.status != "complete" or not sqr.citations:
            continue

        # Resolve evidence links through the identity map. Iterating over
        # identities (not a URL dict) means duplicates cannot shadow each
        # other and ordering cannot change which row is referenced.
        source_ids = []
        for c in sqr.citations:
            key = source_identity(c.url, title=c.title)
            source_id = value_by_key.get(key)
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)

        source_titles = [c.title for c in sqr.citations[:5]]
        content = (
            f"{sqr.sub_query}\n\n"
            f"Supported by {len(sqr.citations)} source(s): "
            + ", ".join(source_titles)
        )

        digest = _content_digest(content)
        existing = finding_by_digest.get(digest)
        if existing is not None:
            existing.source_ids = source_ids
            continue

        finding = models.ResearchFinding(
            research_id=research_id,
            content=content,
            source_ids=source_ids,
            created_by="ai",
        )
        db.add(finding)
        finding_by_digest[digest] = finding
        saved += 1

    logger.debug(
        f"Merged {saved} new finding(s) for research id={research_id}"
    )


def save_notes_to_db(
    db: Session,
    research_id: int,
    notes: list[ResearchNote],
) -> None:
    """Merge agent notes into the database.

    Agent notes are identified by (agent, content), so re-running a workflow
    does not duplicate the running commentary. Notes with ``agent="user"`` are
    authored by a human and are never inserted or modified here.
    """
    existing_notes = db.query(models.ResearchNote).filter(
        models.ResearchNote.research_id == research_id
    ).all()
    seen = {
        (note.agent, _content_digest(note.content)) for note in existing_notes
    }

    saved = 0
    for note in notes:
        if note.agent == USER_NOTE_AGENT:
            # The pipeline never owns user notes; the chat layer writes them.
            continue
        signature = (note.agent, _content_digest(note.content))
        if signature in seen:
            continue
        db.add(models.ResearchNote(
            research_id=research_id,
            agent=note.agent,
            content=note.content,
        ))
        seen.add(signature)
        saved += 1

    logger.debug(
        f"Merged {saved} new research note(s) for research id={research_id}"
    )


async def process_research_async(
    research_id: int, query: str, resume: bool = False,
):
    """
    Async background task to run the research workflow with progress streaming.

    Runs the LangGraph workflow and saves results to the database.
    Emits WebSocket events for progress tracking.

    Args:
        research_id: Database ID for the research task
        query: The research query
        resume: If True, load saved state and resume from last checkpoint
    """
    logger.info(f"Starting research task: id={research_id} (resume={resume})")

    try:
        # Broadcast status change
        await ws_manager.broadcast_status_change(
            research_id, "planning",
            "Resuming research workflow"
            if resume
            else "Initializing research workflow",
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

        # Load saved state for resumption.
        #
        # Nothing is deleted here. The knowledge base (sources, findings,
        # notes) is the durable record and may contain user-authored notes,
        # tags, and source annotations; re-running merges into it through the
        # idempotent save_* helpers instead. Deleting these rows used to
        # destroy user data on every resume, and left the knowledge base empty
        # if the resumed run failed.
        resume_state = None
        if resume and research.state_json:
            try:
                resume_state = ResearchState.from_dict(research.state_json)
                logger.info(
                    f"Loaded saved state for research {research_id}: "
                    f"sub_queries={len(resume_state.sub_queries)}, "
                    f"citations={len(resume_state.citations)}, "
                    f"has_draft={bool(resume_state.draft)}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load saved state for {research_id}, "
                    f"starting fresh: {e}"
                )
                resume_state = None

        # Update status to researching
        research.status = "researching"
        db.commit()
        await ws_manager.broadcast_status_change(
            research_id, "researching",
            "Resuming research workflow"
            if resume_state
            else "Running research workflow",
        )

        # Callback to persist intermediate state during workflow execution
        async def save_intermediate_state(state_dict: dict):
            try:
                db.query(models.Research).filter(
                    models.Research.id == research_id
                ).update(
                    {"state_json": state_dict},
                    synchronize_session=False,
                )
                db.commit()
            except Exception as e:
                logger.warning(
                    f"Failed to save intermediate state for {research_id}: {e}"
                )
                db.rollback()

        # Run the async workflow.
        #
        # It runs in two segments with full-text retrieval in between, so
        # synthesis can quote real paper text instead of only search-result
        # snippets. The second segment resumes from the state the first
        # segment produced (LangGraph's interrupt_after makes this a
        # supported flow rather than a special case).
        logger.debug(f"Running research workflow for id={research_id}")
        search_state = await run_research_workflow(
            research_id, query,
            on_state_update=save_intermediate_state,
            resume_state=resume_state,
            interrupt_after=["chase_references"],
        )

        if search_state.citations and not search_state.draft:
            try:
                search_state.evidence = await collect_fulltext_evidence(
                    db=db,
                    research_id=research_id,
                    query=query,
                    citations=search_state.citations,
                )
                logger.info(
                    f"[FULLTEXT] {len(search_state.evidence)} evidence "
                    f"span(s) available for synthesis"
                )
            except Exception as exc:
                # Grounding is an enhancement; never fail the research
                # because a PDF could not be fetched or parsed.
                logger.warning(
                    f"[FULLTEXT] Evidence retrieval skipped: {exc}"
                )

        final_state = await run_research_workflow(
            research_id, query,
            on_state_update=save_intermediate_state,
            resume_state=search_state,
        )

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

        # Number the citations once, now that every collection wave (search,
        # reference chasing, hypothesis investigation) has finished. The
        # returned map is what pins each source row to the marker the reader
        # sees, so the document and the API cannot disagree.
        final_state.final_document, markers_by_identity = renumber_document(
            final_state.final_document or "", final_state.citations
        )

        # Save results
        research.result = final_state.final_document or final_state.draft
        research.status = final_state.status
        research.state_json = final_state.to_dict()

        # Save citations as sources. This is an idempotent merge that returns
        # the identity map, so findings link to the same rows that survive
        # re-runs instead of resolving URLs through an order-dependent dict.
        sources_by_identity = save_citations_to_db(
            db, research_id, final_state.citations,
            markers_by_identity=markers_by_identity,
        )

        # Save sub-query results as findings
        save_findings_to_db(
            db, research_id,
            final_state.sub_query_results,
            final_state.citations,
            sources_by_identity=sources_by_identity,
        )

        # Save research notes
        if final_state.research_notes:
            save_notes_to_db(db, research_id, final_state.research_notes)

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


def process_research(research_id: int, query: str, resume: bool = False):
    """
    Synchronous wrapper for process_research_async.
    Used by background task worker.
    """
    asyncio.run(process_research_async(research_id, query, resume=resume))
