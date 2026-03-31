# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for PromptLoader.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from virtual_assistant_common.mcp.multi_client_manager import MultiMCPClientManager

from virtual_assistant_common.mcp.config_manager import (
    MCPAuthenticationConfig,
    MCPConfigManager,
    MCPServerConfig,
    MCPSystemPromptsConfig,
)
from virtual_assistant_common.mcp.prompt_loader import AssistantType, PromptLoader


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    manager = MagicMock(spec=MCPConfigManager)

    # Mock server with systemPrompts
    server_config = MCPServerConfig(
        name="prompt-server",
        type="streamable-http",
        url="https://prompt-server.example.com",
        headers=None,
        authentication=MCPAuthenticationConfig(
            type="cognito", secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test"
        ),
        system_prompts=MCPSystemPromptsConfig(chat="custom_chat_prompt", voice="custom_voice_prompt"),
    )

    manager.load_config.return_value = {"prompt-server": server_config}
    manager.find_prompt_server.return_value = "prompt-server"

    return manager


@pytest.fixture
def mock_client_manager():
    """Mock multi-client manager."""
    manager = AsyncMock(spec=MultiMCPClientManager)
    return manager


class TestPromptLoaderInit:
    """Tests for PromptLoader initialization."""

    def test_init(self, mock_client_manager, mock_config_manager):
        """Test initialization."""
        loader = PromptLoader(mock_client_manager, mock_config_manager)

        assert loader.client_manager is mock_client_manager
        assert loader.config_manager is mock_config_manager


class TestPromptLoaderLoadPrompt:
    """Tests for load_prompt method."""

    @pytest.mark.asyncio
    async def test_load_prompt_chat_custom_success(self, mock_client_manager, mock_config_manager):
        """Test successful loading of custom chat prompt."""
        mock_client_manager.get_prompt = AsyncMock(return_value="Custom chat prompt text")

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.CHAT)

        assert prompt == "Custom chat prompt text"
        mock_client_manager.get_prompt.assert_called_once_with("custom_chat_prompt", "prompt-server")

    @pytest.mark.asyncio
    async def test_load_prompt_voice_custom_success(self, mock_client_manager, mock_config_manager):
        """Test successful loading of custom voice prompt."""
        mock_client_manager.get_prompt = AsyncMock(return_value="Custom voice prompt text")

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.VOICE)

        assert prompt == "Custom voice prompt text"
        mock_client_manager.get_prompt.assert_called_once_with("custom_voice_prompt", "prompt-server")

    @pytest.mark.asyncio
    async def test_load_prompt_fallback_to_default(self, mock_client_manager, mock_config_manager):
        """Test fallback to default prompt name when custom fails."""

        # First call (custom) fails, second call (default) succeeds
        async def get_prompt_side_effect(prompt_name, server_name):
            if prompt_name == "custom_chat_prompt":
                raise Exception("Custom prompt not found")
            elif prompt_name == "chat_system_prompt":
                return "Default chat prompt text"
            else:
                raise Exception("Prompt not found")

        mock_client_manager.get_prompt = AsyncMock(side_effect=get_prompt_side_effect)

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.CHAT)

        assert prompt == "Default chat prompt text"
        assert mock_client_manager.get_prompt.call_count == 2

    @pytest.mark.asyncio
    async def test_load_prompt_fallback_to_generic_default(self, mock_client_manager, mock_config_manager):
        """Test fallback to generic default_system_prompt."""

        # First two calls fail, third succeeds
        async def get_prompt_side_effect(prompt_name, server_name):
            if prompt_name in ["custom_chat_prompt", "chat_system_prompt"]:
                raise Exception("Prompt not found")
            elif prompt_name == "default_system_prompt":
                return "Generic default prompt text"
            else:
                raise Exception("Prompt not found")

        mock_client_manager.get_prompt = AsyncMock(side_effect=get_prompt_side_effect)

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.CHAT)

        assert prompt == "Generic default prompt text"
        assert mock_client_manager.get_prompt.call_count == 3

    @pytest.mark.asyncio
    async def test_load_prompt_all_fail_emergency_fallback_chat(self, mock_client_manager, mock_config_manager):
        """Test emergency fallback for chat when all MCP attempts fail."""
        mock_client_manager.get_prompt = AsyncMock(side_effect=Exception("All prompts failed"))

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.CHAT)

        assert "technical difficulties" in prompt
        assert "try again" in prompt

    @pytest.mark.asyncio
    async def test_load_prompt_all_fail_emergency_fallback_voice(self, mock_client_manager, mock_config_manager):
        """Test emergency fallback for voice when all MCP attempts fail."""
        mock_client_manager.get_prompt = AsyncMock(side_effect=Exception("All prompts failed"))

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.VOICE)

        assert "technical difficulties" in prompt
        # Voice prompt should be shorter
        assert len(prompt) < 200

    @pytest.mark.asyncio
    async def test_load_prompt_no_prompt_server(self, mock_client_manager, mock_config_manager):
        """Test emergency fallback when no prompt server is configured."""
        mock_config_manager.find_prompt_server.return_value = None

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.CHAT)

        assert "technical difficulties" in prompt
        # Should not attempt to get prompt from MCP
        mock_client_manager.get_prompt.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_prompt_no_custom_prompt_configured(self, mock_client_manager, mock_config_manager):
        """Test loading when no custom prompt is configured in systemPrompts."""
        # Server without custom prompts for this assistant type
        server_config = MCPServerConfig(
            name="prompt-server",
            type="streamable-http",
            url="https://prompt-server.example.com",
            headers=None,
            authentication=MCPAuthenticationConfig(
                type="cognito", secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:test"
            ),
            system_prompts=MCPSystemPromptsConfig(voice="custom_voice_prompt"),  # Only voice, no chat
        )

        mock_config_manager.load_config.return_value = {"prompt-server": server_config}
        mock_client_manager.get_prompt = AsyncMock(return_value="Default chat prompt")

        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = await loader.load_prompt(AssistantType.CHAT)

        assert prompt == "Default chat prompt"
        # Should skip custom and go straight to default
        mock_client_manager.get_prompt.assert_called_once_with("chat_system_prompt", "prompt-server")


class TestPromptLoaderEmergencyFallback:
    """Tests for _get_emergency_fallback method."""

    def test_emergency_fallback_chat(self, mock_client_manager, mock_config_manager):
        """Test emergency fallback message for chat."""
        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = loader._get_emergency_fallback(AssistantType.CHAT)

        assert "technical difficulties" in prompt
        assert "try again" in prompt
        assert isinstance(prompt, str)

    def test_emergency_fallback_voice(self, mock_client_manager, mock_config_manager):
        """Test emergency fallback message for voice."""
        loader = PromptLoader(mock_client_manager, mock_config_manager)
        prompt = loader._get_emergency_fallback(AssistantType.VOICE)

        assert "technical difficulties" in prompt
        assert isinstance(prompt, str)
        # Voice should be more concise
        assert len(prompt) < len(loader._get_emergency_fallback(AssistantType.CHAT))
