"""
Tests for core modules: config.py, llm_provider.py, and rate_limiter.py

These tests validate configuration loading, LLM provider factory,
and rate limiting functionality in isolation.
"""

import pytest
import time
from unittest.mock import MagicMock, patch

from app.config import Settings
from app.llm_provider import (
    LLMProvider,
    OpenAIProvider,
    OllamaProvider,
    LLMProviderFactory,
)
from app.rate_limiter import (
    TokenBucket,
    RateLimiter,
    check_research_rate_limit,
)
from fastapi import HTTPException


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self):
        """Test that default settings are loaded."""
        # Don't test specific values from .env, just test structure
        from app.config import settings

        # Check that required fields exist and have reasonable values
        assert isinstance(settings.database_url, str)
        assert len(settings.database_url) > 0
        assert settings.app_env in ["development", "production", "test"]
        assert settings.llm_provider in ["openai", "ollama"]
        assert isinstance(settings.llm_model, str)
        assert settings.llm_temperature >= 0.0
        assert settings.llm_temperature <= 1.0
        assert settings.research_max_sources > 0
        assert settings.research_timeout > 0

    def test_settings_from_environment(self):
        """Test loading settings from environment variables."""
        env = {
            "DATABASE_URL": "postgresql://custom:custom@localhost:5432/test",
            "OPENAI_API_KEY": "sk-test-key",
            "TAVILY_API_KEY": "tvly-test-key",
            "LLM_PROVIDER": "openai",
            "LLM_MODEL": "gpt-4o",
            "LLM_TEMPERATURE": "0.5",
            "APP_ENV": "production",
            "RESEARCH_MAX_SOURCES": "50",
            "RESEARCH_TIMEOUT": "600",
        }

        with patch.dict("os.environ", env, clear=True):
            settings = Settings()

            assert settings.database_url == "postgresql://custom:custom@localhost:5432/test"
            assert settings.openai_api_key == "sk-test-key"
            assert settings.tavily_api_key == "tvly-test-key"
            assert settings.llm_provider == "openai"
            assert settings.llm_model == "gpt-4o"
            assert settings.llm_temperature == 0.5
            assert settings.app_env == "production"
            assert settings.research_max_sources == 50
            assert settings.research_timeout == 600

    def test_optional_api_keys(self):
        """Test that optional API keys default to empty strings."""
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.semantic_scholar_api_key == ""
            assert settings.ncbi_api_key == ""
            assert settings.ncbi_email == "llm-researcher@example.com"

    def test_ollama_base_url_default(self):
        """Test Ollama base URL has a default value."""
        from app.config import settings

        # Just check it's a valid URL string
        assert isinstance(settings.ollama_base_url, str)
        assert settings.ollama_base_url.startswith("http://")
        assert "11434" in settings.ollama_base_url  # Default Ollama port


class TestOpenAIProvider:
    """Tests for OpenAI provider."""

    def test_create_openai_provider(self):
        """Test creating an OpenAI provider."""
        provider = OpenAIProvider(
            model="gpt-4o",
            api_key="sk-test-key",
            temperature=0.3,
        )

        assert provider.model == "gpt-4o"
        assert provider.api_key == "sk-test-key"
        assert provider.temperature == 0.3

    def test_openai_provider_default_values(self):
        """Test OpenAI provider with default values."""
        provider = OpenAIProvider()

        assert provider.model == "gpt-4o"
        assert provider.temperature == 0.2
        assert provider.api_key is None

    def test_openai_get_llm(self):
        """Test getting LLM instance from OpenAI provider."""
        provider = OpenAIProvider(
            model="gpt-4o",
            api_key="sk-test-key",
        )

        with patch("app.llm_provider.ChatOpenAI") as mock_chat:
            llm = provider.get_llm()

            # Verify ChatOpenAI was called with correct parameters
            mock_chat.assert_called_once_with(
                model="gpt-4o",
                api_key="sk-test-key",
                temperature=0.2,
            )


class TestOllamaProvider:
    """Tests for Ollama provider."""

    def test_create_ollama_provider(self):
        """Test creating an Ollama provider."""
        provider = OllamaProvider(
            model="llama2",
            base_url="http://localhost:11434",
            temperature=0.5,
        )

        assert provider.model == "llama2"
        assert provider.base_url == "http://localhost:11434"
        assert provider.temperature == 0.5

    def test_ollama_provider_default_values(self):
        """Test Ollama provider with default values."""
        provider = OllamaProvider()

        assert provider.model == "llama2"
        assert provider.base_url == "http://localhost:11434"
        assert provider.temperature == 0.2

    def test_ollama_get_llm(self):
        """Test getting LLM instance from Ollama provider."""
        provider = OllamaProvider(
            model="qwen3:4b",
            base_url="http://localhost:11434",
        )

        with patch("app.llm_provider.ChatOllama") as mock_chat:
            llm = provider.get_llm()

            # Verify ChatOllama was called with correct parameters
            mock_chat.assert_called_once_with(
                model="qwen3:4b",
                base_url="http://localhost:11434",
                temperature=0.2,
            )


