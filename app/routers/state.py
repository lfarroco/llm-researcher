"""
State router - research state, plan, steps, and knowledge base endpoints.

Handles viewing and updating the internal research state, plans,
agent steps, and knowledge base aggregation.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.schemas import (
    ResearchStateResponse,
    ResearchPlanResponse,
    ResearchPlanUpdate,
    ResearchDocumentResponse,
    ResearchSourceResponse,
    ResearchEntitiesResponse,
)
from app.nlp.entity_extractor import EntityExtractor

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
    "/research/{research_id}/state",
    response_model=ResearchStateResponse,
)
def get_research_state(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Get the current AI state for a research project.

    Returns current status, pending/completed queries, reasoning log,
    and statistics about the knowledge base.
    """
    research = _get_research_or_404(research_id, db)

    state_data = research.state_json or {}

    source_count = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).count()

    finding_count = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).count()

    sub_queries = state_data.get("sub_queries", [])
    findings = state_data.get("findings", {})

    completed_queries = [q for q in sub_queries if q in findings]
    pending_queries = [q for q in sub_queries if q not in findings]

    reasoning_log = state_data.get("ai_reasoning", [])

    current_plan = None
    if sub_queries:
        current_plan = {
            "main_query": state_data.get("query", research.query),
            "refined_question": state_data.get("refined_question"),
            "total_queries": len(sub_queries),
            "completed": len(completed_queries),
            "pending": len(pending_queries),
            "outline": state_data.get("outline"),
        }

    return ResearchStateResponse(
        status=research.status,
        current_plan=current_plan,
        pending_queries=pending_queries,
        completed_queries=completed_queries,
        reasoning_log=reasoning_log,
        last_activity=research.updated_at,
        source_count=source_count,
        finding_count=finding_count,
    )


