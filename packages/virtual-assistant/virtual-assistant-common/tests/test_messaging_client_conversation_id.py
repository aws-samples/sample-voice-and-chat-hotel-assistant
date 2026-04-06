# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for messaging client conversation ID functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from virtual_assistant_common.clients.messaging_client import MessagingClient
from virtual_assistant_common.models.messaging import SendMessageRequest


class TestMessagingClientConversationId:
    """Test MessagingClient conversation ID functionality."""

    @pytest.fixture
    def client(self):
        """Create messaging client for testing."""
        return MessagingClient(api_endpoint="https://api.example.com")

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"messageId": "msg-123", "conversationId": "conv-456", "success": True}
        mock_client.post.return_value = mock_response
        return mock_client, mock_response

    @pytest.mark.asyncio
    async def test_send_message_without_conversation_id(self, client, mock_http_client):
        """Test sending message without conversation ID."""
        mock_client, mock_response = mock_http_client

        with (
            patch.object(client, "_get_client", return_value=mock_client),
            patch.object(client, "_get_auth_headers", return_value={}),
        ):
            result = await client.send_message(recipient_id="user-123", content="Hello world")

            # Verify API call was made correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args

            # Check URL
            assert call_args[0][0] == "https://api.example.com/messages"

            # Check request data
            request_data = call_args[1]["json"]
            assert request_data["recipient_id"] == "user-123"
            assert request_data["content"] == "Hello world"
            assert request_data["conversation_id"] is None

            # Check response
            assert result["messageId"] == "msg-123"
            assert result["conversationId"] == "conv-456"

    def test_send_message_request_model_without_conversation_id(self):
        """Test SendMessageRequest model without conversation ID."""
        request = SendMessageRequest(recipient_id="user-123", content="Hello world")

        assert request.recipient_id == "user-123"
        assert request.content == "Hello world"
        assert request.conversation_id is None  # default value
        assert request.platform == "web"  # default value
