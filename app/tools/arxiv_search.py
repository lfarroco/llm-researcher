"""
ArXiv search tool for academic papers.

Useful for research queries that benefit from scientific/academic sources.

Two things about the arXiv API shape this module:

* **Query syntax.** The API expects field-prefixed terms (``all:electron``),
  not a free-form natural-language question. A raw question containing commas
  and question marks is rejected outright, so every query is sanitized and
  rewritten before it is sent (:func:`build_arxiv_query`).
* **Rate limits.** arXiv asks for no more than one request every three seconds
  and answers bursts with ``HTTP 406``. The library's per-client delay does not
  help when several plugin calls run concurrently, each with its own client, so
  requests are paced process-wide here (:func:`_wait_for_arxiv_slot`).
"""

import asyncio
import logging
import re
import threading
import time

import arxiv
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# arXiv's API terms ask for no more than one request every three seconds.
# Overridable through ``settings.arxiv_min_interval_seconds`` (0 disables
# pacing, which tests use).
DEFAULT_MIN_INTERVAL_SECONDS = 3.0

# How long to stop calling arXiv after it answers with a rate-limit status.
# Its cooldown lasts minutes, so short retries only burn time.
DEFAULT_COOLDOWN_SECONDS = 300.0

# Field prefix that makes a bare term list search all metadata fields.
_FIELD_PREFIX = "all:"

# How many content terms to keep. More terms means a narrower AND query, and
# arXiv matches every term, so a long question would return nothing.
MAX_QUERY_TERMS = 6

# Characters arXiv treats as query syntax. Anything that is not a word
# character, whitespace, or a hyphen (as in "meta-analysis") is stripped.
_QUERY_NOISE_RE = re.compile(r"[^\w\s-]", re.UNICODE)

# A trailing publication year is almost never present in the indexed text of
# a paper, so ANDing it in silently destroys recall.
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")

_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "could", "did", "do",
    "does", "doing", "done", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "me", "might", "more", "most", "my", "no", "nor", "not", "now", "of",
    "off", "on", "once", "only", "or", "other", "our", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "we",
    "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "will", "with", "would", "you", "your",
})

# ``all:term term`` style queries; used when sanitizing leaves nothing behind.
_MAX_FALLBACK_CHARS = 120

# Pacing state. A thread lock (not an asyncio lock) is used because the actual
# request runs in a worker thread via ``asyncio.to_thread`` and because the
# background worker may run research tasks on separate event loops.
_pace_lock = threading.Lock()
_last_request_at = 0.0
# When arXiv answers with a rate-limit status it is already unhappy, and it
# keeps rejecting everything for a while. Retrying makes that worse (and costs
# a 3 s pacing slot per attempt), so the tool backs off entirely for a cooldown
# period instead of asking again.
_cooldown_until = 0.0

# Statuses that mean "you are asking too often", not "your query is wrong".
_RATE_LIMIT_STATUSES = frozenset({406, 429, 503})


class ArxivResult(BaseModel):
    """A single ArXiv paper result."""

    title: str = Field(description="Paper title")
    authors: list[str] = Field(description="List of author names")
    summary: str = Field(description="Paper abstract/summary")
    url: str = Field(description="ArXiv URL")
    pdf_url: str = Field(description="Direct PDF URL")
    published: str = Field(description="Publication date")
    categories: list[str] = Field(
        default_factory=list, description="ArXiv categories")


def build_arxiv_query(raw_query: str) -> str:
    """Turn a natural-language question into arXiv query syntax.

    Strips punctuation the API treats as syntax, drops stopwords and
    publication years, keeps the first :data:`MAX_QUERY_TERMS` distinct content
    terms, and prefixes the result with the ``all:`` field so every term is
    matched against all metadata::

        "Which functional languages, frameworks and libraries are used in 2026?"
        -> "all:functional languages frameworks libraries used"

    Falls back to a sanitized prefix of the original text when nothing
    survives stopword removal, and never returns an empty query.
    """
    text = _QUERY_NOISE_RE.sub(" ", (raw_query or "").lower())

    terms: list[str] = []
    seen: set[str] = set()
    for term in text.split():
        if len(term) < 2 or term in _STOPWORDS or _YEAR_RE.match(term):
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
        if len(terms) >= MAX_QUERY_TERMS:
            break

    if not terms:
        fallback = " ".join(text.split())[:_MAX_FALLBACK_CHARS].strip()
        if not fallback:
            return _FIELD_PREFIX
        return f"{_FIELD_PREFIX}{fallback}"

    return f"{_FIELD_PREFIX}{' '.join(terms)}"


def _min_interval_seconds() -> float:
    """Configured pacing interval, read lazily so tests can override it."""
    try:
        from app.config import settings

        value = settings.arxiv_min_interval_seconds
    except Exception:  # pragma: no cover - config import is always available
        return DEFAULT_MIN_INTERVAL_SECONDS
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return DEFAULT_MIN_INTERVAL_SECONDS


def _wait_for_arxiv_slot() -> None:
    """Block until arXiv's minimum spacing since the last request has passed.

    Runs inside the worker thread, so the sleep never stalls the event loop.
    Calls from concurrent sub-query searches queue here instead of arriving as
    a burst that arXiv answers with an ``HTTP 406``.
    """
    global _last_request_at

    interval = _min_interval_seconds()
    with _pace_lock:
        if interval > 0 and _last_request_at:
            remaining = interval - (time.monotonic() - _last_request_at)
            if remaining > 0:
                logger.info(
                    "[ARXIV] Pacing request: sleeping %.1fs to respect the "
                    "API rate limit", remaining,
                )
                time.sleep(remaining)
        _last_request_at = time.monotonic()


