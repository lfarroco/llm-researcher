"""
Base types and protocols for research tools.

This module provides:
- Common result wrapper for all tools
- Error handling patterns
- Configuration patterns for testability
"""

from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class ToolErrorType(str, Enum):
    """Categorized error types for tool failures."""

    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    NOT_FOUND = "not_found"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    UNKNOWN = "unknown"


class ToolError(BaseModel):
    """Standardized error information from a tool."""

    error_type: ToolErrorType = Field(description="Category of error")
    message: str = Field(description="Human-readable error message")
    details: Optional[dict] = Field(
        default=None, description="Additional error context")
    recoverable: bool = Field(
        default=True, description="Whether the error might succeed on retry")


T = TypeVar("T")


class ToolResponse(BaseModel, Generic[T]):
    """
    Wrapper for tool responses providing consistent success/failure handling.

    Use this to wrap tool results so callers can handle errors uniformly.
    """

    success: bool = Field(description="Whether the tool call succeeded")
    data: Optional[list[T]] = Field(
        default=None, description="Result data if successful")
    error: Optional[ToolError] = Field(
        default=None, description="Error info if failed")

    @classmethod
    def ok(cls, data: list[T]) -> "ToolResponse[T]":
        """Create a successful response."""
        return cls(success=True, data=data)

    @classmethod
    def fail(
        cls,
        error_type: ToolErrorType,
        message: str,
        details: Optional[dict] = None,
        recoverable: bool = True,
    ) -> "ToolResponse[T]":
        """Create a failed response."""
        return cls(
            success=False,
            error=ToolError(
                error_type=error_type,
                message=message,
                details=details,
                recoverable=recoverable,
            ),
        )


class BaseSearchResult(BaseModel):
    """Common fields for all search results."""

    model_config = ConfigDict(extra="allow")  # Allow subclasses to add fields

    title: str = Field(description="Title of the result")
    url: str = Field(description="URL to the source")
    snippet: str = Field(description="Relevant text excerpt")


def get_setting(value: Optional[str], setting_name: str) -> Optional[str]:
    """
    Get a configuration value with fallback to app settings.

    This pattern allows tools to be tested with explicit values
    while still using app settings in production.

    Args:
        value: Explicitly provided value (takes precedence)
        setting_name: Name of the setting in app.config.settings

    Returns:
        The value to use, or None if not configured
    """
    if value is not None:
        return value

    # Lazy import to avoid circular imports and allow testing without full app
    try:
        from app.config import settings
        return getattr(settings, setting_name, None)
    except ImportError:
        return None
