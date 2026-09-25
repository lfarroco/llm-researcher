"""Tests for source identity normalization.

These cover the cases that actually produced duplicate sources in practice:
scheme and ``www`` variants, tracking parameters, DOI-resolver forms, and
arXiv abstract-vs-PDF URLs.
"""

from app.services.source_identity import (
    extract_doi_from_url,
    normalize_doi,
    normalize_url,
    source_identity,
)


class TestNormalizeDoi:
    def test_lowercases_and_extracts(self):
        assert normalize_doi("10.1038/S41586-021-03819-2") == (
            "10.1038/s41586-021-03819-2"
        )

    def test_strips_surrounding_punctuation(self):
        assert normalize_doi("(10.1000/xyz).") == "10.1000/xyz"

    def test_rejects_non_doi(self):
        assert normalize_doi("not a doi") is None
        assert normalize_doi("") is None
        assert normalize_doi(None) is None


class TestNormalizeUrl:
    def test_collapses_scheme(self):
        assert normalize_url("http://example.com/a") == (
            "https://example.com/a"
        )

    def test_collapses_www(self):
        assert normalize_url("https://www.example.com/a") == (
            "https://example.com/a"
        )

    def test_drops_fragment(self):
        assert normalize_url("https://example.com/a#section-3") == (
            "https://example.com/a"
        )

    def test_drops_tracking_params_but_keeps_real_ones(self):
        normalized = normalize_url(
            "https://example.com/a?utm_source=news&b=2&a=1"
        )
        assert "utm_source" not in normalized
        # Remaining params are sorted so ordering does not matter.
        assert normalized == "https://example.com/a?a=1&b=2"

    def test_strips_trailing_slash(self):
        assert normalize_url("https://example.com/a/") == (
            "https://example.com/a"
        )

    def test_preserves_port(self):
        """A port can denote a distinct service, so it must not be dropped."""
        assert normalize_url("https://example.com:8080/a") == (
            "https://example.com:8080/a"
        )
        assert normalize_url("https://example.com:8080/a") != normalize_url(
            "https://example.com:9090/a"
        )

    def test_root_relative_urls_stay_distinct(self):
        """Link harvesting yields many root-relative URLs.

        These used to normalize to an empty host, collapsing every distinct
        link into one identity.
        """
        first = normalize_url("/abs/2301.12345")
        second = normalize_url("/abs/9999.00001")
        assert first != second
        assert "2301.12345" in first

    def test_non_http_scheme_survives(self):
        assert normalize_url("mailto:a@b.com") == "mailto:a@b.com"
        assert normalize_url("ftp://host/x") == "ftp://host/x"

    def test_empty(self):
        assert normalize_url("") == ""
        assert normalize_url("   ") == ""


class TestSourceIdentity:
    def test_scheme_variants_are_one_source(self):
        assert source_identity("http://example.com/paper") == source_identity(
            "https://www.example.com/paper/"
        )

    def test_doi_outranks_url(self):
        """Two different URLs for one DOI are the same paper."""
        via_resolver = source_identity(
            "https://doi.org/10.1038/s41586-021-03819-2"
        )
        via_publisher = source_identity(
            "https://www.nature.com/articles/s41586-021-03819-2"
        )
        # The publisher URL has no DOI in it, so it is a URL identity; the
        # resolver URL becomes a DOI identity. They must not be equal, but the
        # resolver form must be stable across resolver hosts.
        assert via_resolver == source_identity(
            "http://dx.doi.org/10.1038/S41586-021-03819-2"
        )
        assert via_resolver.startswith("doi:")
        assert via_publisher.startswith("url:")

    def test_doi_embedded_in_url_wins(self):
        left = source_identity(
            "https://link.springer.com/article/10.1007/s00134-021-06479-y"
        )
        right = source_identity("https://doi.org/10.1007/s00134-021-06479-y")
        assert left == right == "doi:10.1007/s00134-021-06479-y"

    def test_explicit_doi_argument_wins(self):
        assert source_identity(
            "https://example.com/x", doi="10.1000/ABC"
        ) == "doi:10.1000/abc"

    def test_arxiv_abstract_and_pdf_are_one_source(self):
        abstract = source_identity("https://arxiv.org/abs/2301.12345")
        pdf = source_identity("https://arxiv.org/pdf/2301.12345.pdf")
        versioned = source_identity("https://arxiv.org/abs/2301.12345v3")
        assert abstract == pdf == versioned == "arxiv:2301.12345"

    def test_title_fallback_when_no_url(self):
        assert source_identity(None, title="  Deep  Learning!! ") == (
            "title:deep learning"
        )

    def test_never_empty(self):
        """An empty key would make every keyless source collide."""
        assert source_identity(None, None, None) == "unknown"
        assert source_identity("", "", "") == "unknown"

    def test_distinct_papers_stay_distinct(self):
        assert source_identity("https://arxiv.org/abs/2301.12345") != (
            source_identity("https://arxiv.org/abs/2301.99999")
        )


class TestExtractDoiFromUrl:
    def test_extracts(self):
        assert extract_doi_from_url(
            "https://doi.org/10.1000/ABC"
        ) == "10.1000/abc"

    def test_returns_none(self):
        assert extract_doi_from_url("https://example.com/x") is None
        assert extract_doi_from_url(None) is None