class TestLLMProviderFactory:
    """Tests for LLM provider factory."""

    def test_create_openai_provider(self):
        """Test factory creates OpenAI provider."""
        provider = LLMProviderFactory.create_provider(
            provider_type="openai",
            model="gpt-4o",
            api_key="sk-test-key",
            temperature=0.3,
        )

        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4o"
        assert provider.api_key == "sk-test-key"
        assert provider.temperature == 0.3

    def test_create_openai_provider_case_insensitive(self):
        """Test factory handles case-insensitive provider type."""
        provider = LLMProviderFactory.create_provider(
            provider_type="OpenAI",
            model="gpt-4o",
            api_key="sk-test-key",
        )

        assert isinstance(provider, OpenAIProvider)

    def test_create_ollama_provider(self):
        """Test factory creates Ollama provider."""
        provider = LLMProviderFactory.create_provider(
            provider_type="ollama",
            model="llama2",
            base_url="http://localhost:11434",
            temperature=0.5,
        )

        assert isinstance(provider, OllamaProvider)
        assert provider.model == "llama2"
        assert provider.base_url == "http://localhost:11434"
        assert provider.temperature == 0.5

    def test_create_ollama_provider_default_base_url(self):
        """Test factory uses default base_url for Ollama when not provided."""
        provider = LLMProviderFactory.create_provider(
            provider_type="ollama",
            model="llama2",
        )

        assert isinstance(provider, OllamaProvider)
        assert provider.base_url == "http://localhost:11434"

    def test_create_provider_invalid_type(self):
        """Test factory raises error for invalid provider type."""
        with pytest.raises(ValueError) as exc_info:
            LLMProviderFactory.create_provider(
                provider_type="invalid",
                model="test-model",
            )

        assert "Unsupported provider type: invalid" in str(exc_info.value)
        assert "openai, ollama" in str(exc_info.value)