def _cooldown_seconds() -> float:
    """Configured rate-limit cooldown, read lazily for tests."""
    try:
        from app.config import settings

        value = settings.arxiv_rate_limit_cooldown_seconds
    except Exception:  # pragma: no cover - config import is always available
        return DEFAULT_COOLDOWN_SECONDS
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return DEFAULT_COOLDOWN_SECONDS


def _in_cooldown() -> bool:
    """Whether a rate-limit response is still being backed off from."""
    return time.monotonic() < _cooldown_until


def _start_cooldown() -> None:
    """Stop calling arXiv for a while after a rate-limit response."""
    global _cooldown_until

    seconds = _cooldown_seconds()
    _cooldown_until = time.monotonic() + seconds
    if seconds > 0:
        logger.warning(
            "[ARXIV] Rate limited; skipping arXiv for %.0fs so the run is "
            "not spent waiting on a throttled API", seconds,
        )


def _arxiv_search_sync(
    arxiv_query: str,
    max_results: int,
    sort_by: str,
) -> list[ArxivResult]:
    """Perform the blocking arXiv request. Called via ``asyncio.to_thread``."""
    sort_criterion = {
        "relevance": arxiv.SortCriterion.Relevance,
        "lastUpdatedDate": arxiv.SortCriterion.LastUpdatedDate,
        "submittedDate": arxiv.SortCriterion.SubmittedDate,
    }.get(sort_by, arxiv.SortCriterion.Relevance)

    # The library defaults to fetching 100-entry pages; ask only for what the
    # caller needs. Pacing is handled here, so the client's own delay is off.
    page_size = max(1, min(max_results, 100))
    # num_retries=0 is deliberate: the library's retry fires immediately, so a
    # single logical call would put two requests on the wire inside one pacing
    # interval and trip arXiv's rate limiter on its own.
    client = arxiv.Client(
        page_size=page_size, delay_seconds=0.0, num_retries=0
    )
    search = arxiv.Search(
        query=arxiv_query,
        max_results=max_results,
        sort_by=sort_criterion,
    )

    _wait_for_arxiv_slot()

    results: list[ArxivResult] = []
    try:
        for paper in client.results(search):
            results.append(ArxivResult(
                title=paper.title,
                authors=[author.name for author in paper.authors],
                summary=paper.summary[:1500],  # Limit summary length
                url=paper.entry_id,
                pdf_url=paper.pdf_url or "",
                published=(
                    paper.published.isoformat() if paper.published else ""
                ),
                categories=paper.categories,
            ))
    except arxiv.HTTPError as exc:
        status = getattr(exc, "status", None)
        if status in _RATE_LIMIT_STATUSES:
            # Overwhelmingly the rate limiter, not a bad query. Back off and
            # let the other search plugins carry this sub-query.
            _start_cooldown()
        else:
            logger.warning("[ARXIV] Search failed (HTTP %s): %s", status, exc)
        return []
    except Exception as exc:  # noqa: BLE001 - never fail the whole search
        logger.warning("[ARXIV] Search failed: %s", exc)
        return []

    logger.info(
        "[ARXIV] Search complete, returning %d results", len(results)
    )
    return results


async def arxiv_search(
    query: str,
    max_results: int = 5,
    sort_by: str = "relevance",
) -> list[ArxivResult]:
    """
    Search ArXiv for academic papers.

    Args:
        query: Natural-language query; it is rewritten into arXiv query
            syntax by :func:`build_arxiv_query`.
        max_results: Maximum number of results
        sort_by: Sort order - "relevance", "lastUpdatedDate", or "submittedDate"

    Returns:
        List of ArxivResult objects (empty when the API is rate limiting)
    """
    arxiv_query = build_arxiv_query(query)
    logger.info(
        "[ARXIV] Searching: '%s' (from '%s')",
        arxiv_query, (query or "")[:80],
    )
    logger.debug(
        "[ARXIV] Parameters: max_results=%d, sort_by=%s",
        max_results, sort_by,
    )

    if _in_cooldown():
        logger.info(
            "[ARXIV] Skipping query while backing off from a rate-limit "
            "response"
        )
        return []

    # The client is synchronous and paces itself with time.sleep, so it runs in
    # a worker thread rather than blocking the event loop.
    return await asyncio.to_thread(
        _arxiv_search_sync, arxiv_query, max_results, sort_by
    )


# Strong, unambiguous signals that a query is asking about scholarship.
# Deliberately excludes generic software words ("framework", "model",
# "method", "approach"): those appear in ordinary product questions and used
# to route nearly every web-development query through the academic plugins.
_ACADEMIC_KEYWORDS = (
    "research", "study", "studies", "paper", "papers", "preprint",
    "journal", "publication", "peer-reviewed", "peer reviewed", "citation",
    "theory", "theoretical", "hypothesis", "experiment", "experimental",
    "empirical", "analysis", "analyses", "scientific", "science",
    "algorithm", "algorithms", "dataset", "benchmark", "evaluation",
    "literature", "review", "systematic review", "survey", "meta-analysis",
    "methodology", "arxiv", "academic", "scholarly",
)


def is_academic_query(query: str) -> bool:
    """
    Heuristic to determine if a query would benefit from academic sources.

    Returns True if the query contains an explicit academic marker (research,
    paper, study, benchmark, ...). Generic engineering words such as
    "framework" or "model" are intentionally *not* markers — they appear in
    everyday product questions and would enable academic plugins for almost
    every query.
    """
    query_lower = (query or "").lower()
    return any(keyword in query_lower for keyword in _ACADEMIC_KEYWORDS)
