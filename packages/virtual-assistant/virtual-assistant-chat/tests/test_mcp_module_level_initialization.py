#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestAgentConfiguration:
    """Test suite for agent configuration validation."""

    def test_validate_configuration_success(self, mock_agent_module):
        """Test successful configuration validation."""
        # Act
        memory_id, aws_region = mock_agent_module.validate_configuration()

        # Assert
        assert memory_id == "testMemory-1234567890"
        assert aws_region == "us-east-1"

    def test_validate_configuration_missing_memory_id(self):
        """Test configuration validation with missing AGENTCORE_MEMORY_ID."""
        with (
            patch.dict(os.environ, {"AWS_REGION": "us-east-1", "MCP_CONFIG_PARAMETER": "/test/mcp/config"}, clear=True),
            patch("virtual_assistant_common.mcp.config_manager.MCPConfigManager.load_config") as mock_load_config,
            patch("virtual_assistant_common.mcp.prompt_loader.PromptLoader.load_prompt") as mock_load_prompt,
            patch("boto3.client"),  # Mock boto3 client creation
        ):
            # Mock load_config and load_prompt
            mock_load_config.return_value = {}
            mock_load_prompt.return_value = "Test prompt"

            # Remove module from cache to force re-import
            if "virtual_assistant_chat.agent" in sys.modules:
                del sys.modules["virtual_assistant_chat.agent"]

            import virtual_assistant_chat.agent

            with pytest.raises(ValueError, match="AGENTCORE_MEMORY_ID environment variable is required"):
                virtual_assistant_chat.agent.validate_configuration()

    def test_validate_configuration_missing_aws_region(self):
        """Test configuration validation with missing AWS_REGION."""
        with (
            patch.dict(
                os.environ,
                {"AGENTCORE_MEMORY_ID": "testMemory-1234567890", "MCP_CONFIG_PARAMETER": "/test/mcp/config"},
                clear=True,
            ),
            patch("virtual_assistant_common.mcp.config_manager.MCPConfigManager.load_config") as mock_load_config,
            patch("virtual_assistant_common.mcp.prompt_loader.PromptLoader.load_prompt") as mock_load_prompt,
            patch("boto3.client"),  # Mock boto3 client creation
        ):
            # Mock load_config and load_prompt
            mock_load_config.return_value = {}
            mock_load_prompt.return_value = "Test prompt"

            # Remove module from cache to force re-import
            if "virtual_assistant_chat.agent" in sys.modules:
                del sys.modules["virtual_assistant_chat.agent"]

            import virtual_assistant_chat.agent

            with pytest.raises(ValueError, match="AWS_REGION environment variable is required"):
                virtual_assistant_chat.agent.validate_configuration()

    def test_create_session_manager_success(self, mock_agent_module):
        """Test successful SessionManager creation."""
        with (
            patch("virtual_assistant_chat.agent.AgentCoreMemorySessionManager") as mock_session_manager_class,
            patch("virtual_assistant_chat.agent.AgentCoreMemoryConfig") as mock_config_class,
        ):
            # Arrange
            mock_session_manager = MagicMock()
            mock_session_manager_class.return_value = mock_session_manager
            mock_config = MagicMock()
            mock_config_class.return_value = mock_config

            # Act
            result = mock_agent_module.create_session_manager("test-session", "test-actor")

            # Assert
            assert result is mock_session_manager
            mock_config_class.assert_called_once_with(
                memory_id="testMemory-1234567890",
                session_id="test-session",
                actor_id="test-actor",
            )
            mock_session_manager_class.assert_called_once_with(
                agentcore_memory_config=mock_config,
                region_name="us-east-1",
            )


class TestModuleLevelInitialization:
    """Test suite for module-level initialization."""

    def test_module_initialization_loads_prompt(self, mock_agent_module):
        """Test that module loads system prompt at initialization."""
        # Assert that instructions were loaded
        assert hasattr(mock_agent_module, "instructions")
        assert mock_agent_module.instructions == "Test system prompt for chat assistant"

    def test_module_initialization_creates_config_manager(self, mock_agent_module):
        """Test that module creates MCPConfigManager at initialization."""
        # Assert that config_manager exists
        assert hasattr(mock_agent_module, "config_manager")
        assert mock_agent_module.config_manager is not None

    def test_module_initialization_with_app(self, mock_agent_module):
        """Test that module creates BedrockAgentCoreApp."""
        # Assert that app exists
        assert hasattr(mock_agent_module, "app")
        assert mock_agent_module.app is not None
