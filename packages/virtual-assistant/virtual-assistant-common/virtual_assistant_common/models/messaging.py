# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared messaging models for hotel assistant components."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageStatus(str, Enum):
    """Valid message status values - matches chatbot-messaging-backend."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    WARNING = "warning"
    DELETED = "deleted"


class MessageEvent(BaseModel):
    """SNS message event for agent processing.

    This model represents the message data that flows through SNS/SQS
    for asynchronous agent processing.
    """

    model_config = {"populate_by_name": True}

    message_id: str = Field(alias="messageId", description="Unique identifier for the message")
    conversation_id: str = Field(
        alias="conversationId", description="Conversation identifier in format senderId#recipientId"
    )
    sender_id: str = Field(alias="senderId", description="Identifier of the message sender")
    recipient_id: str = Field(alias="recipientId", description="Identifier of the message recipient")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="ISO8601 timestamp when message was created")
    platform: str = Field(default="web", description="Platform source: web, twilio, aws-eum")
    platform_metadata: dict[str, Any] | None = Field(
        default=None, description="Platform-specific metadata (phone numbers, channel info, etc.)"
    )
    status: str | None = Field(default=None, description="Message status (sent, delivered, etc.)")
    model_id: str | None = Field(default=None, alias="modelId", description="Optional model override")
    temperature: float | None = Field(default=None, description="Optional temperature override")


@dataclass
class MessageGroup:
    """Group of messages from the same sender.

    This is a lightweight wrapper around a list of MessageEvent objects,
    providing convenient access to derived properties without duplicating data.
    """

    messages: list[MessageEvent]

    @property
    def sender_id(self) -> str:
        """Get sender ID from first message."""
        return self.messages[0].sender_id

    @property
    def conversation_id(self) -> str:
        """Get conversation ID from first message."""
        return self.messages[0].conversation_id

    @property
    def combined_content(self) -> str:
        """Combine message content with newlines."""
        return "\n".join(msg.content for msg in self.messages)

    @property
    def message_ids(self) -> list[str]:
        """Get all message IDs."""
        return [msg.message_id for msg in self.messages]

    @property
    def platform(self) -> str:
        """Get platform from first message."""
        return self.messages[0].platform


class AgentInvocationPayload(BaseModel):
    """Payload for AgentCore Runtime invocation."""

    prompt: str = Field(description="User message content to process")
    actor_id: str = Field(description="User/actor identifier")
    message_id: str = Field(description="Original message ID for status tracking")
    conversation_id: str = Field(description="Conversation identifier")
    model_id: str | None = Field(default=None, description="Optional model override")
    temperature: float | None = Field(default=None, description="Optional temperature override")


class PlatformMessage(BaseModel):
    """Abstract message format for different platforms."""

    content: str = Field(description="Message content")
    sender_id: str = Field(description="Sender identifier")
    recipient_id: str = Field(description="Recipient identifier")
    platform: str = Field(description="Platform identifier: web, twilio, aws-eum")
    platform_specific_data: dict[str, Any] | None = Field(
        default=None, description="Platform-specific data (phone numbers, webhook data, etc.)"
    )


class MessageResponse(BaseModel):
    """Standard response format for messaging operations."""

    success: bool = Field(description="Whether the operation was successful")
    message_id: str | None = Field(default=None, description="Message ID if applicable")
    error: str | None = Field(default=None, description="Error message if operation failed")
    data: dict[str, Any] | None = Field(default=None, description="Additional response data")


class StatusUpdateRequest(BaseModel):
    """Request format for message status updates."""

    message_id: str = Field(description="Message ID to update")
    status: MessageStatus = Field(description="New status value")
    platform: str = Field(default="web", description="Platform context")


class SendMessageRequest(BaseModel):
    """Request format for sending messages."""

    recipient_id: str = Field(description="Message recipient identifier")
    content: str = Field(description="Message content")
    conversation_id: str | None = Field(default=None, description="Optional conversation identifier (UUID format)")
    platform: str = Field(default="web", description="Platform to send through")
    platform_metadata: dict[str, Any] | None = Field(default=None, description="Platform-specific metadata")


class AgentCoreInvocationRequest(BaseModel):
    """Request format for invoking AgentCore Runtime."""

    prompt: str = Field(description="User message content to process")
    actor_id: str = Field(alias="actorId", description="User/actor identifier")
    message_ids: list[str] = Field(alias="messageIds", description="List of message IDs for status tracking")
    conversation_id: str = Field(alias="conversationId", description="Conversation identifier")
    model_id: str | None = Field(default=None, alias="modelId", description="Optional model override")
    temperature: float | None = Field(default=None, description="Optional temperature override")
    task_token: str | None = Field(
        default=None,
        alias="taskToken",
        description="Optional Step Functions task token for async callback. When present, the agent will send success/failure callbacks to Step Functions.",
    )


class AgentCoreInvocationResponse(BaseModel):
    """Response format from AgentCore Runtime invocation."""

    success: bool = Field(description="Whether the invocation was successful")
    message_id: str = Field(description="Original message ID")
    error: str | None = Field(default=None, description="Error message if invocation failed")
    invocation_id: str | None = Field(default=None, description="AgentCore invocation ID if successful")
    response_body: dict[str, Any] | None = Field(default=None, description="Parsed response body from agent")
