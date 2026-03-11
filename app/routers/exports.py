"""
Exports router - document export endpoints (PDF, HTML, DOCX, Markdown).

Handles exporting research documents in various formats using pandoc.
Also provides data exports for sources (BibTeX) and findings (CSV/JSON).
"""

import csv
import io
import json
import logging
from datetime import datetime

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
from app.tools.bibtex_parser import (
    BibTeXEntry,
    entries_to_bibtex_string,
    create_citation_key,
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


def _get_research_or_404(research_id: int, db: Session) -> models.Research:
    """Fetch research by ID or raise 404."""
    research = db.query(models.Research).filter(
        models.Research.id == research_id
    ).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
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


@router.get("/research/{research_id}/export/sources/bibtex")
def export_sources_as_bibtex(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export all sources as BibTeX format.

    Useful for bibliography management and academic writing.
    Uses structured BibTeX parser for proper formatting.
    """
    research = _get_research_or_404(research_id, db)

    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    if not sources:
        raise HTTPException(
            status_code=404,
            detail="No sources found for this research"
        )

    # Convert sources to BibTeX entries using our parser
    bibtex_entries = []
    for source in sources:
        # Parse authors if available
        authors = []
        if source.author:
            # Assume comma-separated or "and"-separated
            if " and " in source.author:
                authors = [a.strip() for a in source.author.split(" and ")]
            elif "," in source.author:
                authors = [a.strip() for a in source.author.split(",")]
            else:
                authors = [source.author]

        # Extract year from accessed_at if no other year available
        year = source.accessed_at.year if source.accessed_at else None

        # Create citation key
        cite_key = create_citation_key(
            authors=authors,
            year=year,
            title=source.title
        )

        # Determine entry type based on source type
        entry_type = "misc"
        extra_fields = {}

        if source.source_type == "arxiv":
            entry_type = "article"
            # ArXiv papers often have an eprint field
            if "arxiv.org" in source.url.lower():
                # Extract arxiv ID from URL
                import re
                match = re.search(
                    r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', source.url)
                if match:
                    extra_fields["eprint"] = match.group(1)
                    extra_fields["archiveprefix"] = "arXiv"
        elif source.source_type in ["pubmed", "semantic_scholar"]:
            entry_type = "article"
        elif source.source_type == "wikipedia":
            entry_type = "misc"
            extra_fields["howpublished"] = "\\url{" + source.url + "}"
        else:
            entry_type = "misc"
            if source.source_type:
                extra_fields["note"] = f"Source type: {source.source_type}"

        # Add access date note
        access_note = f"Accessed: {source.accessed_at.strftime('%Y-%m-%d')}"
        if "note" in extra_fields:
            extra_fields["note"] = extra_fields["note"] + f", {access_note}"
        else:
            extra_fields["note"] = access_note

        # Create BibTeX entry
        entry = BibTeXEntry(
            entry_type=entry_type,
            cite_key=cite_key,
            title=source.title,
            authors=authors,
            year=year,
            url=source.url,
            abstract=source.content_snippet[:500] if source.content_snippet else None,
            extra_fields=extra_fields
        )
        bibtex_entries.append(entry)

    # Convert to BibTeX string using our parser
    bibtex_content = entries_to_bibtex_string(bibtex_entries)
    filename = _safe_filename(research.query, research_id, "bib")

    return Response(
        content=bibtex_content.encode('utf-8'),
        media_type="application/x-bibtex",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )


@router.get("/research/{research_id}/export/findings/csv")
def export_findings_as_csv(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export all findings as CSV format.

    Includes finding content, source IDs, creator, and timestamps.
    """
    research = _get_research_or_404(research_id, db)

    findings = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).all()

    if not findings:
        raise HTTPException(
            status_code=404,
            detail="No findings found for this research"
        )

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            'id',
            'content',
            'source_ids',
            'created_by',
            'created_at',
            'updated_at'
        ]
    )
    writer.writeheader()

    for finding in findings:
        writer.writerow({
            'id': finding.id,
            'content': finding.content,
            'source_ids': json.dumps(finding.source_ids) if finding.source_ids else '',
            'created_by': finding.created_by,
            'created_at': finding.created_at.isoformat(),
            'updated_at': finding.updated_at.isoformat(),
        })

    csv_content = output.getvalue()
    filename = _safe_filename(research.query, research_id, "csv")

    return Response(
        content=csv_content.encode('utf-8'),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )


@router.get("/research/{research_id}/export/findings/json")
def export_findings_as_json(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export all findings as JSON format.

    Includes all finding data in structured JSON format.
    """
    research = _get_research_or_404(research_id, db)

    findings = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).all()

    if not findings:
        raise HTTPException(
            status_code=404,
            detail="No findings found for this research"
        )

    # Convert to JSON-serializable format
    findings_data = [
        {
            'id': f.id,
            'content': f.content,
            'source_ids': f.source_ids,
            'created_by': f.created_by,
            'created_at': f.created_at.isoformat(),
            'updated_at': f.updated_at.isoformat(),
        }
        for f in findings
    ]

    json_content = json.dumps(findings_data, indent=2)
    filename = _safe_filename(research.query, research_id, "json")

    return Response(
        content=json_content.encode('utf-8'),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )


@router.get("/research/{research_id}/export/data")
def export_research_data(
    research_id: int,
    db: Session = Depends(get_db),
):
    """
    Export full research data as JSON.

    Includes research metadata, all sources, findings, and notes.
    Useful for backup, migration, or data analysis.
    """
    research = _get_research_or_404(research_id, db)

    # Fetch all related data
    sources = db.query(models.ResearchSource).filter(
        models.ResearchSource.research_id == research_id
    ).all()

    findings = db.query(models.ResearchFinding).filter(
        models.ResearchFinding.research_id == research_id
    ).all()

    notes = db.query(models.ResearchNote).filter(
        models.ResearchNote.research_id == research_id
    ).all()

    # Build complete data structure
    research_data = {
        'research': {
            'id': research.id,
            'query': research.query,
            'result': research.result,
            'status': research.status,
            'user_notes': research.user_notes,
            'tags': research.tags,
            'created_at': research.created_at.isoformat(),
            'updated_at': research.updated_at.isoformat(),
        },
        'sources': [
            {
                'id': s.id,
                'url': s.url,
                'title': s.title,
                'author': s.author,
                'content_snippet': s.content_snippet,
                'source_type': s.source_type,
                'relevance_score': s.relevance_score,
                'user_notes': s.user_notes,
                'tags': s.tags,
                'accessed_at': s.accessed_at.isoformat(),
            }
            for s in sources
        ],
        'findings': [
            {
                'id': f.id,
                'content': f.content,
                'source_ids': f.source_ids,
                'created_by': f.created_by,
                'created_at': f.created_at.isoformat(),
                'updated_at': f.updated_at.isoformat(),
            }
            for f in findings
        ],
        'notes': [
            {
                'id': n.id,
                'agent': n.agent,
                'category': n.category,
                'content': n.content,
                'created_at': n.created_at.isoformat(),
                'updated_at': n.updated_at.isoformat(),
            }
            for n in notes
        ],
        'export_metadata': {
            'exported_at': datetime.now().isoformat(),
            'version': '1.0',
        }
    }

    json_content = json.dumps(research_data, indent=2)
    filename = _safe_filename(
        research.query,
        research_id,
        "full_data.json"
    )

    return Response(
        content=json_content.encode('utf-8'),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )
