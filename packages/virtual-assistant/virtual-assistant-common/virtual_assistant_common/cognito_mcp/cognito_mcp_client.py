# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Cognito MCP client factory function.

This module provides the cognito_mcp_client async context manager function
that creates authenticated MCP clients using the standard streamablehttp_client interface.
Includes retry logic with exponential backoff for handling rate limiting (429 errors).
"""

import logging
from datetime import timedelta

import httpx
from mcp.client.streamable_http import streamablehttp_client

from ..http import create_retry_http_client
from .cognito_auth import CognitoAuth
from .exceptions import CognitoAuthError, CognitoMCPClientError

logger = logging.getLogger(__name__)


# Retry logic is implemented in RetryHTTPClient from virtual_assistant_common.http
# which is used via httpx_client_factory parameter


def cognito_mcp_client(
    url: str,
    user_pool_id: str,
    client_id: str,
    client_secret: str,
    region: str = "us-east-1",
    headers: dict[str, str] | None = None,
    timeout: float | timedelta = 30,
    sse_read_timeout: float | timedelta = 60 * 5,
    terminate_on_close: bool = True,
):
    """
    Create an authenticated MCP client using Cognito OAuth2 authentication with retry logic.

    This function wraps the standard streamablehttp_client with Cognito authentication
    and adds exponential backoff retry logic with jitter for handling rate limiting (HTTP 429) and
    server errors (5xx) that can occur during HTTP requests.

    The retry logic is implemented by overriding the httpx.AsyncClient.send() method in RetryHTTPClient,
    which intercepts responses before the MCP library calls response.raise_for_status(). This allows
    us to retry on HTTP error status codes without monkey patching.

    Retry configuration:
    - 5 attempts with exponential backoff + jitter (multiplier=2, min=1s, max=60s)
    - Retries on: HTTP 429 (rate limiting), HTTP 5xx (server errors), connection/timeout errors
    - Does not retry on: HTTP 4xx (except 429) client errors
    - Total max time: ~2 minutes

    Args:
        url: MCP server URL
        user_pool_id: Cognito user pool ID
        client_id: Cognito client ID
        client_secret: Cognito client secret
        region: AWS region for Cognito (default: us-east-1)
        headers: Additional HTTP headers to send with requests
        timeout: HTTP request timeout
        sse_read_timeout: Server-sent events read timeout
        terminate_on_close: Whether to terminate the connection on close

    Returns:
        Async context manager that yields:
            - read_stream: Stream for reading messages from the server
            - write_stream: Stream for sending messages to the server
            - get_session_id_callback: Function to retrieve the current session ID

    Raises:
        CognitoAuthError: If authentication setup fails
        CognitoMCPClientError: If client creation fails or all retry attempts are exhausted

    Example:
        ```python
        async with cognito_mcp_client(
            url="https://api.example.com/mcp",
            user_pool_id="us-east-1_example",
            client_id="example_client_id",
            client_secret="example_secret",
        ) as (read_stream, write_stream, get_session_id):
            # Use the MCP client...
        ```
    """
    try:
        # Create Cognito authentication handler
        auth = CognitoAuth(
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region=region,
            timeout=timeout.total_seconds() if isinstance(timeout, timedelta) else timeout,
        )

        # Create timeout object for HTTP client
        http_timeout = httpx.Timeout(
            timeout.total_seconds() if isinstance(timeout, timedelta) else timeout,
            read=sse_read_timeout.total_seconds() if isinstance(sse_read_timeout, timedelta) else sse_read_timeout,
        )

        # Return the streamablehttp_client with retry-enabled HTTP client
        return streamablehttp_client(
            url=url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            terminate_on_close=terminate_on_close,
            auth=auth,
            httpx_client_factory=lambda **kwargs: create_retry_http_client(
                headers=kwargs.get("headers"),
                timeout=kwargs.get("timeout", http_timeout),
                auth=kwargs.get("auth"),
            ),
        )

    except CognitoAuthError:
        # Re-raise CognitoAuthError without modification
        raise

    except Exception as e:
        # Wrap other exceptions in CognitoMCPClientError
        raise CognitoMCPClientError(
            f"Failed to create authenticated MCP client: {e}",
            url=url,
            user_pool_id=user_pool_id,
            client_id=client_id,
            region=region,
        ) from e
