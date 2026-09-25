from pydantic_settings import BaseSettings
from pydantic import ConfigDict, computed_field
from typing import Any, Optional
from threading import Lock
import time


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    database_url: str = "postgresql://postgres:postgres@db:5432/researcher"
    openai_api_key: str = ""
    groq_api_key: str = ""
    deepseek_api_key: str = ""
    tavily_api_key: str = ""  # For web search
    semantic_scholar_api_key: str = ""  # Optional: higher rate limits
    springer_api_key: str = ""  # Optional: Springer Nature metadata API
    elsevier_api_key: str = ""  # Optional: Elsevier Scopus API
    ncbi_api_key: str = ""  # Optional: for PubMed higher rate limits
    ncbi_email: str = "llm-researcher@example.com"  # Required for NCBI API
    app_env: str = "development"

    # LLM Provider Configuration
    llm_provider: str = "ollama"  # Options: "openai", "ollama", "groq", "deepseek"
    # Model: "gpt-4o", "qwen3:4b", "llama2", etc.
    llm_model: str = "qwen3:4b"
    llm_temperature: float = 0.2
    # Ollama server URL
    ollama_base_url: str = "http://host.docker.internal:11434"
    # DeepSeek OpenAI-compatible API base URL
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Research settings
    research_max_sources: int = 20  # Max citations per research
    research_timeout: int = 300  # Max seconds per research
    # Min relevance score (0-1) for including sources
    research_relevance_threshold: float = 0.5
    # Enable/disable relevance filtering
    research_enable_relevance_filter: bool = True
    # Enable/disable query expansion (generating query variations)
    research_enable_query_expansion: bool = True
    # Number of query variations to generate per sub-query
    research_query_variations: int = 2
    # How many citations are assessed per relevance-filter LLM call. Batching
    # keeps the filter to a handful of calls instead of one call per citation.
    research_relevance_batch_size: int = 20
    # When relevance filtering would remove every candidate for a sub-query,
    # keep at least this many of the highest-scoring ones instead of leaving
    # the sub-question with no sources at all.
    research_relevance_fallback_keep: int = 3
    # Enable/disable reference chasing (following citations from sources)
    research_reference_chase_enabled: bool = True
    # Max depth for reference chasing (1 = follow refs from initial sources,
    # 2 = also follow refs from those refs, etc.)
    research_reference_chase_depth: int = 2
    # Target minimum word count for the synthesized report. The synthesis
    # prompt asks the model to write at least this many words.
    research_report_word_target: int = 2500
    # How many characters of each source's snippet are passed to the
    # synthesis model. Longer excerpts give the writer more material to
    # work with when producing a detailed report.
    research_synthesis_excerpt_chars: int = 1200

    # Full-text grounding: when enabled, the search phase downloads each
    # open-access PDF it can reach, parses it (GROBID, with local
    # pdfplumber/PyPDF2 fallbacks) and chunks it so synthesis can quote
    # real paper text instead of only search-result snippets.
    research_fulltext_enabled: bool = True
    # Candidate sources considered for full-text retrieval per research run.
    # Downloads are network-bound and slow, so this is deliberately bounded.
    research_fulltext_max_sources: int = 8
    # Chunks stored per source (ranked by relevance to the sub-query).
    research_fulltext_chunks_per_source: int = 3
    # Character budget for full-text evidence handed to the synthesis model,
    # per source. Sits alongside (not instead of) the snippet budget.
    research_synthesis_fulltext_chars: int = 6000

    # PDF retrieval and parsing
    # Directory used to cache downloaded PDFs. Defaults to None, which
    # resolves to the system temp directory at call time.
    pdf_cache_dir: Optional[str] = None
    # Refuse to download PDFs larger than this.
    max_pdf_size_mb: int = 50
    # GROBID server used for structured academic PDF parsing.
    grobid_server: str = "http://grobid:8070"
    # Seconds to wait for a GROBID parse before falling back to local parsers.
    grobid_timeout_seconds: float = 30.0

    # Minimum seconds between arXiv API requests, process-wide. arXiv asks for
    # no more than one request every three seconds and answers bursts with
    # HTTP 406; set to 0 to disable pacing (tests).
    arxiv_min_interval_seconds: float = 3.0
    # How long to stop calling arXiv after it answers with a rate-limit
    # status, so a throttled API does not consume the run's time budget.
    arxiv_rate_limit_cooldown_seconds: float = 300.0

    # LLM Rate Limiting & Backoff
    llm_max_retries: int = 10  # Max retry attempts for LLM API calls
    llm_max_concurrent_requests: int = 2  # Max concurrent LLM requests
    # Explicit max output tokens per LLM response. Setting this allows
    # long-form outputs (e.g. the research report) instead of relying on
    # each provider's often-smaller server-side default.
    llm_max_output_tokens: int = 8192
    # DeepSeek thinking mode (chain-of-thought). DeepSeek v4 models reason
    # before answering; this is enabled by default at the API level too.
    # Effort is one of "low", "high", "max". Note: temperature is ignored
    # while thinking mode is enabled.
    llm_thinking_enabled: bool = True
    llm_thinking_effort: str = "high"
    llm_retry_min_wait: float = 4.0  # Min seconds between retries
    llm_retry_max_wait: float = 120.0  # Max seconds between retries
    llm_base_delay: float = 0.5  # Base delay between all LLM calls

    @computed_field
    @property
    def llm_api_key(self) -> str:
        """Return the API key for the configured LLM provider."""
        return {
            "openai": self.openai_api_key,
            "groq": self.groq_api_key,
            "deepseek": self.deepseek_api_key,
        }.get(
            self.llm_provider, ""
        )

    @computed_field
    @property
    def llm_base_url(self) -> str:
        """Return the base URL for the configured LLM provider."""
        return {
            "ollama": self.ollama_base_url,
            "deepseek": self.deepseek_base_url,
        }.get(self.llm_provider, "")


