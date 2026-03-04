from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    database_url: str = "postgresql://postgres:postgres@db:5432/researcher"
    openai_api_key: str = ""
    tavily_api_key: str = ""  # For web search
    semantic_scholar_api_key: str = ""  # Optional: higher rate limits
    ncbi_api_key: str = ""  # Optional: for PubMed higher rate limits
    ncbi_email: str = "llm-researcher@example.com"  # Required for NCBI API
    app_env: str = "development"

    # LLM Provider Configuration
    llm_provider: str = "ollama"  # Options: "openai", "ollama"
    # Model: "gpt-4o", "qwen3:4b", "llama2", etc.
    llm_model: str = "qwen3:4b"
    llm_temperature: float = 0.2
    # Ollama server URL
    ollama_base_url: str = "http://host.docker.internal:11434"

    # Research settings
    research_max_sources: int = 20  # Max citations per research
    research_timeout: int = 300  # Max seconds per research


settings = Settings()
