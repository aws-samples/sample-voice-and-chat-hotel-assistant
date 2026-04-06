# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for virtual_assistant_chat.agent_factory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from virtual_assistant_chat.agent_factory import (
    AgentFactory,
    AgentFactoryError,
    MCPConfigurationError,
    SystemPromptError,
)

MOCK_SYSTEM_PROMPT = (
    "You are a helpful hotel assistant for Paraiso Hotels & Resorts. "
    "You help guests with reservations, room information, amenities, and general inquiries. "
    "Always respond in a friendly and professional manner. "
    "Use <message> tags to wrap your responses to the user."
)


@pytest.fixture
def mock_server_config():
    config = MagicMock()
    config.url = "https://mcp-server.example.com"
    config.headers = {"X-Custom-Header": "value"}
    config.authentication = MagicMock()
    config.authentication.secret_arn = "arn:aws:secretsmanager:us-east-1:123:secret:test"
    return config


@pytest.fixture
def mock_credentials():
    return {
        "userPoolId": "us-east-1_test123",
        "clientId": "test-client-id",
        "clientSecret": "test-client-secret",
        "region": "us-east-1",
    }


@pytest.fixture
def mock_config_manager(mock_server_config, mock_credentials):
    manager = MagicMock()
    manager.load_config.return_value = {"hotel-assistant-mcp": mock_server_config}
    manager.get_credentials.return_value = mock_credentials
    return manager


class TestAgentFactoryInit:
    def test_init_sets_defaults(self, mock_config_manager):
        factory = AgentFactory(mock_config_manager)
        assert factory.config_manager is mock_config_manager
        assert factory.system_prompt is None
        assert factory._mcp_clients == []
        assert factory.is_initialized is False


class TestAgentFactoryInitialize:
    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_success(self, mock_prompt_loader_cls, mock_config_manager):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader

        factory = AgentFactory(mock_config_manager)

        with patch("virtual_assistant_chat.agent_factory.MCPClient") as mock_mcp_cls:
            mock_mcp_cls.return_value = MagicMock()
            await factory.initialize()

        assert factory.is_initialized is True
        assert factory.system_prompt == MOCK_SYSTEM_PROMPT
        assert len(factory._mcp_clients) == 1

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_no_servers(self, mock_prompt_loader_cls, mock_config_manager):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_config_manager.load_config.return_value = {}

        factory = AgentFactory(mock_config_manager)

        with pytest.raises(MCPConfigurationError, match="No MCP servers found"):
            await factory.initialize()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_invalid_prompt(self, mock_prompt_loader_cls, mock_config_manager):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value="Short")
        mock_prompt_loader_cls.return_value = mock_loader

        factory = AgentFactory(mock_config_manager)

        with pytest.raises(SystemPromptError, match="System prompt appears invalid"):
            await factory.initialize()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_no_auth_server(self, mock_prompt_loader_cls, mock_config_manager, mock_server_config):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_server_config.authentication = None
        mock_config_manager.load_config.return_value = {"server": mock_server_config}

        factory = AgentFactory(mock_config_manager)

        with pytest.raises(MCPConfigurationError, match="No MCP clients could be created"):
            await factory.initialize()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_config_load_failure(self, mock_prompt_loader_cls, mock_config_manager):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_config_manager.load_config.side_effect = RuntimeError("SSM error")

        factory = AgentFactory(mock_config_manager)

        with pytest.raises(MCPConfigurationError, match="Failed to initialize AgentFactory"):
            await factory.initialize()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_prompt_loader_failure(self, mock_prompt_loader_cls, mock_config_manager):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(side_effect=RuntimeError("MCP connection failed"))
        mock_prompt_loader_cls.return_value = mock_loader

        factory = AgentFactory(mock_config_manager)

        with pytest.raises(MCPConfigurationError, match="Failed to initialize AgentFactory"):
            await factory.initialize()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    async def test_initialize_credentials_failure(self, mock_prompt_loader_cls, mock_config_manager):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_config_manager.get_credentials.side_effect = RuntimeError("Secrets Manager error")

        factory = AgentFactory(mock_config_manager)

        with (
            patch("virtual_assistant_chat.agent_factory.MCPClient"),
            pytest.raises(MCPConfigurationError, match="No MCP clients could be created"),
        ):
            await factory.initialize()


