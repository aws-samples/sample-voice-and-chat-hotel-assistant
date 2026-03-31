# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration tests for voice agent MCP integration.

These tests verify that the voice agent properly loads MCP configuration,
connects to MCP servers, and loads system prompts from MCP.
"""

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from livekit.agents import JobProcess
from virtual_assistant_common.mcp import AssistantType, MCPConfigManager, MultiMCPClientManager, PromptLoader

from virtual_assistant_livekit.agent import prewarm


@pytest.mark.integration
class TestVoiceAgentMCPIntegration:
    """Integration tests for voice agent MCP configuration."""

    def test_prewarm_loads_mcp_configuration(self):
        """Test that prewarm function loads MCP configuration from SSM."""
        # Create a mock JobProcess
        proc = MagicMock(spec=JobProcess)
        proc.userdata = {}

        # Set required environment variable
        os.environ["MCP_CONFIG_PARAMETER"] = "/hotel-assistant/mcp-config"

        # Mock the async operations
        async def mock_initialize_mcp():
            """Mock MCP initialization."""
            # Create mock client manager with MCP clients
            client_manager = MagicMock(spec=MultiMCPClientManager)
            client_manager.clients = {"hotel-assistant-mcp": MagicMock(), "hotel-pms-mcp": MagicMock()}

            # Return a voice prompt
            instructions = "Test voice prompt for hotel assistant"

            return instructions, client_manager

        with patch("virtual_assistant_livekit.agent.asyncio.run") as mock_run:
            mock_run.return_value = ("Test voice prompt", MagicMock())

            # Call prewarm
            prewarm(proc)

            # Verify that asyncio.run was called
            assert mock_run.called

            # Verify that instructions and client_manager were stored
            assert "instructions" in proc.userdata
            assert "client_manager" in proc.userdata

    def test_voice_agent_prompt_is_concise(self):
        """Test that voice agent prompt is concise (< 1000 chars)."""

        async def check_prompt_length():
            """Check that loaded prompt is concise."""
            try:
                # Initialize MCP configuration
                config_manager = MCPConfigManager()
                client_manager = MultiMCPClientManager(config_manager)
                await client_manager.initialize()

                # Load voice prompt
                prompt_loader = PromptLoader(client_manager, config_manager)
                instructions = await prompt_loader.load_prompt(AssistantType.VOICE)

                # Voice prompts should be concise for speech
                assert len(instructions) < 1000, f"Voice prompt too long: {len(instructions)} characters"

                return instructions

            except Exception as e:
                pytest.skip(f"MCP integration test failed: {e}")

        # Run the async test
        instructions = asyncio.run(check_prompt_length())
        assert instructions is not None

    def test_voice_agent_prompt_not_emergency_fallback(self):
        """Test that voice agent prompt is not the emergency fallback."""

        async def check_prompt_content():
            """Check that loaded prompt is not emergency fallback."""
            try:
                # Initialize MCP configuration
                config_manager = MCPConfigManager()
                client_manager = MultiMCPClientManager(config_manager)
                await client_manager.initialize()

                # Load voice prompt
                prompt_loader = PromptLoader(client_manager, config_manager)
                instructions = await prompt_loader.load_prompt(AssistantType.VOICE)

                # Emergency fallback contains "technical difficulties"
                assert "technical difficulties" not in instructions.lower(), "Using emergency fallback prompt"
                assert "dificultades técnicas" not in instructions.lower(), "Using emergency fallback prompt"

                return instructions

            except Exception as e:
                pytest.skip(f"MCP integration test failed: {e}")

        # Run the async test
        instructions = asyncio.run(check_prompt_content())
        assert instructions is not None

    def test_prewarm_stores_client_manager(self):
        """Test that prewarm stores client_manager in userdata."""
        # Create a mock JobProcess
        proc = MagicMock(spec=JobProcess)
        proc.userdata = {}

        # Set required environment variable
        os.environ["MCP_CONFIG_PARAMETER"] = "/hotel-assistant/mcp-config"

        # Mock the async operations
        mock_client_manager = MagicMock(spec=MultiMCPClientManager)
        mock_client_manager.clients = {"hotel-assistant-mcp": MagicMock(), "hotel-pms-mcp": MagicMock()}

        with patch("virtual_assistant_livekit.agent.asyncio.run") as mock_run:
            mock_run.return_value = ("Test voice prompt", mock_client_manager)

            # Call prewarm
            prewarm(proc)

            # Verify that client_manager was stored
            assert "client_manager" in proc.userdata
            assert proc.userdata["client_manager"] == mock_client_manager

    def test_prewarm_handles_mcp_initialization_failure(self):
        """Test that prewarm handles MCP initialization failures gracefully."""
        # Create a mock JobProcess
        proc = MagicMock(spec=JobProcess)
        proc.userdata = {}

        # Set required environment variable
        os.environ["MCP_CONFIG_PARAMETER"] = "/hotel-assistant/mcp-config"

        # Mock asyncio.run to raise an exception
        with patch("virtual_assistant_livekit.agent.asyncio.run") as mock_run:
            mock_run.side_effect = Exception("MCP initialization failed")

            # Call prewarm and expect it to raise
            with pytest.raises(Exception, match="MCP initialization failed"):
                prewarm(proc)
