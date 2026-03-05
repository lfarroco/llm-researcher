"""
Rate limiting middleware for API endpoints.

Implements token bucket rate limiting per IP address.
"""

import logging
import time
from typing import Dict, Tuple

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, tokens: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            tokens: Maximum number of tokens (requests)
            refill_rate: Tokens per second refill rate
        """
        self.capacity = tokens
        self.tokens = tokens
        self.refill_rate = refill_rate
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.

        Returns:
            True if tokens were consumed, False if bucket is empty
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait before tokens are available."""
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Average requests allowed per minute
            burst_size: Maximum burst size (bucket capacity)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.refill_rate = requests_per_minute / 60.0  # tokens per second

        # Store buckets per IP address
        self.buckets: Dict[str, TokenBucket] = {}

        # Track last cleanup time
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # Clean up every 5 minutes

    def _get_bucket(self, identifier: str) -> TokenBucket:
        """Get or create a token bucket for an identifier (e.g., IP)."""
        if identifier not in self.buckets:
            self.buckets[identifier] = TokenBucket(
                self.burst_size,
                self.refill_rate
            )
        return self.buckets[identifier]

    def _cleanup_old_buckets(self):
        """Remove buckets that haven't been used recently."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return

        # Remove buckets older than 10 minutes
        cutoff = now - 600
        to_remove = [
            key for key, bucket in self.buckets.items()
            if bucket.last_refill < cutoff
        ]

        for key in to_remove:
            del self.buckets[key]

        self.last_cleanup = now
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old rate limit buckets")

    def check_rate_limit(self, identifier: str) -> Tuple[bool, float]:
        """
        Check if request is allowed under rate limit.

        Args:
            identifier: Unique identifier (e.g., IP address)

        Returns:
            Tuple of (allowed, wait_time)
        """
        self._cleanup_old_buckets()

        bucket = self._get_bucket(identifier)
        allowed = bucket.consume(1)
        wait_time = bucket.get_wait_time(1) if not allowed else 0.0

        return allowed, wait_time


# Global rate limiter instances
_default_rate_limiter = RateLimiter(
    requests_per_minute=60,
    burst_size=10
)

_research_rate_limiter = RateLimiter(
    requests_per_minute=10,  # More restrictive for research creation
    burst_size=3
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to requests."""

    def __init__(self, app, rate_limiter: RateLimiter = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or _default_rate_limiter

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Skip rate limiting for health checks
        if request.url.path == "/":
            return await call_next(request)

        # Check rate limit
        allowed, wait_time = self.rate_limiter.check_rate_limit(client_ip)

        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {request.url.path}"
            )
            return HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": int(wait_time) + 1
                },
                headers={"Retry-After": str(int(wait_time) + 1)}
            )

        response = await call_next(request)
        return response


def check_research_rate_limit(client_ip: str):
    """
    Check rate limit for research creation endpoints.

    Raises HTTPException if rate limit exceeded.
    """
    allowed, wait_time = _research_rate_limiter.check_rate_limit(client_ip)

    if not allowed:
        logger.warning(
            f"Research rate limit exceeded for {client_ip}"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Research creation rate limit exceeded",
                "message": "Too many research requests. Please try again later.",
                "retry_after": int(wait_time) + 1
            },
            headers={"Retry-After": str(int(wait_time) + 1)}
        )
