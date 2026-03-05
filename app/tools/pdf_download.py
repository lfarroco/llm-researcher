"""
PDF download and caching tool.

Downloads PDFs from URLs and caches them locally to avoid
repeated downloads. Includes validation for file size,
format, and integrity.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import httpx
import aiofiles
from pydantic import BaseModel, Field

from app.tools.base import get_setting

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_CACHE_DIR = "/tmp/llm-researcher-pdfs"
DEFAULT_MAX_SIZE_MB = 50
PDF_MAGIC_BYTES = b"%PDF"


class PDFDownloadResult(BaseModel):
    """Result of a PDF download operation."""

    success: bool = Field(description="Whether download succeeded")
    file_path: Optional[str] = Field(
        default=None, description="Local path to cached PDF"
    )
    file_size_bytes: int = Field(
        default=0, description="Size of downloaded file in bytes"
    )
    url: str = Field(description="Original URL")
    error: Optional[str] = Field(
        default=None, description="Error message if download failed"
    )
    cached: bool = Field(
        default=False,
        description="True if file was already cached"
    )
    content_type: Optional[str] = Field(
        default=None, description="Content-Type header from response"
    )


def _get_cache_dir() -> Path:
    """Get the PDF cache directory path from settings or default."""
    cache_dir_str = get_setting("PDF_CACHE_DIR", DEFAULT_CACHE_DIR)
    cache_dir = Path(cache_dir_str)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_max_size_mb() -> int:
    """Get the maximum PDF size from settings or default."""
    max_size_str = get_setting("MAX_PDF_SIZE_MB", str(DEFAULT_MAX_SIZE_MB))
    try:
        return int(max_size_str)
    except ValueError:
        logger.warning(
            f"Invalid MAX_PDF_SIZE_MB setting: {max_size_str}, "
            f"using default {DEFAULT_MAX_SIZE_MB}"
        )
        return DEFAULT_MAX_SIZE_MB


def _url_to_filename(url: str) -> str:
    """Convert URL to a safe filename using hash."""
    # Create a hash of the URL for the filename
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"{url_hash}.pdf"


def _validate_pdf_header(content: bytes) -> bool:
    """Check if content starts with PDF magic bytes."""
    return content.startswith(PDF_MAGIC_BYTES)


async def download_pdf(
    url: str,
    force_redownload: bool = False,
) -> PDFDownloadResult:
    """
    Download a PDF from a URL and cache it locally.

    Args:
        url: URL of the PDF to download
        force_redownload: If True, download even if cached

    Returns:
        PDFDownloadResult with download status and file path
    """
    logger.info(f"[PDF] Downloading from: {url}")

    cache_dir = _get_cache_dir()
    max_size_mb = _get_max_size_mb()
    max_size_bytes = max_size_mb * 1024 * 1024

    # Generate cache filename
    filename = _url_to_filename(url)
    file_path = cache_dir / filename

    # Check if already cached
    if file_path.exists() and not force_redownload:
        logger.info(f"[PDF] Using cached file: {file_path}")
        file_size = os.path.getsize(file_path)
        return PDFDownloadResult(
            success=True,
            file_path=str(file_path),
            file_size_bytes=file_size,
            url=url,
            cached=True,
        )

    # Download the PDF
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            # Stream the download to check size before saving
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                logger.debug(f"[PDF] Content-Type: {content_type}")

                # Check content length if provided
                content_length = response.headers.get("content-length")
                if content_length:
                    size = int(content_length)
                    if size > max_size_bytes:
                        error_msg = (
                            f"PDF too large: {size / 1024 / 1024:.1f}MB "
                            f"(max: {max_size_mb}MB)"
                        )
                        logger.warning(f"[PDF] {error_msg}")
                        return PDFDownloadResult(
                            success=False,
                            url=url,
                            error=error_msg,
                            content_type=content_type,
                        )

                # Download in chunks
                chunks = []
                total_size = 0
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    total_size += len(chunk)

                    # Check size limit while downloading
                    if total_size > max_size_bytes:
                        error_msg = (
                            f"PDF exceeded size limit during download: "
                            f"{total_size / 1024 / 1024:.1f}MB "
                            f"(max: {max_size_mb}MB)"
                        )
                        logger.warning(f"[PDF] {error_msg}")
                        return PDFDownloadResult(
                            success=False,
                            url=url,
                            error=error_msg,
                            content_type=content_type,
                        )

                content = b"".join(chunks)

        # Validate PDF format
        if not _validate_pdf_header(content):
            error_msg = "Downloaded file is not a valid PDF"
            logger.warning(f"[PDF] {error_msg}")
            return PDFDownloadResult(
                success=False,
                url=url,
                error=error_msg,
                file_size_bytes=total_size,
                content_type=content_type,
            )

        # Save to cache
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        logger.info(
            f"[PDF] Successfully downloaded and cached: "
            f"{total_size / 1024:.1f}KB"
        )

        return PDFDownloadResult(
            success=True,
            file_path=str(file_path),
            file_size_bytes=total_size,
            url=url,
            cached=False,
            content_type=content_type,
        )

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e}"
        logger.error(f"[PDF] {error_msg}")
        return PDFDownloadResult(
            success=False,
            url=url,
            error=error_msg,
        )
    except httpx.TimeoutException:
        error_msg = "Download timeout (60s)"
        logger.error(f"[PDF] {error_msg}")
        return PDFDownloadResult(
            success=False,
            url=url,
            error=error_msg,
        )
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.error(f"[PDF] {error_msg}")
        return PDFDownloadResult(
            success=False,
            url=url,
            error=error_msg,
        )


async def get_cached_pdf_path(url: str) -> Optional[str]:
    """
    Check if a PDF is cached and return its path.

    Args:
        url: URL of the PDF

    Returns:
        Path to cached file if exists, None otherwise
    """
    cache_dir = _get_cache_dir()
    filename = _url_to_filename(url)
    file_path = cache_dir / filename

    if file_path.exists():
        return str(file_path)
    return None


async def clear_pdf_cache(
    older_than_days: Optional[int] = None
) -> dict:
    """
    Clear the PDF cache.

    Args:
        older_than_days: Only delete files older than this many days.
                        If None, delete all.

    Returns:
        Dictionary with deletion statistics
    """
    logger.info("[PDF] Clearing cache...")

    cache_dir = _get_cache_dir()
    deleted_count = 0
    deleted_size = 0
    error_count = 0

    import time
    current_time = time.time()
    age_threshold = (
        older_than_days * 24 * 60 * 60 if older_than_days else 0
    )

    for pdf_file in cache_dir.glob("*.pdf"):
        try:
            # Check file age if threshold specified
            if older_than_days:
                file_age = current_time - pdf_file.stat().st_mtime
                if file_age < age_threshold:
                    continue

            file_size = pdf_file.stat().st_size
            pdf_file.unlink()
            deleted_count += 1
            deleted_size += file_size
            logger.debug(f"[PDF] Deleted cached file: {pdf_file.name}")

        except Exception as e:
            logger.error(
                f"[PDF] Error deleting {pdf_file.name}: {e}"
            )
            error_count += 1

    logger.info(
        f"[PDF] Cache cleared: {deleted_count} files, "
        f"{deleted_size / 1024 / 1024:.1f}MB"
    )

    return {
        "deleted_count": deleted_count,
        "deleted_size_bytes": deleted_size,
        "deleted_size_mb": deleted_size / 1024 / 1024,
        "error_count": error_count,
    }


# Test function
async def test_pdf_download():
    """Test function for manual verification."""
    print("Testing PDF download...")

    # Test with an ArXiv PDF
    test_url = "https://arxiv.org/pdf/1706.03762.pdf"  # Transformer paper

    print("\n1. First download (should download):")
    result1 = await download_pdf(test_url)
    print(f"   Success: {result1.success}")
    print(f"   Cached: {result1.cached}")
    print(f"   Size: {result1.file_size_bytes / 1024:.1f}KB")
    print(f"   Path: {result1.file_path}")

    print("\n2. Second download (should use cache):")
    result2 = await download_pdf(test_url)
    print(f"   Success: {result2.success}")
    print(f"   Cached: {result2.cached}")
    print(f"   Size: {result2.file_size_bytes / 1024:.1f}KB")

    print("\n3. Testing cache lookup:")
    cached_path = await get_cached_pdf_path(test_url)
    print(f"   Cached path: {cached_path}")

    print("\n4. Clearing cache:")
    stats = await clear_pdf_cache()
    print(f"   Deleted: {stats['deleted_count']} files")
    print(f"   Size: {stats['deleted_size_mb']:.1f}MB")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_pdf_download())
