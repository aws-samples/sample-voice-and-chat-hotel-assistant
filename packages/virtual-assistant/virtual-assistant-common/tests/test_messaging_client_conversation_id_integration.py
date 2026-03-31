# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for messaging client conversation ID functionality."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from virtual_assistant_common.clients.messaging_client import MessagingClient


class TestMessagingClientConversationIdIntegration:
    """Integration tests for conversation ID functionality."""

    @pytest.fixture
    def client(self):
        """Create messaging client for testing."""
        return MessagingClient(api_endpoint="https://api.example.com")

    @pytest.mark.asyncio
    async def test_conversation_id_end_to_end_flow(self, client):
        """Test complete conversation ID flow from client to API."""
        conversation_id = str(uuid.uuid4())

        # Mock the HTTP client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "messageId": "msg-123",
            "conversationId": conversation_id,
            "senderId": "hotel-assistant",
            "recipientId": "user-123",
            "content": "Hello world",
            "status": "sent",
            "timestamp": "2024-01-01T00:00:00Z",
            "success": True,
        }
        mock_client.post.return_value = mock_response

        with (
            patch.object(client, "_get_client", return_value=mock_client),
            patch.object(client, "_get_auth_headers", return_value={"Authorization": "Bearer token"}),
        ):
            # Send message with conversation ID
            result = await client.send_message(
                recipient_id="user-123", content="Hello world", conversation_id=conversation_id
            )

            # Verify the API was called correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            # Check URL
            assert call_args[0][0] == "https://api.example.com/messages"

            # Check headers
            assert call_args[1]["headers"]["Authorization"] == "Bearer token"

            # Check request payload
            request_data = call_args[1]["json"]
            assert request_data["recipient_id"] == "user-123"
            assert request_data["content"] == "Hello world"

            assert request_data["conversation_id"] == conversation_id
            assert request_data["platform"] == "web"

            # Check response
            assert result["messageId"] == "msg-123"
            assert result["conversationId"] == conversation_id
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_conversation_id_none_flow(self, client):
        """Test conversation ID flow when None is provided."""
        # Mock the HTTP client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "messageId": "msg-456",
            "conversationId": "generated-uuid-789",  # Backend generates UUID
            "senderId": "hotel-assistant",
            "recipientId": "user-456",
            "content": "Hello without conversation ID",
            "status": "sent",
            "timestamp": "2024-01-01T00:00:00Z",
            "success": True,
        }
        mock_client.post.return_value = mock_response

        with (
            patch.object(client, "_get_client", return_value=mock_client),
            patch.object(client, "_get_auth_headers", return_value={}),
        ):
            # Send message without conversation ID
            result = await client.send_message(recipient_id="user-456", content="Hello without conversation ID")

            # Verify the API was called correctly
            call_args = mock_client.post.call_args
            request_data = call_args[1]["json"]

            # Conversation ID should be None in request
            assert request_data["conversation_id"] is None

            # But backend should return a generated UUID
            assert result["conversationId"] == "generated-uuid-789"

    @pytest.mark.asyncio
    async def test_multiple_messages_same_conversation(self, client):
        """Test sending multiple messages with the same conversation ID."""
        conversation_id = str(uuid.uuid4())

        # Mock the HTTP client and responses
        mock_client = AsyncMock()
        responses = []

        for i in range(3):
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "messageId": f"msg-{i}",
                "conversationId": conversation_id,
                "senderId": "hotel-assistant",
                "recipientId": "user-123",
                "content": f"Message {i}",
                "status": "sent",
                "timestamp": "2024-01-01T00:00:00Z",
                "success": True,
            }
            responses.append(mock_response)

        mock_client.post.side_effect = responses

        with (
            patch.object(client, "_get_client", return_value=mock_client),
            patch.object(client, "_get_auth_headers", return_value={}),
        ):
            # Send multiple messages with same conversation ID
            results = []
            for i in range(3):
                result = await client.send_message(
                    recipient_id="user-123", content=f"Message {i}", conversation_id=conversation_id
                )
                results.append(result)

            # Verify all messages were sent with same conversation ID
            assert len(results) == 3
            for i, result in enumerate(results):
                assert result["messageId"] == f"msg-{i}"
                assert result["conversationId"] == conversation_id

            # Verify all API calls used the same conversation ID
            assert mock_client.post.call_count == 3
            for call in mock_client.post.call_args_list:
                request_data = call[1]["json"]
                assert request_data["conversation_id"] == conversation_id

    @pytest.mark.asyncio
    async def test_conversation_id_with_custom_parameters(self, client):
        """Test conversation ID with custom sender and other parameters."""
        conversation_id = str(uuid.uuid4())

        # Mock the HTTP client and response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "messageId": "msg-custom",
            "conversationId": conversation_id,
            "senderId": "custom-sender",
            "recipientId": "user-789",
            "content": "Custom message",
            "status": "sent",
            "timestamp": "2024-01-01T00:00:00Z",
            "success": True,
        }
        mock_client.post.return_value = mock_response

        with (
            patch.object(client, "_get_client", return_value=mock_client),
            patch.object(client, "_get_auth_headers", return_value={}),
        ):
            # Send message with custom parameters and conversation ID
            result = await client.send_message(
                recipient_id="user-789",
                content="Custom message",
                conversation_id=conversation_id,
            )

            # Verify the API was called with all parameters
            call_args = mock_client.post.call_args
            request_data = call_args[1]["json"]

            assert request_data["recipient_id"] == "user-789"
            assert request_data["content"] == "Custom message"

            assert request_data["conversation_id"] == conversation_id

            # Check response
            assert result["messageId"] == "msg-custom"
            assert result["conversationId"] == conversation_id
            assert result["senderId"] == "custom-sender"
