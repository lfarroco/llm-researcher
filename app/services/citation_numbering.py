"""Assign the citation numbers a reader actually sees.

The research pipeline collects sources in several waves (search, reference
chasing, hypothesis investigation). Each wave continues a running
``Citation.id`` marker sequence, and the formatter then drops sources the model
did not cite. That left two problems:

* the reference list kept the gaps (``[1]..[11]``, ``[14]..``), and
* those markers were unrelated to the ids of the ``ResearchSource`` rows the
  API returns, because rows are numbered by insertion after identity-dedup
  merges — so following citation ``[16]`` in the document could land on a
  different source than the sentence was written from.

This module is the single place that turns pipeline markers into the final,
contiguous ``1..N`` numbering, rewrites the inline markers to match, and
rebuilds the reference list. It returns the marker for each source identity so
the caller can persist it on the source row and keep the document, the
knowledge base, and the API in agreement.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.memory.research_state import Citation
from app.services.source_identity import source_identity

logger = logging.getLogger(__name__)

REFERENCES_HEADING = "## References"

_MARKER_RE = re.compile(r"\[(\d+)\]")
_CITATION_ID_RE = re.compile(r"\[(\d+)\]")
_REFERENCES_SPLIT_RE = re.compile(
    r"^[ \t]*#{1,6}[ \t]*References[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# The horizontal rule the formatter writes between the body and the reference
# list. It belongs to the references section, so it is not part of the body.
_TRAILING_RULE_RE = re.compile(r"\n+[ \t]*-{3,}[ \t]*$")


def marker_number(citation_id: Optional[str]) -> Optional[int]:
    """Extract the integer from a ``"[3]"`` style citation marker."""
    match = _CITATION_ID_RE.search(citation_id or "")
    return int(match.group(1)) if match else None


def format_reference_line(citation: Citation, marker: int) -> str:
    """Render one entry of the reference list.

    Kept in one place so the formatter and the renumbering step cannot drift
    apart; the shape matches what ``synthesis_agent`` has always emitted.
    """
    line = f"[{marker}] "
    if citation.author:
        line += f"{citation.author}. "
    line += f'"{citation.title}." '
    line += f"Retrieved from {citation.url} "
    line += f"on {(citation.date_accessed or '')[:10]}.\n\n"
    return line


def split_references(document: str) -> tuple[str, str]:
    """Split a finished document into body and reference-list text.

    Returns ``(body, references)``. When the document has no references
    heading the whole string is the body and the references part is empty.
    A trailing horizontal rule is treated as part of the references section
    so re-rendering the list does not produce a doubled ``---``.
    """
    text = document or ""
    match = _REFERENCES_SPLIT_RE.search(text)
    if not match:
        return text, ""
    body = text[:match.start()].rstrip()
    body = _TRAILING_RULE_RE.sub("", body).rstrip()
    return body, text[match.end():].strip()


def cited_markers_in_order(body: str) -> list[int]:
    """Return the distinct citation markers of ``body``, in reading order."""
    ordered: list[int] = []
    for match in _MARKER_RE.finditer(body or ""):
        number = int(match.group(1))
        if number not in ordered:
            ordered.append(number)
    return ordered


def renumber_document(
    document: str,
    citations: list[Citation],
) -> tuple[str, dict[str, int]]:
    """Renumber ``document``'s citations contiguously and rebuild its refs.

    Markers are reassigned ``1..N`` in order of first appearance in the body,
    which is the convention a reader expects, and the reference list is rebuilt
    from the citations that are actually cited.

    Numbering is keyed on :func:`~app.services.source_identity.source_identity`
    rather than on the citation: collection can surface one document twice
    under URL variants that the knowledge base merges into a single row, and a
    report that numbered those separately would contain markers no source row
    carries. Such duplicates collapse to one marker and one reference entry.

    Args:
        document: The finished markdown document, including its reference list
            as produced by the formatting step.
        citations: All citations collected during the run, carrying their
            pipeline markers in ``Citation.id``.

    Returns:
        ``(new_document, markers_by_identity)`` where ``markers_by_identity``
        maps ``source_identity(...)`` to the new marker, ready to persist on
        the matching ``ResearchSource`` row. The mapping is empty when there is
        nothing to renumber, in which case the document is returned unchanged.
    """
    if not document:
        return document, {}

    body, _existing_references = split_references(document)
    if not body.strip():
        return document, {}

    by_marker: dict[int, Citation] = {}
    for citation in citations:
        number = marker_number(citation.id)
        if number is None:
            continue
        if number in by_marker:
            logger.warning(
                "[CITATIONS] Duplicate pipeline marker %s ('%s' vs '%s'); "
                "keeping the first", citation.id,
                by_marker[number].title[:50], citation.title[:50],
            )
            continue
        by_marker[number] = citation

    cited_order = [
        number
        for number in cited_markers_in_order(body)
        if number in by_marker
    ]
    if not cited_order:
        return document, {}

    # Number sources, not citations. Collection can surface the same document
    # twice under URL variants (a fragment, a tracking parameter) that the
    # knowledge base merges into one row; numbering each of those separately
    # would put a marker in the report that no source row carries.
    identity_marker: dict[str, int] = {}
    old_to_new: dict[int, int] = {}
    ordered_citations: list[Citation] = []
    for old in cited_order:
        citation = by_marker[old]
        key = source_identity(citation.url, title=citation.title)
        existing = identity_marker.get(key)
        if existing is not None:
            old_to_new[old] = existing
            logger.info(
                "[CITATIONS] Marker %s resolves to the same source as an "
                "earlier citation; citing it once as [%d]",
                citation.id, existing,
            )
            continue
        marker = len(ordered_citations) + 1
        identity_marker[key] = marker
        old_to_new[old] = marker
        ordered_citations.append(citation)

    def _replace(match: re.Match) -> str:
        number = int(match.group(1))
        replacement = old_to_new.get(number)
        return f"[{replacement}]" if replacement is not None else match.group(0)

    new_body = _MARKER_RE.sub(_replace, body)

    reference_lines = "".join(
        format_reference_line(citation, identity_marker[
            source_identity(citation.url, title=citation.title)
        ])
        for citation in ordered_citations
    )
    new_document = (
        f"{new_body}\n\n---\n\n{REFERENCES_HEADING}\n\n{reference_lines}"
    )

    logger.info(
        "[CITATIONS] Renumbered %d cited source(s) to 1..%d "
        "(%d collected, %d duplicate marker(s) collapsed)",
        len(ordered_citations), len(ordered_citations), len(citations),
        len(cited_order) - len(ordered_citations),
    )
    return new_document, identity_marker