class TestTokenBucket:
    """Tests for TokenBucket rate limiting."""

    def test_create_token_bucket(self):
        """Test creating a token bucket."""
        bucket = TokenBucket(tokens=10, refill_rate=2.0)

        assert bucket.capacity == 10
        assert bucket.tokens == 10
        assert bucket.refill_rate == 2.0

    def test_consume_tokens_success(self):
        """Test consuming tokens when available."""
        bucket = TokenBucket(tokens=10, refill_rate=1.0)

        # Should succeed
        result = bucket.consume(3)

        assert result is True
        assert bucket.tokens == 7

    def test_consume_tokens_failure(self):
        """Test consuming tokens when insufficient."""
        bucket = TokenBucket(tokens=2, refill_rate=1.0)

        # Try to consume more than available
        result = bucket.consume(5)

        assert result is False
        assert bucket.tokens == 2  # Unchanged

    def test_consume_all_tokens(self):
        """Test consuming all tokens."""
        bucket = TokenBucket(tokens=5, refill_rate=1.0)

        result = bucket.consume(5)

        assert result is True
        assert bucket.tokens == 0

    def test_token_refill_over_time(self):
        """Test that tokens refill over time."""
        bucket = TokenBucket(
            tokens=10, refill_rate=20.0)  # 20 tokens/sec (faster)

        # Consume all tokens first
        bucket.consume(10)
        assert bucket.tokens == 0

        # Wait 1 second (should refill ~20 tokens, capped at capacity 10)
        time.sleep(1.0)

        # Refill is called automatically by consume
        # Try to consume just 5 tokens (well below what should be refilled)
        result = bucket.consume(5)

        # Should succeed after refill
        assert result is True

    def test_token_refill_caps_at_capacity(self):
        """Test that refill doesn't exceed capacity."""
        bucket = TokenBucket(tokens=10, refill_rate=100.0)

        # Wait a bit and refill
        time.sleep(0.5)
        bucket._refill()

        # Should not exceed capacity
        assert bucket.tokens <= bucket.capacity

    def test_get_wait_time_with_tokens(self):
        """Test wait time when tokens are available."""
        bucket = TokenBucket(tokens=10, refill_rate=1.0)

        wait_time = bucket.get_wait_time(3)

        assert wait_time == 0.0

    def test_get_wait_time_without_tokens(self):
        """Test wait time when tokens are needed."""
        bucket = TokenBucket(tokens=0, refill_rate=2.0)  # 2 tokens/sec

        # Need 4 tokens, rate is 2/sec, so wait time should be ~2 seconds
        wait_time = bucket.get_wait_time(4)

        assert wait_time == pytest.approx(2.0, abs=0.1)


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_create_rate_limiter(self):
        """Test creating a rate limiter."""
        limiter = RateLimiter(
            requests_per_minute=60,
            burst_size=10,
        )

        assert limiter.requests_per_minute == 60
        assert limiter.burst_size == 10
        assert limiter.refill_rate == 1.0  # 60/60 = 1 token/sec

    def test_check_rate_limit_allowed(self):
        """Test checking rate limit when allowed."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)

        allowed, wait_time = limiter.check_rate_limit("client1")

        assert allowed is True
        assert wait_time == 0.0

    def test_check_rate_limit_multiple_clients(self):
        """Test that different clients have separate buckets."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=5)

        # Client 1 consumes tokens
        for _ in range(5):
            allowed, _ = limiter.check_rate_limit("client1")
            assert allowed is True

        # Client 1 should be rate limited
        allowed, _ = limiter.check_rate_limit("client1")
        assert allowed is False

        # Client 2 should still be allowed
        allowed, _ = limiter.check_rate_limit("client2")
        assert allowed is True

    def test_check_rate_limit_burst(self):
        """Test burst limit."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=3)

        # First 3 requests should succeed (burst)
        for i in range(3):
            allowed, _ = limiter.check_rate_limit("client1")
            assert allowed is True, f"Request {i+1} should be allowed"

        # 4th request should fail
        allowed, wait_time = limiter.check_rate_limit("client1")
        assert allowed is False
        assert wait_time > 0

    def test_check_rate_limit_returns_wait_time(self):
        """Test that wait time is returned when rate limited."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)

        # Exhaust burst
        limiter.check_rate_limit("client1")
        limiter.check_rate_limit("client1")

        # Next request should be denied with wait time
        allowed, wait_time = limiter.check_rate_limit("client1")

        assert allowed is False
        assert wait_time > 0
        assert wait_time < 10  # Should be reasonable

    def test_rate_limiter_cleanup(self):
        """Test that old buckets are cleaned up."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        limiter.cleanup_interval = 0.1  # Fast cleanup for testing

        # Create a bucket
        limiter.check_rate_limit("client1")
        assert "client1" in limiter.buckets

        # Mock old timestamp
        limiter.buckets["client1"].last_refill = time.time() - 700  # Old

        # Trigger cleanup
        time.sleep(0.2)
        limiter.check_rate_limit("client2")  # This triggers cleanup

        # Old bucket should be removed
        assert "client1" not in limiter.buckets


class TestCheckResearchRateLimit:
    """Tests for check_research_rate_limit function."""

    def test_check_research_rate_limit_allowed(self):
        """Test research rate limit when allowed."""
        # Should not raise exception
        try:
            check_research_rate_limit("client1")
        except HTTPException:
            pytest.fail("Should not raise HTTPException")

    def test_check_research_rate_limit_exceeded(self):
        """Test research rate limit when exceeded."""
        from app.rate_limiter import _research_rate_limiter

        # Exhaust the rate limit (burst_size=3 by default)
        for _ in range(3):
            try:
                check_research_rate_limit("test_client")
            except HTTPException:
                pass

        # Next request should raise exception
        with pytest.raises(HTTPException) as exc_info:
            check_research_rate_limit("test_client")

        assert exc_info.value.status_code == 429
        assert "rate limit" in str(exc_info.value.detail).lower()

    def test_check_research_rate_limit_includes_retry_after(self):
        """Test that rate limit exception includes retry-after header."""
        from app.rate_limiter import _research_rate_limiter

        # Exhaust the rate limit
        for _ in range(3):
            try:
                check_research_rate_limit("test_client2")
            except HTTPException:
                pass

        # Check exception details
        with pytest.raises(HTTPException) as exc_info:
            check_research_rate_limit("test_client2")

        assert "retry_after" in exc_info.value.detail


class TestRateLimiterIntegration:
    """Integration tests for rate limiting."""

    def test_rate_limiter_refill_allows_new_requests(self):
        """Test that after waiting, new requests are allowed."""
        limiter = RateLimiter(
            requests_per_minute=60,  # 1 token/sec
            burst_size=2,
        )

        # Exhaust burst
        limiter.check_rate_limit("client1")
        limiter.check_rate_limit("client1")

        # Should be rate limited
        allowed, _ = limiter.check_rate_limit("client1")
        assert allowed is False

        # Wait for refill (1+ second)
        time.sleep(1.1)

        # Should be allowed again
        allowed, _ = limiter.check_rate_limit("client1")
        assert allowed is True

    def test_concurrent_requests_from_same_client(self):
        """Test handling of rapid requests from same client."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=5)

        results = []
        for _ in range(10):
            allowed, _ = limiter.check_rate_limit("rapid_client")
            results.append(allowed)

        # First 5 should succeed (burst), rest should fail
        assert sum(results) == 5  # Exactly 5 allowed
        assert results[:5] == [True] * 5
        assert results[5:] == [False] * 5
