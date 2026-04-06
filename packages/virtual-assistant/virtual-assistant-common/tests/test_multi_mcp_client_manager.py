# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for MultiMCPClientManager.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from virtual_assistant_common.mcp.multi_client_manager import MultiMCPClientManager

from virtual_assistant_common.mcp.config_manager import (
    MCPAuthenticationConfig,
    MCPConfigManager,
    MCPServerConfig,
    MCPSystemPromptsConfig,
)


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    manager = MagicMock(spec=MCPConfigManager)

    # Mock server configurations
    server1 = MCPServerConfig(
        name="server1",
        type="streamable-http",
        url="https://server1.example.com",
        headers=None,
        authentication=MCPAuthenticationConfig(
            type="cognito", secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:server1"
        ),
        system_prompts=MCPSystemPromptsConfig(chat="chat_prompt", voice="voice_prompt"),
    )

    server2 = MCPServerConfig(
        name="server2",
        type="streamable-http",
        url="https://server2.example.com",
        headers={"X-Custom": "value"},
        authentication=MCPAuthenticationConfig(
            type="cognito", secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:server2"
        ),
        system_prompts=None,
    )

    manager.load_config.return_value = {"server1": server1, "server2": server2}

    # Mock credentials
    manager.get_credentials.return_value = {
        "userPoolId": "us-east-1_test",
        "clientId": "test-client",
        "clientSecret": "test-secret",
        "region": "us-east-1",
    }

    return manager


@pytest.fixture
def mock_tool():
    """Mock MCP tool."""
    tool = MagicMock()
    tool.name = "test_tool"
    return tool


@pytest.fixture
def mock_tools_list(mock_tool):
    """Mock tools list response."""
    tools_list = MagicMock()
    tools_list.tools = [mock_tool]
    return tools_list


@pytest.fixture
def mock_session(mock_tools_list):
    """Mock MCP client session."""
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=mock_tools_list)
    return session


class TestMultiMCPClientManagerInit:
    """Tests for MultiMCPClientManager initialization."""

    def test_init(self, mock_config_manager):
        """Test initialization."""
        manager = MultiMCPClientManager(mock_config_manager)

        assert manager.config_manager is mock_config_manager
        assert manager.clients == {}
        assert manager.tools == {}
        assert manager.unavailable_servers == set()


class TestMultiMCPClientManagerInitialize:
    """Tests for initialize method."""

    @pytest.mark.asyncio
    @patch("virtual_assistant_common.mcp.multi_client_manager.cognito_mcp_client")
    @patch("virtual_assistant_common.mcp.multi_client_manager.ClientSession")
    async def test_initialize_success(
        self, mock_client_session_class, mock_cognito_client, mock_config_manager, mock_session
    ):
        """Test successful initialization with multiple servers."""
        # Mock cognito_mcp_client context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_cognito_client.return_value = mock_context

        # Mock ClientSession
        mock_client_session_class.return_value = mock_session

        manager = MultiMCPClientManager(mock_config_manager)
        await manager.initialize()

        # Verify connections were attempted for both servers
        assert mock_cognito_client.call_count == 2
        assert len(manager.clients) == 2
        assert "server1" in manager.clients
        assert "server2" in manager.clients
        assert len(manager.unavailable_servers) == 0

    @pytest.mark.asyncio
    @patch("virtual_assistant_common.mcp.multi_client_manager.cognito_mcp_client")
    @patch("virtual_assistant_common.mcp.multi_client_manager.ClientSession")
    async def test_initialize_with_connection_failure(
        self, mock_client_session_class, mock_cognito_client, mock_config_manager, mock_session
    ):
        """Test graceful handling of server connection failures."""

        # First server succeeds, second fails
        def cognito_client_side_effect(*args, **kwargs):
            if kwargs.get("url") == "https://server1.example.com":
                mock_context = AsyncMock()
                mock_context.__aenter__.return_value = (MagicMock(), MagicMock(), MagicMock())
                return mock_context
            else:
                raise ConnectionError("Connection failed")

        mock_cognito_client.side_effect = cognito_client_side_effect
        mock_client_session_class.return_value = mock_session

        manager = MultiMCPClientManager(mock_config_manager)
        await manager.initialize()

        # Verify one server connected, one failed
        assert len(manager.clients) == 1
        assert "server1" in manager.clients
        assert "server2" in manager.unavailable_servers

    @pytest.mark.asyncio
    @patch("virtual_assistant_common.mcp.multi_client_manager.cognito_mcp_client")
    async def test_initialize_all_servers_fail(self, mock_cognito_client, mock_config_manager):
        """Test error when all servers fail to connect."""
        mock_cognito_client.side_effect = ConnectionError("Connection failed")

        manager = MultiMCPClientManager(mock_config_manager)

        with pytest.raises(RuntimeError, match="Failed to connect to any MCP servers"):
            await manager.initialize()


class TestMultiMCPClientManagerDiscoverTools:
    """Tests for _discover_tools method."""

    @pytest.mark.asyncio
    async def test_discover_tools_no_conflict(self, mock_config_manager, mock_session, mock_tool):
        """Test tool discovery without name conflicts."""
        manager = MultiMCPClientManager(mock_config_manager)
        await manager._discover_tools("server1", mock_session)

        assert "test_tool" in manager.tools
        assert manager.tools["test_tool"]["server"] == "server1"
        assert manager.tools["test_tool"]["tool"] == mock_tool

    @pytest.mark.asyncio
    async def test_discover_tools_with_conflict(self, mock_config_manager, mock_session, mock_tool):
        """Test tool discovery with name conflicts."""
        manager = MultiMCPClientManager(mock_config_manager)

        # Add tool from first server
        await manager._discover_tools("server1", mock_session)
        assert manager.tools["test_tool"]["server"] == "server1"

        # Add same tool from second server (should create prefixed name)
        await manager._discover_tools("server2", mock_session)
        assert manager.tools["test_tool"]["server"] == "server1"  # Original unchanged
        assert "server2__test_tool" in manager.tools
        assert manager.tools["server2__test_tool"]["server"] == "server2"
        # Tool name should be updated
        assert manager.tools["server2__test_tool"]["tool"].name == "server2__test_tool"

    @pytest.mark.asyncio
    async def test_discover_tools_failure(self, mock_config_manager):
        """Test handling of tool discovery failure."""
        mock_session = AsyncMock()
        mock_session.list_tools.side_effect = Exception("Discovery failed")

        manager = MultiMCPClientManager(mock_config_manager)
        # Should not raise, just log error
        await manager._discover_tools("server1", mock_session)

        assert len(manager.tools) == 0


