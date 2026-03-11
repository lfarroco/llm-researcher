"""
Document chunker - splits large documents into manageable chunks.

Useful for:
- Processing long PDFs with LLMs (token limit constraints)
- Creating embeddings for vector search (Phase 11)
- Enabling semantic search within documents
- Parallel processing of document sections

Implements smart chunking strategies that:
- Respect paragraph boundaries
- Keep sections together when possible
- Maintain context with overlapping chunks
- Preserve document structure metadata
"""

import logging
import re
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 1000  # tokens (approximate using words)
DEFAULT_CHUNK_OVERLAP = 200  # tokens overlap between chunks
DEFAULT_MIN_CHUNK_SIZE = 100  # minimum viable chunk size


class ChunkingStrategy(str, Enum):
    """Strategy for splitting documents into chunks."""
    
    FIXED_SIZE = "fixed_size"  # Fixed size chunks with overlap
    PARAGRAPH = "paragraph"  # Split on paragraph boundaries
    SECTION = "section"  # Split on section headings
    SENTENCE = "sentence"  # Split on sentence boundaries


class DocumentChunk(BaseModel):
    """A chunk of a document with metadata."""
    
    text: str = Field(description="Chunk text content")
    chunk_index: int = Field(description="Index of this chunk in the document")
    start_char: int = Field(description="Character offset where chunk starts")
    end_char: int = Field(description="Character offset where chunk ends")
    token_count: int = Field(description="Approximate token count")
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata (section, page, etc.)"
    )


