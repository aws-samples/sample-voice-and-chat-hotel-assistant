# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Message data model and validation."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MessageStatus(str, Enum):
    """Valid message status values."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    WARNING = "warning"
    DELETED = "deleted"


class Message(BaseModel):
    """Message data model with validation.

    Represents a message in the chatbot messaging system with all required
    fields and validation rules.
    """

    message_id: str = Field(description="Unique identifier for the message", min_length=1, max_length=255)
    conversation_id: str = Field(
        description="Conversation identifier (UUID format or legacy senderId#recipientId)", min_length=1, max_length=255
    )
    sender_id: str = Field(description="Identifier of the message sender", min_length=1, max_length=255)
    recipient_id: str = Field(description="Identifier of the message recipient", min_length=1, max_length=255)
    content: str = Field(
        description="Message content",
        min_length=1,
        max_length=10000,  # Reasonable limit for message content
    )
    status: MessageStatus = Field(description="Current status of the message", default=MessageStatus.SENT)
    timestamp: str = Field(description="ISO8601 timestamp used as DynamoDB sort key")
    created_at: str = Field(description="ISO8601 timestamp when message was created (immutable)")
    updated_at: str = Field(description="ISO8601 timestamp when message was last updated")

    @field_validator("message_id")
    @classmethod
    def validate_message_id(cls, v: str) -> str:
        """Validate message ID format."""
        if not v or not v.strip():
            raise ValueError("Message ID cannot be empty")
        return v.strip()

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: str) -> str:
        """Validate conversation ID format (UUID or legacy senderId#recipientId)."""
        if not v or not v.strip():
            raise ValueError("Conversation ID cannot be empty")

        v = v.strip()

        # Check if it's a valid UUID format
        try:
            uuid.UUID(v)
            return v  # Valid UUID format
        except ValueError:
            pass  # Not a UUID, check legacy format

        # Check legacy format (senderId#recipientId)
        if "#" not in v:
            raise ValueError("Conversation ID must be either a valid UUID or in format 'senderId#recipientId'")

        parts = v.split("#")
        if len(parts) != 2:
            raise ValueError("Conversation ID must contain exactly one '#' separator")

        sender_part, recipient_part = parts
        if not sender_part.strip() or not recipient_part.strip():
            raise ValueError("Both sender and recipient parts must be non-empty")

        return v

    @field_validator("sender_id", "recipient_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate sender and recipient IDs."""
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")
        return v.strip()

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate message content."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()

    @field_validator("timestamp", "created_at", "updated_at")
    @classmethod
    def validate_iso8601_timestamp(cls, v: str) -> str:
        """Validate ISO8601 timestamp format."""
        if not v or not v.strip():
            raise ValueError("Timestamp cannot be empty")

        v = v.strip()
        try:
            # Parse to validate ISO8601 format
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid ISO8601 timestamp format: {e}") from e

        return v

    def to_dynamodb_item(self) -> dict:
        """Convert message to DynamoDB item format.

        Returns:
            Dictionary suitable for DynamoDB operations
        """
        return {
            "conversationId": self.conversation_id,  # Partition key
            "timestamp": self.timestamp,  # Sort key
            "messageId": self.message_id,
            "senderId": self.sender_id,
            "recipientId": self.recipient_id,
            "content": self.content,
            "status": self.status.value,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Message":
        """Create Message from DynamoDB item.

        Args:
            item: DynamoDB item dictionary

        Returns:
            Message instance
        """
        return cls(
            message_id=item["messageId"],
            conversation_id=item["conversationId"],
            sender_id=item["senderId"],
            recipient_id=item["recipientId"],
            content=item["content"],
            status=MessageStatus(item["status"]),
            timestamp=item["timestamp"],
            created_at=item["createdAt"],
            updated_at=item["updatedAt"],
        )

    def to_sns_message(self) -> dict:
        """Convert message to SNS message format.

        Returns:
            Dictionary suitable for SNS publishing
        """
        return {
            "messageId": self.message_id,
            "conversationId": self.conversation_id,
            "senderId": self.sender_id,
            "recipientId": self.recipient_id,
            "content": self.content,
            "timestamp": self.timestamp,
            "status": self.status.value,
        }


def generate_message_id() -> str:
    """Generate a unique message ID.

    Returns:
        UUID4 string for message identification
    """
    return str(uuid.uuid4())


def generate_conversation_id(sender_id: str, recipient_id: str) -> str:
    """Generate conversation ID from sender and recipient.

    Creates a normalized conversation ID that is consistent regardless of message direction.
    For conversations involving 'hotel-assistant', the format is always 'userId#hotel-assistant'.
    This handles cases where the assistant may have a UUID as sender_id but recipient_id is 'hotel-assistant'.

    Args:
        sender_id: Identifier of the sender
        recipient_id: Identifier of the recipient

    Returns:
        Normalized conversation ID
    """
    if not sender_id or not sender_id.strip():
        raise ValueError("Sender ID cannot be empty")
    if not recipient_id or not recipient_id.strip():
        raise ValueError("Recipient ID cannot be empty")

    sender_id = sender_id.strip()
    recipient_id = recipient_id.strip()

    # Special case: conversations with hotel-assistant
    # Always use the non-assistant ID first, then #hotel-assistant
    if sender_id == "hotel-assistant" or sender_id.startswith("hotel-assistant-"):
        return f"{recipient_id}#hotel-assistant"
    elif recipient_id == "hotel-assistant" or recipient_id.startswith("hotel-assistant-"):
        return f"{sender_id}#hotel-assistant"
    else:
        # For other conversations, use lexicographic ordering for consistency
        participants = sorted([sender_id, recipient_id])
        return f"{participants[0]}#{participants[1]}"


def generate_iso8601_timestamp() -> str:
    """Generate current timestamp in ISO8601 format.

    Returns:
        Current UTC timestamp in ISO8601 format
    """
    return datetime.now(timezone.utc).isoformat()


def create_message(
    sender_id: str,
    recipient_id: str,
    content: str,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
    status: MessageStatus = MessageStatus.SENT,
) -> Message:
    """Create a new message with generated timestamps and IDs.

    Args:
        sender_id: Identifier of the sender
        recipient_id: Identifier of the recipient
        content: Message content
        conversation_id: Optional conversation ID (UUID format, generated if not provided)
        message_id: Optional message ID (generated if not provided)
        status: Message status (defaults to SENT)

    Returns:
        New Message instance with all required fields
    """
    if message_id is None:
        message_id = generate_message_id()

    # Use provided conversation_id or generate UUID
    if conversation_id is None:
        conversation_id = str(uuid.uuid4())

    timestamp = generate_iso8601_timestamp()

    return Message(
        message_id=message_id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content,
        status=status,
        timestamp=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
