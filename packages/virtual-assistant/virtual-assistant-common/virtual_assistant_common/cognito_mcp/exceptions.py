# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Exception classes for Cognito MCP client.

This module defines the exception hierarchy for Cognito MCP authentication
and connection errors. These exceptions provide detailed error context
for debugging authentication and connectivity issues.
"""

from typing import Any

from ..exceptions import HotelAssistantError


class CognitoMcpError(HotelAssistantError):
    """
    Base exception for Cognito MCP client errors.

    This is the root exception class for all Cognito MCP related errors.
    It inherits from HotelAssistantError to maintain consistency with
    the overall error hierarchy.
    """

    pass


class CognitoAuthError(CognitoMcpError):
    """
    Raised when Cognito authentication fails.

    This exception is raised when OAuth2 authentication with Cognito
    fails due to invalid credentials, network issues, or service errors.
    It provides detailed context for debugging authentication failures.
    """

    def __init__(
        self,
        message: str,
        user_pool_id: str | None = None,
        client_id: str | None = None,
        region: str | None = None,
        auth_flow: str | None = None,
        status_code: int | None = None,
        cognito_error_code: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Cognito authentication error.

        Args:
            message: Human-readable error message
            user_pool_id: Cognito user pool ID
            client_id: Cognito client ID (masked for security)
            region: AWS region
            auth_flow: OAuth2 flow type (e.g., "client_credentials")
            status_code: HTTP status code from Cognito
            cognito_error_code: Cognito-specific error code
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.get("details", {})
        if user_pool_id:
            details["user_pool_id"] = user_pool_id
        if client_id:
            # Mask client ID for security - only show first 4 and last 4 chars
            masked_client_id = f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) > 8 else "***"
            details["client_id"] = masked_client_id
        if region:
            details["region"] = region
        if auth_flow:
            details["auth_flow"] = auth_flow
        if status_code:
            details["status_code"] = status_code
        if cognito_error_code:
            details["cognito_error_code"] = cognito_error_code

        super().__init__(message, details=details, error_code="COGNITO_AUTH_ERROR", **kwargs)
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
        self.auth_flow = auth_flow
        self.status_code = status_code
        self.cognito_error_code = cognito_error_code


class CognitoConfigError(CognitoMcpError):
    """
    Raised when Cognito MCP configuration is invalid or missing.

    This exception is raised when required Cognito configuration
    parameters are missing, invalid, or cannot be loaded from
    environment variables or AWS Secrets Manager.
    """

    def __init__(
        self,
        message: str,
        missing_config: list[str] | None = None,
        invalid_config: list[str] | None = None,
        config_source: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Cognito configuration error.

        Args:
            message: Human-readable error message
            missing_config: List of missing configuration keys
            invalid_config: List of invalid configuration keys
            config_source: Source of configuration (e.g., "environment", "secrets_manager")
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.get("details", {})
        if missing_config:
            details["missing_config"] = missing_config
        if invalid_config:
            details["invalid_config"] = invalid_config
        if config_source:
            details["config_source"] = config_source

        super().__init__(message, details=details, error_code="COGNITO_CONFIG_ERROR", **kwargs)
        self.missing_config = missing_config or []
        self.invalid_config = invalid_config or []
        self.config_source = config_source


class McpConnectionError(CognitoMcpError):
    """
    Raised when MCP connection fails.

    This exception is raised when the MCP client fails to connect
    to the AgentCore Gateway, encounters network issues, or receives
    unexpected responses from the MCP server.
    """

    def __init__(
        self,
        message: str,
        mcp_url: str | None = None,
        connection_type: str | None = None,
        status_code: int | None = None,
        response_body: str | None = None,
        retry_count: int | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize MCP connection error.

        Args:
            message: Human-readable error message
            mcp_url: MCP server URL
            connection_type: Type of connection (e.g., "streaming_http", "websocket")
            status_code: HTTP status code if applicable
            response_body: Response body from server (truncated for logging)
            retry_count: Number of retry attempts made
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.get("details", {})
        if mcp_url:
            details["mcp_url"] = mcp_url
        if connection_type:
            details["connection_type"] = connection_type
        if status_code:
            details["status_code"] = status_code
        if response_body:
            # Truncate response body for logging (max 500 chars)
            truncated_body = response_body[:500] + "..." if len(response_body) > 500 else response_body
            details["response_body"] = truncated_body
        if retry_count is not None:
            details["retry_count"] = retry_count

        super().__init__(message, details=details, error_code="MCP_CONNECTION_ERROR", **kwargs)
        self.mcp_url = mcp_url
        self.connection_type = connection_type
        self.status_code = status_code
        self.response_body = response_body
        self.retry_count = retry_count


class TokenRefreshError(CognitoMcpError):
    """
    Raised when token refresh fails.

    This exception is a specialized authentication error that occurs
    specifically during token refresh operations. It provides additional
    context about the refresh attempt.
    """

    def __init__(
        self,
        message: str,
        token_expires_at: float | None = None,
        refresh_attempt: int | None = None,
        user_pool_id: str | None = None,
        client_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize token refresh error.

        Args:
            message: Human-readable error message
            token_expires_at: Unix timestamp when token expires
            refresh_attempt: Which refresh attempt failed (1, 2, 3, etc.)
            user_pool_id: Cognito user pool ID
            client_id: Cognito client ID (will be masked for security)
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.get("details", {})
        if token_expires_at:
            details["token_expires_at"] = token_expires_at
        if refresh_attempt:
            details["refresh_attempt"] = refresh_attempt
        if user_pool_id:
            details["user_pool_id"] = user_pool_id
        if client_id:
            # Mask client ID for security - only show first 4 and last 4 chars
            masked_client_id = f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) > 8 else "***"
            details["client_id"] = masked_client_id

        super().__init__(message, details=details, error_code="TOKEN_REFRESH_ERROR", **kwargs)
        self.token_expires_at = token_expires_at
        self.refresh_attempt = refresh_attempt
        self.user_pool_id = user_pool_id
        self.client_id = client_id


class CognitoMCPClientError(CognitoMcpError):
    """
    Raised when MCP client creation or operation fails.

    This exception is raised when the cognito_mcp_client function fails
    to create an authenticated MCP client due to connection issues,
    configuration problems, or other non-authentication related errors.
    """

    def __init__(
        self,
        message: str,
        url: str | None = None,
        user_pool_id: str | None = None,
        client_id: str | None = None,
        region: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Cognito MCP client error.

        Args:
            message: Human-readable error message
            url: MCP server URL
            user_pool_id: Cognito user pool ID
            client_id: Cognito client ID (will be masked for security)
            region: AWS region
            **kwargs: Additional arguments passed to parent class
        """
        details = kwargs.get("details", {})
        if url:
            details["url"] = url
        if user_pool_id:
            details["user_pool_id"] = user_pool_id
        if client_id:
            # Mask client ID for security - only show first 4 and last 4 chars
            masked_client_id = f"{client_id[:4]}...{client_id[-4:]}" if len(client_id) > 8 else "***"
            details["client_id"] = masked_client_id
        if region:
            details["region"] = region

        super().__init__(message, details=details, error_code="COGNITO_MCP_CLIENT_ERROR", **kwargs)
        self.url = url
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
