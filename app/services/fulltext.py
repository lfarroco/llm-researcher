"""Full-text evidence retrieval.

The search phase yields citations whose ``snippet`` is whatever the source API
returned — usually an abstract. Reports written from abstracts alone cannot
make claim-level statements, quote numbers, or describe methods.

This module closes that gap: after search, it downloads the open-access PDFs
it can reach, parses them (GROBID, falling back to local parsers), chunks the
text, and keeps the passages most relevant to the research question. Those
passages are persisted as ``ResearchEvidence`` rows and copied into
``ResearchState.evidence`` for synthesis to quote.

Network retrieval is bounded by ``research_fulltext_max_sources`` and is
best-effort: a source that cannot be retrieved is marked and skipped, never
fatal.
"""

import logging
import re
import time
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.memory.research_state import Citation, EvidenceSpan
from app.services.source_identity import source_identity
from app.tools.document_chunker import ChunkingStrategy, chunk_document
from app.tools.pdf_parser import parse_pdf_from_url

logger = logging.getLogger(__name__)

# Hosts and path patterns whose URLs are usually a direct open-access PDF.
# Everything else is skipped unless it already looks like a PDF link.
_PDF_URL_RE = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)

# Sources from these types have reliable open-access full text.
_FULLTEXT_FRIENDLY_TYPES = {
    "arxiv",
    "openalex",
    "semantic_scholar",
    "pubmed",
    "pdf",
}

# Words that carry no retrieval signal when ranking chunks.
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that",
    "this", "these", "those", "is", "are", "was", "were", "be", "been",
    "being", "to", "of", "in", "on", "at", "by", "for", "with", "about",
    "as", "from", "into", "during", "including", "such", "can", "could",
    "may", "might", "will", "would", "should", "do", "does", "did", "not",
    "no", "nor", "so", "yet", "it", "its", "we", "our", "they", "their",
    "what", "which", "who", "whom", "how", "why", "when", "where", "use",
    "used", "using", "also", "more", "most", "other", "some", "any", "all",
})


