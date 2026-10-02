"""
Default search plugins shipped with llm-researcher.

Each class wraps one of the tool functions in app/tools/ and implements the
SearchPlugin protocol, handling the mapping from tool-specific result types to
the common Citation model.

The built-in plugins (web, arxiv, wikipedia, pubmed, semantic_scholar,
openalex, crossref, springer, elsevier) are registered into the global
ToolRegistry via :func:`register_defaults`, which is called during application
startup from app/main.py.

To add a custom plugin without touching this file:

    from app.tools.registry import get_registry
    get_registry().register(MyPlugin())
"""

import logging
import re

from app.config import settings
from app.memory.research_state import Citation, SourceType
from app.tools.arxiv_search import arxiv_search
from app.tools.crossref_search import crossref_search
from app.tools.elsevier_search import elsevier_search
from app.tools.openalex_search import openalex_search
from app.tools.pubmed_search import is_biomedical_query, pubmed_search
from app.tools.semantic_scholar import semantic_scholar_search
from app.tools.springer_search import springer_search
from app.tools.web_search import web_search
from app.tools.wikipedia import wikipedia_search

logger = logging.getLogger(__name__)


def _first_authors(authors: list[str], limit: int = 3) -> str | None:
    """Render up to ``limit`` author names as a citation-ready string."""
    if not authors:
        return None
    return ", ".join(authors[:limit])


def _doi_url(doi: str | None) -> str | None:
    """Turn a bare or URL-shaped DOI into a resolvable ``doi.org`` link."""
    if not doi:
        return None
    cleaned = doi.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith(("http://", "https://")):
        return cleaned
    return f"https://doi.org/{cleaned}"


_JATS_TAG_RE = re.compile(r"<[^>]+>")


