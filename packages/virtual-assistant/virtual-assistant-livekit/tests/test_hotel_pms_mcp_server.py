# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Tests for HotelPmsMCPServer class.
"""

from unittest.mock import AsyncMock, patch

import pytest
from virtual_assistant_common.cognito_mcp.exceptions import CognitoConfigError

from virtual_assistant_livekit.hotel_pms_mcp_server import HotelPmsMCPServer


class TestHotelPmsMCPServer:
    """Test cases for HotelPmsMCPServer class."""

    def test_init_default_timeout(self):
        """Test HotelPmsMCPServer initialization with default timeout."""
        server = HotelPmsMCPServer()
        assert server._read_timeout == 30.0
        assert not server.initialized

    def test_init_custom_timeout(self):
        """Test HotelPmsMCPServer initialization with custom timeout."""
        server = HotelPmsMCPServer(client_session_timeout_seconds=60.0)
        assert server._read_timeout == 60.0
        assert not server.initialized

    def test_client_streams_method_exists(self):
        """Test that client_streams method exists and is callable."""
        server = HotelPmsMCPServer()
        assert hasattr(server, "client_streams")
        assert callable(server.client_streams)

    @patch("hotel_assistant_livekit.hotel_pms_mcp_server.hotel_pms_mcp_client")
    def test_client_streams_delegates_to_hotel_pms_mcp_client(self, mock_hotel_pms_mcp_client):
        """Test that client_streams delegates to hotel_pms_mcp_client."""
        # Setup mock
        mock_context_manager = AsyncMock()
        mock_hotel_pms_mcp_client.return_value = mock_context_manager

        server = HotelPmsMCPServer()
        result = server.client_streams()

        # Verify delegation
        mock_hotel_pms_mcp_client.assert_called_once_with()
        assert result is mock_context_manager

    @patch("hotel_assistant_livekit.hotel_pms_mcp_server.hotel_pms_mcp_client")
    def test_client_streams_propagates_exceptions(self, mock_hotel_pms_mcp_client):
        """Test that client_streams properly propagates exceptions from hotel_pms_mcp_client."""
        # Setup mock to raise exception
        mock_hotel_pms_mcp_client.side_effect = CognitoConfigError(
            "Test configuration error", missing_config=["url"], invalid_config=[], config_source="test"
        )

        server = HotelPmsMCPServer()

        # Verify exception is propagated
        with pytest.raises(CognitoConfigError, match="Test configuration error"):
            server.client_streams()

        mock_hotel_pms_mcp_client.assert_called_once_with()

    def test_inheritance_from_mcp_server(self):
        """Test that HotelPmsMCPServer properly inherits from MCPServer."""
        from livekit.agents import mcp

        server = HotelPmsMCPServer()
        assert isinstance(server, mcp.MCPServer)

    def test_abstract_method_implementation(self):
        """Test that client_streams method properly implements the abstract method."""
        import inspect

        from livekit.agents import mcp

        # Get the abstract method signature
        abstract_method = mcp.MCPServer.client_streams
        concrete_method = HotelPmsMCPServer.client_streams

        # Verify signatures match (excluding 'self' parameter)
        abstract_sig = inspect.signature(abstract_method)
        concrete_sig = inspect.signature(concrete_method)

        # Both should have no parameters except self
        assert len(abstract_sig.parameters) == 1  # just 'self'
        assert len(concrete_sig.parameters) == 1  # just 'self'
