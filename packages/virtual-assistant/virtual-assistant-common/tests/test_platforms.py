# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for messaging platform interfaces."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from virtual_assistant_common.models.messaging import MessageEvent
from virtual_assistant_common.platforms import (
    AWSEndUserMessaging,
    TwilioMessaging,
    WebMessaging,
)


class TestWebMessaging:
    """Test WebMessaging platform implementation."""

    @pytest.mark.asyncio
    async def test_process_incoming_message(self):
        """Test processing incoming web message."""
        with patch.dict(os.environ, {"MESSAGING_API_ENDPOINT": "https://api.example.com"}):
            platform = WebMessaging()

        message_event = MessageEvent(
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
            sender_id="user-456",
            recipient_id="hotel-assistant",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            platform="web",
        )

        response = await platform.process_incoming_message(message_event)

        assert response.success is True
        assert response.message_id == "msg-123"
        assert response.data["platform"] == "web"
        assert response.data["status"] == "already_processed"

    @pytest.mark.asyncio
    async def test_update_message_status_success(self):
        """Test successful message status update."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client
            mock_client = AsyncMock()
            mock_client.update_message_status.return_value = {"status": "read"}
            platform.messaging_client = mock_client

            response = await platform.update_message_status("msg-123", "read")

            assert response.success is True
            assert response.message_id == "msg-123"
            mock_client.update_message_status.assert_called_once_with("msg-123", "read")

    @pytest.mark.asyncio
    async def test_update_message_status_error(self):
        """Test message status update with error."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client to raise an exception
            mock_client = AsyncMock()
            mock_client.update_message_status.side_effect = Exception("API Error")
            platform.messaging_client = mock_client

            response = await platform.update_message_status("msg-123", "read")

            assert response.success is False
            assert response.message_id == "msg-123"
            assert "API Error" in response.error

    @pytest.mark.asyncio
    async def test_send_response_success(self):
        """Test successful response sending."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client
            mock_client = AsyncMock()
            mock_client.send_message.return_value = {"messageId": "msg-456"}
            platform.messaging_client = mock_client

            response = await platform.send_response("user-456#hotel-assistant", "Your reservation is confirmed")

            assert response.success is True
            assert response.message_id == "msg-456"

            # Verify the client was called with correct recipient
            mock_client.send_message.assert_called_once_with(
                recipient_id="user-456", content="Your reservation is confirmed"
            )

    @pytest.mark.asyncio
    async def test_send_response_conversation_id_parsing(self):
        """Test conversation ID parsing for recipient extraction."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client
            mock_client = AsyncMock()
            mock_client.send_message.return_value = {"messageId": "msg-456"}
            platform.messaging_client = mock_client

            # Test with hotel-assistant as second part
            await platform.send_response("user-789#hotel-assistant", "Hello")

            mock_client.send_message.assert_called_with(recipient_id="user-789", content="Hello")

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful direct message sending."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client
            mock_client = AsyncMock()
            mock_client.send_message.return_value = {"messageId": "msg-789"}
            platform.messaging_client = mock_client

            response = await platform.send_message(
                recipient_id="user-456",
                content="Welcome to our hotel!",
                platform_metadata={"source": "web"},
            )

            assert response.success is True
            assert response.message_id == "msg-789"

            # Verify platform_metadata is ignored for web platform
            mock_client.send_message.assert_called_once_with(recipient_id="user-456", content="Welcome to our hotel!")

    @pytest.mark.asyncio
    async def test_update_message_status_multiple_ids_success(self):
        """Test successful message status update with multiple message IDs."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client
            mock_client = AsyncMock()
            mock_client.update_message_status.return_value = {"status": "delivered"}
            platform.messaging_client = mock_client

            message_ids = ["msg-1", "msg-2", "msg-3"]
            response = await platform.update_message_status(message_ids, "delivered")

            assert response.success is True
            assert response.data["updated_count"] == 3
            assert response.data["message_ids"] == message_ids

            # Verify client was called for each message ID
            assert mock_client.update_message_status.call_count == 3

    @pytest.mark.asyncio
    async def test_update_message_status_single_id_as_string(self):
        """Test message status update with single message ID as string."""
        with patch.object(WebMessaging, "__init__", lambda x: None):
            platform = WebMessaging()

            # Mock the messaging client
            mock_client = AsyncMock()
            mock_client.update_message_status.return_value = {"status": "read"}
            platform.messaging_client = mock_client

            response = await platform.update_message_status("msg-123", "read")

            assert response.success is True
            assert response.message_id == "msg-123"

            # Verify client was called once
            mock_client.update_message_status.assert_called_once_with("msg-123", "read")


class TestTwilioMessaging:
    """Test TwilioMessaging platform stub."""

    @pytest.mark.asyncio
    async def test_process_incoming_message_not_implemented(self):
        """Test that Twilio message processing returns not implemented error."""
        platform = TwilioMessaging()

        message_event = MessageEvent(
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
            sender_id="user-456",
            recipient_id="hotel-assistant",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            platform="twilio",
        )

        response = await platform.process_incoming_message(message_event)

        assert response.success is False
        assert response.message_id == "msg-123"
        assert "not yet implemented" in response.error

    @pytest.mark.asyncio
    async def test_update_message_status_not_implemented(self):
        """Test that Twilio status update returns not implemented error."""
        platform = TwilioMessaging()

        response = await platform.update_message_status("msg-123", "read")

        assert response.success is False
        assert response.message_id == "msg-123"
        assert "not yet implemented" in response.error

    @pytest.mark.asyncio
    async def test_send_response_not_implemented(self):
        """Test that Twilio response sending returns not implemented error."""
        platform = TwilioMessaging()

        response = await platform.send_response("user-456#hotel-assistant", "Hello")

        assert response.success is False
        assert "not yet implemented" in response.error

    @pytest.mark.asyncio
    async def test_send_message_not_implemented(self):
        """Test that Twilio message sending returns not implemented error."""
        platform = TwilioMessaging()

        response = await platform.send_message(
            recipient_id="user-456", content="Hello", platform_metadata={"phone_number": "+1234567890"}
        )

        assert response.success is False
        assert "not yet implemented" in response.error


class TestAWSEndUserMessaging:
    """Test AWSEndUserMessaging platform implementation."""

    @pytest.mark.asyncio
    async def test_process_incoming_message_success(self):
        """Test successful AWS EUM message processing."""
        platform = AWSEndUserMessaging()

        message_event = MessageEvent(
            message_id="wamid.HBgLNTY5NDExNjIyNzgVAgASGBYzRUIwODFDOTFCRERFNDA5NjAzODZEAA==",
            conversation_id="whatsapp-conversation-+1234567890-session",
            sender_id="+1234567890",
            recipient_id="hotel-assistant",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            platform="aws-eum",
        )

        response = await platform.process_incoming_message(message_event)

        assert response.success is True
        assert response.message_id == "wamid.HBgLNTY5NDExNjIyNzgVAgASGBYzRUIwODFDOTFCRERFNDA5NjAzODZEAA=="

    @pytest.mark.asyncio
    async def test_update_message_status_read_success(self):
        """Test successful read status update."""
        with patch.dict(os.environ, {"EUM_SOCIAL_PHONE_NUMBER_ID": "phone-number-id-123"}):
            platform = AWSEndUserMessaging()

            with patch.object(platform, "_get_eum_social_client") as mock_client_getter:
                mock_client = Mock()
                mock_client.send_whatsapp_message.return_value = {"messageId": "receipt-123"}
                mock_client_getter.return_value = mock_client

                response = await platform.update_message_status("wamid.123", "read")

                assert response.success is True
                assert response.message_id == "wamid.123"
                mock_client.send_whatsapp_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_message_status_other_status(self):
        """Test non-read status update (no API call needed)."""
        platform = AWSEndUserMessaging()

        response = await platform.update_message_status("wamid.123", "delivered")

        assert response.success is True
        assert response.message_id == "wamid.123"

    @pytest.mark.asyncio
    async def test_update_message_status_missing_phone_id(self):
        """Test read status update without phone number ID."""
        with patch.dict(os.environ, {}, clear=True):
            platform = AWSEndUserMessaging()

            response = await platform.update_message_status("wamid.123", "read")

            assert response.success is False
            assert response.message_id == "wamid.123"
            assert "EUM_SOCIAL_PHONE_NUMBER_ID" in response.error

    @pytest.mark.asyncio
    async def test_send_response_success(self):
        """Test successful WhatsApp response sending."""
        with patch.dict(os.environ, {"EUM_SOCIAL_PHONE_NUMBER_ID": "phone-number-id-123"}):
            platform = AWSEndUserMessaging()

            with patch.object(platform, "_get_eum_social_client") as mock_client_getter:
                mock_client = Mock()
                mock_client.send_whatsapp_message.return_value = {"messageId": "msg-456"}
                mock_client_getter.return_value = mock_client

                response = await platform.send_response("whatsapp-conversation-+1234567890-session", "Hello")

                assert response.success is True
                assert response.message_id == "msg-456"
                mock_client.send_whatsapp_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful WhatsApp message sending."""
        with patch.dict(os.environ, {"EUM_SOCIAL_PHONE_NUMBER_ID": "phone-number-id-123"}):
            platform = AWSEndUserMessaging()

            with patch.object(platform, "_get_eum_social_client") as mock_client_getter:
                mock_client = Mock()
                mock_client.send_whatsapp_message.return_value = {"messageId": "msg-789"}
                mock_client_getter.return_value = mock_client

                response = await platform.send_message(
                    recipient_id="+1234567890",
                    content="Welcome!",
                )

                assert response.success is True
                assert response.message_id == "msg-789"

    @pytest.mark.asyncio
    async def test_update_message_status_multiple_ids_read(self):
        """Test read status update with multiple message IDs."""
        with patch.dict(os.environ, {"EUM_SOCIAL_PHONE_NUMBER_ID": "phone-number-id-123"}):
            platform = AWSEndUserMessaging()

            with patch.object(platform, "_get_eum_social_client") as mock_client_getter:
                mock_client = Mock()
                mock_client.send_whatsapp_message.return_value = {"messageId": "receipt-123"}
                mock_client_getter.return_value = mock_client

                message_ids = ["wamid.1", "wamid.2", "wamid.3"]
                response = await platform.update_message_status(message_ids, "read")

                assert response.success is True
                assert response.data["updated_count"] == 3
                assert response.data["message_ids"] == message_ids

                # Verify client was called for each message ID
                assert mock_client.send_whatsapp_message.call_count == 3

    @pytest.mark.asyncio
    async def test_update_message_status_multiple_ids_other_status(self):
        """Test non-read status update with multiple message IDs."""
        platform = AWSEndUserMessaging()

        message_ids = ["wamid.1", "wamid.2"]
        response = await platform.update_message_status(message_ids, "delivered")

        assert response.success is True
        assert response.data["updated_count"] == 2
        assert response.data["message_ids"] == message_ids
