"""
Reference extractor - pulls references/citations from web pages and articles.

Given a URL (web page, Wikipedia article, or academic paper), this tool
extracts outbound references that may be worth following for deeper research.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Request configuration
REQUEST_TIMEOUT = 15.0
USER_AGENT = (
    "Mozilla/5.0 (compatible; LLMResearcher/1.0; "
    "+https://github.com/lfarroco/llm-researcher)"
)

# Domains/patterns to skip (navigation, social, ads, etc.)
SKIP_DOMAINS = {
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "youtube.com", "reddit.com", "tiktok.com",
    "pinterest.com", "amazon.com", "ebay.com", "google.com",
    "bing.com", "yahoo.com", "apple.com", "microsoft.com",
    "play.google.com", "apps.apple.com",
}

SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".mp3", ".mp4", ".avi", ".mov", ".pdf", ".zip", ".tar",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
}


class ExtractedReference(BaseModel):
    """A reference extracted from a source page."""

    url: str = Field(description="URL of the referenced resource")
    title: str = Field(default="", description="Link text or title")
    context: str = Field(
        default="",
        description="Surrounding text context for the reference"
    )
    source_url: str = Field(
        description="URL of the page this reference was found on"
    )
    ref_type: str = Field(
        default="link",
        description="Type: link|footnote|bibliography|wikipedia_ref|academic"
    )


def _is_useful_url(url: str, source_domain: str) -> bool:
    """Filter out non-useful URLs (navigation, images, social, etc.)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Must have scheme and netloc
    if not parsed.scheme or not parsed.netloc:
        return False

    # Only http(s)
    if parsed.scheme not in ("http", "https"):
        return False

    # Skip known non-reference domains
    domain = parsed.netloc.lower().replace("www.", "")
    if domain in SKIP_DOMAINS:
        return False

    # Skip file extensions that aren't documents
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return False

    # Skip anchors to the same page
    if domain == source_domain and (
        not parsed.path or parsed.path == "/"
    ):
        return False

    # Skip very short paths (usually homepages/navigation)
    if len(parsed.path) <= 1 and not parsed.query:
        return False

    return True


async def extract_references_from_html(
    url: str,
    html: str,
    max_refs: int = 30,
) -> list[ExtractedReference]:
    """
    Extract reference-like links from HTML content.

    Focuses on links that look like citations/references rather than
    navigation links. Prioritizes:
    - Links in footnotes, bibliography, or reference sections
    - Links with citation-like context
    - External links (not same-domain navigation)

    Args:
        url: The source URL
        html: Raw HTML content
        max_refs: Maximum references to extract

    Returns:
        List of ExtractedReference objects
    """
    from bs4 import BeautifulSoup

    logger.debug(f"[REF_EXTRACT] Parsing HTML from {url}")
    soup = BeautifulSoup(html, "html.parser")
    source_domain = urlparse(url).netloc.lower().replace("www.", "")

    references = []
    seen_urls = set()

    # Strategy 1: Look for dedicated reference/citation sections
    ref_sections = _find_reference_sections(soup)
    for section in ref_sections:
        for link in section.find_all("a", href=True):
            ref_url = urljoin(url, link["href"])
            if ref_url in seen_urls:
                continue
            if not _is_useful_url(ref_url, source_domain):
                continue
            seen_urls.add(ref_url)

            # Get surrounding text for context
            parent_text = link.parent.get_text(
                strip=True)[:200] if link.parent else ""

            references.append(ExtractedReference(
                url=ref_url,
                title=link.get_text(strip=True)[:200],
                context=parent_text,
                source_url=url,
                ref_type="bibliography",
            ))

    # Strategy 2: Look for footnote-style links ([1], [2], etc.)
    for link in soup.find_all("a", href=True):
        ref_url = urljoin(url, link["href"])
        if ref_url in seen_urls:
            continue
        if not _is_useful_url(ref_url, source_domain):
            continue

        link_text = link.get_text(strip=True)
        # Check if it looks like a footnote reference
        is_footnote = bool(re.match(r'^\[\d+\]$', link_text))
        # Or if the link has a citation-like class
        link_classes = " ".join(link.get("class", []))
        is_citation_class = any(
            kw in link_classes.lower()
            for kw in ["cite", "ref", "footnote", "note", "biblio"]
        )

        if is_footnote or is_citation_class:
            seen_urls.add(ref_url)
            parent_text = link.parent.get_text(
                strip=True)[:200] if link.parent else ""
            references.append(ExtractedReference(
                url=ref_url,
                title=link_text,
                context=parent_text,
                source_url=url,
                ref_type="footnote",
            ))

    # Strategy 3: External links (not same domain) in article body
    # These are often inline citations or "further reading"
    article_body = _find_article_body(soup)
    if article_body:
        for link in article_body.find_all("a", href=True):
            ref_url = urljoin(url, link["href"])
            if ref_url in seen_urls:
                continue
            if not _is_useful_url(ref_url, source_domain):
                continue

            ref_domain = urlparse(ref_url).netloc.lower().replace("www.", "")
            if ref_domain == source_domain:
                continue  # Skip same-domain links in body

            seen_urls.add(ref_url)
            parent_text = link.parent.get_text(
                strip=True)[:200] if link.parent else ""
            references.append(ExtractedReference(
                url=ref_url,
                title=link.get_text(strip=True)[:200],
                context=parent_text,
                source_url=url,
                ref_type="link",
            ))

    logger.info(
        f"[REF_EXTRACT] Extracted {len(references)} references from {url}"
    )
    return references[:max_refs]


