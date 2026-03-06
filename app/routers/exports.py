"""
Exports router - document export endpoints (PDF, HTML, DOCX, Markdown).

Handles exporting research documents in various formats using pandoc.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.output.pdf_exporter import (
    export_research_to_pdf,
    export_research_to_html,
    export_research_to_docx,
    check_pandoc_installed,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])


def _get_research_with_document(
    research_id: int, db: Session
) -> models.Research:
    """Fetch research by ID, ensuring it has a document."""
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    if not research.result:
        raise HTTPException(
            status_code=400,
            detail=(
                "No document available for this research. "
                "Please complete the research first."
            ),
        )
    return research


def _safe_filename(query: str, research_id: int, ext: str) -> str:
    """Generate a safe filename from research query."""
    chars = [
        c for c in query if c.isalnum() or c in (' ', '-', '_')
    ]
    safe = "".join(chars)[:50]
    return f"research_{research_id}_{safe}.{ext}"


@router.get("/research/{research_id}/export/pdf")
def export_research_as_pdf(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export research document as PDF.

    Requires pandoc to be installed on the system.
    """
    if not check_pandoc_installed():
        raise HTTPException(
            status_code=503,
            detail="PDF export is not available. Pandoc is not installed.",
        )

    research = _get_research_with_document(research_id, db)

    try:
        pdf_content = export_research_to_pdf(
            markdown_content=research.result,
            title=research.query,
            author="LLM Researcher",
            date=research.updated_at.strftime("%Y-%m-%d"),
        )

        filename = _safe_filename(research.query, research_id, "pdf")
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    except ValueError as e:
        logger.error(f"PDF export failed for research {research_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export PDF: {str(e)}",
        )


@router.get("/research/{research_id}/export/html")
def export_research_as_html(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export research document as HTML.

    Requires pandoc to be installed on the system.
    """
    if not check_pandoc_installed():
        raise HTTPException(
            status_code=503,
            detail="HTML export is not available. Pandoc is not installed.",
        )

    research = _get_research_with_document(research_id, db)

    try:
        html_content = export_research_to_html(
            markdown_content=research.result,
            title=research.query,
            author="LLM Researcher",
        )

        filename = _safe_filename(research.query, research_id, "html")
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    except ValueError as e:
        logger.error(f"HTML export failed for research {research_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export HTML: {str(e)}",
        )


@router.get("/research/{research_id}/export/docx")
def export_research_as_docx(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export research document as DOCX (Microsoft Word).

    Requires pandoc to be installed on the system.
    """
    if not check_pandoc_installed():
        raise HTTPException(
            status_code=503,
            detail="DOCX export is not available. Pandoc is not installed.",
        )

    research = _get_research_with_document(research_id, db)

    try:
        docx_content = export_research_to_docx(
            markdown_content=research.result,
            title=research.query,
            author="LLM Researcher",
        )

        filename = _safe_filename(research.query, research_id, "docx")
        media_type = (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        )
        return Response(
            content=docx_content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            },
        )
    except ValueError as e:
        logger.error(f"DOCX export failed for research {research_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export DOCX: {str(e)}",
        )


@router.get("/research/{research_id}/export/markdown")
def export_research_as_markdown(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export research document as Markdown.

    Returns the raw markdown document.
    """
    research = _get_research_with_document(research_id, db)

    filename = _safe_filename(research.query, research_id, "md")
    return Response(
        content=research.result.encode('utf-8'),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )
