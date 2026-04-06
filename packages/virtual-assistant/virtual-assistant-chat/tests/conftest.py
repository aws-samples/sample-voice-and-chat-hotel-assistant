#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Shared test configuration and fixtures for virtual-assistant-chat tests.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_mcp_environment():
    """Mock MCP environment variables and configuration for testing."""
    with (
        patch.dict(
            os.environ,
            {
                # Valid format: [a-zA-Z][a-zA-Z0-9-_]{0,99}-[a-zA-Z0-9]{10}
                "AGENTCORE_MEMORY_ID": "testMemory-1234567890",
                "AWS_REGION": "us-east-1",
                "MCP_CONFIG_PARAMETER": "/test/mcp/config",
            },
        ),
        patch("virtual_assistant_common.mcp.config_manager.MCPConfigManager.load_config") as mock_load_config,
        patch("virtual_assistant_common.mcp.prompt_loader.PromptLoader.load_prompt") as mock_load_prompt,
        patch("strands.tools.mcp.MCPClient") as mock_mcp_client_class,
        patch(
            "bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager"
        ) as mock_session_manager_class,
    ):
        # Mock load_config to return empty dict (no MCP servers)
        mock_load_config.return_value = {}

        # Mock load_prompt to return test prompt
        mock_load_prompt.return_value = "Test system prompt for chat assistant"

        # Mock Strands MCPClient
        mock_mcp_client = MagicMock()
        mock_mcp_client.__aenter__ = AsyncMock(return_value=mock_mcp_client)
        mock_mcp_client.__aexit__ = AsyncMock(return_value=None)
        mock_mcp_client_class.return_value = mock_mcp_client

        # Mock the session manager to avoid AgentCore Memory validation
        mock_session_manager = MagicMock()
        mock_session_manager_class.return_value = mock_session_manager

        # Clear module cache to force re-import with mocked MCP
        if "virtual_assistant_chat.agent" in sys.modules:
            del sys.modules["virtual_assistant_chat.agent"]

        yield {
            "mock_load_config": mock_load_config,
            "mock_load_prompt": mock_load_prompt,
            "mock_mcp_client": mock_mcp_client,
            "mock_mcp_client_class": mock_mcp_client_class,
            "mock_session_manager": mock_session_manager,
            "mock_session_manager_class": mock_session_manager_class,
        }


@pytest.fixture
def mock_agent_module(mock_mcp_environment):
    """Import the agent module with proper MCP mocking."""
    import virtual_assistant_chat.agent

    return virtual_assistant_chat.agent
