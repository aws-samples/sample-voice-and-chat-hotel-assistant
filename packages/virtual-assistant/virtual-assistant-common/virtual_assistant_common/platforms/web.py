# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Web platform messaging implementation."""

import logging
from typing import Any

from ..clients.messaging_client import MessagingClient
from ..models.messaging import MessageEvent, MessageResponse
from .base import MessagingPlatform

logger = logging.getLogger(__name__)


class WebMessaging(MessagingPlatform):
    """Web interface messaging implementation.

    Handles messaging for the web interface by delegating to the
    messaging API client. This platform is fully implemented since
    it uses the existing chatbot-messaging-backend.
    """

    def __init__(self):
        """Initialize web messaging platform."""
        self._messaging_client = None

    @property
    def messaging_client(self) -> MessagingClient:
        """Lazy initialization of messaging client."""
        if self._messaging_client is None:
            self._messaging_client = MessagingClient()
        return self._messaging_client

    @messaging_client.setter
    def messaging_client(self, client: MessagingClient) -> None:
        """Set messaging client (primarily for testing)."""
        self._messaging_client = client

    async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
        """Process web message - already handled by messaging API.

        For web messages, the processing is already handled by the
        chatbot-messaging-backend API, so this is a no-op.

        Args:
            message_event: The message event to process

        Returns:
            Success response since web messages are pre-processed
        """
        logger.info(f"Web message {message_event.message_id} already processed by messaging API")
        return MessageResponse(
            success=True, message_id=message_event.message_id, data={"platform": "web", "status": "already_processed"}
        )

    async def update_message_status(self, message_id: str | list[str], status: str) -> MessageResponse:
        """Update message status via messaging API.

        Args:
            message_id: ID of the message to update, or list of message IDs
            status: New status value

        Returns:
            MessageResponse indicating success/failure
        """
        try:
            # Handle both single message ID and list of message IDs
            message_ids = [message_id] if isinstance(message_id, str) else message_id

            # Update status for all message IDs
            results = []
            for msg_id in message_ids:
                result = await self.messaging_client.update_message_status(msg_id, status)
                results.append(result)

            # Return success if all updates succeeded
            return MessageResponse(
                success=True,
                message_id=message_ids[0] if len(message_ids) == 1 else None,
                data={"updated_count": len(message_ids), "message_ids": message_ids, "results": results},
            )
        except Exception as e:
            logger.error(f"Failed to update message status for {message_id}: {e}")
            return MessageResponse(
                success=False, message_id=message_id if isinstance(message_id, str) else None, error=str(e)
            )

    async def send_response(self, conversation_id: str, content: str) -> MessageResponse:
        """Send response via messaging API.

        Args:
            conversation_id: Conversation to send message to (may be senderId#recipientId format)
            content: Message content to send

        Returns:
            MessageResponse with message details or error
        """
        try:
            # Extract recipient from conversation ID (format: userId#hotel-assistant or userId#clientId)
            if "#" in conversation_id:
                parts = conversation_id.split("#")
                # Find the non-assistant part as recipient
                recipient_id = parts[0] if parts[1] == "hotel-assistant" else parts[1]
            else:
                # Fallback - use conversation_id as recipient
                recipient_id = conversation_id

            result = await self.messaging_client.send_message(
                recipient_id=recipient_id, content=content, conversation_id=conversation_id
            )
            return MessageResponse(success=True, message_id=result.get("messageId"), data=result)
        except Exception as e:
            logger.error(f"Failed to send response to conversation {conversation_id}: {e}")
            return MessageResponse(success=False, error=str(e))

    async def send_message(
        self,
        recipient_id: str,
        content: str,
        platform_metadata: dict[str, Any] = None,
    ) -> MessageResponse:
        """Send message via messaging API.

        Args:
            recipient_id: Recipient identifier
            content: Message content
            platform_metadata: Platform-specific metadata (ignored for web)

        Returns:
            MessageResponse with message details or error
        """
        try:
            result = await self.messaging_client.send_message(recipient_id=recipient_id, content=content)
            return MessageResponse(success=True, message_id=result.get("messageId"), data=result)
        except Exception as e:
            logger.error(f"Failed to send message to {recipient_id}: {e}")
            return MessageResponse(success=False, error=str(e))