_base_settings = Settings()


SENSITIVE_SETTINGS = {
    "openai_api_key",
    "groq_api_key",
    "deepseek_api_key",
    "tavily_api_key",
    "semantic_scholar_api_key",
    "springer_api_key",
    "elsevier_api_key",
    "ncbi_api_key",
}

# database_url is intentionally excluded because it is used to build the
# SQLAlchemy engine at startup and cannot be safely switched at runtime.
EDITABLE_SETTINGS = tuple(
    field_name
    for field_name in Settings.model_fields
    if field_name != "database_url"
)


def _setting_type_name(default_value: Any) -> str:
    if isinstance(default_value, bool):
        return "boolean"
    if isinstance(default_value, int):
        return "integer"
    if isinstance(default_value, float):
        return "number"
    return "string"


def get_env_setting_value(setting_key: str) -> Any:
    """Return the setting value loaded from .env / process environment."""
    return getattr(_base_settings, setting_key)


def coerce_override_value(raw_value: Any, default_value: Any) -> Any:
    """Convert persisted string override into the setting's native type."""
    if isinstance(default_value, bool):
        if isinstance(raw_value, bool):
            return raw_value
        value = str(raw_value).strip().lower()
        if value in {"true", "1", "yes", "on"}:
            return True
        if value in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"Invalid boolean override value: {raw_value}")

    if isinstance(default_value, int):
        return int(raw_value)

    if isinstance(default_value, float):
        return float(raw_value)

    return str(raw_value)


def serialize_override_value(value: Any, default_value: Any) -> str:
    """Validate and serialize a UI-provided override for database storage."""
    if isinstance(default_value, bool):
        if not isinstance(value, bool):
            raise ValueError("Expected a boolean value")
        return "true" if value else "false"

    if isinstance(default_value, int):
        if isinstance(value, bool):
            raise ValueError("Expected an integer value")
        return str(int(value))

    if isinstance(default_value, float):
        if isinstance(value, bool):
            raise ValueError("Expected a numeric value")
        return str(float(value))

    if not isinstance(value, str):
        raise ValueError("Expected a string value")
    return value


def get_setting_metadata() -> list[dict[str, Any]]:
    """Describe editable runtime settings for API consumers."""
    metadata: list[dict[str, Any]] = []
    for key in EDITABLE_SETTINGS:
        default_value = get_env_setting_value(key)
        metadata.append(
            {
                "key": key,
                "type": _setting_type_name(default_value),
                "sensitive": key in SENSITIVE_SETTINGS,
                "default_value": default_value,
            }
        )
    return metadata


class RuntimeSettingsProxy:
    """Proxy that resolves DB overrides with .env fallback."""

    def __init__(self):
        self._cache_lock = Lock()
        self._cache_ttl_seconds = 3.0
        self._cache_time = 0.0
        self._cache_data: dict[str, str] = {}

    def _read_overrides_from_db(self) -> dict[str, str]:
        try:
            from app.database import SessionLocal
            from app.models import AppSetting

            db = SessionLocal()
            try:
                rows = db.query(AppSetting).all()
                return {row.key: row.value for row in rows}
            finally:
                db.close()
        except Exception:
            # If migrations have not run yet or DB is unavailable,
            # keep using .env values.
            return {}

    def _get_overrides(self) -> dict[str, str]:
        now = time.monotonic()
        if now - self._cache_time <= self._cache_ttl_seconds:
            return self._cache_data

        with self._cache_lock:
            now = time.monotonic()
            if now - self._cache_time <= self._cache_ttl_seconds:
                return self._cache_data
            self._cache_data = self._read_overrides_from_db()
            self._cache_time = now
            return self._cache_data

    def invalidate_cache(self) -> None:
        with self._cache_lock:
            self._cache_time = 0.0
            self._cache_data = {}

    def __getattr__(self, name: str) -> Any:
        if name == "llm_api_key":
            provider = self.llm_provider
            provider_keys = {
                "openai": self.openai_api_key,
                "groq": self.groq_api_key,
                "deepseek": self.deepseek_api_key,
            }
            return provider_keys.get(provider, "")

        if name == "llm_base_url":
            provider = self.llm_provider
            provider_urls = {
                "ollama": self.ollama_base_url,
                "deepseek": self.deepseek_base_url,
            }
            return provider_urls.get(provider, "")

        default_value = getattr(_base_settings, name)
        if name not in EDITABLE_SETTINGS:
            return default_value

        override = self._get_overrides().get(name)
        if override is None:
            return default_value

        try:
            return coerce_override_value(override, default_value)
        except (TypeError, ValueError):
            return default_value


settings = RuntimeSettingsProxy()
