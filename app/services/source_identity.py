"""Stable identity for research sources.

Collection, reference chasing, and resume all re-discover the same papers from
different angles: the same DOI arrives from Crossref, from an arXiv landing
page, and from a reference list, each time spelled slightly differently
(``http`` vs ``https``, ``www.`` prefix, tracking parameters, ``dx.doi.org``
vs ``doi.org``, trailing slash, DOI case).

Without a normalization step those variants become separate
``ResearchSource`` rows, which previously meant duplicate sources and
order-dependent evidence links (see docs/HARNESS_FEASIBILITY.md 8.3).

This module is the single place that decides when two strings mean the same
source. It is intentionally dependency-free so it can be used from services,
tools, and migrations alike.
"""

import re
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query parameters that identify a session or a referrer rather than a
# document. They vary between collections of the *same* paper, so they are
# stripped before comparing.
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_referrer",
    "gclid", "fbclid", "msclkid", "dclid", "yclid",
    "mc_cid", "mc_eid", "igshid", "ref", "referrer", "source",
    "spm", "scid", "cmpid", "WT.mc_id", "_ga", "_gl",
})

# Prefixes that are pure DOI resolvers; the DOI itself is the identity.
_DOI_RESOLVER_HOSTS = frozenset({
    "doi.org", "dx.doi.org", "www.doi.org", "www.dx.doi.org",
})

# A DOI is "10." followed by a registrant code, a slash, and a suffix.
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>()\[\]{}]+", re.IGNORECASE)

# arxiv.org/abs/<id> and /pdf/<id>(.pdf) are the same paper.
_ARXIV_ID_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf)/(?P<id>[^/?#]+?)(?:\.pdf)?(?:[?#]|$)",
    re.IGNORECASE,
)


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Return a canonical ``10.xxxx/suffix`` DOI, or None.

    DOIs are case-insensitive; the conventional canonical form is lowercase.
    """
    if not doi:
        return None
    text = doi.strip()
    if not text:
        return None
    match = _DOI_RE.search(text)
    if not match:
        return None
    # Trailing punctuation is almost always sentence punctuation or a stray
    # delimiter rather than part of the DOI.
    return match.group(0).rstrip(".,;:").lower()


def extract_doi_from_url(url: Optional[str]) -> Optional[str]:
    """Pull a DOI out of a URL, if the URL is DOI-based or embeds one."""
    if not url:
        return None
    return normalize_doi(url)


def normalize_url(url: str) -> str:
    """Canonicalize a URL for comparison purposes.

    Not a general-purpose URL canonicalizer: it only removes variation that
    never changes which document is being identified. Anything that cannot be
    confidently canonicalized is returned in a merely case/whitespace-folded
    form, which is always safe because it still distinguishes two different
    inputs.
    """
    text = (url or "").strip()
    if not text:
        return ""

    split = urlsplit(text)

    scheme = (split.scheme or "").lower()
    if scheme not in {"http", "https"}:
        # Non-web schemes (mailto:, ftp:), root-relative URLs, and anything
        # else without an authority component. Rebuilding these through
        # urlunsplit would either drop the scheme or invent an empty host, so
        # only case and whitespace are normalized.
        return text.lower()

    # Use netloc rather than hostname: hostname drops the port and IPv6
    # brackets, which would merge distinct services into one identity.
    host = (split.netloc or "").lower()
    if not host:
        return text.lower()
    if host.startswith("www."):
        host = host[4:]

    # Drop tracking parameters, then sort what remains so parameter order
    # does not create a false distinction.
    kept = [
        (key, value)
        for key, value in parse_qsl(split.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    query = urlencode(sorted(kept))

    path = split.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Fragments are navigational within a document, never a different document.
    return urlunsplit(("https", host, path, query, ""))


def source_identity(
    url: Optional[str] = None,
    doi: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Return the stable identity key for a source.

    Precedence is deliberate:

    1. **DOI** — the strongest identifier; two different URLs for one DOI are
       the same paper.
    2. **arXiv id** — arXiv papers frequently lack a DOI in search metadata,
       and their abstract and PDF URLs are the same document.
    3. **Normalized URL** — the fallback for everything else.
    4. **Normalized title** — last resort when there is no usable URL. This is
       deliberately weak and is only used so a missing URL does not make every
       result collide into one empty key.

    Returns a non-empty string suitable for ``ResearchSource.dedupe_key``.
    """
    normalized_doi = normalize_doi(doi) or extract_doi_from_url(url)
    if normalized_doi:
        return f"doi:{normalized_doi}"

    if url:
        arxiv_match = _ARXIV_ID_RE.search(url)
        if arxiv_match:
            arxiv_id = arxiv_match.group("id").lower()
            # Version suffixes (v1, v2) are revisions of one paper.
            arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
            return f"arxiv:{arxiv_id}"

        normalized = normalize_url(url)
        if normalized:
            return f"url:{normalized}"

    if title:
        collapsed = re.sub(r"\s+", " ", title).strip().lower()
        collapsed = re.sub(r"[^a-z0-9 ]+", "", collapsed)
        if collapsed:
            return f"title:{collapsed[:300]}"

    return "unknown"


def is_same_source(a: str, b: str) -> bool:
    """Convenience predicate for tests and one-off comparisons."""
    return source_identity(a) == source_identity(b)
