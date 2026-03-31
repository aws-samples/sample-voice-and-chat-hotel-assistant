# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for hotel_pms_mcp_client function.

This module tests the Hotel PMS MCP client factory function, including
configuration loading from Secrets Manager and environment variables,
configuration validation, and integration with cognito_mcp_client.
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from virtual_assistant_common.cognito_mcp.exceptions import CognitoConfigError
from virtual_assistant_common.exceptions import ConfigurationError
from virtual_assistant_common.hotel_pms_mcp_client import (
    HotelPmsMcpConfig,
    _load_config_from_environment,
    _load_config_from_secrets_manager,
    _merge_config,
    _validate_config,
    hotel_pms_mcp_client,
)


class TestHotelPmsMcpConfig:
    """Test the HotelPmsMcpConfig Pydantic model."""

    def test_valid_config(self):
        """Test creating config with valid data."""
        config_data = {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
            "region": "us-west-2",
        }

        config = HotelPmsMcpConfig(**config_data)

        assert config.url == "https://example.com/mcp"
        assert config.user_pool_id == "us-east-1_abcd1234"
        assert config.client_id == "client123"
        assert config.client_secret == "secret456"
        assert config.region == "us-west-2"

    def test_default_region(self):
        """Test that region defaults to us-east-1."""
        config_data = {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
        }

        config = HotelPmsMcpConfig(**config_data)
        assert config.region == "us-east-1"

    def test_missing_required_fields(self):
        """Test validation error for missing required fields."""
        config_data = {
            "url": "https://example.com/mcp",
            # Missing user_pool_id, client_id, client_secret
        }

        with pytest.raises(ValidationError) as exc_info:
            HotelPmsMcpConfig(**config_data)

        errors = exc_info.value.errors()
        missing_fields = [error["loc"][0] for error in errors if error["type"] == "missing"]
        assert "user_pool_id" in missing_fields
        assert "client_id" in missing_fields
        assert "client_secret" in missing_fields

    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        config_data = {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
            "extra_field": "not_allowed",
        }

        with pytest.raises(ValidationError) as exc_info:
            HotelPmsMcpConfig(**config_data)

        errors = exc_info.value.errors()
        assert any(error["type"] == "extra_forbidden" for error in errors)


class TestLoadConfigFromSecretsManager:
    """Test the _load_config_from_secrets_manager function."""

    @patch("boto3.Session")
    def test_successful_load(self, mock_session):
        """Test successfully loading configuration from Secrets Manager."""
        # Mock the Secrets Manager client
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock successful response
        config_data = {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
            "region": "us-west-2",
        }
        mock_client.get_secret_value.return_value = {"SecretString": json.dumps(config_data)}

        test_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-AbCdEf"
        result = _load_config_from_secrets_manager(test_arn, "us-east-1")

        assert result == config_data
        mock_session.assert_called_once()
        mock_session.return_value.client.assert_called_once_with("secretsmanager", region_name="us-east-1")
        mock_client.get_secret_value.assert_called_once_with(SecretId=test_arn)

    @patch("boto3.Session")
    def test_client_error(self, mock_session):
        """Test handling of AWS client errors."""
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock ClientError
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}
        mock_client.get_secret_value.side_effect = ClientError(error_response, "GetSecretValue")

        test_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:nonexistent-secret-AbCdEf"
        result = _load_config_from_secrets_manager(test_arn, "us-east-1")

        assert result is None

    @patch("boto3.Session")
    def test_invalid_json(self, mock_session):
        """Test handling of invalid JSON in secret."""
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock response with invalid JSON
        mock_client.get_secret_value.return_value = {"SecretString": "invalid json {"}

        test_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-AbCdEf"
        with pytest.raises(ConfigurationError) as exc_info:
            _load_config_from_secrets_manager(test_arn, "us-east-1")

        assert "Invalid JSON in Secrets Manager secret" in str(exc_info.value)
        assert exc_info.value.error_code == "INVALID_SECRET_JSON"

    @patch("boto3.Session")
    def test_unexpected_error(self, mock_session):
        """Test handling of unexpected errors."""
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock unexpected error
        mock_client.get_secret_value.side_effect = Exception("Unexpected error")

        test_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-AbCdEf"
        result = _load_config_from_secrets_manager(test_arn, "us-east-1")

        assert result is None

    @patch.dict(os.environ, {}, clear=True)
    def test_no_secret_arn_provided(self):
        """Test when no secret ARN is provided and environment variable is not set."""
        result = _load_config_from_secrets_manager(None, "us-east-1")
        assert result is None

    @patch.dict(
        os.environ,
        {"HOTEL_PMS_MCP_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:env-secret-AbCdEf"},
    )
    @patch("boto3.Session")
    def test_secret_arn_from_environment(self, mock_session):
        """Test loading secret ARN from environment variable."""
        # Mock the Secrets Manager client
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client

        # Mock successful response
        config_data = {"url": "https://example.com/mcp"}
        mock_client.get_secret_value.return_value = {"SecretString": json.dumps(config_data)}

        result = _load_config_from_secrets_manager(None, "us-east-1")

        assert result == config_data
        mock_client.get_secret_value.assert_called_once_with(
            SecretId="arn:aws:secretsmanager:us-east-1:123456789012:secret:env-secret-AbCdEf"
        )


