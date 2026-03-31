# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Test the RetryHTTPClient and create_retry_http_client function.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from virtual_assistant_common.http import RetryHTTPClient, create_retry_http_client


class TestRetryHTTPClient:
    """Test the RetryHTTPClient class."""

    def test_retry_http_client_creation(self):
        """Test that RetryHTTPClient can be created."""
        client = RetryHTTPClient()
        assert isinstance(client, RetryHTTPClient)
        assert isinstance(client, httpx.AsyncClient)

    def test_retry_http_client_with_params(self):
        """Test that RetryHTTPClient accepts httpx parameters."""
        timeout = httpx.Timeout(30.0)
        headers = {"User-Agent": "test"}

        client = RetryHTTPClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=False,
        )

        assert client.timeout == timeout
        assert client.headers["User-Agent"] == "test"
        assert client.follow_redirects is False

    @pytest.mark.asyncio
    async def test_send_method_retry_on_429(self):
        """Test that send() method retries on 429 status codes."""
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
    async def test_send_method_retry_on_500(self):
        """Test that send() method retries on 500 status codes."""
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
    async def test_send_method_no_retry_on_400(self):
        """Test that send() method does NOT retry on 400 status codes."""
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

    @pytest.mark.asyncio
    async def test_request_method_retry_on_429(self):
        """Test that request() method retries on 429 status codes."""
        call_count = 0

        async def mock_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count <= 2:
                # Return 429 for first two calls
                response = httpx.Response(
                    status_code=429,
                    headers={"Retry-After": "1"},
                    request=httpx.Request(method, url),
                )
                return response
            else:
                # Return 200 for third call
                return httpx.Response(
                    status_code=200,
                    headers={},
                    request=httpx.Request(method, url),
                )

        # Patch the parent request method
        with patch.object(httpx.AsyncClient, "request", side_effect=mock_request):
            client = RetryHTTPClient()

            response = await client.request("POST", "https://example.com/test")
            assert response.status_code == 200
            assert call_count == 3  # Should have retried twice


class TestCreateRetryHttpClient:
    """Test the create_retry_http_client factory function."""

    def test_create_retry_http_client_basic(self):
        """Test basic creation of RetryHTTPClient."""
        client = create_retry_http_client()
        assert isinstance(client, RetryHTTPClient)
        assert client.follow_redirects is True
        assert client.timeout.connect == 30.0

    def test_create_retry_http_client_with_auth(self):
        """Test creation with authentication."""
        mock_auth = AsyncMock()
        client = create_retry_http_client(auth=mock_auth)
        assert client.auth is not None

    def test_create_retry_http_client_with_headers(self):
        """Test creation with custom headers."""
        headers = {"X-Custom-Header": "test-value"}
        client = create_retry_http_client(headers=headers)
        assert client.headers["X-Custom-Header"] == "test-value"

    def test_create_retry_http_client_with_timeout(self):
        """Test creation with custom timeout."""
        timeout = httpx.Timeout(45.0, read=60.0)
        client = create_retry_http_client(timeout=timeout)
        assert client.timeout == timeout

    def test_create_retry_http_client_with_kwargs(self):
        """Test creation with additional kwargs."""
        client = create_retry_http_client(
            follow_redirects=False,
            max_redirects=10,
        )
        assert client.follow_redirects is False
        # max_redirects would be set if follow_redirects was True
