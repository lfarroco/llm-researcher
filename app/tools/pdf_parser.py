"""
PDF parsing tool using GROBID and fallback parsers.

Extracts structured content from academic PDFs including:
- Title, authors, abstract
- Full text with sections
- References/citations
- Figures and tables metadata
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from pydantic import BaseModel, Field
from grobid_client.grobid_client import GrobidClient
import pdfplumber
from PyPDF2 import PdfReader
import bibtexparser

from app.tools.base import ToolResponse, ToolErrorType, get_setting
from app.tools.pdf_download import download_pdf

logger = logging.getLogger(__name__)

# Default GROBID settings
DEFAULT_GROBID_SERVER = "http://grobid:8070"


class PDFSection(BaseModel):
    """A section of the PDF document."""
    
    heading: str = Field(description="Section heading/title")
    content: str = Field(description="Section text content")
    level: int = Field(default=1, description="Heading level (1=main, 2=sub, etc.)")


class PDFReference(BaseModel):
    """A reference/citation extracted from the PDF."""
    
    raw_text: str = Field(description="Raw reference text")
    title: Optional[str] = Field(default=None, description="Paper title if parsed")
    authors: Optional[List[str]] = Field(default=None, description="Author list if parsed")
    year: Optional[int] = Field(default=None, description="Publication year if parsed")
    doi: Optional[str] = Field(default=None, description="DOI if available")


class PDFFigure(BaseModel):
    """Metadata about a figure in the PDF."""
    
    number: str = Field(description="Figure number/label")
    caption: Optional[str] = Field(default=None, description="Figure caption")
    page: int = Field(description="Page number where figure appears")


class PDFTable(BaseModel):
    """Metadata about a table in the PDF."""
    
    number: str = Field(description="Table number/label")
    caption: Optional[str] = Field(default=None, description="Table caption")
    page: int = Field(description="Page number where table appears")


class ParsedPDF(BaseModel):
    """Complete parsed PDF document."""
    
    title: Optional[str] = Field(default=None, description="Document title")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    abstract: Optional[str] = Field(default=None, description="Abstract text")
    sections: List[PDFSection] = Field(default_factory=list, description="Document sections")
    references: List[PDFReference] = Field(default_factory=list, description="References/bibliography")
    figures: List[PDFFigure] = Field(default_factory=list, description="Figure metadata")
    tables: List[PDFTable] = Field(default_factory=list, description="Table metadata")
    keywords: List[str] = Field(default_factory=list, description="Keywords if available")
    full_text: str = Field(default="", description="Complete document text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    parser_used: str = Field(description="Which parser was used (grobid/pdfplumber/pypdf2)")


def _get_grobid_server() -> str:
    """Get the GROBID server URL from settings or default."""
    return get_setting("GROBID_SERVER", DEFAULT_GROBID_SERVER) or DEFAULT_GROBID_SERVER


def _parse_with_grobid(pdf_path: str) -> Optional[ParsedPDF]:
    """
    Parse PDF using GROBID for high-quality structured extraction.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        ParsedPDF if successful, None on error
    """
    try:
        grobid_server = _get_grobid_server()
        logger.info(f"[PDF Parser] Using GROBID server: {grobid_server}")
        
        client = GrobidClient(grobid_server=grobid_server)
        
        # Process the PDF using GROBID's processFulltextDocument endpoint
        # This returns TEI XML with structured content
        result = client.process_pdf(
            "processFulltextDocument",
            pdf_path,
            generateIDs=True,
            consolidate_header=True,
            consolidate_citations=False,  # Faster without full citation resolution
            include_raw_citations=True,
            include_raw_affiliations=True,
            tei_coordinates=False,
            segment_sentences=False,
        )
        
        if not result:
            logger.warning("[PDF Parser] GROBID returned empty result")
            return None
        
        # Parse the TEI XML response
        import xml.etree.ElementTree as ET
        
        # GROBID returns bytes, decode to string
        if isinstance(result, bytes):
            result = result.decode('utf-8')
        
        root = ET.fromstring(result)
        
        # Define XML namespaces used by GROBID
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        
        # Extract title
        title = None
        title_elem = root.find('.//tei:titleStmt/tei:title[@type="main"]', ns)
        if title_elem is not None and title_elem.text:
            title = title_elem.text.strip()
        
        # Extract authors
        authors = []
        for author in root.findall('.//tei:sourceDesc//tei:persName', ns):
            forename = author.find('tei:forename', ns)
            surname = author.find('tei:surname', ns)
            if forename is not None and surname is not None:
                name = f"{forename.text} {surname.text}".strip()
                if name:
                    authors.append(name)
        
        # Extract abstract
        abstract = None
        abstract_elem = root.find('.//tei:profileDesc/tei:abstract', ns)
        if abstract_elem is not None:
            abstract_parts = []
            for p in abstract_elem.findall('.//tei:p', ns):
                if p.text:
                    abstract_parts.append(p.text.strip())
            abstract = ' '.join(abstract_parts)
        
        # Extract sections
        sections = []
        for div in root.findall('.//tei:body//tei:div', ns):
            head = div.find('tei:head', ns)
            if head is not None and head.text:
                heading = head.text.strip()
                content_parts = []
                for p in div.findall('.//tei:p', ns):
                    if p.text:
                        content_parts.append(p.text.strip())
                content = ' '.join(content_parts)
                if content:
                    sections.append(PDFSection(
                        heading=heading,
                        content=content,
                        level=1
                    ))
        
        # Extract references
        references = []
        for bibl in root.findall('.//tei:listBibl/tei:biblStruct', ns):
            ref_title = None
            title_elem = bibl.find('.//tei:title[@type="main"]', ns)
            if title_elem is not None and title_elem.text:
                ref_title = title_elem.text.strip()
            
            ref_authors = []
            for author in bibl.findall('.//tei:author//tei:persName', ns):
                forename = author.find('tei:forename', ns)
                surname = author.find('tei:surname', ns)
                if surname is not None and surname.text:
                    name = surname.text
                    if forename is not None and forename.text:
                        name = f"{forename.text} {surname.text}"
                    ref_authors.append(name.strip())
            
            ref_year = None
            date_elem = bibl.find('.//tei:date[@type="published"]', ns)
            if date_elem is not None and date_elem.get('when'):
                try:
                    ref_year = int(date_elem.get('when')[:4])
                except (ValueError, TypeError):
                    pass
            
            ref_doi = None
            doi_elem = bibl.find('.//tei:idno[@type="DOI"]', ns)
            if doi_elem is not None and doi_elem.text:
                ref_doi = doi_elem.text.strip()
            
            # Get raw text as fallback
            raw_text = ref_title or "Unknown reference"
            
            references.append(PDFReference(
                raw_text=raw_text,
                title=ref_title,
                authors=ref_authors if ref_authors else None,
                year=ref_year,
                doi=ref_doi
            ))
        
        # Extract keywords
        keywords = []
        for keyword in root.findall('.//tei:keywords//tei:term', ns):
            if keyword.text:
                keywords.append(keyword.text.strip())
        
        # Combine all text for full_text
        full_text_parts = []
        if abstract:
            full_text_parts.append(abstract)
        for section in sections:
            full_text_parts.append(section.content)
        full_text = '\n\n'.join(full_text_parts)
        
        logger.info(
            f"[PDF Parser] GROBID extracted: "
            f"title={bool(title)}, authors={len(authors)}, "
            f"sections={len(sections)}, refs={len(references)}"
        )
        
        return ParsedPDF(
            title=title,
            authors=authors,
            abstract=abstract,
            sections=sections,
            references=references,
            figures=[],  # GROBID can extract these but requires more parsing
            tables=[],   # GROBID can extract these but requires more parsing
            keywords=keywords,
            full_text=full_text,
            metadata={},
            parser_used="grobid"
        )
        
    except Exception as e:
        logger.error(f"[PDF Parser] GROBID failed: {e}")
        return None


def _parse_with_pdfplumber(pdf_path: str) -> ParsedPDF:
    """
    Fallback parser using pdfplumber for basic text extraction.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        ParsedPDF with basic text extraction
    """
    logger.info("[PDF Parser] Using pdfplumber fallback")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text_parts = []
            
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text_parts.append(text)
            
            full_text = '\n\n'.join(full_text_parts)
            
            # Try to extract title from first page (heuristic: first non-empty line)
            title = None
            if full_text_parts:
                first_lines = full_text_parts[0].split('\n')
                for line in first_lines:
                    line = line.strip()
                    if line and len(line) > 10:  # Skip very short lines
                        title = line
                        break
            
            logger.info(
                f"[PDF Parser] pdfplumber extracted {len(full_text_parts)} pages"
            )
            
            return ParsedPDF(
                title=title,
                authors=[],
                abstract=None,
                sections=[],
                references=[],
                figures=[],
                tables=[],
                keywords=[],
                full_text=full_text,
                metadata={"num_pages": len(pdf.pages)},
                parser_used="pdfplumber"
            )
            
    except Exception as e:
        logger.error(f"[PDF Parser] pdfplumber failed: {e}")
        raise


def _parse_with_pypdf2(pdf_path: str) -> ParsedPDF:
    """
    Last-resort fallback parser using PyPDF2 for very basic text extraction.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        ParsedPDF with minimal text extraction
    """
    logger.info("[PDF Parser] Using PyPDF2 last-resort fallback")
    
    try:
        reader = PdfReader(pdf_path)
        full_text_parts = []
        
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text_parts.append(text)
        
        full_text = '\n\n'.join(full_text_parts)
        
        # Try to extract title from metadata
        title = None
        if reader.metadata and reader.metadata.title:
            title = reader.metadata.title
        
        logger.info(
            f"[PDF Parser] PyPDF2 extracted {len(reader.pages)} pages"
        )
        
        return ParsedPDF(
            title=title,
            authors=[],
            abstract=None,
            sections=[],
            references=[],
            figures=[],
            tables=[],
            keywords=[],
            full_text=full_text,
            metadata={"num_pages": len(reader.pages)},
            parser_used="pypdf2"
        )
        
    except Exception as e:
        logger.error(f"[PDF Parser] PyPDF2 failed: {e}")
        raise


async def parse_pdf_from_url(url: str, force_redownload: bool = False) -> ToolResponse[ParsedPDF]:
    """
    Download and parse a PDF from a URL.
    
    Uses GROBID for high-quality extraction with fallbacks to pdfplumber and PyPDF2.
    
    Args:
        url: URL of the PDF to parse
        force_redownload: If True, redownload even if cached
        
    Returns:
        ToolResponse containing parsed PDF data
    """
    logger.info(f"[PDF Parser] Parsing PDF from: {url}")
    
    # Download the PDF first
    download_result = await download_pdf(url, force_redownload=force_redownload)
    
    if not download_result.success or not download_result.file_path:
        return ToolResponse.fail(
            error_type=ToolErrorType.NETWORK_ERROR,
            message=f"Failed to download PDF: {download_result.error}",
            details={"url": url}
        )
    
    pdf_path = download_result.file_path
    
    try:
        # Try GROBID first (best quality)
        parsed_pdf = _parse_with_grobid(pdf_path)
        
        # If GROBID fails, try pdfplumber
        if parsed_pdf is None:
            logger.warning("[PDF Parser] GROBID failed, trying pdfplumber")
            try:
                parsed_pdf = _parse_with_pdfplumber(pdf_path)
            except Exception as e:
                logger.warning(f"[PDF Parser] pdfplumber failed: {e}, trying PyPDF2")
                parsed_pdf = _parse_with_pypdf2(pdf_path)
        
        if not parsed_pdf.full_text:
            return ToolResponse.fail(
                error_type=ToolErrorType.PARSE_ERROR,
                message="No text content could be extracted from PDF",
                details={"url": url, "parser": parsed_pdf.parser_used}
            )
        
        logger.info(
            f"[PDF Parser] Successfully parsed PDF using {parsed_pdf.parser_used}: "
            f"{len(parsed_pdf.full_text)} chars"
        )
        
        return ToolResponse.ok([parsed_pdf])
        
    except Exception as e:
        logger.error(f"[PDF Parser] All parsers failed: {e}")
        return ToolResponse.fail(
            error_type=ToolErrorType.PARSE_ERROR,
            message=f"Failed to parse PDF: {str(e)}",
            details={"url": url}
        )


async def parse_pdf_from_file(file_path: str) -> ToolResponse[ParsedPDF]:
    """
    Parse a PDF from a local file path.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        ToolResponse containing parsed PDF data
    """
    logger.info(f"[PDF Parser] Parsing PDF from file: {file_path}")
    
    if not Path(file_path).exists():
        return ToolResponse.fail(
            error_type=ToolErrorType.NOT_FOUND,
            message=f"PDF file not found: {file_path}",
            details={"file_path": file_path}
        )
    
    try:
        # Try GROBID first
        parsed_pdf = _parse_with_grobid(file_path)
        
        # Fallback to pdfplumber if GROBID fails
        if parsed_pdf is None:
            logger.warning("[PDF Parser] GROBID failed, trying pdfplumber")
            try:
                parsed_pdf = _parse_with_pdfplumber(file_path)
            except Exception as e:
                logger.warning(f"[PDF Parser] pdfplumber failed: {e}, trying PyPDF2")
                parsed_pdf = _parse_with_pypdf2(file_path)
        
        if not parsed_pdf.full_text:
            return ToolResponse.fail(
                error_type=ToolErrorType.PARSE_ERROR,
                message="No text content could be extracted from PDF",
                details={"file_path": file_path, "parser": parsed_pdf.parser_used}
            )
        
        logger.info(
            f"[PDF Parser] Successfully parsed PDF using {parsed_pdf.parser_used}: "
            f"{len(parsed_pdf.full_text)} chars"
        )
        
        return ToolResponse.ok([parsed_pdf])
        
    except Exception as e:
        logger.error(f"[PDF Parser] All parsers failed: {e}")
        return ToolResponse.fail(
            error_type=ToolErrorType.PARSE_ERROR,
            message=f"Failed to parse PDF: {str(e)}",
            details={"file_path": file_path}
        )
