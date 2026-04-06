# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for LiveKit agent initialization with simplified credential management.

This module tests the agent initialization logic including credential
retrieval from environment variables and AWS Secrets Manager.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCredentialRetrieval:
    """Test credential retrieval logic."""

    def setup_method(self):
        """Set up test environment."""
        # Clean environment variables
        for key in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_SECRET_NAME"]:
            if key in os.environ:
                del os.environ[key]

    def test_get_credentials_from_env_variables(self):
        """Test getting credentials from environment variables."""
        from virtual_assistant_livekit.credentials import get_livekit_credentials

        # Set environment variables
        os.environ["LIVEKIT_URL"] = "wss://env.livekit.cloud"
        os.environ["LIVEKIT_API_KEY"] = "env-api-key"
        os.environ["LIVEKIT_API_SECRET"] = "env-api-secret"

        # Get credentials
        result = get_livekit_credentials()

        # Verify environment variables were used
        assert result.url == "wss://env.livekit.cloud"
        assert result.api_key == "env-api-key"
        assert result.api_secret == "env-api-secret"

    @patch("boto3.client")
    def test_get_credentials_from_secrets_manager(self, mock_boto_client):
        """Test getting credentials from AWS Secrets Manager."""
        from virtual_assistant_livekit.credentials import get_livekit_credentials

        # Set secret name
        os.environ["LIVEKIT_SECRET_NAME"] = "test-secret"

        # Mock boto3 client
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": (
                '{"LIVEKIT_URL": "wss://secret.livekit.cloud", '
                '"LIVEKIT_API_KEY": "secret-api-key", '
                '"LIVEKIT_API_SECRET": "secret-api-secret"}'
            )
        }

        # Get credentials
        result = get_livekit_credentials()

        # Verify secret was retrieved
        mock_client.get_secret_value.assert_called_once_with(SecretId="test-secret")
        assert result.url == "wss://secret.livekit.cloud"
        assert result.api_key == "secret-api-key"
        assert result.api_secret == "secret-api-secret"

    def test_get_credentials_no_credentials_available(self):
        """Test error when no credentials are available."""
        from virtual_assistant_livekit.credentials import get_livekit_credentials

        # No environment variables or secret name set
        with pytest.raises(SystemExit) as exc_info:
            get_livekit_credentials()

        assert exc_info.value.code == 1

    @patch("boto3.client")
    def test_get_credentials_secret_missing_fields(self, mock_boto_client):
        """Test error when secret is missing required fields."""
        from virtual_assistant_livekit.credentials import get_livekit_credentials

        # Set secret name
        os.environ["LIVEKIT_SECRET_NAME"] = "test-secret"

        # Mock boto3 client with incomplete secret
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_secret_value.return_value = {
            "SecretString": '{"LIVEKIT_URL": "wss://secret.livekit.cloud"}'  # Missing API key and secret
        }

        # Get credentials should fail
        with pytest.raises(SystemExit) as exc_info:
            get_livekit_credentials()

        assert exc_info.value.code == 1


class TestEntrypointFunction:
    """Test entrypoint function behavior."""

    @pytest.mark.asyncio
    async def test_entrypoint_basic_flow(self):
        """Test basic entrypoint flow with mocked dependencies."""
        from virtual_assistant_livekit.agent import entrypoint

        # Mock JobContext
        mock_ctx = AsyncMock()
        mock_ctx.connect = AsyncMock()
        mock_ctx.room = MagicMock()
        # Mock proc.userdata (current implementation)
        mock_proc = MagicMock()
        mock_proc.userdata = {"instructions": "Test instructions", "hotels": []}
        mock_ctx.proc = mock_proc

        # Mock all LiveKit dependencies
        with (
            patch("hotel_assistant_livekit.agent.Agent") as mock_agent_class,
            patch("hotel_assistant_livekit.agent.AgentSession") as mock_session_class,
            patch("hotel_assistant_livekit.agent.BackgroundAudioPlayer") as mock_audio,
            patch("hotel_assistant_livekit.agent.greeting_audio") as mock_greeting,
            patch("hotel_assistant_livekit.agent.generate_dynamic_hotel_instructions") as mock_instructions,
            patch("hotel_assistant_livekit.agent.HotelPmsMCPServer") as mock_mcp_server_class,
        ):
            # Configure mocks
            mock_instructions.return_value = "Fallback instructions"
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            mock_session = MagicMock()
            mock_session.on = MagicMock(return_value=lambda func: func)  # Mock decorator
            mock_session.start = AsyncMock()
            mock_session.say = AsyncMock()
            mock_session_class.return_value = mock_session
            mock_audio_player = AsyncMock()
            mock_audio.return_value = mock_audio_player
            mock_greeting.return_value = "greeting_audio"
            mock_mcp_server = MagicMock()
            mock_mcp_server_class.return_value = mock_mcp_server

            # Call entrypoint
            await entrypoint(mock_ctx)

            # Verify basic flow
            mock_ctx.connect.assert_called_once()
            mock_agent_class.assert_called_once_with(instructions="Test instructions")
            mock_mcp_server_class.assert_called_once()
            mock_session_class.assert_called_once()
            mock_session.start.assert_called_once()
            mock_session.say.assert_called_once()


class TestMainFunction:
    """Test the main function with credential integration."""

    @patch("hotel_assistant_livekit.agent.get_livekit_credentials")
    @patch("hotel_assistant_livekit.agent.start_metrics_publishing")
    @patch("hotel_assistant_livekit.agent.agents.cli.run_app")
    @patch("asyncio.run")
    def test_main_success(self, mock_asyncio_run, mock_run_app, mock_start_metrics, mock_get_creds):
        """Test successful main function execution."""
        from virtual_assistant_livekit.agent import main
        from virtual_assistant_livekit.credentials import LiveKitCredentials

        # Mock credentials return value
        mock_credentials = LiveKitCredentials(
            url="wss://test.livekit.cloud", api_key="test-api-key", api_secret="test-api-secret"
        )
        mock_get_creds.return_value = mock_credentials

        # Mock asyncio.run for metrics publishing
        mock_asyncio_run.return_value = None

        # Call main function
        main()

        # Verify credentials were retrieved
        mock_get_creds.assert_called_once()
        # asyncio.run should be called twice: once for start_metrics, once for stop_metrics if needed
        mock_run_app.assert_called_once()

    @patch("hotel_assistant_livekit.agent.get_livekit_credentials")
    def test_main_credential_failure(self, mock_get_creds):
        """Test main function with credential failure."""
        from virtual_assistant_livekit.agent import main

        # Mock credential failure
        mock_get_creds.side_effect = SystemExit(1)

        # Call main function and expect SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
