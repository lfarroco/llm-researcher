from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    database_url: str = "postgresql://postgres:postgres@db:5432/researcher"
    openai_api_key: str = ""
    app_env: str = "development"

    # LLM Provider Configuration
    llm_provider: str = "ollama"  # Options: "openai", "ollama"
    # Model: "gpt-4o", "qwen3:4b", "llama2", etc.
    llm_model: str = "qwen3:4b"
    llm_temperature: float = 0.2
    ollama_base_url: str = "http://host.docker.internal:11434"  # Ollama server URL


settings = Settings()