def _estimate_token_count(text: str) -> int:
    """
    Estimate token count for a text string.
    
    Uses a simple heuristic: ~1.3 tokens per word on average for English.
    This is approximate but good enough for chunking purposes.
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    words = len(text.split())
    return int(words * 1.3)


def _split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs.
    
    Paragraphs are separated by double newlines or more.
    """
    # Split on 2+ newlines
    paragraphs = re.split(r'\n\s*\n', text)
    # Clean up whitespace
    return [p.strip() for p in paragraphs if p.strip()]


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences.
    
    Uses simple regex for sentence boundaries.
    Not perfect but good enough for chunking.
    """
    # Split on period, question mark, or exclamation followed by space
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def _find_section_boundaries(text: str) -> List[tuple[int, str]]:
    """
    Find section headings in text.
    
    Looks for common heading patterns:
    - Lines that are all caps
    - Lines ending with colons
    - Numbered sections (1., 2., etc.)
    
    Returns:
        List of (start_position, heading_text) tuples
    """
    boundaries = []
    
    lines = text.split('\n')
    current_pos = 0
    
    for line in lines:
        line_stripped = line.strip()
        
        if line_stripped:
            # Check for section heading patterns
            is_heading = False
            
            # All caps line (at least 3 words)
            if line_stripped.isupper() and len(line_stripped.split()) >= 3:
                is_heading = True
            
            # Numbered section (1. Introduction, 2.1 Methods, etc.)
            elif re.match(r'^\d+(\.\d+)*\.?\s+[A-Z]', line_stripped):
                is_heading = True
            
            # Line ending with colon (Section heading:)
            elif line_stripped.endswith(':') and len(line_stripped.split()) <= 8:
                is_heading = True
            
            if is_heading:
                boundaries.append((current_pos, line_stripped))
        
        current_pos += len(line) + 1  # +1 for newline
    
    return boundaries


def chunk_text_fixed_size(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
) -> List[DocumentChunk]:
    """
    Chunk text into fixed-size pieces with overlap.
    
    This is the simplest strategy but doesn't respect document structure.
    Good for when structure doesn't matter or text is unstructured.
    
    Args:
        text: Text to chunk
        chunk_size: Target chunk size in tokens
        chunk_overlap: Overlap between chunks in tokens
        min_chunk_size: Minimum chunk size to avoid tiny chunks
        
    Returns:
        List of DocumentChunk objects
    """
    logger.info(
        f"[Chunker] Fixed-size chunking: size={chunk_size}, "
        f"overlap={chunk_overlap}"
    )
    
    # Split into words for token-based chunking
    words = text.split()
    total_tokens = _estimate_token_count(text)
    
    chunks = []
    chunk_index = 0
    start_word_idx = 0
    
    while start_word_idx < len(words):
        # Calculate end index for this chunk
        end_word_idx = min(
            start_word_idx + int(chunk_size / 1.3),  # Convert tokens to words
            len(words)
        )
        
        # Extract chunk text
        chunk_words = words[start_word_idx:end_word_idx]
        chunk_text = ' '.join(chunk_words)
        
        # Skip if chunk is too small (unless it's the last chunk)
        token_count = _estimate_token_count(chunk_text)
        if token_count < min_chunk_size and end_word_idx < len(words):
            break
        
        # Calculate character offsets (approximate)
        # This is a rough estimate as we lost exact positions when splitting
        avg_word_len = len(text) / len(words) if words else 0
        start_char = int(start_word_idx * avg_word_len)
        end_char = int(end_word_idx * avg_word_len)
        
        chunks.append(DocumentChunk(
            text=chunk_text,
            chunk_index=chunk_index,
            start_char=start_char,
            end_char=end_char,
            token_count=token_count,
            metadata={
                "total_tokens": total_tokens,
                "strategy": "fixed_size"
            }
        ))
        
        chunk_index += 1
        
        # Move start position with overlap
        overlap_words = int(chunk_overlap / 1.3)
        start_word_idx = end_word_idx - overlap_words
        
        # Ensure we make progress
        if start_word_idx <= chunk_index * int(chunk_size / 1.3):
            start_word_idx = end_word_idx
    
    logger.info(f"[Chunker] Created {len(chunks)} chunks")
    return chunks


def chunk_text_by_paragraphs(
    text: str,
    max_chunk_size: int = DEFAULT_CHUNK_SIZE,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
) -> List[DocumentChunk]:
    """
    Chunk text by paragraph boundaries.
    
    Combines paragraphs until reaching max_chunk_size, keeping paragraphs intact.
    This preserves logical document structure better than fixed-size chunking.
    
    Args:
        text: Text to chunk
        max_chunk_size: Maximum chunk size in tokens
        min_chunk_size: Minimum chunk size
        
    Returns:
        List of DocumentChunk objects
    """
    logger.info(f"[Chunker] Paragraph chunking: max_size={max_chunk_size}")
    
    paragraphs = _split_into_paragraphs(text)
    
    chunks = []
    chunk_index = 0
    current_chunk_paragraphs = []
    current_chunk_tokens = 0
    current_start_char = 0
    char_offset = 0
    
    for para in paragraphs:
        para_tokens = _estimate_token_count(para)
        
        # If this paragraph alone exceeds max size, split it
        if para_tokens > max_chunk_size:
            # Save current chunk if it exists
            if current_chunk_paragraphs:
                chunk_text = '\n\n'.join(current_chunk_paragraphs)
                chunks.append(DocumentChunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_char=current_start_char,
                    end_char=char_offset,
                    token_count=current_chunk_tokens,
                    metadata={"strategy": "paragraph"}
                ))
                chunk_index += 1
                current_chunk_paragraphs = []
                current_chunk_tokens = 0
            
            # Split large paragraph with fixed-size chunking
            para_chunks = chunk_text_fixed_size(
                para,
                chunk_size=max_chunk_size,
                chunk_overlap=0,
                min_chunk_size=min_chunk_size
            )
            
            for pc in para_chunks:
                pc.chunk_index = chunk_index
                pc.start_char = char_offset + pc.start_char
                pc.end_char = char_offset + pc.end_char
                pc.metadata["strategy"] = "paragraph+fixed"
                chunks.append(pc)
                chunk_index += 1
            
            current_start_char = char_offset + len(para) + 2  # +2 for \n\n
        
        # If adding this paragraph exceeds max size, save current chunk
        elif current_chunk_tokens + para_tokens > max_chunk_size and current_chunk_paragraphs:
            chunk_text = '\n\n'.join(current_chunk_paragraphs)
            chunks.append(DocumentChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=current_start_char,
                end_char=char_offset,
                token_count=current_chunk_tokens,
                metadata={"strategy": "paragraph"}
            ))
            chunk_index += 1
            
            # Start new chunk with current paragraph
            current_chunk_paragraphs = [para]
            current_chunk_tokens = para_tokens
            current_start_char = char_offset
        
        # Add paragraph to current chunk
        else:
            current_chunk_paragraphs.append(para)
            current_chunk_tokens += para_tokens
        
        char_offset += len(para) + 2  # +2 for \n\n separator
    
    # Add final chunk if it exists
    if current_chunk_paragraphs:
        chunk_text = '\n\n'.join(current_chunk_paragraphs)
        if _estimate_token_count(chunk_text) >= min_chunk_size:
            chunks.append(DocumentChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=current_start_char,
                end_char=len(text),
                token_count=current_chunk_tokens,
                metadata={"strategy": "paragraph"}
            ))
    
    logger.info(f"[Chunker] Created {len(chunks)} paragraph-based chunks")
    return chunks


def chunk_text_by_sections(
    text: str,
    max_chunk_size: int = DEFAULT_CHUNK_SIZE * 2,  # Sections tend to be larger
) -> List[DocumentChunk]:
    """
    Chunk text by section boundaries.
    
    Best for academic papers and structured documents with clear sections.
    Tries to keep entire sections together when possible.
    
    Args:
        text: Text to chunk
        max_chunk_size: Maximum chunk size in tokens
        
    Returns:
        List of DocumentChunk objects
    """
    logger.info(f"[Chunker] Section chunking: max_size={max_chunk_size}")
    
    boundaries = _find_section_boundaries(text)
    
    if not boundaries:
        # No sections found, fall back to paragraph chunking
        logger.warning("[Chunker] No sections found, using paragraph chunking")
        return chunk_text_by_paragraphs(text, max_chunk_size=max_chunk_size)
    
    chunks = []
    chunk_index = 0
    
    # Add implicit first section (before first heading)
    if boundaries[0][0] > 0:
        boundaries.insert(0, (0, "Preamble"))
    
    # Add implicit last boundary at end
    boundaries.append((len(text), "End"))
    
    for i in range(len(boundaries) - 1):
        start_pos, heading = boundaries[i]
        end_pos = boundaries[i + 1][0]
        
        section_text = text[start_pos:end_pos].strip()
        section_tokens = _estimate_token_count(section_text)
        
        # If section fits in max size, use it as one chunk
        if section_tokens <= max_chunk_size:
            chunks.append(DocumentChunk(
                text=section_text,
                chunk_index=chunk_index,
                start_char=start_pos,
                end_char=end_pos,
                token_count=section_tokens,
                metadata={
                    "section": heading,
                    "strategy": "section"
                }
            ))
            chunk_index += 1
        
        # Section too large, split by paragraphs
        else:
            section_chunks = chunk_text_by_paragraphs(
                section_text,
                max_chunk_size=max_chunk_size
            )
            for sc in section_chunks:
                sc.chunk_index = chunk_index
                sc.start_char = start_pos + sc.start_char
                sc.end_char = start_pos + sc.end_char
                sc.metadata["section"] = heading
                sc.metadata["strategy"] = "section+paragraph"
                chunks.append(sc)
                chunk_index += 1
    
    logger.info(f"[Chunker] Created {len(chunks)} section-based chunks")
    return chunks


def chunk_document(
    text: str,
    strategy: ChunkingStrategy = ChunkingStrategy.PARAGRAPH,
    max_chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
) -> List[DocumentChunk]:
    """
    Chunk a document using the specified strategy.
    
    This is the main entry point for document chunking.
    
    Args:
        text: Document text to chunk
        strategy: Chunking strategy to use
        max_chunk_size: Maximum chunk size in tokens
        chunk_overlap: Overlap between chunks (for fixed_size only)
        min_chunk_size: Minimum chunk size
        
    Returns:
        List of DocumentChunk objects
    """
    if not text or not text.strip():
        logger.warning("[Chunker] Empty text provided")
        return []
    
    logger.info(f"[Chunker] Chunking {len(text)} chars using {strategy} strategy")
    
    if strategy == ChunkingStrategy.FIXED_SIZE:
        return chunk_text_fixed_size(
            text,
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            min_chunk_size=min_chunk_size
        )
    elif strategy == ChunkingStrategy.PARAGRAPH:
        return chunk_text_by_paragraphs(
            text,
            max_chunk_size=max_chunk_size,
            min_chunk_size=min_chunk_size
        )
    elif strategy == ChunkingStrategy.SECTION:
        return chunk_text_by_sections(
            text,
            max_chunk_size=max_chunk_size
        )
    elif strategy == ChunkingStrategy.SENTENCE:
        # For sentence-level chunking, use paragraph chunker
        # but with smaller chunk size
        return chunk_text_by_paragraphs(
            text,
            max_chunk_size=max_chunk_size // 2,
            min_chunk_size=min_chunk_size
        )
    else:
        raise ValueError(f"Unknown chunking strategy: {strategy}")
