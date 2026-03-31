# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the MessageService class.

These tests focus on the business logic in the service layer,
testing the service methods directly with mocked dependencies.
"""

from unittest.mock import Mock, patch

import pytest

from chatbot_messaging_backend.models.message import MessageStatus
from chatbot_messaging_backend.services.message_service import MessageService
from chatbot_messaging_backend.utils.repository import MessageRepository
from chatbot_messaging_backend.utils.sns_publisher import SNSPublisher


class TestMessageService:
    """Test cases for the MessageService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_repository = Mock(spec=MessageRepository)
        self.mock_sns_publisher = Mock(spec=SNSPublisher)
        self.service = MessageService(repository=self.mock_repository, sns_publisher=self.mock_sns_publisher)

    def test_service_initialization(self):
        """Test that MessageService initializes correctly."""
        assert self.service.repository == self.mock_repository
        assert self.service.sns_publisher == self.mock_sns_publisher

    @patch("chatbot_messaging_backend.services.message_service.create_message")
    def test_send_message_success(self, mock_create_message):
        """Test successful message sending through service."""
        # Setup mocks
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_message.to_sns_message.return_value = {
            "messageId": "msg-123",
            "conversationId": "user123#user456",
            "senderId": "user123",
            "recipientId": "user456",
            "content": "Hello, world!",
            "timestamp": "2023-01-01T12:00:00Z",
            "status": "sent",
        }

        mock_create_message.return_value = mock_message
        self.mock_repository.create_message.return_value = mock_message
        self.mock_sns_publisher.publish_message.return_value = True

        # Call service method
        result = self.service.send_message(sender_id="user123", recipient_id="user456", content="Hello, world!")

        # Verify result
        assert result == mock_message

        # Verify mocks were called correctly
        mock_create_message.assert_called_once_with(
            sender_id="user123", recipient_id="user456", content="Hello, world!", conversation_id=None
        )
        self.mock_repository.create_message.assert_called_once_with(mock_message)
        self.mock_sns_publisher.publish_message.assert_called_once_with(mock_message.to_sns_message.return_value)

    @patch("chatbot_messaging_backend.services.message_service.create_message")
    def test_send_message_invalid_data(self, mock_create_message):
        """Test send message with invalid data raises ValueError."""
        # Setup mock to raise ValueError
        mock_create_message.side_effect = ValueError("Invalid recipient ID")

        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Invalid message data: Invalid recipient ID"):
            self.service.send_message(sender_id="user123", recipient_id="", content="Hello, world!")

        # Verify repository and SNS were not called
        self.mock_repository.create_message.assert_not_called()
        self.mock_sns_publisher.publish_message.assert_not_called()

    @patch("chatbot_messaging_backend.services.message_service.create_message")
    def test_send_message_repository_failure(self, mock_create_message):
        """Test send message with repository failure raises RuntimeError."""
        # Setup mocks
        mock_message = Mock()
        mock_create_message.return_value = mock_message
        self.mock_repository.create_message.side_effect = Exception("Database error")

        # Call service method and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to store message"):
            self.service.send_message(sender_id="user123", recipient_id="user456", content="Hello, world!")

        # Verify SNS was not called
        self.mock_sns_publisher.publish_message.assert_not_called()

    @patch("chatbot_messaging_backend.services.message_service.create_message")
    def test_send_message_sns_failure_raises_error(self, mock_create_message):
        """Test send message with SNS failure raises RuntimeError."""
        # Setup mocks
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.to_sns_message.return_value = {}
        mock_create_message.return_value = mock_message
        self.mock_repository.create_message.return_value = mock_message
        self.mock_sns_publisher.publish_message.return_value = False  # SNS failure

        # Call service method and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to publish message"):
            self.service.send_message(sender_id="user123", recipient_id="user456", content="Hello, world!")

    @patch("chatbot_messaging_backend.services.message_service.create_message")
    def test_send_message_sns_exception_does_not_fail(self, mock_create_message):
        """Test that SNS exceptions don't fail the entire operation."""
        # Setup mocks
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.to_sns_message.return_value = {}
        mock_create_message.return_value = mock_message
        self.mock_repository.create_message.return_value = mock_message
        self.mock_sns_publisher.publish_message.side_effect = Exception("SNS error")

        # Call service method - should not raise exception
        result = self.service.send_message(sender_id="user123", recipient_id="user456", content="Hello, world!")

        # Verify result is still returned
        assert result == mock_message

    @patch("chatbot_messaging_backend.services.message_service.generate_iso8601_timestamp")
    def test_update_message_status_success(self, mock_generate_timestamp):
        """Test successful message status update through service."""
        # Setup mocks
        mock_timestamp = "2023-01-01T12:30:00Z"
        mock_generate_timestamp.return_value = mock_timestamp

        mock_updated_message = Mock()
        mock_updated_message.message_id = "msg-123"
        mock_updated_message.status = MessageStatus.READ
        mock_updated_message.updated_at = mock_timestamp
        self.mock_repository.update_message_status.return_value = mock_updated_message

        # Call service method
        result = self.service.update_message_status(message_id="msg-123", status=MessageStatus.READ)

        # Verify result
        assert result == mock_updated_message

        # Verify mocks were called correctly
        mock_generate_timestamp.assert_called_once()
        self.mock_repository.update_message_status.assert_called_once_with(
            message_id="msg-123", status=MessageStatus.READ, updated_at=mock_timestamp
        )

    def test_update_message_status_empty_message_id(self):
        """Test update message status with empty message ID raises ValueError."""
        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Message ID cannot be empty"):
            self.service.update_message_status(message_id="", status=MessageStatus.READ)

        # Verify repository was not called
        self.mock_repository.update_message_status.assert_not_called()

    def test_update_message_status_whitespace_message_id(self):
        """Test update message status with whitespace-only message ID raises ValueError."""
        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Message ID cannot be empty"):
            self.service.update_message_status(message_id="   ", status=MessageStatus.READ)

        # Verify repository was not called
        self.mock_repository.update_message_status.assert_not_called()

    @patch("chatbot_messaging_backend.services.message_service.generate_iso8601_timestamp")
    def test_update_message_status_not_found(self, mock_generate_timestamp):
        """Test update message status when message is not found."""
        # Setup mocks
        mock_timestamp = "2023-01-01T12:30:00Z"
        mock_generate_timestamp.return_value = mock_timestamp
        self.mock_repository.update_message_status.return_value = None  # Message not found

        # Call service method
        result = self.service.update_message_status(message_id="msg-123", status=MessageStatus.READ)

        # Verify result is None
        assert result is None

        # Verify repository was called correctly
        self.mock_repository.update_message_status.assert_called_once_with(
            message_id="msg-123", status=MessageStatus.READ, updated_at=mock_timestamp
        )

    @patch("chatbot_messaging_backend.services.message_service.generate_iso8601_timestamp")
    def test_update_message_status_repository_failure(self, mock_generate_timestamp):
        """Test update message status with repository failure raises RuntimeError."""
        # Setup mocks
        mock_timestamp = "2023-01-01T12:30:00Z"
        mock_generate_timestamp.return_value = mock_timestamp
        self.mock_repository.update_message_status.side_effect = Exception("Database error")

        # Call service method and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to update message status"):
            self.service.update_message_status(message_id="msg-123", status=MessageStatus.READ)

    def test_update_message_status_valid_statuses(self):
        """Test update message status with all valid status values."""
        valid_statuses = [
            MessageStatus.SENT,
            MessageStatus.DELIVERED,
            MessageStatus.READ,
            MessageStatus.FAILED,
            MessageStatus.WARNING,
            MessageStatus.DELETED,
        ]

        for status in valid_statuses:
            # Reset mock for each iteration
            self.mock_repository.reset_mock()

            # Setup mock
            mock_updated_message = Mock()
            mock_updated_message.status = status
            self.mock_repository.update_message_status.return_value = mock_updated_message

            with patch("chatbot_messaging_backend.services.message_service.generate_iso8601_timestamp"):
                # Call service method
                result = self.service.update_message_status(message_id="msg-123", status=status)

                # Verify result
                assert result == mock_updated_message
                assert result.status == status

    @patch("chatbot_messaging_backend.services.message_service.create_message")
    def test_send_message_logs_operations(self, mock_create_message):
        """Test that send_message logs important operations."""
        # Setup mocks
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.to_sns_message.return_value = {}
        mock_create_message.return_value = mock_message
        self.mock_repository.create_message.return_value = mock_message
        self.mock_sns_publisher.publish_message.return_value = True

        # Call service method
        with patch("chatbot_messaging_backend.services.message_service.logger") as mock_logger:
            self.service.send_message(sender_id="user123", recipient_id="user456", content="Hello, world!")

            # Verify logging calls were made
            assert mock_logger.info.call_count >= 3  # At least 3 info logs expected
            assert mock_logger.warning.call_count == 0  # No warnings expected for success case

    @patch("chatbot_messaging_backend.services.message_service.generate_iso8601_timestamp")
    def test_update_message_status_logs_operations(self, mock_generate_timestamp):
        """Test that update_message_status logs important operations."""
        # Setup mocks
        mock_timestamp = "2023-01-01T12:30:00Z"
        mock_generate_timestamp.return_value = mock_timestamp
        mock_updated_message = Mock()
        mock_updated_message.message_id = "msg-123"
        mock_updated_message.status = MessageStatus.READ
        self.mock_repository.update_message_status.return_value = mock_updated_message

        # Call service method
        with patch("chatbot_messaging_backend.services.message_service.logger") as mock_logger:
            self.service.update_message_status(message_id="msg-123", status=MessageStatus.READ)

            # Verify logging calls were made
            assert mock_logger.info.call_count >= 2  # At least 2 info logs expected
            assert mock_logger.warning.call_count == 0  # No warnings expected for success case

    def test_get_messages_success(self):
        """Test successful message retrieval through service."""
        # Setup mocks
        mock_messages = [Mock(), Mock(), Mock()]
        for i, msg in enumerate(mock_messages):
            msg.message_id = f"msg-{i}"
            msg.conversation_id = "user123#user456"
            msg.timestamp = f"2023-01-01T12:0{i}:00Z"

        # Return 3 messages (limit is 5, so no more messages)
        self.mock_repository.query_messages.return_value = mock_messages

        # Call service method
        messages, has_more = self.service.get_messages(conversation_id="user123#user456", limit=5)

        # Verify result
        assert messages == mock_messages
        assert has_more is False

        # Verify repository was called correctly
        self.mock_repository.query_messages.assert_called_once_with(
            conversation_id="user123#user456",
            since_timestamp=None,
            limit=6,  # limit + 1
        )

    def test_get_messages_with_timestamp_filter(self):
        """Test message retrieval with timestamp filtering."""
        # Setup mocks
        mock_messages = [Mock(), Mock()]
        self.mock_repository.query_messages.return_value = mock_messages

        # Call service method with timestamp filter
        messages, has_more = self.service.get_messages(
            conversation_id="user123#user456", since_timestamp="2023-01-01T12:00:00Z", limit=10
        )

        # Verify result
        assert messages == mock_messages
        assert has_more is False

        # Verify repository was called correctly
        self.mock_repository.query_messages.assert_called_once_with(
            conversation_id="user123#user456", since_timestamp="2023-01-01T12:00:00Z", limit=11
        )

    def test_get_messages_has_more_true(self):
        """Test message retrieval when there are more messages available."""
        # Setup mocks - return limit + 1 messages to indicate more are available
        mock_messages = [Mock() for _ in range(6)]  # 6 messages for limit of 5
        self.mock_repository.query_messages.return_value = mock_messages

        # Call service method
        messages, has_more = self.service.get_messages(conversation_id="user123#user456", limit=5)

        # Verify result - should return only 5 messages but has_more should be True
        assert len(messages) == 5
        assert messages == mock_messages[:5]  # First 5 messages
        assert has_more is True

        # Verify repository was called correctly
        self.mock_repository.query_messages.assert_called_once_with(
            conversation_id="user123#user456", since_timestamp=None, limit=6
        )

    def test_get_messages_empty_conversation_id(self):
        """Test get messages with empty conversation ID raises ValueError."""
        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Conversation ID cannot be empty"):
            self.service.get_messages(conversation_id="", limit=10)

        # Verify repository was not called
        self.mock_repository.query_messages.assert_not_called()

    def test_get_messages_whitespace_conversation_id(self):
        """Test get messages with whitespace-only conversation ID raises ValueError."""
        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Conversation ID cannot be empty"):
            self.service.get_messages(conversation_id="   ", limit=10)

        # Verify repository was not called
        self.mock_repository.query_messages.assert_not_called()

    def test_get_messages_invalid_limit_zero(self):
        """Test get messages with zero limit raises ValueError."""
        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Limit must be greater than 0"):
            self.service.get_messages(conversation_id="user123#user456", limit=0)

        # Verify repository was not called
        self.mock_repository.query_messages.assert_not_called()

    def test_get_messages_invalid_limit_negative(self):
        """Test get messages with negative limit raises ValueError."""
        # Call service method and expect ValueError
        with pytest.raises(ValueError, match="Limit must be greater than 0"):
            self.service.get_messages(conversation_id="user123#user456", limit=-5)

        # Verify repository was not called
        self.mock_repository.query_messages.assert_not_called()

    def test_get_messages_limit_too_high(self):
        """Test get messages with limit too high gets capped at 100."""
        # Setup mocks
        mock_messages = [Mock() for _ in range(50)]
        self.mock_repository.query_messages.return_value = mock_messages

        # Call service method with high limit
        messages, has_more = self.service.get_messages(conversation_id="user123#user456", limit=200)

        # Verify result
        assert messages == mock_messages
        assert has_more is False

        # Verify repository was called with capped limit
        self.mock_repository.query_messages.assert_called_once_with(
            conversation_id="user123#user456",
            since_timestamp=None,
            limit=101,  # 100 + 1
        )

    def test_get_messages_repository_failure(self):
        """Test get messages with repository failure raises RuntimeError."""
        # Setup mock to raise exception
        self.mock_repository.query_messages.side_effect = Exception("Database error")

        # Call service method and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to retrieve messages"):
            self.service.get_messages(conversation_id="user123#user456", limit=10)

    def test_get_messages_default_limit(self):
        """Test get messages with default limit."""
        # Setup mocks
        mock_messages = [Mock() for _ in range(10)]
        self.mock_repository.query_messages.return_value = mock_messages

        # Call service method without specifying limit
        messages, has_more = self.service.get_messages(conversation_id="user123#user456")

        # Verify result
        assert messages == mock_messages
        assert has_more is False

        # Verify repository was called with default limit
        self.mock_repository.query_messages.assert_called_once_with(
            conversation_id="user123#user456",
            since_timestamp=None,
            limit=51,  # 50 + 1
        )

    def test_get_messages_logs_operations(self):
        """Test that get_messages logs important operations."""
        # Setup mocks
        mock_messages = [Mock(), Mock()]
        self.mock_repository.query_messages.return_value = mock_messages

        # Call service method
        with patch("chatbot_messaging_backend.services.message_service.logger") as mock_logger:
            self.service.get_messages(conversation_id="user123#user456", limit=10)

            # Verify logging calls were made
            assert mock_logger.info.call_count >= 2  # At least 2 info logs expected
            assert mock_logger.warning.call_count == 0  # No warnings expected for success case