@router.get(
    "/research/{research_id}/steps",
)
def get_research_steps(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Get the agent steps for a research project.

    Returns the list of steps taken by the agent during research,
    useful for debugging and understanding the agent's process.
    """
    research = _get_research_or_404(research_id, db)

    state_data = research.state_json or {}
    agent_steps = state_data.get("agent_steps", [])

    return {
        "research_id": research_id,
        "status": research.status,
        "steps": agent_steps,
        "total_steps": len(agent_steps),
    }


@router.get(
    "/research/{research_id}/knowledge-base",
)
def get_knowledge_base(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Get the full knowledge base for a research project.

    Returns the query, sub-queries, all citations with their sub-query
    associations, source type distribution, and hypothesis investigations.
    Designed for visualization of the research knowledge graph.
    """
    research = _get_research_or_404(research_id, db)

    state_data = research.state_json or {}

    sub_queries = state_data.get("sub_queries", [])
    citations_raw = state_data.get("citations", [])
    sub_query_results = state_data.get("sub_query_results", [])

    # Build sub-query groups with their associated citations
    sub_query_groups = []
    assigned_urls = set()

    for sqr in sub_query_results:
        sq_citations = sqr.get("citations", [])
        group = {
            "sub_query": sqr.get("sub_query", ""),
            "status": sqr.get("status", "unknown"),
            "error": sqr.get("error"),
            "citation_count": len(sq_citations),
            "citations": [],
        }
        for c in sq_citations:
            url = c.get("url", "")
            group["citations"].append({
                "id": c.get("id", ""),
                "title": c.get("title", ""),
                "url": url,
                "source_type": c.get("source_type", "web"),
                "relevance_score": c.get("relevance_score", 0),
                "author": c.get("author"),
                "snippet": (c.get("snippet", "") or "")[:300],
            })
            assigned_urls.add(url)
        sub_query_groups.append(group)

    # Collect citations not assigned to any sub-query
    unassigned = []
    for c in citations_raw:
        url = c.get("url", "")
        if url not in assigned_urls:
            unassigned.append({
                "id": c.get("id", ""),
                "title": c.get("title", ""),
                "url": url,
                "source_type": c.get("source_type", "web"),
                "relevance_score": c.get("relevance_score", 0),
                "author": c.get("author"),
                "snippet": (c.get("snippet", "") or "")[:300],
            })

    # Source type distribution
    type_counts: dict[str, int] = {}
    for c in citations_raw:
        st = c.get("source_type", "web")
        type_counts[st] = type_counts.get(st, 0) + 1

    # Extract hypotheses from agent steps
    agent_steps = state_data.get("agent_steps", [])
    hypotheses = [
        {
            "title": s.get("title", ""),
            "description": s.get("description", ""),
            "status": s.get("status", ""),
            "metadata": s.get("metadata", {}),
        }
        for s in agent_steps
        if s.get("step_type") == "hypothesis"
    ]

    return {
        "research_id": research_id,
        "query": research.query,
        "status": research.status,
        "sub_queries": sub_queries,
        "sub_query_groups": sub_query_groups,
        "unassigned_citations": unassigned,
        "hypotheses": hypotheses,
        "total_citations": len(citations_raw),
        "source_type_distribution": type_counts,
    }


@router.get(
    "/research/{research_id}/entities",
    response_model=ResearchEntitiesResponse,
)
def get_research_entities(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Extract entities from current research sources and findings."""
    research = _get_research_or_404(research_id, db)

    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()
    findings = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).all()

    documents: list[dict[str, str]] = []

    for source in sources:
        text_parts = [
            source.title or "",
            source.content_snippet or "",
            source.user_notes or "",
        ]
        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            continue
        documents.append({
            "text": text,
            "mention": source.title or source.url or f"source:{source.id}",
        })

    for finding in findings:
        text = (finding.content or "").strip()
        if not text:
            continue
        documents.append({
            "text": text,
            "mention": f"finding:{finding.id}",
        })

    extractor = EntityExtractor()
    entities = extractor.extract_with_mentions(documents)

    return ResearchEntitiesResponse(
        research_id=research_id,
        status=research.status,
        total_entities=len(entities),
        entities=entities,
    )


@router.get(
    "/research/{research_id}/plan",
    response_model=ResearchPlanResponse,
)
def get_research_plan(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Get the research plan with progress details.

    Returns the main query, refined question, sub-queries with
    progress tracking, and document outline.
    """
    research = _get_research_or_404(research_id, db)

    state_data = research.state_json or {}

    sub_queries = state_data.get("sub_queries", [])
    findings = state_data.get("findings", {})

    progress = {}
    for query in sub_queries:
        if query in findings:
            progress[query] = {
                "status": "completed",
                "finding": (
                    findings[query][:200] + "..."
                    if len(findings[query]) > 200
                    else findings[query]
                ),
            }
        else:
            progress[query] = {
                "status": "pending",
                "finding": None,
            }

    return ResearchPlanResponse(
        query=state_data.get("query", research.query),
        refined_question=state_data.get("refined_question"),
        sub_queries=sub_queries,
        progress=progress,
        outline=state_data.get("outline"),
    )


@router.patch(
    "/research/{research_id}/plan",
    response_model=ResearchPlanResponse,
)
def update_research_plan(
    research_id: int,
    payload: ResearchPlanUpdate,
    db: Session = Depends(get_db),
):
    """Update the research plan by adding/removing queries.

    Allows users to manually adjust the research direction
    by modifying the list of sub-queries to investigate.
    """
    research = _get_research_or_404(research_id, db)

    state_data = research.state_json or {}
    sub_queries = state_data.get("sub_queries", [])

    if payload.add_queries:
        for query in payload.add_queries:
            if query not in sub_queries:
                sub_queries.append(query)

    if payload.remove_queries:
        for query in payload.remove_queries:
            if query in sub_queries:
                sub_queries.remove(query)

    if payload.refined_question is not None:
        state_data["refined_question"] = payload.refined_question

    state_data["sub_queries"] = sub_queries
    research.state_json = state_data

    db.commit()
    db.refresh(research)

    return get_research_plan(research_id, db)


@router.get(
    "/research/{research_id}/document",
    response_model=ResearchDocumentResponse,
)
def get_research_document(
    research_id: int,
    db: Session = Depends(get_db),
):
    """Get the full research document with all sources."""
    research = _get_research_or_404(research_id, db)

    return ResearchDocumentResponse(
        id=research.id,
        query=research.query,
        document=research.result,
        status=research.status,
        sources=[
            ResearchSourceResponse.model_validate(s)
            for s in research.sources
        ],
        created_at=research.created_at,
        updated_at=research.updated_at,
    )
