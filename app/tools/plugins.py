"""
Default search plugins shipped with llm-researcher.

Each class wraps one of the tool functions in app/tools/ and implements the
SearchPlugin protocol, handling the mapping from tool-specific result types to
the common Citation model.

The built-in plugins (web, arxiv, wikipedia, springer, elsevier) are
registered into the
global ToolRegistry via :func:`register_defaults`, which is called during
application startup from app/main.py.

To add a custom plugin without touching this file:

    from app.tools.registry import get_registry
    get_registry().register(MyPlugin())
"""

import logging

from app.config import settings
from app.memory.research_state import Citation, SourceType
from app.tools.arxiv_search import arxiv_search
from app.tools.elsevier_search import elsevier_search
from app.tools.springer_search import springer_search
from app.tools.web_search import web_search
from app.tools.wikipedia import wikipedia_search

logger = logging.getLogger(__name__)


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
    first_variation_only = False
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
    registry.register(SpringerPlugin())
    registry.register(ElsevierPlugin())
    logger.debug(
        "[REGISTRY] Registered default plugins: web, arxiv, wikipedia, "
        "springer, elsevier"
    )