def _find_reference_sections(soup) -> list:
    """Find HTML sections that likely contain references/bibliography."""
    sections = []

    # Look for elements with reference-related IDs or classes
    ref_keywords = [
        "reference", "bibliography", "citations", "works-cited",
        "further-reading", "sources", "footnotes", "endnotes",
        "refs", "cite_note",
    ]

    for keyword in ref_keywords:
        # By ID
        elements = soup.find_all(id=re.compile(keyword, re.IGNORECASE))
        sections.extend(elements)

        # By class
        elements = soup.find_all(
            class_=re.compile(keyword, re.IGNORECASE)
        )
        sections.extend(elements)

    # Look for headings followed by lists (common reference pattern)
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text(strip=True).lower()
        if any(kw in heading_text for kw in ref_keywords):
            # Get the next sibling elements (likely the reference list)
            sibling = heading.find_next_sibling()
            if sibling:
                sections.append(sibling)

    return sections


def _find_article_body(soup):
    """Find the main article body element."""
    # Try common article body selectors
    for selector in [
        "article", "main",
        {"role": "main"},
        {"class_": re.compile(r"article|content|post|entry", re.IGNORECASE)},
        {"id": re.compile(r"article|content|post|entry", re.IGNORECASE)},
    ]:
        if isinstance(selector, str):
            body = soup.find(selector)
        else:
            body = soup.find(**selector)
        if body:
            return body

    return soup.body


async def extract_references_from_url(
    url: str,
    max_refs: int = 30,
) -> list[ExtractedReference]:
    """
    Fetch a URL and extract its references.

    Args:
        url: URL to fetch and extract references from
        max_refs: Maximum number of references to extract

    Returns:
        List of ExtractedReference objects
    """
    logger.info(f"[REF_EXTRACT] Fetching URL for reference extraction: {url}")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            response.raise_for_status()
            html = response.text
    except Exception as e:
        logger.warning(f"[REF_EXTRACT] Failed to fetch {url}: {e}")
        return []

    return await extract_references_from_html(url, html, max_refs)


async def extract_wikipedia_references(
    page_title: str,
) -> list[ExtractedReference]:
    """
    Extract references from a Wikipedia page using the wikipedia library.

    Wikipedia pages have structured references that are especially valuable.

    Args:
        page_title: Title of the Wikipedia page

    Returns:
        List of ExtractedReference objects
    """
    import wikipedia as wiki_lib

    logger.info(
        f"[REF_EXTRACT] Extracting Wikipedia references for: {page_title}"
    )

    try:
        page = wiki_lib.page(page_title, auto_suggest=False)
    except (wiki_lib.exceptions.PageError,
            wiki_lib.exceptions.DisambiguationError) as e:
        logger.warning(
            f"[REF_EXTRACT] Wikipedia page error for '{page_title}': {e}"
        )
        return []

    references = []
    page_url = page.url

    # wikipedia.page.references gives us all external reference URLs
    for ref_url in page.references:
        if not _is_useful_url(ref_url, "wikipedia.org"):
            continue

        references.append(ExtractedReference(
            url=ref_url,
            title="",  # Wikipedia references don't carry titles easily
            context=f"Referenced from Wikipedia article: {page_title}",
            source_url=page_url,
            ref_type="wikipedia_ref",
        ))

    logger.info(
        f"[REF_EXTRACT] Found {len(references)} Wikipedia references "
        f"for '{page_title}'"
    )
    return references


async def extract_academic_references(
    paper_id: str,
    max_refs: int = 10,
) -> list[ExtractedReference]:
    """
    Extract references from an academic paper via Semantic Scholar.

    Args:
        paper_id: Semantic Scholar paper ID, DOI, or ArXiv ID
        max_refs: Maximum number of references to return

    Returns:
        List of ExtractedReference objects
    """
    from app.tools.semantic_scholar import get_paper_references

    logger.info(
        f"[REF_EXTRACT] Extracting academic references for paper: {paper_id}"
    )

    try:
        papers = await get_paper_references(paper_id, max_results=max_refs)
    except Exception as e:
        logger.warning(
            f"[REF_EXTRACT] Failed to get academic references: {e}"
        )
        return []

    references = []
    for paper in papers:
        references.append(ExtractedReference(
            url=paper.url,
            title=paper.title,
            context=paper.abstract[:300] if paper.abstract else "",
            source_url=f"https://www.semanticscholar.org/paper/{paper_id}",
            ref_type="academic",
        ))

    logger.info(
        f"[REF_EXTRACT] Found {len(references)} academic references"
    )
    return references