class TestMultiMCPClientManagerGetMCPClients:
    """Tests for get_mcp_clients method."""

    def test_get_mcp_clients(self, mock_config_manager, mock_session):
        """Test getting MCP client sessions."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session, "server2": mock_session}

        clients = manager.get_mcp_clients()

        assert len(clients) == 2
        assert "server1" in clients
        assert "server2" in clients

    def test_get_mcp_clients_excludes_unavailable(self, mock_config_manager, mock_session):
        """Test that unavailable servers are excluded."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session, "server2": mock_session}
        manager.unavailable_servers.add("server2")

        clients = manager.get_mcp_clients()

        assert len(clients) == 1
        assert "server1" in clients
        assert "server2" not in clients


class TestMultiMCPClientManagerGetToolsForStrands:
    """Tests for get_tools_for_strands method."""

    def test_get_tools_for_strands(self, mock_config_manager, mock_session, mock_tool):
        """Test getting tools for Strands."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session}

        tool1 = MagicMock()
        tool1.name = "tool1"
        tool2 = MagicMock()
        tool2.name = "tool2"

        manager.tools = {"tool1": {"server": "server1", "tool": tool1}, "tool2": {"server": "server1", "tool": tool2}}

        tools = manager.get_tools_for_strands()

        assert len(tools) == 2
        assert tool1 in tools
        assert tool2 in tools

    def test_get_tools_for_strands_excludes_unavailable(self, mock_config_manager, mock_session):
        """Test that tools from unavailable servers are excluded."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session, "server2": mock_session}

        tool1 = MagicMock()
        tool1.name = "tool1"
        tool2 = MagicMock()
        tool2.name = "tool2"

        manager.tools = {"tool1": {"server": "server1", "tool": tool1}, "tool2": {"server": "server2", "tool": tool2}}
        manager.unavailable_servers.add("server2")

        tools = manager.get_tools_for_strands()

        assert len(tools) == 1
        assert tool1 in tools
        assert tool2 not in tools


class TestMultiMCPClientManagerGetPrompt:
    """Tests for get_prompt method."""

    @pytest.mark.asyncio
    async def test_get_prompt_with_server_name(self, mock_config_manager, mock_session):
        """Test getting prompt from specific server."""
        mock_prompt = MagicMock()
        mock_prompt.messages = [MagicMock()]
        mock_prompt.messages[0].content.text = "Test prompt"
        mock_session.get_prompt = AsyncMock(return_value=mock_prompt)

        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session}

        prompt = await manager.get_prompt("test_prompt", "server1")

        assert prompt == "Test prompt"
        mock_session.get_prompt.assert_called_once_with("test_prompt")

    @pytest.mark.asyncio
    async def test_get_prompt_auto_detect_server(self, mock_config_manager, mock_session):
        """Test getting prompt with auto-detection of prompt server."""
        mock_config_manager.find_prompt_server.return_value = "server1"

        mock_prompt = MagicMock()
        mock_prompt.messages = [MagicMock()]
        mock_prompt.messages[0].content.text = "Test prompt"
        mock_session.get_prompt = AsyncMock(return_value=mock_prompt)

        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session}

        prompt = await manager.get_prompt("test_prompt")

        assert prompt == "Test prompt"
        mock_config_manager.find_prompt_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_prompt_no_prompt_server(self, mock_config_manager):
        """Test error when no prompt server is configured."""
        mock_config_manager.find_prompt_server.return_value = None

        manager = MultiMCPClientManager(mock_config_manager)

        with pytest.raises(ValueError, match="No MCP server configured with systemPrompts"):
            await manager.get_prompt("test_prompt")

    @pytest.mark.asyncio
    async def test_get_prompt_unknown_server(self, mock_config_manager):
        """Test error when server is not found."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {}

        with pytest.raises(ValueError, match="Unknown MCP server: unknown"):
            await manager.get_prompt("test_prompt", "unknown")

    @pytest.mark.asyncio
    async def test_get_prompt_unavailable_server(self, mock_config_manager, mock_session):
        """Test error when server is unavailable."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.clients = {"server1": mock_session}
        manager.unavailable_servers.add("server1")

        with pytest.raises(RuntimeError, match="MCP server server1 is unavailable"):
            await manager.get_prompt("test_prompt", "server1")


class TestMultiMCPClientManagerGetAllTools:
    """Tests for get_all_tools method."""

    def test_get_all_tools(self, mock_config_manager):
        """Test getting all tool names."""
        manager = MultiMCPClientManager(mock_config_manager)
        manager.tools = {
            "tool1": {"server": "server1", "tool": MagicMock()},
            "tool2": {"server": "server2", "tool": MagicMock()},
            "tool3": {"server": "server1", "tool": MagicMock()},
        }

        tools = manager.get_all_tools()

        assert len(tools) == 3
        assert "tool1" in tools
        assert "tool2" in tools
        assert "tool3" in tools
