import logging
from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def get_llm(self) -> BaseChatModel:
        """Return a configured LLM instance."""
        pass


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI models."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        temperature: float = 0.2,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        logger.debug(
            f"Initialized OpenAI provider with model={model}, temperature={temperature}"
        )

    def get_llm(self) -> BaseChatModel:
        logger.debug(f"Creating ChatOpenAI instance with model={self.model}")
        llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
        )
        logger.debug("ChatOpenAI instance created successfully")
        return llm


class OllamaProvider(LLMProvider):
    """Provider for Ollama models (local LLMs)."""

    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
    ):
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        logger.debug(
            f"Initialized Ollama provider with model={model}, base_url={base_url}, temperature={temperature}"
        )

    def get_llm(self) -> BaseChatModel:
        logger.debug(
            f"Creating ChatOllama instance with model={self.model}, base_url={self.base_url}")
        llm = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
        )
        logger.debug("ChatOllama instance created successfully")
        return llm


class LLMProviderFactory:
    """Factory class to create LLM providers based on configuration."""

    @staticmethod
    def create_provider(
        provider_type: str,
        model: str,
        temperature: float = 0.2,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> LLMProvider:
        """
        Create an LLM provider based on the provider type.

        Args:
            provider_type: Type of provider ("openai" or "ollama")
            model: Model name to use
            temperature: Temperature for generation
            api_key: API key for OpenAI (required for OpenAI provider)
            base_url: Base URL for Ollama server
                (optional, defaults to localhost:11434)

        Returns:
            An instance of the appropriate LLMProvider

        Raises:
            ValueError: If provider_type is not supported
        """
        provider_type = provider_type.lower()
        logger.debug(
            f"Creating provider: type={provider_type}, model={model}, temperature={temperature}"
        )

        if provider_type == "openai":
            return OpenAIProvider(
                model=model,
                api_key=api_key,
                temperature=temperature,
            )
        elif provider_type == "ollama":
            return OllamaProvider(
                model=model,
                base_url=base_url or "http://localhost:11434",
                temperature=temperature,
            )
        else:
            logger.error(f"Unsupported provider type: {provider_type}")
            raise ValueError(
                f"Unsupported provider type: {provider_type}. "
                f"Supported types are: openai, ollama"
            )
