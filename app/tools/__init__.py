"""Search and scraping tools for research agents."""

from app.tools.base import (
    BaseSearchResult,
    ToolError,
    ToolErrorType,
    ToolResponse,
    get_setting,
)
from app.tools.web_search import web_search, WebSearchResult
from app.tools.arxiv_search import arxiv_search, ArxivResult
from app.tools.wikipedia import wikipedia_search, WikipediaResult
from app.tools.web_scraper import scrape_url, ScrapedContent
from app.tools.pubmed_search import pubmed_search, PubMedResult
from app.tools.semantic_scholar import (
    semantic_scholar_search,
    SemanticScholarResult,
    get_paper_details,
    get_paper_citations,
    get_paper_references,
)

__all__ = [
    # Base types
    "BaseSearchResult",
    "ToolError",
    "ToolErrorType",
    "ToolResponse",
    "get_setting",
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
]
