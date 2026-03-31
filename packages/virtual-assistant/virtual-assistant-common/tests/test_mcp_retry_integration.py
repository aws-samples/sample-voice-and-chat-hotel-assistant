# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration test for MCP retry logic using RetryHTTPClient.

This test verifies that our RetryHTTPClient correctly adds retry logic
for MCP requests by overriding the send() method.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from virtual_assistant_common.http import RetryHTTPClient, create_retry_http_client


class TestMCPRetryIntegration:
    """Test the MCP retry logic using RetryHTTPClient."""

    def test_retry_http_client_creation(self):
        """Test that RetryHTTPClient can be created correctly."""
        client = create_retry_http_client()
        assert isinstance(client, RetryHTTPClient)
        assert isinstance(client, httpx.AsyncClient)

    def test_retry_http_client_with_auth(self):
        """Test that RetryHTTPClient works with authentication."""
        mock_auth = AsyncMock()
        client = create_retry_http_client(auth=mock_auth)
        # httpx might wrap the auth in a FunctionAuth, so just check it's not None
        assert client.auth is not None

    @pytest.mark.asyncio
    async def test_retry_logic_on_429(self):
        """Test that RetryHTTPClient retries on 429 status codes."""
        call_count = 0

        async def mock_send(request, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                # Return 429 for first two calls
                response = httpx.Response(
                    status_code=429,
                    headers={"Retry-After": "1"},
                    request=request,
                )
                # Mock the aclose method
                response.aclose = AsyncMock()
                return response
            else:
                # Return 200 for third call
                return httpx.Response(
                    status_code=200,
                    headers={},
                    request=request,
                )

        # Patch the parent send method
        with patch.object(httpx.AsyncClient, "send", side_effect=mock_send):
            client = RetryHTTPClient()

            # Create a mock request
            request = httpx.Request("POST", "https://example.com/test")

            response = await client.send(request)
            assert response.status_code == 200
            assert call_count == 3  # Should have retried twice

    @pytest.mark.asyncio
    async def test_retry_logic_on_500(self):
        """Test that RetryHTTPClient retries on 500 status codes."""
        call_count = 0

        async def mock_send(request, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                # Return 500 for first two calls
                response = httpx.Response(
                    status_code=500,
                    headers={},
                    request=request,
                )
                # Mock the aclose method
                response.aclose = AsyncMock()
                return response
            else:
                # Return 200 for third call
                return httpx.Response(
                    status_code=200,
                    headers={},
                    request=request,
                )

        # Patch the parent send method
        with patch.object(httpx.AsyncClient, "send", side_effect=mock_send):
            client = RetryHTTPClient()

            # Create a mock request
            request = httpx.Request("POST", "https://example.com/test")

            response = await client.send(request)
            assert response.status_code == 200
            assert call_count == 3  # Should have retried twice

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self):
        """Test that RetryHTTPClient does NOT retry on 400 status codes."""
        call_count = 0

        async def mock_send(request, **kwargs):
            nonlocal call_count
            call_count += 1

            # Always return 400
            return httpx.Response(
                status_code=400,
                headers={},
                request=request,
            )

        # Patch the parent send method
        with patch.object(httpx.AsyncClient, "send", side_effect=mock_send):
            client = RetryHTTPClient()

            # Create a mock request
            request = httpx.Request("POST", "https://example.com/test")

            response = await client.send(request)
            assert response.status_code == 400
            assert call_count == 1  # Should NOT have retried
