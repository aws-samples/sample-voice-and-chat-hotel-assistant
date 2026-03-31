# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Base exception classes for hotel assistant common package.

This module defines the base exception hierarchy that can be extended
by specific modules within the hotel assistant common package.
"""

from typing import Any


class HotelAssistantError(Exception):
    """
    Base exception for hotel assistant common package errors.

    This is the root exception class for all hotel assistant related errors.
    It provides a consistent interface for error handling and logging.

    Attributes:
        message: Human-readable error message
        details: Additional error context and details
        error_code: Optional error code for programmatic handling
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            details: Additional error context and details
            error_code: Optional error code for programmatic handling
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = error_code

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        """Return detailed representation of the error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"details={self.details!r}, "
            f"error_code={self.error_code!r})"
        )


class ConfigurationError(HotelAssistantError):
    """
    Raised when configuration is invalid or missing.

    This exception is raised when required configuration parameters
    are missing, invalid, or cannot be loaded from their sources.
    """

    def __init__(
        self,
        message: str,
        missing_keys: list[str] | None = None,
        invalid_keys: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize configuration error.

        Args:
            message: Human-readable error message
            missing_keys: List of missing configuration keys
            invalid_keys: List of invalid configuration keys
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.pop("details", {})
        if missing_keys:
            details["missing_keys"] = missing_keys
        if invalid_keys:
            details["invalid_keys"] = invalid_keys

        super().__init__(message, details=details, **kwargs)
        self.missing_keys = missing_keys or []
        self.invalid_keys = invalid_keys or []


class ConnectionError(HotelAssistantError):
    """
    Raised when connection to external services fails.

    This exception is raised when network connections fail, timeout,
    or encounter other connectivity issues.
    """

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        endpoint: str | None = None,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize connection error.

        Args:
            message: Human-readable error message
            service_name: Name of the service that failed
            endpoint: Endpoint URL that failed
            status_code: HTTP status code if applicable
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.pop("details", {})
        if service_name:
            details["service_name"] = service_name
        if endpoint:
            details["endpoint"] = endpoint
        if status_code:
            details["status_code"] = status_code

        super().__init__(message, details=details, **kwargs)
        self.service_name = service_name
        self.endpoint = endpoint
        self.status_code = status_code


class AgentCoreSessionBusyError(HotelAssistantError):
    """
    Raised when AgentCore Runtime session is busy processing another request.

    This exception is raised when attempting to invoke AgentCore Runtime
    for a session that is already processing a request. This triggers
    retry logic in Step Functions workflows.
    """

    def __init__(
        self,
        message: str,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize session busy error.

        Args:
            message: Human-readable error message
            session_id: Session ID that is busy
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.pop("details", {})
        if session_id:
            details["session_id"] = session_id

        super().__init__(message, details=details, error_code="SESSION_BUSY", **kwargs)
        self.session_id = session_id
