# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Test retry logic for Cognito MCP client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from virtual_assistant_common.cognito_mcp.cognito_mcp_client import cognito_mcp_client
from virtual_assistant_common.http import RetryHTTPClient, create_retry_http_client


class TestRetryLogic:
    """Test retry logic for rate limiting and server errors."""

    def test_create_retry_http_client(self):
        """Test that RetryHTTPClient can be created."""
        client = create_retry_http_client()
        assert isinstance(client, RetryHTTPClient)
        assert isinstance(client, httpx.AsyncClient)

    def test_create_retry_http_client_with_auth(self):
        """Test that RetryHTTPClient can be created with auth."""
        auth = httpx.BasicAuth("user", "pass")
        client = create_retry_http_client(auth=auth)
        assert isinstance(client, RetryHTTPClient)
        assert client.auth == auth

    def test_create_retry_http_client_with_headers(self):
        """Test that RetryHTTPClient can be created with headers."""
        headers = {"Authorization": "Bearer token"}
        client = create_retry_http_client(headers=headers)
        assert isinstance(client, RetryHTTPClient)
        assert client.headers["Authorization"] == "Bearer token"

    @pytest.mark.asyncio
    async def test_cognito_mcp_client_creation(self):
        """Test that cognito_mcp_client can be created successfully."""
        with (
            patch("virtual_assistant_common.cognito_mcp.cognito_mcp_client.CognitoAuth") as mock_auth,
            patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.streamablehttp_client") as mock_client,
        ):
            mock_auth.return_value = MagicMock()
            mock_client.return_value = AsyncMock()

            # Create client (retry logic is now in the HTTP client)
            client = cognito_mcp_client(
                url="https://test.example.com",
                user_pool_id="test-pool",
                client_id="test-client",
                client_secret="test-secret",
            )

            # The client should be created
            assert client is not None

            # Verify that streamablehttp_client was called with httpx_client_factory
            mock_client.assert_called_once()
            call_kwargs = mock_client.call_args[1]
            assert "httpx_client_factory" in call_kwargs

            # Test that the factory creates a RetryHTTPClient
            factory = call_kwargs["httpx_client_factory"]
            retry_client = factory()
            assert isinstance(retry_client, RetryHTTPClient)

    @pytest.mark.asyncio
    async def test_retry_http_client_429_handling(self):
        """Test that RetryHTTPClient properly handles 429 responses."""
        # Create a mock response that returns 429
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "1"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Too Many Requests", request=MagicMock(), response=mock_response
        )

        # Create RetryHTTPClient and mock the parent request method
        client = RetryHTTPClient()

        with patch.object(httpx.AsyncClient, "request", return_value=mock_response) as mock_request:
            # The request should raise HTTPStatusError due to 429, which will trigger retry
            with pytest.raises(httpx.HTTPStatusError):
                await client.request("POST", "https://example.com/test")

            # Verify the parent request was called
            mock_request.assert_called()

    @pytest.mark.asyncio
    async def test_retry_http_client_success_response(self):
        """Test that RetryHTTPClient passes through successful responses."""
        # Create a mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        # Create RetryHTTPClient and mock the parent request method
        client = RetryHTTPClient()

        with patch.object(httpx.AsyncClient, "request", return_value=mock_response) as mock_request:
            result = await client.request("GET", "https://example.com/test")

            # Should return the response without raising
            assert result == mock_response
            mock_request.assert_called_once()