class TestAgentFactoryCreateAgent:
    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    @patch("virtual_assistant_chat.agent_factory.get_bedrock_boto_session")
    @patch("virtual_assistant_chat.agent_factory.BedrockModel")
    @patch("virtual_assistant_chat.agent_factory.Agent")
    async def test_create_agent_success(
        self, mock_agent_cls, mock_model_cls, mock_get_session, mock_prompt_loader_cls, mock_config_manager
    ):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_get_session.return_value = MagicMock()
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model
        mock_agent = MagicMock()
        mock_agent_cls.return_value = mock_agent

        factory = AgentFactory(mock_config_manager)

        with patch("virtual_assistant_chat.agent_factory.MCPClient") as mock_mcp_cls:
            mock_mcp_client = MagicMock()
            mock_mcp_cls.return_value = mock_mcp_client
            await factory.initialize()

            agent = factory.create_agent("us.amazon.nova-lite-v1:0")

        assert agent is mock_agent
        mock_get_session.assert_called_once_with(region="us-east-1")
        mock_model_cls.assert_called_once_with(model_id="us.amazon.nova-lite-v1:0", boto_session=mock_get_session())

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["model"] is mock_model
        assert call_kwargs["system_prompt"] == MOCK_SYSTEM_PROMPT
        assert call_kwargs["tools"] == [mock_mcp_client]
        assert "session_manager" not in call_kwargs

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    @patch("virtual_assistant_chat.agent_factory.get_bedrock_boto_session")
    @patch("virtual_assistant_chat.agent_factory.BedrockModel")
    @patch("virtual_assistant_chat.agent_factory.Agent")
    async def test_create_agent_custom_region(
        self, mock_agent_cls, mock_model_cls, mock_get_session, mock_prompt_loader_cls, mock_config_manager
    ):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_get_session.return_value = MagicMock()
        mock_model_cls.return_value = MagicMock()
        mock_agent_cls.return_value = MagicMock()

        factory = AgentFactory(mock_config_manager)

        with patch("virtual_assistant_chat.agent_factory.MCPClient") as mock_mcp_cls:
            mock_mcp_cls.return_value = MagicMock()
            await factory.initialize()
            factory.create_agent("us.amazon.nova-lite-v1:0", region="eu-west-1")

        mock_get_session.assert_called_once_with(region="eu-west-1")

    def test_create_agent_without_initialize_raises(self, mock_config_manager):
        factory = AgentFactory(mock_config_manager)

        with pytest.raises(RuntimeError, match="Must call initialize\\(\\)"):
            factory.create_agent("us.amazon.nova-lite-v1:0")

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    @patch("virtual_assistant_chat.agent_factory.get_bedrock_boto_session")
    @patch("virtual_assistant_chat.agent_factory.BedrockModel")
    async def test_create_agent_model_failure(
        self, mock_model_cls, mock_get_session, mock_prompt_loader_cls, mock_config_manager
    ):
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_get_session.return_value = MagicMock()
        mock_model_cls.side_effect = Exception("Bedrock error")

        factory = AgentFactory(mock_config_manager)
        await factory.initialize()

        with pytest.raises(AgentFactoryError, match="Failed to create agent"):
            factory.create_agent("invalid-model-id")

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    @patch("virtual_assistant_chat.agent_factory.get_bedrock_boto_session")
    @patch("virtual_assistant_chat.agent_factory.BedrockModel")
    @patch("virtual_assistant_chat.agent_factory.Agent")
    async def test_create_agent_with_session_manager(
        self, mock_agent_cls, mock_model_cls, mock_get_session, mock_prompt_loader_cls, mock_config_manager
    ):
        """Test that session_manager is forwarded to Agent constructor."""
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_get_session.return_value = MagicMock()
        mock_model_cls.return_value = MagicMock()
        mock_agent_cls.return_value = MagicMock()

        mock_session_manager = MagicMock()
        factory = AgentFactory(mock_config_manager)

        with patch("virtual_assistant_chat.agent_factory.MCPClient") as mock_mcp_cls:
            mock_mcp_cls.return_value = MagicMock()
            await factory.initialize()
            factory.create_agent("us.amazon.nova-lite-v1:0", session_manager=mock_session_manager)

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["session_manager"] is mock_session_manager

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    @patch("virtual_assistant_chat.agent_factory.get_bedrock_boto_session")
    @patch("virtual_assistant_chat.agent_factory.BedrockModel")
    @patch("virtual_assistant_chat.agent_factory.Agent")
    async def test_create_agent_temperature_forwarded_to_model(
        self, mock_agent_cls, mock_model_cls, mock_get_session, mock_prompt_loader_cls, mock_config_manager
    ):
        """Test that temperature is extracted from kwargs and passed to BedrockModel."""
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_model_cls.return_value = MagicMock()
        mock_agent_cls.return_value = MagicMock()

        factory = AgentFactory(mock_config_manager)

        with patch("virtual_assistant_chat.agent_factory.MCPClient") as mock_mcp_cls:
            mock_mcp_cls.return_value = MagicMock()
            await factory.initialize()
            factory.create_agent("us.amazon.nova-lite-v1:0", temperature=0.7)

        mock_model_cls.assert_called_once_with(
            model_id="us.amazon.nova-lite-v1:0", boto_session=mock_session, temperature=0.7
        )
        # temperature should NOT be forwarded to Agent
        assert "temperature" not in mock_agent_cls.call_args.kwargs

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent_factory.PromptLoader")
    @patch("virtual_assistant_chat.agent_factory.get_bedrock_boto_session")
    @patch("virtual_assistant_chat.agent_factory.BedrockModel")
    @patch("virtual_assistant_chat.agent_factory.Agent")
    async def test_create_agent_arbitrary_kwargs_forwarded(
        self, mock_agent_cls, mock_model_cls, mock_get_session, mock_prompt_loader_cls, mock_config_manager
    ):
        """Test that arbitrary kwargs are forwarded to Agent constructor."""
        mock_loader = MagicMock()
        mock_loader.load_prompt = AsyncMock(return_value=MOCK_SYSTEM_PROMPT)
        mock_prompt_loader_cls.return_value = mock_loader
        mock_get_session.return_value = MagicMock()
        mock_model_cls.return_value = MagicMock()
        mock_agent_cls.return_value = MagicMock()

        mock_callback = MagicMock()
        factory = AgentFactory(mock_config_manager)

        with patch("virtual_assistant_chat.agent_factory.MCPClient") as mock_mcp_cls:
            mock_mcp_cls.return_value = MagicMock()
            await factory.initialize()
            factory.create_agent(
                "us.amazon.nova-lite-v1:0",
                callback_handler=mock_callback,
                trace_attributes={"session.id": "test-123"},
            )

        call_kwargs = mock_agent_cls.call_args.kwargs
        assert call_kwargs["callback_handler"] is mock_callback
        assert call_kwargs["trace_attributes"] == {"session.id": "test-123"}
