# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for platform router integration in message processor."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from virtual_assistant_common.models.messaging import MessageEvent

from virtual_assistant_messaging_lambda.handlers.message_processor import _process_message_async


class TestPlatformRouterIntegration:
    """Test cases for platform router integration."""

    def setup_method(self):
        """Set up test environment variables."""
        os.environ["AGENTCORE_RUNTIME_ARN"] = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-agent"
        os.environ["AWS_REGION"] = "us-east-1"

    def teardown_method(self):
        """Clean up environment variables."""
        for var in ["AGENTCORE_RUNTIME_ARN", "AWS_REGION", "EUM_SOCIAL_PHONE_NUMBER_ID"]:
            if var in os.environ:
                del os.environ[var]

    @pytest.mark.asyncio
    async def test_process_message_with_web_platform(self):
        """Test message processing with web platform (no EUM Social config)."""
        # No EUM_SOCIAL_PHONE_NUMBER_ID set, should use web platform

        event = MessageEvent(
            message_id="test-msg-123",
            conversation_id="user123-session",
            sender_id="user123",
            recipient_id="hotel-assistant",
            content="Hello, I need help",
            timestamp="2024-01-01T12:00:00Z",
            platform="web",
        )

        # Mock platform router
        mock_platform_router = AsyncMock()
        mock_platform_router.update_message_status = AsyncMock()
        mock_platform_router.send_response = AsyncMock()
        mock_platform_router.get_current_platform.return_value = "web"

        # Mock successful response
        mock_response = MagicMock()
        mock_response.success = True
        mock_platform_router.send_response.return_value = mock_response

        # Mock AgentCore client
        mock_agentcore_client = MagicMock()
        mock_agentcore_response = MagicMock()
        mock_agentcore_response.success = True
        mock_agentcore_response.content = "Hello! How can I help you?"
        mock_agentcore_response.model_dump.return_value = {"status": "success"}
        mock_agentcore_client.invoke_agent.return_value = mock_agentcore_response

        with (
            patch(
                "virtual_assistant_messaging_lambda.handlers.message_processor.platform_router",
                mock_platform_router,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.message_processor.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            result = await _process_message_async(event)

            # Verify result
            assert result.success is True
            assert result.message_id == "test-msg-123"

            # Verify platform router calls
            mock_platform_router.update_message_status.assert_any_call("test-msg-123", "delivered")
            mock_platform_router.send_response.assert_called_once_with("user123-session", "Hello! How can I help you?")
            mock_platform_router.update_message_status.assert_any_call("test-msg-123", "read")

    @pytest.mark.asyncio
    async def test_process_message_with_whatsapp_platform(self):
        """Test message processing with WhatsApp platform (EUM Social configured)."""
        # Set EUM Social configuration
        os.environ["EUM_SOCIAL_PHONE_NUMBER_ID"] = "phone-123"

        event = MessageEvent(
            message_id="wamid.123",
            conversation_id="conversation-1234567890-session",
            sender_id="+1234567890",
            recipient_id="+0987654321",
            content="Hello from WhatsApp",
            timestamp="2024-01-01T12:00:00Z",
            platform="aws-eum",
        )

        # Mock platform router
        mock_platform_router = AsyncMock()
        mock_platform_router.update_message_status = AsyncMock()
        mock_platform_router.send_response = AsyncMock()
        mock_platform_router.get_current_platform.return_value = "aws-eum"

        # Mock successful response
        mock_response = MagicMock()
        mock_response.success = True
        mock_platform_router.send_response.return_value = mock_response

        # Mock AgentCore client
        mock_agentcore_client = MagicMock()
        mock_agentcore_response = MagicMock()
        mock_agentcore_response.success = True
        mock_agentcore_response.content = "Hello! How can I help you via WhatsApp?"
        mock_agentcore_response.model_dump.return_value = {"status": "success"}
        mock_agentcore_client.invoke_agent.return_value = mock_agentcore_response

        with (
            patch(
                "virtual_assistant_messaging_lambda.handlers.message_processor.platform_router",
                mock_platform_router,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.message_processor.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            result = await _process_message_async(event)

            # Verify result
            assert result.success is True
            assert result.message_id == "wamid.123"

            # Verify platform router calls
            mock_platform_router.update_message_status.assert_any_call("wamid.123", "delivered")
            mock_platform_router.send_response.assert_called_once_with(
                "conversation-1234567890-session", "Hello! How can I help you via WhatsApp?"
            )
            mock_platform_router.update_message_status.assert_any_call("wamid.123", "read")

    @pytest.mark.asyncio
    async def test_process_message_with_response_failure(self):
        """Test message processing when response sending fails."""
        event = MessageEvent(
            message_id="test-msg-456",
            conversation_id="user456-session",
            sender_id="user456",
            recipient_id="hotel-assistant",
            content="Test message",
            timestamp="2024-01-01T12:00:00Z",
            platform="web",
        )

        # Mock platform router with failed response
        mock_platform_router = AsyncMock()
        mock_platform_router.update_message_status = AsyncMock()
        mock_platform_router.send_response = AsyncMock()
        mock_platform_router.get_current_platform.return_value = "web"

        # Mock failed response
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.error = "Network error"
        mock_platform_router.send_response.return_value = mock_response

        # Mock AgentCore client
        mock_agentcore_client = MagicMock()
        mock_agentcore_response = MagicMock()
        mock_agentcore_response.success = True
        mock_agentcore_response.content = "Test response"
        mock_agentcore_response.model_dump.return_value = {"status": "success"}
        mock_agentcore_client.invoke_agent.return_value = mock_agentcore_response

        with (
            patch(
                "virtual_assistant_messaging_lambda.handlers.message_processor.platform_router",
                mock_platform_router,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.message_processor.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            result = await _process_message_async(event)

            # Verify result is still successful (AgentCore succeeded)
            assert result.success is True
            assert result.message_id == "test-msg-456"

            # Verify platform router calls
            mock_platform_router.update_message_status.assert_any_call("test-msg-456", "delivered")
            mock_platform_router.send_response.assert_called_once_with("user456-session", "Test response")
            # Should mark as failed since response sending failed
            mock_platform_router.update_message_status.assert_any_call("test-msg-456", "failed")

    def test_platform_detection_with_eum_social(self):
        """Test platform detection when EUM Social is configured."""
        os.environ["EUM_SOCIAL_PHONE_NUMBER_ID"] = "phone-123"

        # Import here to get fresh platform router with new env vars
        from virtual_assistant_common.platforms.router import PlatformRouter

        router = PlatformRouter()
        assert router.get_current_platform() == "aws-eum"

    def test_platform_detection_without_eum_social(self):
        """Test platform detection when EUM Social is not configured."""
        # Ensure no EUM Social config
        if "EUM_SOCIAL_PHONE_NUMBER_ID" in os.environ:
            del os.environ["EUM_SOCIAL_PHONE_NUMBER_ID"]

        # Import here to get fresh platform router with new env vars
        from virtual_assistant_common.platforms.router import PlatformRouter

        router = PlatformRouter()
        assert router.get_current_platform() == "web"
