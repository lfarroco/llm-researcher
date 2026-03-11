"""Search and scraping tools for research agents."""

from app.tools.base import (
    BaseSearchResult,
    ToolError,
    ToolErrorType,
    ToolResponse,
    get_setting,
)
from app.tools.registry import SearchPlugin, ToolRegistry, get_registry
from app.tools.plugins import (
    WebSearchPlugin,
    ArxivPlugin,
    WikipediaPlugin,
    SpringerPlugin,
    register_defaults,
)
from app.tools.web_search import web_search, WebSearchResult
from app.tools.arxiv_search import arxiv_search, ArxivResult
from app.tools.wikipedia import wikipedia_search, WikipediaResult
from app.tools.web_scraper import scrape_url, ScrapedContent
from app.tools.reference_extractor import (
    extract_references_from_url,
    extract_references_from_html,
    extract_wikipedia_references,
    extract_academic_references,
    ExtractedReference,
)
from app.tools.pubmed_search import pubmed_search, PubMedResult
from app.tools.semantic_scholar import (
    semantic_scholar_search,
    SemanticScholarResult,
    get_paper_details,
    get_paper_citations,
    get_paper_references,
)
from app.tools.openalex_search import (
    openalex_search,
    OpenAlexResult,
    openalex_lookup_doi,
)
from app.tools.springer_search import springer_search, SpringerResult

__all__ = [
    # Base types
    "BaseSearchResult",
    "ToolError",
    "ToolErrorType",
    "ToolResponse",
    "get_setting",
    # Plugin system
    "SearchPlugin",
    "ToolRegistry",
    "get_registry",
    "WebSearchPlugin",
    "ArxivPlugin",
    "WikipediaPlugin",
    "SpringerPlugin",
    "register_defaults",
    # Web search
    "web_search",
    "WebSearchResult",
    # ArXiv
    "arxiv_search",
    "ArxivResult",
    # Wikipedia
    "wikipedia_search",
    "WikipediaResult",
    # Web scraper
    "scrape_url",
    "ScrapedContent",
    # PubMed
    "pubmed_search",
    "PubMedResult",
    # Semantic Scholar
    "semantic_scholar_search",
    "SemanticScholarResult",
    "get_paper_details",
    "get_paper_citations",
    "get_paper_references",
    # OpenAlex
    "openalex_search",
    "OpenAlexResult",
    "openalex_lookup_doi",
    # Springer
    "springer_search",
    "SpringerResult",
    # Reference extractor
    "extract_references_from_url",
    "extract_references_from_html",
    "extract_wikipedia_references",
    "extract_academic_references",
    "ExtractedReference",
]