def _content_tokens(text: str) -> set[str]:
    """Lowercase word tokens with stopwords removed."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def rank_chunks(
    chunks: list,
    query: str,
    limit: int,
) -> list:
    """Return the ``limit`` chunks most relevant to ``query``.

    Ranking is deliberately lexical rather than embedding-based: it needs no
    extra dependency, no index build, and no network call, and it is good
    enough to pull the passages of a paper that discuss the actual question.

    Earlier chunks win ties, which biases toward abstract/introduction.
    """
    if not chunks:
        return []
    if limit <= 0:
        return []

    query_tokens = _content_tokens(query)
    if not query_tokens:
        return chunks[:limit]

    scored = []
    for position, chunk in enumerate(chunks):
        chunk_tokens = _content_tokens(chunk.text)
        if not chunk_tokens:
            continue
        overlap = len(query_tokens & chunk_tokens)
        # Jaccard-ish normalization keeps a long appendix chunk from winning
        # purely by containing more words.
        score = overlap / (len(query_tokens) ** 0.5)
        scored.append((score, chunk.token_count or 0, -position, chunk))

    scored.sort(reverse=True, key=lambda item: (item[0], -item[1]))
    return [item[3] for item in scored[:limit]]


def is_fulltext_candidate(citation: Citation) -> bool:
    """Whether a citation is worth attempting a PDF download for."""
    url = (citation.url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return False

    split = urlsplit(url)

    # A .pdf anywhere in the path, or in a query parameter value (publishers
    # commonly wrap the file in a download endpoint such as
    # ``/download?file=paper.pdf``), means we already have a direct PDF link.
    if _PDF_URL_RE.search(split.path):
        return True
    for _, value in parse_qsl(split.query, keep_blank_values=True):
        if _PDF_URL_RE.search(value):
            return True

    source_type = (
        citation.source_type.value
        if hasattr(citation.source_type, "value")
        else str(citation.source_type)
    )
    return source_type.lower() in _FULLTEXT_FRIENDLY_TYPES


def select_fulltext_candidates(
    citations: Iterable[Citation],
    limit: int,
) -> list[Citation]:
    """Pick up to ``limit`` citations to attempt full-text retrieval for.

    Ordered by relevance score so the budget goes to the most promising
    sources, and de-duplicated by identity so the same paper is not fetched
    twice under two URLs.
    """
    seen: set[str] = set()
    candidates: list[Citation] = []
    for citation in sorted(
        citations, key=lambda c: c.relevance_score or 0.0, reverse=True
    ):
        if not is_fulltext_candidate(citation):
            continue
        key = source_identity(citation.url, title=citation.title)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(citation)
        if len(candidates) >= limit:
            break
    return candidates


def _section_for_offset(sections: list, start_char: int) -> Optional[str]:
    """Find which parsed section a character offset falls into."""
    offset = 0
    for section in sections or []:
        text = getattr(section, "content", "") or ""
        if offset <= start_char < offset + len(text):
            return (getattr(section, "heading", "") or None)
        offset += len(text)
    return None


async def retrieve_source_evidence(
    citation: Citation,
    source: models.ResearchSource,
    research_id: int,
    query: str,
    chunks_per_source: int,
) -> list[models.ResearchEvidence]:
    """Download, parse, chunk and select evidence for a single source.

    Mutates ``source``'s full-text bookkeeping columns. Returns the evidence
    rows to persist (possibly empty). Never raises: retrieval is best-effort.
    """
    started = time.monotonic()
    try:
        response = await parse_pdf_from_url(citation.url)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            f"[FULLTEXT] Unexpected parse failure for {citation.url}: {exc}"
        )
        source.full_text_status = "failed"
        return []

    if not response.success or not response.data:
        error_type = (
            response.error.error_type.value if response.error else "unknown"
        )
        # Not finding a PDF is the common case, not an error worth alarming on.
        source.full_text_status = "unavailable"
        source.full_text_fetched_at = models.utcnow()
        logger.info(
            f"[FULLTEXT] No full text for {citation.url} ({error_type})"
        )
        return []

    parsed = response.data[0]
    full_text = (parsed.full_text or "").strip()
    if not full_text:
        source.full_text_status = "unavailable"
        source.full_text_fetched_at = models.utcnow()
        return []

    chunks = chunk_document(
        full_text,
        strategy=ChunkingStrategy.SECTION,
    )
    if not chunks:
        chunks = chunk_document(
            full_text, strategy=ChunkingStrategy.PARAGRAPH
        )

    selected = rank_chunks(chunks, query, chunks_per_source)

    source.full_text_status = "fetched"
    source.full_text_parser = parsed.parser_used
    source.full_text_chars = len(full_text)
    source.full_text_fetched_at = models.utcnow()

    evidence_rows = []
    for chunk in selected:
        evidence_rows.append(models.ResearchEvidence(
            research_id=research_id,
            source_id=source.id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            token_count=chunk.token_count,
            section=_section_for_offset(
                parsed.sections, chunk.start_char
            ),
            sub_query=None,
        ))

    logger.info(
        f"[FULLTEXT] {citation.url}: {len(full_text)} chars via "
        f"{parsed.parser_used}, kept {len(evidence_rows)}/{len(chunks)} "
        f"chunks in {time.monotonic() - started:.1f}s"
    )
    return evidence_rows


def evidence_to_spans(
    rows: list[models.ResearchEvidence],
    citations: list[Citation],
) -> list[EvidenceSpan]:
    """Convert persisted evidence rows into state spans.

    Each span is annotated with the citation marker (``[1]``, ``[2]``…) of the
    source it came from, so the synthesis prompt and the final reference list
    refer to the same numbering the reader sees.

    Markers are resolved through source *identity*, not the stored URL string.
    The chat layer rebuilds citations from database rows and assigns its own
    markers, so matching on URL would silently drop those spans.
    """
    citation_id_by_identity = {}
    for citation in citations:
        key = source_identity(citation.url, title=citation.title)
        citation_id_by_identity.setdefault(key, citation.id)

    spans: list[EvidenceSpan] = []
    for row in rows:
        source = row.source
        key = source_identity(
            source.url if source else None,
            title=source.title if source else None,
        )
        spans.append(EvidenceSpan(
            source_id=row.source_id,
            citation_id=citation_id_by_identity.get(key, ""),
            title=(source.title if source else "") or "",
            url=(source.url if source else "") or "",
            text=row.text,
            chunk_index=row.chunk_index,
            section=row.section,
        ))
    return spans


def load_evidence(
    db: Session,
    research_id: int,
) -> list[models.ResearchEvidence]:
    """Load all persisted evidence for a research item, in source order."""
    return (
        db.query(models.ResearchEvidence)
        .filter(models.ResearchEvidence.research_id == research_id)
        .order_by(
            models.ResearchEvidence.source_id,
            models.ResearchEvidence.chunk_index,
        )
        .all()
    )


async def collect_fulltext_evidence(
    db: Session,
    research_id: int,
    query: str,
    citations: list[Citation],
) -> list[EvidenceSpan]:
    """Retrieve full text for the best candidates and return evidence spans.

    Sources already marked ``fetched`` are not re-downloaded, so resuming a
    research does not repeat network work. Returns spans ready to place on
    ``ResearchState.evidence``.
    """
    if not settings.research_fulltext_enabled:
        logger.debug("[FULLTEXT] Disabled by configuration")
        return []

    if not citations:
        return []

    candidates = select_fulltext_candidates(
        citations,
        limit=settings.research_fulltext_max_sources,
    )
    if not candidates:
        logger.info("[FULLTEXT] No open-access candidates among citations")
        return []

    sources_by_identity = {
        source_identity(source.url, title=source.title): source
        for source in db.query(models.ResearchSource).filter(
            models.ResearchSource.research_id == research_id
        ).all()
    }

    chunks_per_source = settings.research_fulltext_chunks_per_source
    retrieved = 0

    for citation in candidates:
        key = source_identity(citation.url, title=citation.title)
        source = sources_by_identity.get(key)
        if source is None:
            continue
        if source.full_text_status == "fetched":
            retrieved += 1
            continue

        rows = await retrieve_source_evidence(
            citation=citation,
            source=source,
            research_id=research_id,
            query=query,
            chunks_per_source=chunks_per_source,
        )
        for row in rows:
            db.add(row)
        if rows:
            retrieved += 1
        # Commit per source so a later failure does not discard earlier work.
        db.commit()

    logger.info(
        f"[FULLTEXT] Retrieved full text for {retrieved}/"
        f"{len(candidates)} candidate sources"
    )

    all_rows = load_evidence(db, research_id)
    return evidence_to_spans(all_rows, citations)
