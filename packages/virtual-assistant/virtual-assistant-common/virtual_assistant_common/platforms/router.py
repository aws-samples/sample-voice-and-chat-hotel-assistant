# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Platform routing logic for handling different message sources."""

import logging
import os
from typing import Any

from ..models.messaging import MessageEvent, MessageResponse
from .aws_eum import AWSEndUserMessaging
from .base import MessagingPlatform
from .twilio import TwilioMessaging
from .web import WebMessaging

logger = logging.getLogger(__name__)


class PlatformRouter:
    """Routes messages to appropriate platform handlers.

    This router automatically determines which messaging platform to use
    based on environment variables. If EUM Social environment variables
    are present, it uses the aws-eum platform; otherwise, it uses the web platform.
    """

    def __init__(self):
        """Initialize platform router with automatic platform detection."""
        self._platforms: dict[str, MessagingPlatform] = {}
        self._platform_classes: dict[str, type[MessagingPlatform]] = {
            "web": WebMessaging,
            "twilio": TwilioMessaging,
            "aws-eum": AWSEndUserMessaging,
        }

        # Determine current platform based on environment variables
        self._current_platform = self._detect_current_platform()
        logger.debug(f"Platform router initialized with current platform: {self._current_platform}")

    def _detect_current_platform(self) -> str:
        """Detect the current platform based on environment variables.

        Returns:
            Platform name to use (aws-eum if EUM Social configured, otherwise web)
        """
        # Check for EUM Social configuration
        eum_phone_number_id = os.environ.get("EUM_SOCIAL_PHONE_NUMBER_ID")

        if eum_phone_number_id:
            logger.debug("EUM Social configuration detected - using aws-eum platform")
            return "aws-eum"
        else:
            logger.debug("No EUM Social configuration - using web platform")
            return "web"

    def get_platform(self, platform_name: str) -> MessagingPlatform:
        """Get platform handler by name.

        Args:
            platform_name: Name of the platform (web, twilio, aws-eum)

        Returns:
            MessagingPlatform instance for the specified platform

        Raises:
            ValueError: If platform is not supported
        """
        if platform_name not in self._platform_classes:
            available = ", ".join(self._platform_classes.keys())
            raise ValueError(f"Unsupported platform '{platform_name}'. Available: {available}")

        # Lazy load platform instance
        if platform_name not in self._platforms:
            platform_class = self._platform_classes[platform_name]
            self._platforms[platform_name] = platform_class()
            logger.debug(f"Initialized {platform_name} platform instance")

        return self._platforms[platform_name]

    async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
        """Route incoming message to current platform handler.

        Args:
            message_event: The message event to process

        Returns:
            MessageResponse from the platform handler
        """
        try:
            platform = self.get_platform(self._current_platform)
            logger.debug(f"Processing message {message_event.message_id} via {self._current_platform} platform")
            return await platform.process_incoming_message(message_event)
        except ValueError as e:
            logger.error(f"Platform routing error for message {message_event.message_id}: {e}")
            return MessageResponse(
                success=False, message_id=message_event.message_id, error=f"Platform routing error: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error processing message {message_event.message_id}: {e}")
            return MessageResponse(success=False, message_id=message_event.message_id, error=f"Processing error: {e}")

    async def update_message_status(self, message_id: str | list[str], status: str) -> MessageResponse:
        """Route message status update to current platform.

        Args:
            message_id: ID of the message to update, or list of message IDs
            status: New status value

        Returns:
            MessageResponse from the platform handler
        """
        try:
            platform_handler = self.get_platform(self._current_platform)
            logger.debug(f"Updating message {message_id} status to {status} via {self._current_platform} platform")
            return await platform_handler.update_message_status(message_id, status)
        except ValueError as e:
            logger.error(f"Platform routing error for status update {message_id}: {e}")
            return MessageResponse(
                success=False,
                message_id=message_id if isinstance(message_id, str) else None,
                error=f"Platform routing error: {e}",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating message status {message_id}: {e}")
            return MessageResponse(
                success=False,
                message_id=message_id if isinstance(message_id, str) else None,
                error=f"Status update error: {e}",
            )

    async def send_response(self, conversation_id: str, content: str) -> MessageResponse:
        """Route response sending to current platform.

        Args:
            conversation_id: Conversation to send message to
            content: Message content to send

        Returns:
            MessageResponse from the platform handler
        """
        try:
            platform_handler = self.get_platform(self._current_platform)
            logger.debug(f"Sending response for conversation {conversation_id} via {self._current_platform} platform")
            return await platform_handler.send_response(conversation_id, content)
        except ValueError as e:
            logger.error(f"Platform routing error for response to {conversation_id}: {e}")
            return MessageResponse(success=False, error=f"Platform routing error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending response to {conversation_id}: {e}")
            return MessageResponse(success=False, error=f"Response sending error: {e}")

    async def send_message(
        self,
        recipient_id: str,
        content: str,
        platform_metadata: dict[str, Any] = None,
    ) -> MessageResponse:
        """Route message sending to current platform.

        Args:
            recipient_id: Recipient identifier
            content: Message content
            platform_metadata: Platform-specific metadata

        Returns:
            MessageResponse from the platform handler
        """
        try:
            platform_handler = self.get_platform(self._current_platform)
            logger.debug(f"Sending message to {recipient_id} via {self._current_platform} platform")
            return await platform_handler.send_message(recipient_id, content, platform_metadata)
        except ValueError as e:
            logger.error(f"Platform routing error for message to {recipient_id}: {e}")
            return MessageResponse(success=False, error=f"Platform routing error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending message to {recipient_id}: {e}")
            return MessageResponse(success=False, error=f"Message sending error: {e}")

    def get_current_platform(self) -> str:
        """Get the current platform name.

        Returns:
            Current platform name
        """
        return self._current_platform

    def list_platforms(self) -> dict[str, str]:
        """List all available platforms and their status.

        Returns:
            Dictionary mapping platform names to their implementation status
        """
        status = {}
        for name, platform_class in self._platform_classes.items():
            # Check if platform is fully implemented by testing if it's a stub
            if platform_class == WebMessaging:
                status[name] = "implemented"
            elif platform_class in (TwilioMessaging, AWSEndUserMessaging):
                status[name] = "stub"
            else:
                status[name] = "unknown"

        return status

    def get_platform_capabilities(self, platform_name: str) -> dict[str, Any]:
        """Get capabilities and metadata for a specific platform.

        Args:
            platform_name: Name of the platform

        Returns:
            Dictionary with platform capabilities and metadata

        Raises:
            ValueError: If platform is not supported
        """
        if platform_name not in self._platform_classes:
            available = ", ".join(self._platform_classes.keys())
            raise ValueError(f"Unsupported platform '{platform_name}'. Available: {available}")

        platform_class = self._platform_classes[platform_name]

        # Define capabilities based on platform type
        if platform_class == WebMessaging:
            return {
                "name": platform_name,
                "status": "implemented",
                "channels": ["web"],
                "features": ["text_messages", "status_updates", "real_time_messaging"],
                "authentication": "cognito_jwt",
                "message_types": ["text"],
                "max_message_length": 4000,  # Reasonable web limit
            }
        elif platform_class == TwilioMessaging:
            return {
                "name": platform_name,
                "status": "stub",
                "channels": ["sms", "whatsapp"],
                "features": ["text_messages", "media_messages", "delivery_receipts"],
                "authentication": "twilio_webhook_signature",
                "message_types": ["text", "media"],
                "max_message_length": 1600,  # SMS limit
                "webhook_required": True,
            }
        elif platform_class == AWSEndUserMessaging:
            return {
                "name": platform_name,
                "status": "stub",
                "channels": ["whatsapp", "sms", "facebook_messenger"],
                "features": ["text_messages", "rich_messages", "buttons", "media"],
                "authentication": "aws_iam",
                "message_types": ["text", "rich", "media"],
                "max_message_length": 4096,  # WhatsApp limit
                "managed_service": True,
            }
        else:
            return {
                "name": platform_name,
                "status": "unknown",
                "channels": [],
                "features": [],
            }


# Global router instance for easy access
platform_router = PlatformRouter()
