# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for platform router functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from virtual_assistant_common.models.messaging import MessageEvent, MessageResponse
from virtual_assistant_common.platforms.router import PlatformRouter
from virtual_assistant_common.platforms.web import WebMessaging


class TestPlatformRouter:
    """Test cases for PlatformRouter."""

    def test_router_initialization(self):
        """Test router initializes with correct platform classes."""
        router = PlatformRouter()

        # Check that platform classes are registered
        assert "web" in router._platform_classes
        assert "twilio" in router._platform_classes
        assert "aws-eum" in router._platform_classes

        # Check that no instances are created initially
        assert len(router._platforms) == 0

    def test_get_platform_lazy_loading(self):
        """Test that platforms are lazy-loaded on first access."""
        router = PlatformRouter()

        # Initially no instances
        assert len(router._platforms) == 0

        # Get web platform - should create instance
        web_platform = router.get_platform("web")
        assert isinstance(web_platform, WebMessaging)
        assert len(router._platforms) == 1

        # Get same platform again - should return same instance
        web_platform2 = router.get_platform("web")
        assert web_platform is web_platform2

    def test_get_platform_invalid_platform(self):
        """Test error handling for invalid platform names."""
        router = PlatformRouter()

        with pytest.raises(ValueError, match="Unsupported platform 'invalid'"):
            router.get_platform("invalid")

    @pytest.mark.asyncio
    async def test_process_incoming_message_routing(self):
        """Test message processing is routed to correct platform."""
        router = PlatformRouter()

        # Create test message event
        message_event = MessageEvent(
            message_id="msg-123",
            conversation_id="user456#hotel-assistant",
            sender_id="user456",
            recipient_id="hotel-assistant",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            platform="web",
        )

        # Mock the web platform
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.process_incoming_message.return_value = MessageResponse(success=True, message_id="msg-123")
            mock_get_platform.return_value = mock_platform

            # Process message
            response = await router.process_incoming_message(message_event)

            # Verify routing
            mock_get_platform.assert_called_once_with("web")
            mock_platform.process_incoming_message.assert_called_once_with(message_event)
            assert response.success is True
            assert response.message_id == "msg-123"

    @pytest.mark.asyncio
    async def test_process_incoming_message_platform_error(self):
        """Test error handling when platform routing fails."""
        router = PlatformRouter()

        # Mock get_platform to raise an error
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_get_platform.side_effect = ValueError("Unsupported platform")

            # Create test message event
            message_event = MessageEvent(
                message_id="msg-123",
                conversation_id="user456#hotel-assistant",
                sender_id="user456",
                recipient_id="hotel-assistant",
                content="Hello",
                timestamp="2024-01-01T12:00:00Z",
                platform="invalid",
            )

            # Process message - should handle error gracefully
            response = await router.process_incoming_message(message_event)

            assert response.success is False
            assert "Platform routing error" in response.error
            assert response.message_id == "msg-123"

    @pytest.mark.asyncio
    async def test_update_message_status_routing(self):
        """Test message status update routing."""
        router = PlatformRouter()

        # Mock the platform
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.update_message_status.return_value = MessageResponse(success=True, message_id="msg-123")
            mock_get_platform.return_value = mock_platform

            # Update status
            response = await router.update_message_status("msg-123", "read")

            # Verify routing
            mock_get_platform.assert_called_once_with(router._current_platform)
            mock_platform.update_message_status.assert_called_once_with("msg-123", "read")
            assert response.success is True

    @pytest.mark.asyncio
    async def test_send_response_routing(self):
        """Test response sending routing."""
        router = PlatformRouter()

        # Mock the platform
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.send_response.return_value = MessageResponse(success=True, message_id="msg-456")
            mock_get_platform.return_value = mock_platform

            # Send response
            response = await router.send_response("user123#hotel-assistant", "Hello!")

            # Verify routing
            mock_get_platform.assert_called_once_with(router._current_platform)
            mock_platform.send_response.assert_called_once_with("user123#hotel-assistant", "Hello!")
            assert response.success is True

    @pytest.mark.asyncio
    async def test_send_message_routing(self):
        """Test message sending routing."""
        router = PlatformRouter()

        # Mock the platform
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.send_message.return_value = MessageResponse(success=True, message_id="msg-789")
            mock_get_platform.return_value = mock_platform

            # Send message
            response = await router.send_message("user123", "Hello!", {"key": "value"})

            # Verify routing
            mock_get_platform.assert_called_once_with(router._current_platform)
            mock_platform.send_message.assert_called_once_with("user123", "Hello!", {"key": "value"})
            assert response.success is True

    def test_list_platforms(self):
        """Test platform listing functionality."""
        router = PlatformRouter()

        platforms = router.list_platforms()

        assert platforms["web"] == "implemented"
        assert platforms["twilio"] == "stub"
        assert platforms["aws-eum"] == "stub"

    def test_get_platform_capabilities_web(self):
        """Test getting capabilities for web platform."""
        router = PlatformRouter()

        capabilities = router.get_platform_capabilities("web")

        assert capabilities["name"] == "web"
        assert capabilities["status"] == "implemented"
        assert "web" in capabilities["channels"]
        assert "text_messages" in capabilities["features"]
        assert capabilities["authentication"] == "cognito_jwt"

    def test_get_platform_capabilities_twilio(self):
        """Test getting capabilities for Twilio platform."""
        router = PlatformRouter()

        capabilities = router.get_platform_capabilities("twilio")

        assert capabilities["name"] == "twilio"
        assert capabilities["status"] == "stub"
        assert "sms" in capabilities["channels"]
        assert "whatsapp" in capabilities["channels"]
        assert capabilities["webhook_required"] is True

    def test_get_platform_capabilities_aws_eum(self):
        """Test getting capabilities for AWS EUM platform."""
        router = PlatformRouter()

        capabilities = router.get_platform_capabilities("aws-eum")

        assert capabilities["name"] == "aws-eum"
        assert capabilities["status"] == "stub"
        assert "whatsapp" in capabilities["channels"]
        assert "rich_messages" in capabilities["features"]
        assert capabilities["managed_service"] is True

    def test_get_platform_capabilities_invalid(self):
        """Test error handling for invalid platform capabilities request."""
        router = PlatformRouter()

        with pytest.raises(ValueError, match="Unsupported platform 'invalid'"):
            router.get_platform_capabilities("invalid")

    @pytest.mark.asyncio
    async def test_error_handling_in_routing_methods(self):
        """Test error handling in routing methods when platform methods fail."""
        router = PlatformRouter()

        # Mock platform to raise exception
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.send_message.side_effect = Exception("Platform error")
            mock_get_platform.return_value = mock_platform

            # Send message - should handle error gracefully
            response = await router.send_message("user123", "Hello!", "web")

            assert response.success is False
            assert "Message sending error" in response.error

    def test_platform_instance_caching(self):
        """Test that platform instances are cached properly."""
        router = PlatformRouter()

        # Get platform multiple times
        platform1 = router.get_platform("web")
        platform2 = router.get_platform("web")
        platform3 = router.get_platform("twilio")

        # Should be same instance for same platform
        assert platform1 is platform2

        # Should be different instances for different platforms
        assert platform1 is not platform3

        # Should have 2 cached instances
        assert len(router._platforms) == 2

    @pytest.mark.asyncio
    async def test_update_message_status_with_multiple_ids(self):
        """Test updating status for multiple message IDs."""
        router = PlatformRouter()

        message_ids = ["msg-1", "msg-2", "msg-3"]

        # Mock the platform
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.update_message_status.return_value = MessageResponse(
                success=True, data={"updated_count": 3, "message_ids": message_ids}
            )
            mock_get_platform.return_value = mock_platform

            # Update status with list of message IDs
            response = await router.update_message_status(message_ids, "delivered")

            # Verify routing
            mock_get_platform.assert_called_once_with(router._current_platform)
            mock_platform.update_message_status.assert_called_once_with(message_ids, "delivered")
            assert response.success is True
            assert response.data["updated_count"] == 3
            assert response.data["message_ids"] == message_ids
