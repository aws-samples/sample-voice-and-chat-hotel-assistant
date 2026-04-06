# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Base messaging platform interface."""

from abc import ABC, abstractmethod
from typing import Any

from ..models.messaging import MessageEvent, MessageResponse


class MessagingPlatform(ABC):
    """Base class for messaging platform integrations.

    This abstract base class defines the interface that all messaging
    platforms must implement for consistent message handling across
    different channels (web, SMS, WhatsApp, etc.).
    """

    @abstractmethod
    async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
        """Process incoming message from SNS/SQS.

        Args:
            message_event: The message event to process

        Returns:
            MessageResponse indicating success/failure
        """
        pass

    @abstractmethod
    async def update_message_status(self, message_id: str | list[str], status: str) -> MessageResponse:
        """Update message status.

        Args:
            message_id: ID of the message to update, or list of message IDs
            status: New status value

        Returns:
            MessageResponse indicating success/failure
        """
        pass

    @abstractmethod
    async def send_response(self, conversation_id: str, content: str) -> MessageResponse:
        """Send response message using conversation ID.

        Args:
            conversation_id: Conversation to send message to
            content: Message content to send

        Returns:
            MessageResponse with message details or error
        """
        pass

    @abstractmethod
    async def send_message(
        self,
        recipient_id: str,
        content: str,
        platform_metadata: dict[str, Any] = None,
    ) -> MessageResponse:
        """Send message to specific recipient.

        Args:
            recipient_id: Recipient identifier
            content: Message content
            platform_metadata: Platform-specific metadata

        Returns:
            MessageResponse with message details or error
        """
        pass
