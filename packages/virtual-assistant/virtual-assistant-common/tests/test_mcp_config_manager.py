# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for MCPConfigManager.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from virtual_assistant_common.mcp.config_manager import (
    MCPAuthenticationConfig,
    MCPConfigManager,
    MCPServerConfig,
    MCPSystemPromptsConfig,
)


@pytest.fixture
def valid_mcp_config():
    """Valid MCP configuration JSON."""
    return {
        "mcpServers": {
            "hotel-assistant-mcp": {
                "type": "streamable-http",
                "url": "https://hotel-assistant.example.com",
                "authentication": {"type": "cognito", "secretArn": "arn:aws:secretsmanager:us-east-1:123:secret:test"},
                "systemPrompts": {"chat": "chat_system_prompt", "voice": "voice_system_prompt"},
            },
            "hotel-pms-mcp": {
                "type": "streamable-http",
                "url": "https://hotel-pms.example.com",
                "authentication": {"type": "cognito", "secretArn": "arn:aws:secretsmanager:us-east-1:123:secret:pms"},
            },
            "unauthenticated-mcp": {
                "type": "streamable-http",
                "url": "https://unauthenticated.example.com",
            },
        }
    }


@pytest.fixture
def valid_credentials():
    """Valid credentials from Secrets Manager."""
    return {
        "userPoolId": "us-east-1_test123",
        "clientId": "test-client-id",
        "clientSecret": "test-client-secret",
        "region": "us-east-1",
    }


class TestMCPConfigManagerInit:
    """Tests for MCPConfigManager initialization."""

    def test_init_with_parameter_name(self):
        """Test initialization with explicit parameter name."""
        manager = MCPConfigManager(parameter_name="/test/mcp-config")
        assert manager.parameter_name == "/test/mcp-config"

    def test_init_with_env_var(self, monkeypatch):
        """Test initialization with environment variable."""
        monkeypatch.setenv("MCP_CONFIG_PARAMETER", "/env/mcp-config")
        manager = MCPConfigManager()
        assert manager.parameter_name == "/env/mcp-config"

    def test_init_without_parameter_raises_error(self, monkeypatch):
        """Test initialization without parameter name raises ValueError."""
        monkeypatch.delenv("MCP_CONFIG_PARAMETER", raising=False)
        with pytest.raises(ValueError, match="MCP_CONFIG_PARAMETER environment variable required"):
            MCPConfigManager()


class TestMCPConfigManagerLoadConfig:
    """Tests for load_config method."""

    @patch("boto3.client")
    def test_load_config_success(self, mock_boto_client, valid_mcp_config):
        """Test successful configuration loading from SSM."""
        # Mock SSM client
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(valid_mcp_config)}}
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")
        servers = manager.load_config()

        # Verify SSM was called correctly
        mock_ssm.get_parameter.assert_called_once_with(Name="/test/mcp-config", WithDecryption=True)

        # Verify parsed configuration
        assert len(servers) == 3
        assert "hotel-assistant-mcp" in servers
        assert "hotel-pms-mcp" in servers
        assert "unauthenticated-mcp" in servers

        # Verify hotel-assistant-mcp config
        hotel_assistant = servers["hotel-assistant-mcp"]
        assert isinstance(hotel_assistant, MCPServerConfig)
        assert hotel_assistant.name == "hotel-assistant-mcp"
        assert hotel_assistant.type == "streamable-http"
        assert hotel_assistant.url == "https://hotel-assistant.example.com"
        assert isinstance(hotel_assistant.system_prompts, MCPSystemPromptsConfig)
        assert hotel_assistant.system_prompts.chat == "chat_system_prompt"
        assert hotel_assistant.system_prompts.voice == "voice_system_prompt"
        assert isinstance(hotel_assistant.authentication, MCPAuthenticationConfig)
        assert hotel_assistant.authentication.secret_arn == "arn:aws:secretsmanager:us-east-1:123:secret:test"

        # Verify hotel-pms-mcp config
        hotel_pms = servers["hotel-pms-mcp"]
        assert hotel_pms.name == "hotel-pms-mcp"
        assert hotel_pms.system_prompts is None
        assert isinstance(hotel_pms.authentication, MCPAuthenticationConfig)

        # Verify unauthenticated-mcp config
        unauth = servers["unauthenticated-mcp"]
        assert unauth.name == "unauthenticated-mcp"
        assert unauth.authentication is None

    @patch("boto3.client")
    def test_load_config_caches_result(self, mock_boto_client, valid_mcp_config):
        """Test that configuration is cached after first load."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(valid_mcp_config)}}
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")

        # Load twice
        servers1 = manager.load_config()
        servers2 = manager.load_config()

        # SSM should only be called once
        assert mock_ssm.get_parameter.call_count == 1
        assert servers1 is servers2  # Same object reference

    @patch("boto3.client")
    def test_load_config_parameter_not_found(self, mock_boto_client):
        """Test handling of parameter not found error."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}}, "GetParameter"
        )
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")

        with pytest.raises(RuntimeError, match="MCP configuration parameter '/test/mcp-config' not found"):
            manager.load_config()

    @patch("boto3.client")
    def test_load_config_invalid_json(self, mock_boto_client):
        """Test handling of invalid JSON in parameter."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "not valid json {"}}
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")

        with pytest.raises(RuntimeError, match="MCP configuration is not valid JSON"):
            manager.load_config()

    @patch("boto3.client")
    def test_load_config_missing_mcpservers_key(self, mock_boto_client):
        """Test handling of missing mcpServers key."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps({"servers": {}})}}
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")

        with pytest.raises(RuntimeError, match="Configuration must contain 'mcpServers' key"):
            manager.load_config()