def _strip_markup(text: str | None) -> str:
    """Drop publisher JATS/HTML markup and collapse whitespace.

    Crossref abstracts arrive as JATS fragments such as
    ``<jats:p>Text.</jats:p>``; the raw tags are noise to both the relevance
    filter and the synthesis model.
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", _JATS_TAG_RE.sub(" ", text)).strip()


class WebSearchPlugin:
    """Web search via Tavily (with DuckDuckGo fallback)."""

    name = "web"
    source_type = SourceType.WEB
    requires_academic_context = False
    first_variation_only = False
    default_max_results = 5

    def is_available(self) -> bool:
        return True  # DuckDuckGo fallback requires no API key

    async def search(self, query: str, max_results: int = 5) -> list[Citation]:
        results = await web_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",  # reassigned after deduplication in the search agent
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                source_type=self.source_type,
                relevance_score=r.score,
            )
            for r in results
        ]


class ArxivPlugin:
    """Academic paper search via the ArXiv API (no key required)."""

    name = "arxiv"
    source_type = SourceType.ARXIV
    requires_academic_context = True
    # arXiv rate-limits to roughly one request every three seconds and answers
    # bursts with HTTP 406. One well-formed query per sub-query is the budget;
    # the expanded query variations are covered by the other plugins.
    first_variation_only = True
    default_max_results = 3

    def is_available(self) -> bool:
        return True  # arxiv library requires no API key

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await arxiv_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=r.url,
                title=r.title,
                author=", ".join(r.authors[:3]),
                snippet=r.summary[:500],
                source_type=self.source_type,
                relevance_score=0.8,
            )
            for r in results
        ]


class WikipediaPlugin:
    """Background context search via Wikipedia (no key required)."""

    name = "wikipedia"
    source_type = SourceType.WIKIPEDIA
    requires_academic_context = False
    first_variation_only = True  # one Wikipedia pass per sub-query is enough
    default_max_results = 3

    def is_available(self) -> bool:
        return True  # wikipedia library requires no API key

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await wikipedia_search(query, sentences=5)
        return [
            Citation(
                id="[0]",
                url=r.url,
                title=r.title,
                snippet=r.summary,
                source_type=self.source_type,
                relevance_score=0.7,
            )
            for r in results
        ]


class PubMedPlugin:
    """Biomedical literature search via PubMed (NCBI E-utilities).

    Free and key-less: ``NCBI_API_KEY`` only raises the request rate limit
    from 3/s to 10/s. PubMed indexes biomedicine, so queries with no
    biomedical signal are skipped instead of spending the relevance-filter
    budget on off-topic hits.
    """

    name = "pubmed"
    source_type = SourceType.PUBMED
    requires_academic_context = True
    first_variation_only = True
    default_max_results = 3

    def is_available(self) -> bool:
        # The tool needs Biopython's Entrez client; without it pubmed_search
        # raises ImportError, so the plugin reports itself unavailable.
        try:
            import Bio  # noqa: F401
        except ImportError:
            return False
        return True

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        if not is_biomedical_query(query):
            logger.debug("[PUBMED] Skipping non-biomedical query")
            return []
        results = await pubmed_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=r.url,
                title=r.title,
                author=_first_authors(r.authors),
                snippet=(r.abstract or r.journal or r.title)[:500],
                source_type=self.source_type,
                relevance_score=0.74,
            )
            for r in results
            if r.url
        ]


class SemanticScholarPlugin:
    """Academic search via Semantic Scholar.

    Free without a key (shared, heavily throttled pool); a key raises the
    per-client rate limit. Covers every discipline, so it stays behind the
    academic-context gate.
    """

    name = "semantic_scholar"
    source_type = SourceType.SEMANTIC_SCHOLAR
    requires_academic_context = True
    first_variation_only = True
    default_max_results = 3

    def is_available(self) -> bool:
        return True  # key is optional

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await semantic_scholar_search(
            query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=r.url,
                title=r.title,
                author=_first_authors(r.authors),
                snippet=(r.abstract or r.tldr or r.venue or r.title)[:500],
                source_type=self.source_type,
                relevance_score=0.77,
                pdf_url=r.open_access_pdf or None,
            )
            for r in results
            if r.url
        ]


class OpenAlexPlugin:
    """Scholarly search via OpenAlex (free, no key required).

    OpenAlex is a fully open index of works, authors and venues. It is asked
    to be polite through a ``mailto`` parameter rather than an API key. The
    citation URL is the DOI resolver when a DOI exists, so the same paper
    collected from Crossref or a reference list dedupes to one source.
    """

    name = "openalex"
    source_type = SourceType.OPENALEX
    requires_academic_context = True
    first_variation_only = True
    default_max_results = 3

    def is_available(self) -> bool:
        return True  # free, open, no key

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await openalex_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=_doi_url(r.doi) or r.url,
                title=r.title,
                author=_first_authors(r.authors),
                snippet=(r.abstract or r.venue or r.title)[:500],
                source_type=self.source_type,
                relevance_score=0.78,
                pdf_url=r.pdf_url or None,
            )
            for r in results
            if (_doi_url(r.doi) or r.url)
        ]


class CrossrefPlugin:
    """Scholarly metadata search via Crossref (free, no key required).

    Crossref is the DOI registration agency's own index, so it is the most
    reliable source of canonical citation metadata (journal, volume, page).
    """

    name = "crossref"
    source_type = SourceType.CROSSREF
    requires_academic_context = True
    first_variation_only = True
    default_max_results = 3

    def is_available(self) -> bool:
        return True  # free, open, no key

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await crossref_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=r.url or (_doi_url(r.doi) or ""),
                title=r.title,
                author=_first_authors(r.authors),
                snippet=(
                    _strip_markup(r.abstract)
                    or r.container_title
                    or r.publisher
                    or r.title
                )[:500],
                source_type=self.source_type,
                relevance_score=0.72,
            )
            for r in results
            if (r.url or r.doi)
        ]


class SpringerPlugin:
    """Academic metadata search via Springer Nature API."""

    name = "springer"
    source_type = SourceType.SPRINGER
    requires_academic_context = True
    first_variation_only = False
    default_max_results = 3

    def is_available(self) -> bool:
        return bool(settings.springer_api_key)

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await springer_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=r.url,
                title=r.title,
                author=", ".join(r.authors[:3]) if r.authors else None,
                snippet=(r.abstract or "")[:500],
                source_type=self.source_type,
                relevance_score=0.75,
            )
            for r in results
            if r.url
        ]


class ElsevierPlugin:
    """Academic metadata search via Elsevier Scopus API."""

    name = "elsevier"
    source_type = SourceType.ELSEVIER
    requires_academic_context = True
    first_variation_only = False
    default_max_results = 3

    def is_available(self) -> bool:
        return bool(settings.elsevier_api_key)

    async def search(self, query: str, max_results: int = 3) -> list[Citation]:
        results = await elsevier_search(query, max_results=max_results)
        return [
            Citation(
                id="[0]",
                url=r.url,
                title=r.title,
                author=", ".join(r.authors[:3]) if r.authors else None,
                snippet=(r.abstract or "")[:500],
                source_type=self.source_type,
                relevance_score=0.76,
            )
            for r in results
            if r.url
        ]


def register_defaults() -> None:
    """Register built-in plugins into the global tool registry."""
    from app.tools.registry import get_registry

    registry = get_registry()
    registry.register(WebSearchPlugin())
    registry.register(ArxivPlugin())
    registry.register(WikipediaPlugin())
    # Key-less, free-tier academic indexes. Registering them here is what
    # makes them run; the tools themselves predate the plugin wiring.
    registry.register(PubMedPlugin())
    registry.register(SemanticScholarPlugin())
    registry.register(OpenAlexPlugin())
    registry.register(CrossrefPlugin())
    # Publishers, enabled only when the matching API key is configured.
    registry.register(SpringerPlugin())
    registry.register(ElsevierPlugin())
    logger.debug(
        "[REGISTRY] Registered default plugins: web, arxiv, wikipedia, "
        "pubmed, semantic_scholar, openalex, crossref, springer, elsevier"
    )
