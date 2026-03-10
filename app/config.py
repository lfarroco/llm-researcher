from pydantic_settings import BaseSettings
from pydantic import ConfigDict, computed_field


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    database_url: str = "postgresql://postgres:postgres@db:5432/researcher"
    openai_api_key: str = ""
    groq_api_key: str = ""
    tavily_api_key: str = ""  # For web search
    semantic_scholar_api_key: str = ""  # Optional: higher rate limits
    ncbi_api_key: str = ""  # Optional: for PubMed higher rate limits
    ncbi_email: str = "llm-researcher@example.com"  # Required for NCBI API
    app_env: str = "development"

    # LLM Provider Configuration
    llm_provider: str = "ollama"  # Options: "openai", "ollama", "groq"
    # Model: "gpt-4o", "qwen3:4b", "llama2", etc.
    llm_model: str = "qwen3:4b"
    llm_temperature: float = 0.2
    # Ollama server URL
    ollama_base_url: str = "http://host.docker.internal:11434"

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
    # Enable/disable reference chasing (following citations from sources)
    research_reference_chase_enabled: bool = True
    # Max depth for reference chasing (1 = follow refs from initial sources,
    # 2 = also follow refs from those refs, etc.)
    research_reference_chase_depth: int = 2

    @computed_field
    @property
    def llm_api_key(self) -> str:
        """Return the API key for the configured LLM provider."""
        return {"openai": self.openai_api_key, "groq": self.groq_api_key}.get(
            self.llm_provider, ""
        )


settings = Settings()
