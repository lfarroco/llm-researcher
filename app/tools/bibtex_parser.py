"""
BibTeX parser and formatter.

Provides utilities for:
- Parsing BibTeX files/strings into structured data
- Converting between BibTeX entries and Citation objects
- Generating BibTeX entries from citations
- Validating BibTeX entries
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter
from pydantic import BaseModel, Field

from app.tools.base import ToolResponse, ToolErrorType

logger = logging.getLogger(__name__)


class BibTeXEntry(BaseModel):
    """A structured BibTeX entry."""
    
    entry_type: str = Field(description="Entry type (article, book, inproceedings, etc.)")
    cite_key: str = Field(description="Citation key/ID")
    title: Optional[str] = Field(default=None, description="Title of the work")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    year: Optional[int] = Field(default=None, description="Publication year")
    journal: Optional[str] = Field(default=None, description="Journal name")
    volume: Optional[str] = Field(default=None, description="Volume number")
    number: Optional[str] = Field(default=None, description="Issue number")
    pages: Optional[str] = Field(default=None, description="Page range")
    publisher: Optional[str] = Field(default=None, description="Publisher name")
    booktitle: Optional[str] = Field(default=None, description="Book title (for proceedings)")
    doi: Optional[str] = Field(default=None, description="Digital Object Identifier")
    url: Optional[str] = Field(default=None, description="URL to the resource")
    abstract: Optional[str] = Field(default=None, description="Abstract text")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    extra_fields: Dict[str, str] = Field(default_factory=dict, description="Other BibTeX fields")


def _parse_author_string(author_str: str) -> List[str]:
    """
    Parse BibTeX author string into list of individual authors.
    
    BibTeX uses "and" to separate authors.
    
    Args:
        author_str: Raw author string from BibTeX
        
    Returns:
        List of author names
    """
    if not author_str:
        return []
    
    # Split on " and " (case-insensitive)
    authors = [a.strip() for a in author_str.split(" and ")]
    return [a for a in authors if a]


def _format_authors_for_bibtex(authors: List[str]) -> str:
    """
    Format author list for BibTeX.
    
    Args:
        authors: List of author names
        
    Returns:
        BibTeX-formatted author string
    """
    if not authors:
        return ""
    return " and ".join(authors)


def _parse_keywords(keyword_str: str) -> List[str]:
    """
    Parse BibTeX keywords string into list.
    
    Keywords can be separated by commas or semicolons.
    """
    if not keyword_str:
        return []
    
    # Try comma first, then semicolon
    if "," in keyword_str:
        keywords = [k.strip() for k in keyword_str.split(",")]
    elif ";" in keyword_str:
        keywords = [k.strip() for k in keyword_str.split(";")]
    else:
        keywords = [keyword_str.strip()]
    
    return [k for k in keywords if k]


def parse_bibtex_string(bibtex_str: str) -> ToolResponse[BibTeXEntry]:
    """
    Parse a BibTeX string into structured entries.
    
    Args:
        bibtex_str: BibTeX formatted string
        
    Returns:
        ToolResponse containing list of BibTeXEntry objects
    """
    logger.info("[BibTeX] Parsing BibTeX string")
    
    if not bibtex_str or not bibtex_str.strip():
        return ToolResponse.fail(
            error_type=ToolErrorType.INVALID_INPUT,
            message="Empty BibTeX string provided"
        )
    
    try:
        parser = BibTexParser()
        parser.ignore_nonstandard_types = False  # Parse all entry types
        parser.homogenize_fields = True  # Normalize field names
        
        bib_db = bibtexparser.loads(bibtex_str, parser=parser)
        
        if not bib_db.entries:
            return ToolResponse.fail(
                error_type=ToolErrorType.PARSE_ERROR,
                message="No valid BibTeX entries found in string"
            )
        
        entries = []
        for entry_dict in bib_db.entries:
            # Extract standard fields
            entry_type = entry_dict.get("ENTRYTYPE", "misc").lower()
            cite_key = entry_dict.get("ID", "")
            
            # Parse authors
            author_str = entry_dict.get("author", "")
            authors = _parse_author_string(author_str)
            
            # Parse year
            year = None
            year_str = entry_dict.get("year", "")
            if year_str:
                try:
                    year = int(year_str)
                except (ValueError, TypeError):
                    logger.warning(f"[BibTeX] Invalid year format: {year_str}")
            
            # Parse keywords
            keyword_str = entry_dict.get("keywords", "")
            keywords = _parse_keywords(keyword_str)
            
            # Collect extra fields (non-standard or additional)
            standard_fields = {
                "ENTRYTYPE", "ID", "author", "title", "year", "journal",
                "volume", "number", "pages", "publisher", "booktitle",
                "doi", "url", "abstract", "keywords"
            }
            extra_fields = {
                k: v for k, v in entry_dict.items()
                if k not in standard_fields
            }
            
            entry = BibTeXEntry(
                entry_type=entry_type,
                cite_key=cite_key,
                title=entry_dict.get("title"),
                authors=authors,
                year=year,
                journal=entry_dict.get("journal"),
                volume=entry_dict.get("volume"),
                number=entry_dict.get("number"),
                pages=entry_dict.get("pages"),
                publisher=entry_dict.get("publisher"),
                booktitle=entry_dict.get("booktitle"),
                doi=entry_dict.get("doi"),
                url=entry_dict.get("url"),
                abstract=entry_dict.get("abstract"),
                keywords=keywords,
                extra_fields=extra_fields
            )
            entries.append(entry)
        
        logger.info(f"[BibTeX] Successfully parsed {len(entries)} entries")
        return ToolResponse.ok(entries)
        
    except Exception as e:
        logger.error(f"[BibTeX] Parsing failed: {e}")
        return ToolResponse.fail(
            error_type=ToolErrorType.PARSE_ERROR,
            message=f"Failed to parse BibTeX: {str(e)}",
            details={"error": str(e)}
        )


def parse_bibtex_file(file_path: str) -> ToolResponse[BibTeXEntry]:
    """
    Parse a BibTeX file into structured entries.
    
    Args:
        file_path: Path to the .bib file
        
    Returns:
        ToolResponse containing list of BibTeXEntry objects
    """
    logger.info(f"[BibTeX] Parsing file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            bibtex_str = f.read()
        
        return parse_bibtex_string(bibtex_str)
        
    except FileNotFoundError:
        return ToolResponse.fail(
            error_type=ToolErrorType.NOT_FOUND,
            message=f"BibTeX file not found: {file_path}"
        )
    except Exception as e:
        logger.error(f"[BibTeX] File reading failed: {e}")
        return ToolResponse.fail(
            error_type=ToolErrorType.PARSE_ERROR,
            message=f"Failed to read BibTeX file: {str(e)}",
            details={"file_path": file_path, "error": str(e)}
        )


def entry_to_bibtex_string(entry: BibTeXEntry) -> str:
    """
    Convert a BibTeXEntry back to BibTeX formatted string.
    
    Args:
        entry: BibTeXEntry object
        
    Returns:
        BibTeX formatted string for this entry
    """
    # Build entry dict
    entry_dict = {
        "ENTRYTYPE": entry.entry_type,
        "ID": entry.cite_key,
    }
    
    # Add standard fields
    if entry.title:
        entry_dict["title"] = entry.title
    if entry.authors:
        entry_dict["author"] = _format_authors_for_bibtex(entry.authors)
    if entry.year:
        entry_dict["year"] = str(entry.year)
    if entry.journal:
        entry_dict["journal"] = entry.journal
    if entry.volume:
        entry_dict["volume"] = entry.volume
    if entry.number:
        entry_dict["number"] = entry.number
    if entry.pages:
        entry_dict["pages"] = entry.pages
    if entry.publisher:
        entry_dict["publisher"] = entry.publisher
    if entry.booktitle:
        entry_dict["booktitle"] = entry.booktitle
    if entry.doi:
        entry_dict["doi"] = entry.doi
    if entry.url:
        entry_dict["url"] = entry.url
    if entry.abstract:
        entry_dict["abstract"] = entry.abstract
    if entry.keywords:
        entry_dict["keywords"] = ", ".join(entry.keywords)
    
    # Add extra fields
    entry_dict.update(entry.extra_fields)
    
    # Create BibDatabase and write
    db = BibDatabase()
    db.entries = [entry_dict]
    
    writer = BibTexWriter()
    writer.indent = "  "  # 2-space indentation
    writer.order_entries_by = None  # Keep original order
    
    return writer.write(db)


def entries_to_bibtex_string(entries: List[BibTeXEntry]) -> str:
    """
    Convert multiple BibTeXEntry objects to a single BibTeX string.
    
    Args:
        entries: List of BibTeXEntry objects
        
    Returns:
        BibTeX formatted string containing all entries
    """
    if not entries:
        return ""
    
    entry_strings = [entry_to_bibtex_string(e) for e in entries]
    return "\n".join(entry_strings)


def create_citation_key(
    authors: List[str],
    year: Optional[int] = None,
    title: Optional[str] = None
) -> str:
    """
    Generate a BibTeX citation key from author(s), year, and title.
    
    Format: FirstAuthorLastName + Year + FirstTitleWord
    Example: Smith2020Machine
    
    Args:
        authors: List of author names
        year: Publication year
        title: Paper title
        
    Returns:
        Generated citation key
    """
    # Get first author's last name
    if authors:
        # Try to extract last name (assumes "FirstName LastName" format)
        first_author = authors[0]
        parts = first_author.split()
        if len(parts) > 1:
            last_name = parts[-1]
        else:
            last_name = first_author
        # Remove non-alphanumeric characters
        last_name = "".join(c for c in last_name if c.isalnum())
    else:
        last_name = "Unknown"
    
    # Year component
    year_str = str(year) if year else "XXXX"
    
    # First title word (optional)
    title_word = ""
    if title:
        # Get first significant word from title (skip articles)
        title_words = title.split()
        skip_words = {"the", "a", "an", "on", "in", "at", "of", "for"}
        for word in title_words:
            clean_word = "".join(c for c in word if c.isalnum())
            if clean_word.lower() not in skip_words and len(clean_word) > 2:
                title_word = clean_word.capitalize()
                break
    
    # Combine
    if title_word:
        return f"{last_name}{year_str}{title_word}"
    else:
        return f"{last_name}{year_str}"


def validate_bibtex_entry(entry: BibTeXEntry) -> tuple[bool, List[str]]:
    """
    Validate a BibTeX entry for required fields based on entry type.
    
    Args:
        entry: BibTeXEntry to validate
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Check cite_key
    if not entry.cite_key:
        errors.append("Missing citation key")
    
    # Required fields by entry type
    required_fields = {
        "article": ["title", "authors", "journal", "year"],
        "book": ["title", "authors", "publisher", "year"],
        "inproceedings": ["title", "authors", "booktitle", "year"],
        "proceedings": ["title", "year"],
        "phdthesis": ["title", "authors", "year"],
        "mastersthesis": ["title", "authors", "year"],
        "techreport": ["title", "authors", "year"],
        "misc": ["title"],  # Minimal requirements
    }
    
    # Get required fields for this type (default to misc)
    required = required_fields.get(entry.entry_type.lower(), required_fields["misc"])
    
    for field in required:
        value = getattr(entry, field, None)
        if not value:
            errors.append(f"Missing required field for {entry.entry_type}: {field}")
    
    return (len(errors) == 0, errors)


def merge_bibtex_entries(
    entry1: BibTeXEntry,
    entry2: BibTeXEntry,
    prefer_entry1: bool = True
) -> BibTeXEntry:
    """
    Merge two BibTeX entries, filling in missing fields.
    
    Useful for combining metadata from multiple sources.
    
    Args:
        entry1: First entry
        entry2: Second entry
        prefer_entry1: If True, prefer fields from entry1 when both have values
        
    Returns:
        Merged BibTeXEntry
    """
    if prefer_entry1:
        primary, secondary = entry1, entry2
    else:
        primary, secondary = entry2, entry1
    
    # Start with primary entry fields
    merged_data = primary.model_dump()
    
    # Fill in missing fields from secondary
    for field, value in secondary.model_dump().items():
        if field in ["authors", "keywords"]:
            # Merge lists
            if not merged_data[field] and value:
                merged_data[field] = value
        elif field == "extra_fields":
            # Merge dicts
            merged_data[field] = {**secondary.extra_fields, **primary.extra_fields}
        else:
            # Use secondary if primary is missing
            if not merged_data[field] and value:
                merged_data[field] = value
    
    return BibTeXEntry(**merged_data)