class TestMCPConfigManagerGetCredentials:
    """Tests for get_credentials method."""

    @patch("boto3.client")
    def test_get_credentials_success(self, mock_boto_client, valid_credentials):
        """Test successful credentials retrieval from Secrets Manager."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {"SecretString": json.dumps(valid_credentials)}

        def client_factory(service_name, **kwargs):
            if service_name == "secretsmanager":
                return mock_secrets
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        manager = MCPConfigManager(parameter_name="/test/mcp-config")
        creds = manager.get_credentials("arn:aws:secretsmanager:us-east-1:123:secret:test")

        assert creds == valid_credentials
        mock_secrets.get_secret_value.assert_called_once_with(
            SecretId="arn:aws:secretsmanager:us-east-1:123:secret:test"
        )

    @patch("boto3.client")
    def test_get_credentials_access_denied(self, mock_boto_client):
        """Test handling of access denied error."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}, "GetSecretValue"
        )

        def client_factory(service_name, **kwargs):
            if service_name == "secretsmanager":
                return mock_secrets
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        manager = MCPConfigManager(parameter_name="/test/mcp-config")

        with pytest.raises(RuntimeError, match="Cannot access secret"):
            manager.get_credentials("arn:aws:secretsmanager:us-east-1:123:secret:test")

    @patch("boto3.client")
    def test_get_credentials_invalid_json(self, mock_boto_client):
        """Test handling of invalid JSON in secret."""
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {"SecretString": "not valid json {"}

        def client_factory(service_name, **kwargs):
            if service_name == "secretsmanager":
                return mock_secrets
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        manager = MCPConfigManager(parameter_name="/test/mcp-config")

        with pytest.raises(RuntimeError, match="contains invalid JSON"):
            manager.get_credentials("arn:aws:secretsmanager:us-east-1:123:secret:test")


class TestMCPConfigManagerFindPromptServer:
    """Tests for find_prompt_server method."""

    @patch("boto3.client")
    def test_find_prompt_server_found(self, mock_boto_client, valid_mcp_config):
        """Test finding server with systemPrompts configuration."""
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(valid_mcp_config)}}
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")
        prompt_server = manager.find_prompt_server()

        assert prompt_server == "hotel-assistant-mcp"

    @patch("boto3.client")
    def test_find_prompt_server_not_found(self, mock_boto_client):
        """Test when no server has systemPrompts configuration."""
        config = {
            "mcpServers": {
                "server1": {
                    "type": "streamable-http",
                    "url": "https://example.com",
                    "authentication": {
                        "type": "cognito",
                        "secretArn": "arn:aws:secretsmanager:us-east-1:123:secret:test",
                    },
                }
            }
        }

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": json.dumps(config)}}
        mock_boto_client.return_value = mock_ssm

        manager = MCPConfigManager(parameter_name="/test/mcp-config")
        prompt_server = manager.find_prompt_server()

        assert prompt_server is None
