# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for Nova Sonic 2 model configuration.

This module tests the RealtimeModel configuration including:
- Nova Sonic 2 model initialization
- Voice configuration (tiffany)
- Turn detection sensitivity validation
- Tool choice configuration
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModelConfiguration:
    """Test RealtimeModel configuration for Nova Sonic 2."""

    def setup_method(self):
        """Set up test environment."""
        # Clean environment variables
        for key in ["MODEL_TEMPERATURE", "ENDPOINTING_SENSITIVITY"]:
            if key in os.environ:
                del os.environ[key]

    async def _run_entrypoint_with_mocks(self, mock_realtime_model):
        """Helper to run entrypoint with standard mocks."""
        from virtual_assistant_livekit.agent import entrypoint

        # Create mock context
        mock_ctx = MagicMock()
        mock_ctx.connect = AsyncMock()
        mock_ctx.room = MagicMock()
        mock_ctx.proc.userdata = {
            "instructions": "Test instructions",
            "client_manager": MagicMock(get_mcp_clients=MagicMock(return_value={})),
        }

        # Mock other dependencies
        with (
            patch("virtual_assistant_livekit.agent.VirtualAssistant"),
            patch("virtual_assistant_livekit.agent.AgentSession") as mock_session_class,
            patch("virtual_assistant_livekit.agent.BackgroundAudioPlayer") as mock_audio,
            patch("virtual_assistant_livekit.agent.increment_active_calls"),
        ):
            mock_session = MagicMock()
            mock_session.on = MagicMock(return_value=lambda func: func)
            mock_session.start = AsyncMock()
            mock_session_class.return_value = mock_session

            mock_audio_player = MagicMock()
            mock_audio_player.start = AsyncMock()
            mock_audio.return_value = mock_audio_player

            await entrypoint(mock_ctx)

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_with_nova_sonic_2_creates_correct_model(self, mock_realtime_model):
        """Test that with_nova_sonic_2() factory method is used."""
        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify with_nova_sonic_2 was called
        mock_realtime_model.with_nova_sonic_2.assert_called_once()

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_voice_tiffany_is_configured(self, mock_realtime_model):
        """Test that voice='tiffany' is configured for polyglot support."""
        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify voice='tiffany' was passed
        call_kwargs = mock_realtime_model.with_nova_sonic_2.call_args[1]
        assert call_kwargs["voice"] == "tiffany"

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_turn_detection_uses_environment_variable(self, mock_realtime_model):
        """Test that turn_detection parameter uses ENDPOINTING_SENSITIVITY environment variable."""
        # Set environment variable
        os.environ["ENDPOINTING_SENSITIVITY"] = "HIGH"

        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify turn_detection='HIGH' was passed
        call_kwargs = mock_realtime_model.with_nova_sonic_2.call_args[1]
        assert call_kwargs["turn_detection"] == "HIGH"

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.logger")
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_invalid_sensitivity_defaults_to_medium(self, mock_realtime_model, mock_logger):
        """Test that invalid sensitivity value defaults to MEDIUM with warning."""
        # Set invalid environment variable
        os.environ["ENDPOINTING_SENSITIVITY"] = "INVALID"

        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify warning was logged
        warning_calls = [
            call for call in mock_logger.warning.call_args_list if "Invalid ENDPOINTING_SENSITIVITY" in str(call)
        ]
        assert len(warning_calls) > 0

        # Verify turn_detection='MEDIUM' was used as default
        call_kwargs = mock_realtime_model.with_nova_sonic_2.call_args[1]
        assert call_kwargs["turn_detection"] == "MEDIUM"

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_tool_choice_auto_is_preserved(self, mock_realtime_model):
        """Test that tool_choice='auto' is configured for MCP integration."""
        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify tool_choice='auto' was passed
        call_kwargs = mock_realtime_model.with_nova_sonic_2.call_args[1]
        assert call_kwargs["tool_choice"] == "auto"

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_default_sensitivity_is_medium(self, mock_realtime_model):
        """Test that default sensitivity is MEDIUM when not specified."""
        # Don't set ENDPOINTING_SENSITIVITY environment variable

        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify turn_detection='MEDIUM' was used as default
        call_kwargs = mock_realtime_model.with_nova_sonic_2.call_args[1]
        assert call_kwargs["turn_detection"] == "MEDIUM"

    @pytest.mark.asyncio
    @patch("virtual_assistant_livekit.agent.RealtimeModel")
    async def test_temperature_from_environment(self, mock_realtime_model):
        """Test that temperature is read from MODEL_TEMPERATURE environment variable."""
        # Set environment variable
        os.environ["MODEL_TEMPERATURE"] = "0.5"

        # Mock the with_nova_sonic_2 factory method
        mock_model = MagicMock()
        mock_realtime_model.with_nova_sonic_2 = MagicMock(return_value=mock_model)

        # Run entrypoint
        await self._run_entrypoint_with_mocks(mock_realtime_model)

        # Verify temperature=0.5 was passed
        call_kwargs = mock_realtime_model.with_nova_sonic_2.call_args[1]
        assert call_kwargs["temperature"] == 0.5
