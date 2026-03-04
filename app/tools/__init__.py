"""Search and scraping tools for research agents."""

from app.tools.web_search import web_search, WebSearchResult
from app.tools.arxiv_search import arxiv_search, ArxivResult
from app.tools.wikipedia import wikipedia_search, WikipediaResult
from app.tools.web_scraper import scrape_url, ScrapedContent

__all__ = [
    "web_search",
    "WebSearchResult",
    "arxiv_search",
    "ArxivResult",
    "wikipedia_search",
    "WikipediaResult",
    "scrape_url",
    "ScrapedContent",
]
