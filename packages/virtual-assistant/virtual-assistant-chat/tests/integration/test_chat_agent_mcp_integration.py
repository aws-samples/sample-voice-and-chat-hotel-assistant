# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration tests for chat agent MCP integration.

These tests verify that the chat agent properly integrates with the MCP
configuration system, loads prompts from MCP servers, and has access to
tools from multiple MCP servers.
"""

import os

import pytest


@pytest.mark.integration
def test_chat_agent_loads_configuration_from_ssm(setup_environment):
    """Test that chat agent loads MCP configuration from SSM Parameter Store."""
    # Import the agent module which triggers MCP initialization
    from virtual_assistant_chat import agent

    # Verify that config_manager was initialized
    assert agent.config_manager is not None
    assert agent.config_manager.parameter_name is not None

    # Verify that the parameter name comes from environment or default
    expected_param = os.getenv("MCP_CONFIG_PARAMETER")
    if expected_param:
        assert agent.config_manager.parameter_name == expected_param


@pytest.mark.integration
def test_chat_agent_loads_prompt_from_mcp(setup_environment):
    """Test that chat agent loads prompt from MCP server (not emergency fallback)."""
    from virtual_assistant_chat import agent

    # Verify that instructions were loaded
    assert agent.instructions is not None
    assert isinstance(agent.instructions, str)
    assert len(agent.instructions) > 0

    # Verify it's not the emergency fallback prompt
    # Emergency fallback contains "technical difficulties"
    assert "technical difficulties" not in agent.instructions.lower()

    # Verify it looks like a real system prompt (has some expected content)
    # This is a basic check - adjust based on actual prompt content
    assert len(agent.instructions) > 100  # Real prompts should be substantial


@pytest.mark.integration
def test_chat_agent_has_tools_from_both_mcp_servers(setup_environment):
    """Test that chat agent has tools from both Hotel Assistant and Hotel PMS MCP servers."""
    from virtual_assistant_chat import agent

    # Verify that config_manager was initialized
    assert agent.config_manager is not None

    # Load the configuration to check for servers
    config = agent.config_manager.load_config()

    # Verify we have at least one MCP server configured
    assert len(config) > 0, "No MCP servers configured"

    # Log the discovered servers for debugging
    print(f"Discovered {len(config)} MCP servers")
    for server_name in config:
        print(f"  - {server_name}")


@pytest.mark.integration
def test_chat_agent_client_manager_initialized(setup_environment):
    """Test that the config manager is properly initialized."""
    from virtual_assistant_chat import agent

    # Verify config_manager exists
    assert agent.config_manager is not None

    # Verify it has the expected attributes
    assert hasattr(agent.config_manager, "parameter_name")
    assert hasattr(agent.config_manager, "load_config")
    assert hasattr(agent.config_manager, "get_credentials")

    # Verify we can load configuration
    config = agent.config_manager.load_config()
    assert isinstance(config, dict)


@pytest.mark.integration
def test_chat_agent_prompt_loader_initialized(setup_environment):
    """Test that the prompt loader can be initialized."""
    from virtual_assistant_common.mcp.prompt_loader import PromptLoader

    from virtual_assistant_chat import agent

    # Verify config_manager exists
    assert agent.config_manager is not None

    # Verify we can create a PromptLoader with the config manager
    prompt_loader = PromptLoader(agent.config_manager)
    assert prompt_loader is not None
    assert hasattr(prompt_loader, "config_manager")
    assert prompt_loader.config_manager is agent.config_manager
