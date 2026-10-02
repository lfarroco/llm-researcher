"""
Tests for the built-in search plugins and the registry that runs them.

The free-tier academic sources (PubMed, Semantic Scholar, OpenAlex, Crossref)
are the interesting case: their tool modules and tests already existed, but
nothing registered them as search plugins, so they never ran. These tests pin
the wiring, the availability gates and the result-to-Citation mapping.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.memory.research_state import Citation, SourceType
from app.tools.crossref_search import CrossrefResult
from app.tools.openalex_search import OpenAlexResult
from app.tools.plugins import (
    CrossrefPlugin,
    OpenAlexPlugin,
    PubMedPlugin,
    SemanticScholarPlugin,
    register_defaults,
)
from app.tools.pubmed_search import PubMedResult
from app.tools.registry import ToolRegistry
from app.tools.semantic_scholar import SemanticScholarResult

EXPECTED_PLUGIN_ORDER = [
    "web",
    "arxiv",
    "wikipedia",
    "pubmed",
    "semantic_scholar",
    "openalex",
    "crossref",
    "springer",
    "elsevier",
]


def make_pubmed_result(**overrides) -> PubMedResult:
    defaults = dict(
        pmid="12345678",
        title="Effect of X on Y",
        authors=["Ada Lovelace", "Alan Turing", "Grace Hopper", "Fourth"],
        abstract="A randomised trial of X in Y patients.",
        journal="Journal of Testing",
        pub_date="2024",
        url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        doi="10.1000/abc",
    )
    defaults.update(overrides)
    return PubMedResult(**defaults)


def make_s2_result(**overrides) -> SemanticScholarResult:
    defaults = dict(
        paper_id="abc123",
        title="A Survey of Things",
        authors=["Ada Lovelace"],
        abstract="We survey things.",
        url="https://www.semanticscholar.org/paper/abc123",
        open_access_pdf="https://example.org/survey.pdf",
    )
    defaults.update(overrides)
    return SemanticScholarResult(**defaults)


def make_openalex_result(**overrides) -> OpenAlexResult:
    defaults = dict(
        openalex_id="https://openalex.org/W1",
        title="Open Work",
        authors=["Ada Lovelace"],
        abstract="An open abstract.",
        doi="10.5555/open",
        url="https://openalex.org/W1",
        pdf_url="https://example.org/open.pdf",
    )
    defaults.update(overrides)
    return OpenAlexResult(**defaults)


def make_crossref_result(**overrides) -> CrossrefResult:
    defaults = dict(
        doi="10.5555/cross",
        title="Registered Work",
        authors=["Ada Lovelace"],
        abstract="<jats:p>Marked   up abstract.</jats:p>",
        url="https://doi.org/10.5555/cross",
    )
    defaults.update(overrides)
    return CrossrefResult(**defaults)


class TestRegistryWiring:
    def test_register_defaults_registers_every_source(self):
        fresh = ToolRegistry()
        with patch("app.tools.registry.get_registry", return_value=fresh):
            register_defaults()

        assert [p.name for p in fresh._plugins] == EXPECTED_PLUGIN_ORDER

    def test_free_academic_sources_available_without_keys(self):
        """The whole point of the change: these need no API key to run."""
        for plugin in (
            PubMedPlugin(),
            SemanticScholarPlugin(),
            OpenAlexPlugin(),
            CrossrefPlugin(),
        ):
            assert plugin.is_available(), plugin.name

    def test_publisher_plugins_are_key_gated(self):
        from app.tools.plugins import ElsevierPlugin, SpringerPlugin

        with patch.object(settings, "springer_api_key", ""), \
                patch.object(settings, "elsevier_api_key", ""):
            assert not SpringerPlugin().is_available()
            assert not ElsevierPlugin().is_available()

        with patch.object(settings, "springer_api_key", "k"), \
                patch.object(settings, "elsevier_api_key", "k"):
            assert SpringerPlugin().is_available()
            assert ElsevierPlugin().is_available()

    def test_academic_plugins_skipped_without_academic_context(self):
        fresh = ToolRegistry()
        with patch("app.tools.registry.get_registry", return_value=fresh):
            register_defaults()

        non_academic = {
            p.name
            for p in fresh.get_plugins(
                include_academic=False, first_variation=True)
        }
        assert non_academic == {"web", "wikipedia"}
        assert "openalex" not in non_academic
        assert "crossref" not in non_academic

    def test_non_first_variation_is_limited_to_broad_sources(self):
        fresh = ToolRegistry()
        with patch("app.tools.registry.get_registry", return_value=fresh):
            register_defaults()

        # Publisher plugins are key-gated, so enable them for this check.
        with patch.object(settings, "springer_api_key", "k"), \
                patch.object(settings, "elsevier_api_key", "k"):
            names = {
                p.name
                for p in fresh.get_plugins(
                    include_academic=True, first_variation=False)
            }
        # Broad academic indexes run once per sub-query; the publisher
        # plugins still cover every expanded variation.
        assert {"openalex", "crossref", "pubmed",
                "semantic_scholar"}.isdisjoint(names)
        assert {"springer", "elsevier"} <= names


class TestPubMedPlugin:
    @pytest.mark.asyncio
    async def test_maps_results_to_citations(self):
        plugin = PubMedPlugin()
        results = [make_pubmed_result()]

        with patch(
            "app.tools.plugins.pubmed_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("cancer therapy trial")

        assert len(citations) == 1
        citation = citations[0]
        assert citation.source_type == SourceType.PUBMED
        assert citation.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert citation.author == "Ada Lovelace, Alan Turing, Grace Hopper"
        assert citation.snippet.startswith("A randomised trial")

    @pytest.mark.asyncio
    async def test_skips_non_biomedical_query_without_calling_api(self):
        plugin = PubMedPlugin()
        search = AsyncMock(return_value=[make_pubmed_result()])

        with patch("app.tools.plugins.pubmed_search", new=search):
            citations = await plugin.search("history of the printing press")

        assert citations == []
        search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_journal_when_abstract_missing(self):
        plugin = PubMedPlugin()
        results = [make_pubmed_result(abstract="")]

        with patch(
            "app.tools.plugins.pubmed_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("cardio trial")

        assert citations[0].snippet == "Journal of Testing"

    @pytest.mark.asyncio
    async def test_drops_results_without_url(self):
        plugin = PubMedPlugin()
        results = [make_pubmed_result(url="")]

        with patch(
            "app.tools.plugins.pubmed_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("cancer treatment")

        assert citations == []

    def test_unavailable_without_biopython(self):
        plugin = PubMedPlugin()
        with patch.dict("sys.modules", {"Bio": None}):
            # A None entry makes ``import Bio`` raise ImportError.
            assert plugin.is_available() is False


class TestSemanticScholarPlugin:
    @pytest.mark.asyncio
    async def test_maps_results_and_carries_open_access_pdf(self):
        plugin = SemanticScholarPlugin()
        results = [make_s2_result()]

        with patch(
            "app.tools.plugins.semantic_scholar_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("survey of things")

        citation = citations[0]
        assert citation.source_type == SourceType.SEMANTIC_SCHOLAR
        assert citation.url == "https://www.semanticscholar.org/paper/abc123"
        assert citation.pdf_url == "https://example.org/survey.pdf"

    @pytest.mark.asyncio
    async def test_no_pdf_url_when_paper_is_closed_access(self):
        plugin = SemanticScholarPlugin()
        results = [make_s2_result(open_access_pdf=None)]

        with patch(
            "app.tools.plugins.semantic_scholar_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("closed access")

        assert citations[0].pdf_url is None


class TestOpenAlexPlugin:
    @pytest.mark.asyncio
    async def test_prefers_doi_resolver_url_for_dedup(self):
        plugin = OpenAlexPlugin()
        results = [make_openalex_result()]

        with patch(
            "app.tools.plugins.openalex_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("open work")

        citation = citations[0]
        assert citation.source_type == SourceType.OPENALEX
        # The DOI URL is what lets the knowledge base merge this with the
        # same paper arriving from Crossref or a reference list.
        assert citation.url == "https://doi.org/10.5555/open"
        assert citation.pdf_url == "https://example.org/open.pdf"

    @pytest.mark.asyncio
    async def test_falls_back_to_openalex_page_without_doi(self):
        plugin = OpenAlexPlugin()
        results = [make_openalex_result(doi=None)]

        with patch(
            "app.tools.plugins.openalex_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("open work")

        assert citations[0].url == "https://openalex.org/W1"

    @pytest.mark.asyncio
    async def test_leaves_absolute_doi_urls_alone(self):
        plugin = OpenAlexPlugin()
        results = [
            make_openalex_result(doi="https://doi.org/10.5555/open")
        ]

        with patch(
            "app.tools.plugins.openalex_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("open work")

        assert citations[0].url == "https://doi.org/10.5555/open"


class TestCrossrefPlugin:
    @pytest.mark.asyncio
    async def test_maps_results_and_strips_jats_markup(self):
        plugin = CrossrefPlugin()
        results = [make_crossref_result()]

        with patch(
            "app.tools.plugins.crossref_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("registered work")

        citation = citations[0]
        assert citation.source_type == SourceType.CROSSREF
        assert citation.url == "https://doi.org/10.5555/cross"
        assert citation.snippet == "Marked up abstract."

    @pytest.mark.asyncio
    async def test_builds_url_from_doi_when_missing(self):
        plugin = CrossrefPlugin()
        results = [make_crossref_result(url="")]

        with patch(
            "app.tools.plugins.crossref_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("registered work")

        assert citations[0].url == "https://doi.org/10.5555/cross"

    @pytest.mark.asyncio
    async def test_drops_results_with_neither_url_nor_doi(self):
        plugin = CrossrefPlugin()
        results = [make_crossref_result(url="", doi="")]

        with patch(
            "app.tools.plugins.crossref_search",
            new=AsyncMock(return_value=results),
        ):
            citations = await plugin.search("registered work")

        assert citations == []


class TestCitationPdfUrlPersistence:
    def test_pdf_url_survives_state_round_trip(self):
        from app.memory.research_state import ResearchState

        citation = Citation(
            id="[1]",
            url="https://doi.org/10.1/x",
            title="T",
            snippet="s",
            source_type=SourceType.OPENALEX,
            pdf_url="https://example.org/x.pdf",
        )
        state = ResearchState(research_id=1, query="q")
        state.citations = [citation]

        dumped = state.to_dict()
        restored = ResearchState.from_dict(dumped)

        # Citations live inside agent state; the field must survive JSON
        # round-tripping or full-text would regress after a resume.
        assert restored.to_dict() == dumped
        assert restored.citations[0].pdf_url == "https://example.org/x.pdf"

    def test_old_state_without_pdf_url_still_validates(self):
        """State JSON written before this field existed must still load."""
        legacy = {
            "id": "[1]",
            "url": "https://example.com/a",
            "title": "T",
            "snippet": "s",
            "source_type": "web",
        }
        citation = Citation.model_validate(legacy)
        assert citation.pdf_url is None
