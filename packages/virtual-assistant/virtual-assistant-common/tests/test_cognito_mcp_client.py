# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for cognito_mcp_client function.

This module tests the cognito_mcp_client function,
including client creation, authentication integration, and error handling.
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from virtual_assistant_common.cognito_mcp.cognito_mcp_client import cognito_mcp_client
from virtual_assistant_common.cognito_mcp.exceptions import (
    CognitoAuthError,
    CognitoMCPClientError,
)


class TestCognitoMcpClient:
    """Test cases for cognito_mcp_client function."""

    @pytest.fixture
    def mock_cognito_auth(self):
        """Mock CognitoAuth instance."""
        with patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.CognitoAuth") as mock_auth_class:
            mock_auth_instance = MagicMock()
            mock_auth_class.return_value = mock_auth_instance
            yield mock_auth_instance

    @pytest.fixture
    def mock_streamablehttp_client(self):
        """Mock streamablehttp_client function."""
        with patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.streamablehttp_client") as mock_client:
            # Create mock streams and callback
            mock_read_stream = AsyncMock()
            mock_write_stream = AsyncMock()
            mock_get_session_id = MagicMock(return_value="test-session-123")

            # Create async context manager
            @asynccontextmanager
            async def mock_context(*args, **kwargs):
                yield (mock_read_stream, mock_write_stream, mock_get_session_id)

            mock_client.return_value = mock_context()
            yield mock_client, mock_read_stream, mock_write_stream, mock_get_session_id

    @pytest.mark.asyncio
    async def test_successful_client_creation(self, mock_cognito_auth, mock_streamablehttp_client):
        """Test successful creation of authenticated MCP client."""
        mock_client, mock_read_stream, mock_write_stream, mock_get_session_id = mock_streamablehttp_client

        # Test parameters
        url = "https://api.example.com/mcp"
        user_pool_id = "us-east-1_test123"
        client_id = "test-client-id"
        client_secret = "test-client-secret"
        region = "us-east-1"

        async with cognito_mcp_client(
            url=url,
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region=region,
        ) as (read_stream, write_stream, get_session_id):
            # Verify CognitoAuth was created with correct parameters
            from virtual_assistant_common.cognito_mcp.cognito_mcp_client import CognitoAuth

            CognitoAuth.assert_called_once_with(
                user_pool_id=user_pool_id,
                client_id=client_id,
                client_secret=client_secret,
                region=region,
                timeout=30.0,
            )

            # Verify streamablehttp_client was called with auth parameter and httpx_client_factory
            call_args = mock_client.call_args
            assert call_args is not None
            args, kwargs = call_args

            # Check the expected parameters
            assert kwargs["url"] == url
            assert kwargs["headers"] is None
            assert kwargs["timeout"] == 30
            assert kwargs["sse_read_timeout"] == 300  # 60 * 5
            assert kwargs["terminate_on_close"] is True
            assert kwargs["auth"] == mock_cognito_auth

            # Check that httpx_client_factory is provided and is callable
            assert "httpx_client_factory" in kwargs
            assert callable(kwargs["httpx_client_factory"])

            # Verify returned streams and callback
            assert read_stream is mock_read_stream
            assert write_stream is mock_write_stream
            assert get_session_id is mock_get_session_id

    @pytest.mark.asyncio
    async def test_client_creation_with_custom_parameters(self, mock_cognito_auth, mock_streamablehttp_client):
        """Test client creation with custom parameters."""
        mock_client, mock_read_stream, mock_write_stream, mock_get_session_id = mock_streamablehttp_client

        # Custom parameters
        url = "https://custom.example.com/mcp"
        user_pool_id = "us-west-2_custom123"
        client_id = "custom-client-id"
        client_secret = "custom-client-secret"
        region = "us-west-2"
        headers = {"X-Custom-Header": "test-value"}
        timeout = timedelta(seconds=45)
        sse_read_timeout = timedelta(minutes=10)
        terminate_on_close = False

        async with cognito_mcp_client(
            url=url,
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region=region,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            terminate_on_close=terminate_on_close,
        ):
            # Verify CognitoAuth was created with correct timeout
            from virtual_assistant_common.cognito_mcp.cognito_mcp_client import CognitoAuth

            CognitoAuth.assert_called_once_with(
                user_pool_id=user_pool_id,
                client_id=client_id,
                client_secret=client_secret,
                region=region,
                timeout=45.0,  # timedelta converted to float
            )

            # Verify streamablehttp_client was called with custom parameters and httpx_client_factory
            call_args = mock_client.call_args
            assert call_args is not None
            args, kwargs = call_args

            # Check the expected parameters
            assert kwargs["url"] == url
            assert kwargs["headers"] == headers
            assert kwargs["timeout"] == timeout
            assert kwargs["sse_read_timeout"] == sse_read_timeout
            assert kwargs["terminate_on_close"] == terminate_on_close
            assert kwargs["auth"] == mock_cognito_auth

            # Check that httpx_client_factory is provided and is callable
            assert "httpx_client_factory" in kwargs
            assert callable(kwargs["httpx_client_factory"])

    @pytest.mark.asyncio
    async def test_cognito_auth_error_propagation(self, mock_streamablehttp_client):
        """Test that CognitoAuthError is propagated without modification."""
        # Mock CognitoAuth to raise CognitoAuthError
        auth_error = CognitoAuthError(
            "Authentication failed",
            user_pool_id="us-east-1_test123",
            client_id="test-client-id",
            region="us-east-1",
        )

        with patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.CognitoAuth") as mock_auth_class:
            mock_auth_class.side_effect = auth_error

            with pytest.raises(CognitoAuthError) as exc_info:
                cognito_mcp_client(
                    url="https://api.example.com/mcp",
                    user_pool_id="us-east-1_test123",
                    client_id="test-client-id",
                    client_secret="test-client-secret",
                )

            # Verify the exact same exception is raised
            assert exc_info.value is auth_error

    @pytest.mark.asyncio
    async def test_streamablehttp_client_error_wrapping(self, mock_cognito_auth):
        """Test that streamablehttp_client errors are wrapped in CognitoMCPClientError."""
        # Mock streamablehttp_client to raise an exception
        original_error = ValueError("Connection failed")

        with patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.streamablehttp_client") as mock_client:
            mock_client.side_effect = original_error

            with pytest.raises(CognitoMCPClientError) as exc_info:
                cognito_mcp_client(
                    url="https://api.example.com/mcp",
                    user_pool_id="us-east-1_test123",
                    client_id="test-client-id",
                    client_secret="test-client-secret",
                    region="us-east-1",
                )

            # Verify error details
            error = exc_info.value
            assert "Failed to create authenticated MCP client" in str(error)
            assert error.url == "https://api.example.com/mcp"
            assert error.user_pool_id == "us-east-1_test123"
            assert error.client_id == "test-client-id"
            assert error.region == "us-east-1"
            assert error.__cause__ is original_error

    def test_returns_streamablehttp_client_context_manager(self, mock_cognito_auth):
        """Test that the function returns the streamablehttp_client context manager directly."""
        with patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.streamablehttp_client") as mock_client:
            mock_context_manager = MagicMock()
            mock_client.return_value = mock_context_manager

            result = cognito_mcp_client(
                url="https://api.example.com/mcp",
                user_pool_id="us-east-1_test123",
                client_id="test-client-id",
                client_secret="test-client-secret",
            )

            # Verify the result is the same context manager returned by streamablehttp_client
            assert result is mock_context_manager

    def test_timeout_parameter_conversion(self, mock_cognito_auth, mock_streamablehttp_client):
        """Test that timedelta timeout is properly converted to float for CognitoAuth."""
        timeout = timedelta(seconds=60)

        cognito_mcp_client(
            url="https://api.example.com/mcp",
            user_pool_id="us-east-1_test123",
            client_id="test-client-id",
            client_secret="test-client-secret",
            timeout=timeout,
        )

        # Verify CognitoAuth received float timeout
        from virtual_assistant_common.cognito_mcp.cognito_mcp_client import CognitoAuth

        CognitoAuth.assert_called_once()
        call_args = CognitoAuth.call_args
        assert call_args.kwargs["timeout"] == 60.0

    def test_default_parameters(self, mock_cognito_auth, mock_streamablehttp_client):
        """Test that default parameters are applied correctly."""
        mock_client, _, _, _ = mock_streamablehttp_client

        cognito_mcp_client(
            url="https://api.example.com/mcp",
            user_pool_id="us-east-1_test123",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

        # Verify CognitoAuth defaults
        from virtual_assistant_common.cognito_mcp.cognito_mcp_client import CognitoAuth

        CognitoAuth.assert_called_once_with(
            user_pool_id="us-east-1_test123",
            client_id="test-client-id",
            client_secret="test-client-secret",
            region="us-east-1",  # default
            timeout=30.0,  # default converted to float
        )

        # Verify streamablehttp_client defaults and httpx_client_factory
        call_args = mock_client.call_args
        assert call_args is not None
        args, kwargs = call_args

        # Check the expected parameters
        assert kwargs["url"] == "https://api.example.com/mcp"
        assert kwargs["headers"] is None  # default
        assert kwargs["timeout"] == 30  # default
        assert kwargs["sse_read_timeout"] == 300  # default (60 * 5)
        assert kwargs["terminate_on_close"] is True  # default
        assert kwargs["auth"] == mock_cognito_auth

        # Check that httpx_client_factory is provided and is callable
        assert "httpx_client_factory" in kwargs
        assert callable(kwargs["httpx_client_factory"])

    def test_general_exception_wrapping(self, mock_cognito_auth):
        """Test that general exceptions are wrapped in CognitoMCPClientError."""
        # Mock CognitoAuth to raise a general exception
        original_error = RuntimeError("Unexpected error")

        with patch("hotel_assistant_common.cognito_mcp.cognito_mcp_client.CognitoAuth") as mock_auth_class:
            mock_auth_class.side_effect = original_error

            with pytest.raises(CognitoMCPClientError) as exc_info:
                cognito_mcp_client(
                    url="https://api.example.com/mcp",
                    user_pool_id="us-east-1_test123",
                    client_id="test-client-id",
                    client_secret="test-client-secret",
                )

            # Verify error details
            error = exc_info.value
            assert "Failed to create authenticated MCP client" in str(error)
            assert error.__cause__ is original_error
