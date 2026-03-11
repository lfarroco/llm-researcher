"""
Plugin registry for search tools.

This module defines the SearchPlugin protocol and a ToolRegistry that lets
new search sources be added without modifying the search agent.

To add a custom source, implement SearchPlugin and register it at startup:

    from app.tools.registry import get_registry

    class MyPlugin:
        name = "my_source"
        source_type = SourceType.WEB
        requires_academic_context = False
        first_variation_only = False
        default_max_results = 5

        def is_available(self) -> bool:
            return bool(os.getenv("MY_API_KEY"))

        async def search(self, query: str, max_results: int) -> list[Citation]:
            ...

    get_registry().register(MyPlugin())
"""

from typing import Protocol, runtime_checkable

from app.memory.research_state import Citation, SourceType


@runtime_checkable
class SearchPlugin(Protocol):
    """
    Contract for a search source plugin.

    Plugins own the mapping from their tool's result type to Citation, so the
    search agent doesn't need to know anything about each tool's specific
    shape.
    """

    name: str
    """Unique identifier used in log messages (e.g. "web", "arxiv")."""

    source_type: SourceType
    """SourceType tag written on every Citation produced by this plugin."""

    requires_academic_context: bool
    """
    If True the plugin is skipped unless the query is classified as academic.
    Use this for sources that are only useful for scientific/research queries.
    """

    first_variation_only: bool
    """
    If True the plugin only runs on the first query variation.
    Useful for sources like Wikipedia where a single lookup is enough.
    """

    default_max_results: int
    """How many results to request when the caller doesn't specify."""

    def is_available(self) -> bool:
        """Return False if a required API key or dependency is missing."""
        ...

    async def search(self, query: str, max_results: int) -> list[Citation]:
        """Run the search and return normalised Citations."""
        ...


class ToolRegistry:
    """
    Registry of search plugins consulted by the search agent.

    Plugins are evaluated in registration order. Register additional plugins
    at application startup by calling :meth:`register`.
    """

    def __init__(self) -> None:
        self._plugins: list[SearchPlugin] = []

    def register(self, plugin: SearchPlugin) -> None:
        """Add a plugin to the registry."""
        self._plugins.append(plugin)

    def get_plugins(
        self,
        include_academic: bool = False,
        first_variation: bool = True,
    ) -> list[SearchPlugin]:
        """
        Return the subset of plugins that should run for this search pass.

        Args:
            include_academic: Whether academic sources are appropriate for
                the current query.
            first_variation: Whether this is the first query variation in the
                expansion loop.
        """
        result = []
        for plugin in self._plugins:
            if not plugin.is_available():
                continue
            if plugin.requires_academic_context and not include_academic:
                continue
            if plugin.first_variation_only and not first_variation:
                continue
            result.append(plugin)
        return result


# Module-level default registry, pre-populated in app/tools/plugins.py
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Return the global tool registry."""
    return _registry
