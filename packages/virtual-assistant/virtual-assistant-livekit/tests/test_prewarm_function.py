# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the prewarm function.

This module tests the prewarm function that fetches hotel data
and generates dynamic instructions for the LiveKit agent.
"""

from unittest.mock import AsyncMock, MagicMock, patch


class TestPrewarmFunction:
    """Test prewarm function behavior."""

    def test_prewarm_success(self):
        """Test successful prewarm with hotel data."""
        from virtual_assistant_livekit.agent import prewarm

        # Mock JobContext with real userdata dict
        mock_ctx = MagicMock()
        mock_ctx.userdata = {}

        # Mock hotel data
        mock_hotels = [
            {"hotel_id": "1", "name": "Hotel Test", "location": "Test City"},
            {"hotel_id": "2", "name": "Resort Test", "location": "Test Beach"},
        ]

        # Mock MCP client and session
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        with (
            patch("hotel_assistant_livekit.agent.hotel_pms_mcp_client") as mock_mcp_client,
            patch("hotel_assistant_livekit.agent.get_hotels") as mock_get_hotels,
            patch("hotel_assistant_livekit.agent.generate_dynamic_hotel_instructions") as mock_instructions,
        ):
            # Configure mocks
            mock_mcp_client.return_value.__aenter__.return_value = (
                "read_stream",
                "write_stream",
                "get_session_id",
            )
            mock_get_hotels.return_value = mock_hotels
            mock_instructions.return_value = "Dynamic instructions with hotels"

            # Mock ClientSession context manager
            with patch("hotel_assistant_livekit.agent.ClientSession") as mock_client_session:
                mock_client_session.return_value.__aenter__.return_value = mock_session

                # Call prewarm (now synchronous)
                prewarm(mock_ctx)

                # Verify MCP client was called
                mock_mcp_client.assert_called_once()
                mock_session.initialize.assert_called_once()
                mock_get_hotels.assert_called_once_with(mock_session)

                # Verify instructions were generated with hotel data
                mock_instructions.assert_called_once_with(language="es", hotels=mock_hotels)

                # Verify prewarm data was stored
                assert mock_ctx.userdata["instructions"] == "Dynamic instructions with hotels"
                assert mock_ctx.userdata["hotels"] == mock_hotels

    def test_prewarm_mcp_failure(self):
        """Test prewarm with MCP connection failure."""
        from virtual_assistant_livekit.agent import prewarm

        # Mock JobContext with real userdata dict
        mock_ctx = MagicMock()
        mock_ctx.userdata = {}

        with (
            patch("hotel_assistant_livekit.agent.hotel_pms_mcp_client") as mock_mcp_client,
            patch("hotel_assistant_livekit.agent.generate_dynamic_hotel_instructions") as mock_instructions,
        ):
            # Configure mocks to raise exception
            mock_mcp_client.side_effect = Exception("MCP connection failed")
            mock_instructions.return_value = "Fallback instructions"

            # Call prewarm (now synchronous)
            prewarm(mock_ctx)

            # Verify fallback instructions were generated
            mock_instructions.assert_called_once_with(language="es", hotels=[])

            # Verify prewarm data was stored with empty hotels
            assert mock_ctx.userdata["instructions"] == "Fallback instructions"
            assert mock_ctx.userdata["hotels"] == []

    def test_prewarm_get_hotels_failure(self):
        """Test prewarm with get_hotels failure."""
        from virtual_assistant_livekit.agent import prewarm

        # Mock JobContext with real userdata dict
        mock_ctx = MagicMock()
        mock_ctx.userdata = {}

        # Mock MCP client and session
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()

        with (
            patch("hotel_assistant_livekit.agent.hotel_pms_mcp_client") as mock_mcp_client,
            patch("hotel_assistant_livekit.agent.get_hotels") as mock_get_hotels,
            patch("hotel_assistant_livekit.agent.generate_dynamic_hotel_instructions") as mock_instructions,
        ):
            # Configure mocks
            mock_mcp_client.return_value.__aenter__.return_value = (
                "read_stream",
                "write_stream",
                "get_session_id",
            )
            mock_get_hotels.side_effect = Exception("Failed to get hotels")
            mock_instructions.return_value = "Fallback instructions"

            # Mock ClientSession context manager
            with patch("hotel_assistant_livekit.agent.ClientSession") as mock_client_session:
                mock_client_session.return_value.__aenter__.return_value = mock_session

                # Call prewarm (now synchronous)
                prewarm(mock_ctx)

                # Verify MCP client was called
                mock_mcp_client.assert_called_once()
                mock_session.initialize.assert_called_once()
                mock_get_hotels.assert_called_once_with(mock_session)

                # Verify fallback instructions were generated
                mock_instructions.assert_called_once_with(language="es", hotels=[])

                # Verify prewarm data was stored with empty hotels
                assert mock_ctx.userdata["instructions"] == "Fallback instructions"
                assert mock_ctx.userdata["hotels"] == []