class TestLoadConfigFromEnvironment:
    """Test the _load_config_from_environment function."""

    def test_all_environment_variables_set(self, monkeypatch):
        """Test loading when all environment variables are set."""
        env_vars = {
            "HOTEL_PMS_MCP_URL": "https://example.com/mcp",
            "HOTEL_PMS_MCP_USER_POOL_ID": "us-east-1_abcd1234",
            "HOTEL_PMS_MCP_CLIENT_ID": "client123",
            "HOTEL_PMS_MCP_CLIENT_SECRET": "secret456",
            "HOTEL_PMS_MCP_REGION": "us-west-2",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        result = _load_config_from_environment()

        expected = {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
            "region": "us-west-2",
        }
        assert result == expected

    def test_partial_environment_variables(self, monkeypatch):
        """Test loading when only some environment variables are set."""
        # Clear all existing environment variables first
        env_keys = [
            "HOTEL_PMS_MCP_URL",
            "HOTEL_PMS_MCP_USER_POOL_ID",
            "HOTEL_PMS_MCP_CLIENT_ID",
            "HOTEL_PMS_MCP_CLIENT_SECRET",
            "HOTEL_PMS_MCP_REGION",
        ]
        for key in env_keys:
            monkeypatch.delenv(key, raising=False)

        # Set only some environment variables
        monkeypatch.setenv("HOTEL_PMS_MCP_URL", "https://example.com/mcp")
        monkeypatch.setenv("HOTEL_PMS_MCP_CLIENT_ID", "client123")

        result = _load_config_from_environment()

        expected = {
            "url": "https://example.com/mcp",
            "client_id": "client123",
            "region": "us-east-1",  # Default region
        }
        assert result == expected

    def test_no_environment_variables(self):
        """Test loading when no environment variables are set."""
        # Clear any existing environment variables
        env_keys = [
            "HOTEL_PMS_MCP_URL",
            "HOTEL_PMS_MCP_USER_POOL_ID",
            "HOTEL_PMS_MCP_CLIENT_ID",
            "HOTEL_PMS_MCP_CLIENT_SECRET",
            "HOTEL_PMS_MCP_REGION",
        ]

        for key in env_keys:
            if key in os.environ:
                del os.environ[key]

        result = _load_config_from_environment()

        expected = {"region": "us-east-1"}  # Only default region
        assert result == expected

    def test_default_region(self, monkeypatch):
        """Test that region defaults to us-east-1 when not set."""
        monkeypatch.setenv("HOTEL_PMS_MCP_URL", "https://example.com/mcp")

        result = _load_config_from_environment()

        assert result["region"] == "us-east-1"


class TestMergeConfig:
    """Test the _merge_config function."""

    def test_merge_all_sources(self):
        """Test merging configuration from all sources with correct precedence."""
        secrets_config = {
            "url": "https://secrets.example.com/mcp",
            "user_pool_id": "secrets_pool",
            "client_id": "secrets_client",
            "client_secret": "secrets_secret",
            "region": "us-east-1",
        }

        env_config = {
            "url": "https://env.example.com/mcp",
            "user_pool_id": "env_pool",
            "region": "us-west-2",
        }

        explicit_params = {
            "url": "https://explicit.example.com/mcp",
            "client_id": None,  # Should not override
            "region": None,  # Should not override
        }

        result = _merge_config(secrets_config, env_config, explicit_params)

        expected = {
            "url": "https://explicit.example.com/mcp",  # Explicit (highest precedence)
            "user_pool_id": "env_pool",  # Environment (overrides secrets)
            "client_id": "secrets_client",  # Secrets (not overridden)
            "client_secret": "secrets_secret",  # Secrets only
            "region": "us-west-2",  # Environment (overrides secrets)
        }
        assert result == expected

    def test_merge_no_secrets(self):
        """Test merging when secrets config is None."""
        env_config = {
            "url": "https://env.example.com/mcp",
            "user_pool_id": "env_pool",
        }

        explicit_params = {
            "client_id": "explicit_client",
            "region": None,
        }

        result = _merge_config(None, env_config, explicit_params)

        expected = {
            "url": "https://env.example.com/mcp",
            "user_pool_id": "env_pool",
            "client_id": "explicit_client",
        }
        assert result == expected

    def test_merge_empty_configs(self):
        """Test merging with empty configurations."""
        result = _merge_config({}, {}, {})
        assert result == {}

    def test_explicit_none_values_ignored(self):
        """Test that None values in explicit params don't override other sources."""
        secrets_config = {"url": "https://secrets.example.com/mcp"}
        env_config = {"user_pool_id": "env_pool"}
        explicit_params = {"url": None, "user_pool_id": None, "client_id": "explicit_client"}

        result = _merge_config(secrets_config, env_config, explicit_params)

        expected = {
            "url": "https://secrets.example.com/mcp",  # Not overridden by None
            "user_pool_id": "env_pool",  # Not overridden by None
            "client_id": "explicit_client",  # Set by explicit
        }
        assert result == expected


class TestValidateConfig:
    """Test the _validate_config function."""

    def test_valid_config(self):
        """Test validation of valid configuration."""
        config = {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
            "region": "us-west-2",
        }

        result = _validate_config(config)

        assert isinstance(result, HotelPmsMcpConfig)
        assert result.url == "https://example.com/mcp"
        assert result.user_pool_id == "us-east-1_abcd1234"
        assert result.client_id == "client123"
        assert result.client_secret == "secret456"
        assert result.region == "us-west-2"

    def test_missing_required_fields(self):
        """Test validation error for missing required fields."""
        config = {
            "url": "https://example.com/mcp",
            # Missing user_pool_id, client_id, client_secret
        }

        with pytest.raises(CognitoConfigError) as exc_info:
            _validate_config(config)

        error = exc_info.value
        assert "configuration validation failed" in error.message
        assert "user_pool_id" in error.missing_config
        assert "client_id" in error.missing_config
        assert "client_secret" in error.missing_config
        assert error.config_source == "merged"

    def test_invalid_fields(self):
        """Test validation error for invalid field types."""
        config = {
            "url": 123,  # Should be string
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
        }

        with pytest.raises(CognitoConfigError) as exc_info:
            _validate_config(config)

        error = exc_info.value
        assert "configuration validation failed" in error.message
        assert len(error.invalid_config) > 0


class TestHotelPmsMcpClient:
    """Test the hotel_pms_mcp_client function."""

    @pytest.fixture
    def mock_cognito_mcp_client(self):
        """Mock the cognito_mcp_client function."""
        with patch("virtual_assistant_common.hotel_pms_mcp_client.cognito_mcp_client") as mock:
            # Create mock streams and callback
            mock_read_stream = AsyncMock()
            mock_write_stream = AsyncMock()
            mock_get_session_id = MagicMock(return_value="session123")

            # Create a proper async context manager mock
            async_context_mock = AsyncMock()
            async_context_mock.__aenter__ = AsyncMock(
                return_value=(mock_read_stream, mock_write_stream, mock_get_session_id)
            )
            async_context_mock.__aexit__ = AsyncMock(return_value=None)

            # Make the mock return the async context manager
            mock.return_value = async_context_mock

            yield mock

    @pytest.fixture
    def valid_config(self):
        """Valid configuration for testing."""
        return {
            "url": "https://example.com/mcp",
            "user_pool_id": "us-east-1_abcd1234",
            "client_id": "client123",
            "client_secret": "secret456",
            "region": "us-west-2",
        }

    @pytest.mark.asyncio
    async def test_explicit_parameters_only(self, mock_cognito_mcp_client, valid_config):
        """Test using only explicit parameters."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = None
            mock_env.return_value = {"region": "us-east-1"}

            async with hotel_pms_mcp_client(**valid_config) as session:
                assert session is not None

            # Verify cognito_mcp_client was called with correct parameters
            mock_cognito_mcp_client.assert_called_once()
            call_kwargs = mock_cognito_mcp_client.call_args[1]
            assert call_kwargs["url"] == valid_config["url"]
            assert call_kwargs["user_pool_id"] == valid_config["user_pool_id"]
            assert call_kwargs["client_id"] == valid_config["client_id"]
            assert call_kwargs["client_secret"] == valid_config["client_secret"]
            assert call_kwargs["region"] == valid_config["region"]

    @pytest.mark.asyncio
    async def test_secrets_manager_config(self, mock_cognito_mcp_client, valid_config):
        """Test loading configuration from Secrets Manager."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = valid_config
            mock_env.return_value = {"region": "us-east-1"}

            async with hotel_pms_mcp_client() as session:
                assert session is not None

            # Verify Secrets Manager was called with None (no ARN provided)
            mock_secrets.assert_called_once_with(None, "us-east-1")

    @pytest.mark.asyncio
    async def test_environment_config(self, mock_cognito_mcp_client, valid_config):
        """Test loading configuration from environment variables."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = None
            mock_env.return_value = valid_config

            async with hotel_pms_mcp_client() as session:
                assert session is not None

            # Verify environment loading was called
            mock_env.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_precedence(self, mock_cognito_mcp_client):
        """Test configuration precedence: explicit > env > secrets."""
        secrets_config = {
            "url": "https://secrets.example.com/mcp",
            "user_pool_id": "secrets_pool",
            "client_id": "secrets_client",
            "client_secret": "secrets_secret",
            "region": "us-east-1",
        }

        env_config = {
            "url": "https://env.example.com/mcp",
            "user_pool_id": "env_pool",
            "region": "us-west-2",
        }

        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = secrets_config
            mock_env.return_value = env_config

            # Explicit parameters should have highest precedence
            async with hotel_pms_mcp_client(url="https://explicit.example.com/mcp", client_secret="explicit_secret"):
                pass

                # Verify final configuration used explicit > env > secrets precedence
                call_kwargs = mock_cognito_mcp_client.call_args[1]
                assert call_kwargs["url"] == "https://explicit.example.com/mcp"  # Explicit
                assert call_kwargs["user_pool_id"] == "env_pool"  # Environment
                assert call_kwargs["client_id"] == "secrets_client"  # Secrets
                assert call_kwargs["client_secret"] == "explicit_secret"  # Explicit
                assert call_kwargs["region"] == "us-west-2"  # Environment

    @pytest.mark.asyncio
    async def test_missing_required_config(self, mock_cognito_mcp_client):
        """Test error when required configuration is missing."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = None
            mock_env.return_value = {"region": "us-east-1"}  # Only region, missing required fields

            with pytest.raises(CognitoConfigError) as exc_info:
                async with hotel_pms_mcp_client():
                    pass

            error = exc_info.value
            assert "configuration validation failed" in error.message
            assert "url" in error.missing_config
            assert "user_pool_id" in error.missing_config
            assert "client_id" in error.missing_config
            assert "client_secret" in error.missing_config

    @pytest.mark.asyncio
    async def test_custom_secret_arn(self, mock_cognito_mcp_client, valid_config):
        """Test using custom secret ARN."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = valid_config
            mock_env.return_value = {"region": "us-east-1"}

            custom_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:custom-secret-AbCdEf"
            async with hotel_pms_mcp_client(secret_arn=custom_arn):
                pass

            # Verify custom secret ARN was used
            mock_secrets.assert_called_once_with(custom_arn, "us-east-1")

    @pytest.mark.asyncio
    async def test_custom_region_for_secrets_lookup(self, mock_cognito_mcp_client, valid_config):
        """Test using custom region for Secrets Manager lookup."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = valid_config
            mock_env.return_value = {}

            async with hotel_pms_mcp_client(region="eu-west-1"):
                pass

            # Verify custom region was used for Secrets Manager lookup
            mock_secrets.assert_called_once_with(None, "eu-west-1")

    @pytest.mark.asyncio
    async def test_additional_parameters_passed_through(self, mock_cognito_mcp_client, valid_config):
        """Test that additional parameters are passed through to cognito_mcp_client."""
        with (
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets,
            patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_environment") as mock_env,
        ):
            mock_secrets.return_value = valid_config
            mock_env.return_value = {}

            custom_headers = {"X-Custom-Header": "test"}
            custom_timeout = 60

            async with hotel_pms_mcp_client(headers=custom_headers, timeout=custom_timeout, terminate_on_close=False):
                pass

            # Verify additional parameters were passed through
            call_kwargs = mock_cognito_mcp_client.call_args[1]
            assert call_kwargs["headers"] == custom_headers
            assert call_kwargs["timeout"] == custom_timeout
            assert call_kwargs["terminate_on_close"] is False

    @pytest.mark.asyncio
    async def test_secrets_manager_json_error_propagated(self, mock_cognito_mcp_client):
        """Test that JSON errors from Secrets Manager are properly propagated."""
        with patch("virtual_assistant_common.hotel_pms_mcp_client._load_config_from_secrets_manager") as mock_secrets:
            mock_secrets.side_effect = ConfigurationError(
                "Invalid JSON in Secrets Manager secret 'test-secret': Expecting ',' delimiter",
                error_code="INVALID_SECRET_JSON",
            )

            with pytest.raises(ConfigurationError) as exc_info:
                async with hotel_pms_mcp_client():
                    pass

            assert "Invalid JSON in Secrets Manager secret" in str(exc_info.value)
            assert exc_info.value.error_code == "INVALID_SECRET_JSON"
