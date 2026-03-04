"""
PubMed/MEDLINE search tool for biomedical literature.

Uses NCBI's Entrez API via Biopython to search PubMed,
which contains over 35 million citations for biomedical literature.
"""

import logging
from typing import Optional
from xml.etree import ElementTree

from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

# NCBI requires an email for API access
ENTREZ_EMAIL = "llm-researcher@example.com"


class PubMedResult(BaseModel):
    """A single PubMed article result."""

    pmid: str = Field(description="PubMed ID")
    title: str = Field(description="Article title")
    authors: list[str] = Field(description="List of author names")
    abstract: str = Field(description="Article abstract")
    journal: str = Field(description="Journal name")
    pub_date: str = Field(description="Publication date")
    url: str = Field(description="PubMed article URL")
    doi: Optional[str] = Field(default=None, description="DOI if available")
    mesh_terms: list[str] = Field(
        default_factory=list, description="MeSH terms")


async def pubmed_search(
    query: str,
    max_results: int = 5,
    sort: str = "relevance",
) -> list[PubMedResult]:
    """
    Search PubMed for biomedical literature.

    Args:
        query: Search query (supports PubMed query syntax)
        max_results: Maximum number of results
        sort: Sort order - "relevance" or "pub_date"

    Returns:
        List of PubMedResult objects
    """
    logger.info(f"[PUBMED] Starting search for: '{query[:80]}...'")
    logger.debug(
        f"[PUBMED] Parameters: max_results={max_results}, sort={sort}")

    try:
        from Bio import Entrez
    except ImportError as e:
        logger.error(
            "[PUBMED] Biopython not installed. Install with: pip install biopython")
        raise ImportError(
            "Biopython is required for PubMed search. "
            "Install with: pip install biopython"
        ) from e

    # Configure Entrez
    Entrez.email = getattr(settings, 'ncbi_email', ENTREZ_EMAIL)
    api_key = getattr(settings, 'ncbi_api_key', None)
    if api_key:
        Entrez.api_key = api_key
        logger.debug("[PUBMED] Using NCBI API key for higher rate limits")

    # Map sort options
    sort_param = "relevance" if sort == "relevance" else "pub_date"

    try:
        # First, search for PMIDs
        logger.debug("[PUBMED] Searching for article IDs")
        search_handle = Entrez.esearch(
            db="pubmed",
            term=query,
            retmax=max_results,
            sort=sort_param,
        )
        search_results = Entrez.read(search_handle)
        search_handle.close()

        pmids = search_results.get("IdList", [])
        logger.debug(f"[PUBMED] Found {len(pmids)} article IDs")

        if not pmids:
            logger.info("[PUBMED] No results found")
            return []

        # Fetch article details
        logger.debug("[PUBMED] Fetching article details")
        fetch_handle = Entrez.efetch(
            db="pubmed",
            id=",".join(pmids),
            rettype="xml",
            retmode="xml",
        )
        fetch_data = fetch_handle.read()
        fetch_handle.close()

        # Parse XML results
        results = _parse_pubmed_xml(fetch_data)
        logger.info(
            f"[PUBMED] Search complete, returning {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"[PUBMED] Search failed: {e}")
        raise


def _parse_pubmed_xml(xml_data: bytes) -> list[PubMedResult]:
    """Parse PubMed XML response into structured results."""
    results = []

    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError as e:
        logger.error(f"[PUBMED] Failed to parse XML: {e}")
        return []

    for article in root.findall(".//PubmedArticle"):
        try:
            medline_citation = article.find("MedlineCitation")
            if medline_citation is None:
                continue

            # Get PMID
            pmid_elem = medline_citation.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            # Get article info
            article_elem = medline_citation.find("Article")
            if article_elem is None:
                continue

            # Title
            title_elem = article_elem.find("ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Abstract
            abstract_parts = []
            abstract_elem = article_elem.find("Abstract")
            if abstract_elem is not None:
                for abstract_text in abstract_elem.findall("AbstractText"):
                    label = abstract_text.get("Label", "")
                    text = abstract_text.text or ""
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts)[:2000]  # Limit length

            # Authors
            authors = []
            author_list = article_elem.find("AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last_name = author.find("LastName")
                    fore_name = author.find("ForeName")
                    if last_name is not None:
                        name = last_name.text or ""
                        if fore_name is not None and fore_name.text:
                            name = f"{fore_name.text} {name}"
                        authors.append(name)

            # Journal
            journal_elem = article_elem.find("Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""

            # Publication date
            pub_date_elem = article_elem.find("Journal/JournalIssue/PubDate")
            pub_date = ""
            if pub_date_elem is not None:
                year = pub_date_elem.find("Year")
                month = pub_date_elem.find("Month")
                if year is not None:
                    pub_date = year.text or ""
                    if month is not None and month.text:
                        pub_date = f"{month.text} {pub_date}"

            # DOI
            doi = None
            article_id_list = article.find(".//ArticleIdList")
            if article_id_list is not None:
                for article_id in article_id_list.findall("ArticleId"):
                    if article_id.get("IdType") == "doi":
                        doi = article_id.text

            # MeSH terms
            mesh_terms = []
            mesh_list = medline_citation.find("MeshHeadingList")
            if mesh_list is not None:
                for mesh in mesh_list.findall("MeshHeading/DescriptorName"):
                    if mesh.text:
                        mesh_terms.append(mesh.text)

            results.append(PubMedResult(
                pmid=pmid,
                title=title,
                authors=authors[:10],  # Limit to first 10 authors
                abstract=abstract,
                journal=journal,
                pub_date=pub_date,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                doi=doi,
                mesh_terms=mesh_terms[:10],  # Limit MeSH terms
            ))

        except Exception as e:
            logger.warning(f"[PUBMED] Failed to parse article: {e}")
            continue

    return results


def is_biomedical_query(query: str) -> bool:
    """
    Heuristic to determine if a query would benefit from PubMed.

    Returns True if the query contains biomedical-related keywords.
    """
    biomedical_keywords = [
        "medical", "medicine", "health", "disease", "treatment",
        "drug", "therapy", "clinical", "patient", "diagnosis",
        "symptom", "syndrome", "hospital", "doctor", "physician",
        "cancer", "cell", "gene", "protein", "molecular",
        "biology", "biological", "biochem", "pharma", "cardio",
        "neuro", "immune", "virus", "bacteria", "infection",
        "surgery", "pathology", "epidemiology", "trial",
        "efficacy", "dosage", "adverse", "mortality", "morbidity",
    ]

    query_lower = query.lower()
    return any(keyword in query_lower for keyword in biomedical_keywords)
