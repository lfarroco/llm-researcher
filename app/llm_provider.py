import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# Global semaphore to limit concurrent LLM requests
# This prevents overwhelming API rate limits
_llm_semaphore: Optional[asyncio.Semaphore] = None


def get_llm_semaphore(max_concurrent: int = 3) -> asyncio.Semaphore:
    """Get or create the global LLM semaphore for rate limiting."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(max_concurrent)
        logger.info(
            f"Initialized LLM semaphore with max_concurrent={max_concurrent}"
        )
    return _llm_semaphore


async def rate_limited_llm_call(chain, input_data: dict):
    """
    Execute an LLM chain call with rate limiting via semaphore.

    This prevents overwhelming API rate limits by ensuring only N
    concurrent LLM requests are active at once, and adds a base delay
    between all calls.

    Args:
        chain: LangChain runnable chain
        input_data: Input dictionary for the chain

    Returns:
        Chain output
    """
    from app.config import settings
    semaphore = get_llm_semaphore(settings.llm_max_concurrent_requests)

    async with semaphore:
        active = settings.llm_max_concurrent_requests - semaphore._value
        logger.debug(
            f"[LLM_RATE_LIMIT] Acquired semaphore "
            f"(active: {active}/{settings.llm_max_concurrent_requests})"
        )
        try:
            # Add base delay to space out requests proactively
            if settings.llm_base_delay > 0:
                await asyncio.sleep(settings.llm_base_delay)

            result = await chain.ainvoke(input_data)
            return result
        except Exception as e:
            logger.warning(
                f"[LLM_RATE_LIMIT] Call failed: {e.__class__.__name__}: {e}"
            )
            raise
        finally:
            logger.debug("[LLM_RATE_LIMIT] Released semaphore")


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
        from app.config import settings

        # ChatOpenAI has built-in retry with exponential backoff
        llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_retries=settings.llm_max_retries,
            timeout=180,  # 3 minute timeout
            request_timeout=180,
        )
        logger.debug(
            f"ChatOpenAI configured with {settings.llm_max_retries} retries, "
            f"exponential backoff enabled"
        )
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


class GroqProvider(LLMProvider):
    """Provider for Groq models."""

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        api_key: Optional[str] = None,
        temperature: float = 0.2,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        logger.debug(
            f"Initialized Groq provider with model={model}, temperature={temperature}"
        )

    def get_llm(self) -> BaseChatModel:
        logger.debug(f"Creating ChatGroq instance with model={self.model}")
        from app.config import settings

        # ChatGroq has built-in retry with exponential backoff
        llm = ChatGroq(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_retries=settings.llm_max_retries,
            timeout=180,  # 3 minute timeout
        )
        logger.debug(
            f"ChatGroq configured with {settings.llm_max_retries} retries, "
            f"exponential backoff enabled"
        )
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
        elif provider_type == "groq":
            return GroqProvider(
                model=model,
                api_key=api_key,
                temperature=temperature,
            )
        else:
            logger.error(f"Unsupported provider type: {provider_type}")
            raise ValueError(
                f"Unsupported provider type: {provider_type}. "
                f"Supported types are: openai, ollama, groq"
            )
