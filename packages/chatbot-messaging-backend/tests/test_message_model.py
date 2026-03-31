# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for message data model and validation."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from chatbot_messaging_backend.models.message import (
    Message,
    MessageStatus,
    create_message,
    generate_conversation_id,
    generate_iso8601_timestamp,
    generate_message_id,
)


class TestMessageStatus:
    """Test MessageStatus enum."""

    def test_message_status_values(self):
        """Test that all expected status values are available."""
        assert MessageStatus.SENT == "sent"
        assert MessageStatus.DELIVERED == "delivered"
        assert MessageStatus.READ == "read"
        assert MessageStatus.FAILED == "failed"
        assert MessageStatus.WARNING == "warning"
        assert MessageStatus.DELETED == "deleted"


class TestMessage:
    """Test Message data model."""

    def test_valid_message_creation(self):
        """Test creating a valid message."""
        timestamp = generate_iso8601_timestamp()

        message = Message(
            message_id="test-message-id",
            conversation_id="sender123#recipient456",
            sender_id="sender123",
            recipient_id="recipient456",
            content="Hello, world!",
            status=MessageStatus.SENT,
            timestamp=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

        assert message.message_id == "test-message-id"
        assert message.conversation_id == "sender123#recipient456"
        assert message.sender_id == "sender123"
        assert message.recipient_id == "recipient456"
        assert message.content == "Hello, world!"
        assert message.status == MessageStatus.SENT
        assert message.timestamp == timestamp
        assert message.created_at == timestamp
        assert message.updated_at == timestamp

    def test_default_status(self):
        """Test that default status is SENT."""
        timestamp = generate_iso8601_timestamp()

        message = Message(
            message_id="test-id",
            conversation_id="sender#recipient",
            sender_id="sender",
            recipient_id="recipient",
            content="Test content",
            timestamp=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

        assert message.status == MessageStatus.SENT

    def test_message_id_validation(self):
        """Test message ID validation."""
        timestamp = generate_iso8601_timestamp()

        # Empty message ID should fail
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "String should have at least 1 character" in str(exc_info.value)

        # Whitespace-only message ID should fail
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="   ",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "Message ID cannot be empty" in str(exc_info.value)

    def test_conversation_id_validation(self):
        """Test conversation ID validation."""
        timestamp = generate_iso8601_timestamp()

        # Valid UUID format
        Message(
            message_id="test-id",
            conversation_id="550e8400-e29b-41d4-a716-446655440000",
            sender_id="sender",
            recipient_id="recipient",
            content="Test content",
            timestamp=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

        # Valid legacy format
        Message(
            message_id="test-id",
            conversation_id="sender#recipient",
            sender_id="sender",
            recipient_id="recipient",
            content="Test content",
            timestamp=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

        # Invalid format (neither UUID nor legacy)
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="senderrecipient",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "must be either a valid UUID or in format 'senderId#recipientId'" in str(exc_info.value)

        # Multiple # separators
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient#extra",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "exactly one '#' separator" in str(exc_info.value)

        # Empty sender part
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "Both sender and recipient parts must be non-empty" in str(exc_info.value)

        # Empty recipient part
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "Both sender and recipient parts must be non-empty" in str(exc_info.value)

    def test_user_id_validation(self):
        """Test sender and recipient ID validation."""
        timestamp = generate_iso8601_timestamp()

        # Empty sender ID
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient",
                sender_id="",
                recipient_id="recipient",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "String should have at least 1 character" in str(exc_info.value)

        # Empty recipient ID
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="",
                content="Test content",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "String should have at least 1 character" in str(exc_info.value)

    def test_content_validation(self):
        """Test message content validation."""
        timestamp = generate_iso8601_timestamp()

        # Empty content
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "String should have at least 1 character" in str(exc_info.value)

        # Whitespace-only content
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="   ",
                timestamp=timestamp,
                created_at=timestamp,
                updated_at=timestamp,
            )
        assert "Message content cannot be empty" in str(exc_info.value)

    def test_timestamp_validation(self):
        """Test ISO8601 timestamp validation."""
        valid_timestamp = generate_iso8601_timestamp()

        # Invalid timestamp format
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp="invalid-timestamp",
                created_at=valid_timestamp,
                updated_at=valid_timestamp,
            )
        assert "Invalid ISO8601 timestamp format" in str(exc_info.value)

        # Empty timestamp
        with pytest.raises(ValidationError) as exc_info:
            Message(
                message_id="test-id",
                conversation_id="sender#recipient",
                sender_id="sender",
                recipient_id="recipient",
                content="Test content",
                timestamp="",
                created_at=valid_timestamp,
                updated_at=valid_timestamp,
            )
        assert "Timestamp cannot be empty" in str(exc_info.value)

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item format."""
        timestamp = generate_iso8601_timestamp()

        message = Message(
            message_id="test-message-id",
            conversation_id="sender123#recipient456",
            sender_id="sender123",
            recipient_id="recipient456",
            content="Hello, world!",
            status=MessageStatus.READ,
            timestamp=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

        item = message.to_dynamodb_item()

        expected = {
            "conversationId": "sender123#recipient456",
            "timestamp": timestamp,
            "messageId": "test-message-id",
            "senderId": "sender123",
            "recipientId": "recipient456",
            "content": "Hello, world!",
            "status": "read",
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        assert item == expected

    def test_from_dynamodb_item(self):
        """Test creation from DynamoDB item."""
        timestamp = generate_iso8601_timestamp()

        item = {
            "conversationId": "sender123#recipient456",
            "timestamp": timestamp,
            "messageId": "test-message-id",
            "senderId": "sender123",
            "recipientId": "recipient456",
            "content": "Hello, world!",
            "status": "delivered",
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }

        message = Message.from_dynamodb_item(item)

        assert message.message_id == "test-message-id"
        assert message.conversation_id == "sender123#recipient456"
        assert message.sender_id == "sender123"
        assert message.recipient_id == "recipient456"
        assert message.content == "Hello, world!"
        assert message.status == MessageStatus.DELIVERED
        assert message.timestamp == timestamp
        assert message.created_at == timestamp
        assert message.updated_at == timestamp

    def test_to_sns_message(self):
        """Test conversion to SNS message format."""
        timestamp = generate_iso8601_timestamp()

        message = Message(
            message_id="test-message-id",
            conversation_id="sender123#recipient456",
            sender_id="sender123",
            recipient_id="recipient456",
            content="Hello, world!",
            status=MessageStatus.SENT,
            timestamp=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

        sns_message = message.to_sns_message()

        expected = {
            "messageId": "test-message-id",
            "conversationId": "sender123#recipient456",
            "senderId": "sender123",
            "recipientId": "recipient456",
            "content": "Hello, world!",
            "timestamp": timestamp,
            "status": "sent",
        }

        assert sns_message == expected


class TestUtilityFunctions:
    """Test utility functions."""

    def test_generate_message_id(self):
        """Test message ID generation."""
        message_id = generate_message_id()

        assert isinstance(message_id, str)
        assert len(message_id) > 0

        # Should generate unique IDs
        another_id = generate_message_id()
        assert message_id != another_id

    def test_generate_conversation_id(self):
        """Test conversation ID generation with lexicographic ordering."""
        # Test lexicographic ordering (recipient456 comes before sender123)
        conversation_id = generate_conversation_id("sender123", "recipient456")
        assert conversation_id == "recipient456#sender123"

        # Test with whitespace
        conversation_id = generate_conversation_id("  sender123  ", "  recipient456  ")
        assert conversation_id == "recipient456#sender123"

        # Test hotel-assistant special case (user -> assistant)
        conversation_id = generate_conversation_id("user123", "hotel-assistant")
        assert conversation_id == "user123#hotel-assistant"

        # Test hotel-assistant special case (assistant -> user)
        conversation_id = generate_conversation_id("hotel-assistant", "user123")
        assert conversation_id == "user123#hotel-assistant"

        # Test hotel-assistant-* variant (assistant with UUID -> user)
        conversation_id = generate_conversation_id("hotel-assistant-abc123", "user123")
        assert conversation_id == "user123#hotel-assistant"

        # Test hotel-assistant-* variant (user -> assistant with UUID)
        conversation_id = generate_conversation_id("user123", "hotel-assistant-abc123")
        assert conversation_id == "user123#hotel-assistant"

        # Test validation
        with pytest.raises(ValueError) as exc_info:
            generate_conversation_id("", "recipient")
        assert "Sender ID cannot be empty" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            generate_conversation_id("sender", "")
        assert "Recipient ID cannot be empty" in str(exc_info.value)

    def test_generate_iso8601_timestamp(self):
        """Test ISO8601 timestamp generation."""
        timestamp = generate_iso8601_timestamp()

        assert isinstance(timestamp, str)
        assert len(timestamp) > 0

        # Should be parseable as datetime
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)

        # Should be recent (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = abs((now - parsed).total_seconds())
        assert time_diff < 60  # Within 1 minute

    def test_create_message(self):
        """Test message creation utility."""
        message = create_message(sender_id="sender123", recipient_id="recipient456", content="Hello, world!")

        assert message.sender_id == "sender123"
        assert message.recipient_id == "recipient456"
        assert message.content == "Hello, world!"
        # Should now be UUID format
        import uuid

        uuid.UUID(message.conversation_id)  # This will raise ValueError if not valid UUID
        assert message.status == MessageStatus.SENT
        assert len(message.message_id) > 0
        assert len(message.timestamp) > 0
        assert message.created_at == message.timestamp
        assert message.updated_at == message.timestamp

    def test_create_message_with_conversation_id(self):
        """Test message creation with provided conversation ID."""
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        message = create_message(
            sender_id="sender123", recipient_id="recipient456", content="Hello, world!", conversation_id=conversation_id
        )

        assert message.sender_id == "sender123"
        assert message.recipient_id == "recipient456"
        assert message.content == "Hello, world!"
        assert message.conversation_id == conversation_id
        assert message.status == MessageStatus.SENT

        # Test with custom message ID and status
        custom_message = create_message(
            sender_id="sender123",
            recipient_id="recipient456",
            content="Custom message",
            message_id="custom-id",
            status=MessageStatus.DELIVERED,
        )

        assert custom_message.message_id == "custom-id"
        assert custom_message.status == MessageStatus.DELIVERED
