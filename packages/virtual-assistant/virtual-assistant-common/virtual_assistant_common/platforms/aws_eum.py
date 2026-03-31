# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""AWS End User Messaging Social integration for WhatsApp."""

import json
import logging
import os
from typing import Any

import boto3

from ..models.messaging import MessageEvent, MessageResponse
from .base import MessagingPlatform

logger = logging.getLogger(__name__)

# Cache for EUM Social clients (similar to bedrock sessions)
_eum_social_clients = {}


class AWSEndUserMessaging(MessagingPlatform):
    """AWS End User Messaging Social integration for WhatsApp.

    This platform handles WhatsApp messages through AWS End User Messaging Social,
    supporting both same-account and cross-account deployments with proper
    authentication and error handling.
    """

    def __init__(self):
        """Initialize AWS End User Messaging platform."""
        self.phone_number_id = os.environ.get("EUM_SOCIAL_PHONE_NUMBER_ID")
        self.cross_account_role = os.environ.get("EUM_SOCIAL_CROSS_ACCOUNT_ROLE")
        self.region = os.environ.get("AWS_REGION", "us-east-1")

        if not self.phone_number_id:
            logger.warning("EUM_SOCIAL_PHONE_NUMBER_ID not configured - WhatsApp sending will fail")

        logger.debug("AWSEndUserMessaging platform initialized")

    def _get_eum_social_client(self):
        """Get EUM Social client with caching and optional cross-account role.

        Returns:
            boto3 client for EUM Social (socialmessaging service)

        Raises:
            Exception: If client creation fails
        """
        cache_key = f"{self.region}:{self.cross_account_role or 'same-account'}"

        if cache_key in _eum_social_clients:
            return _eum_social_clients[cache_key]

        try:
            if self.cross_account_role:
                # Use cross-account role assumption
                sts = boto3.client("sts")
                response = sts.assume_role(RoleArn=self.cross_account_role, RoleSessionName="whatsapp-message-sender")

                credentials = response["Credentials"]
                client = boto3.client(
                    "socialmessaging",
                    region_name=self.region,
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                )
            else:
                # Use default credentials
                client = boto3.client("socialmessaging", region_name=self.region)

            _eum_social_clients[cache_key] = client
            return client

        except Exception as e:
            logger.error(f"Failed to create EUM Social client: {e}")
            raise

    async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
        """Process AWS EUM WhatsApp message.

        This method is called by the message processor when a WhatsApp message
        is received. The message has already been parsed from the webhook format
        into a MessageEvent.

        Args:
            message_event: The parsed WhatsApp message event

        Returns:
            MessageResponse indicating processing success
        """
        try:
            logger.debug(f"Processing WhatsApp message {message_event.message_id} from {message_event.sender_id}")

            # For WhatsApp messages, processing mainly involves validation
            # The actual message content is already parsed and ready for AgentCore

            return MessageResponse(success=True, message_id=message_event.message_id, platform="aws-eum")

        except Exception as e:
            logger.error(f"Failed to process WhatsApp message {message_event.message_id}: {e}")
            return MessageResponse(
                success=False, message_id=message_event.message_id, error=f"WhatsApp processing error: {e}"
            )

    async def update_message_status(self, message_id: str | list[str], status: str) -> MessageResponse:
        """Update WhatsApp message status.

        Sends a read receipt for WhatsApp messages when status is 'read'.
        Supports batch status updates for multiple message IDs.

        Args:
            message_id: ID of the message to update, or list of message IDs
            status: New status value (delivered, read, failed)

        Returns:
            MessageResponse indicating success
        """
        try:
            # Handle both single message ID and list of message IDs
            message_ids = [message_id] if isinstance(message_id, str) else message_id

            if status == "read":
                if not self.phone_number_id:
                    raise ValueError("EUM_SOCIAL_PHONE_NUMBER_ID environment variable not set")

                client = self._get_eum_social_client()

                # Send read receipt for each message ID
                receipt_ids = []
                for msg_id in message_ids:
                    # Prepare WhatsApp read receipt message
                    read_receipt = {
                        "messaging_product": "whatsapp",
                        "status": "read",
                        "message_id": msg_id,
                    }

                    message_bytes = json.dumps(read_receipt).encode("utf-8")

                    response = client.send_whatsapp_message(
                        originationPhoneNumberId=self.phone_number_id,
                        message=message_bytes,
                        metaApiVersion="v20.0",
                    )

                    receipt_id = response.get("messageId")
                    receipt_ids.append(receipt_id)
                    logger.debug(f"WhatsApp message {msg_id} marked as read: {receipt_id}")

                return MessageResponse(
                    success=True,
                    message_id=message_ids[0] if len(message_ids) == 1 else None,
                    platform="aws-eum",
                    data={"updated_count": len(message_ids), "message_ids": message_ids, "receipt_ids": receipt_ids},
                )
            else:
                logger.debug(f"WhatsApp messages {message_ids} status: {status}")
                return MessageResponse(
                    success=True,
                    message_id=message_ids[0] if len(message_ids) == 1 else None,
                    platform="aws-eum",
                    data={"updated_count": len(message_ids), "message_ids": message_ids},
                )

        except Exception as e:
            logger.error(f"Failed to update WhatsApp message status {message_id}: {e}")
            return MessageResponse(
                success=False,
                message_id=message_id if isinstance(message_id, str) else None,
                error=f"Status update error: {e}",
            )

    async def send_response(self, conversation_id: str, content: str) -> MessageResponse:
        """Send WhatsApp response using conversation ID.

        Extracts the phone number from the WhatsApp conversation ID format
        (whatsapp-conversation-{phone}-session) and sends the message via EUM Social API.

        Args:
            conversation_id: WhatsApp conversation ID (format: whatsapp-conversation-{phone}-session)
            content: Message content to send

        Returns:
            MessageResponse with message details or error
        """
        try:
            # Extract phone number from conversation ID
            if not conversation_id.startswith("whatsapp-conversation-"):
                raise ValueError(f"Invalid WhatsApp conversation ID format: {conversation_id}")

            # Extract phone number from format: whatsapp-conversation-{phone}-session-id
            # Remove the prefix "whatsapp-conversation-"
            phone_part = conversation_id[len("whatsapp-conversation-") :]

            # Remove the suffix "-session-id" or "-session" (for backward compatibility)
            if phone_part.endswith("-session-id"):
                phone_number = phone_part[: -len("-session-id")]
            elif phone_part.endswith("-session"):
                phone_number = phone_part[: -len("-session")]
            else:
                raise ValueError(f"Invalid WhatsApp conversation ID format: {conversation_id}")

            if not phone_number:
                raise ValueError(f"Could not extract phone number from conversation ID: {conversation_id}")

            # Add + prefix if not present (WhatsApp API expects + prefix)
            if not phone_number.startswith("+"):
                phone_number = f"+{phone_number}"

            return await self.send_message(phone_number, content)

        except Exception as e:
            logger.error(f"Failed to send WhatsApp response to {conversation_id}: {e}")
            return MessageResponse(success=False, error=f"WhatsApp response error: {e}")

    async def send_message(
        self,
        recipient_id: str,
        content: str,
        platform_metadata: dict[str, Any] = None,
    ) -> MessageResponse:
        """Send WhatsApp message using EUM Social API.

        Args:
            recipient_id: Phone number of the recipient
            content: Message content to send
            platform_metadata: WhatsApp-specific metadata (not used currently)

        Returns:
            MessageResponse with message details or error
        """
        try:
            if not self.phone_number_id:
                raise ValueError("EUM_SOCIAL_PHONE_NUMBER_ID environment variable not set")

            client = self._get_eum_social_client()

            # Prepare WhatsApp message object according to Meta API format
            whatsapp_message = {
                "messaging_product": "whatsapp",
                "to": recipient_id,
                "type": "text",
                "text": {"body": content},
            }

            # Convert to bytes as required by AWS API

            message_bytes = json.dumps(whatsapp_message).encode("utf-8")

            response = client.send_whatsapp_message(
                originationPhoneNumberId=self.phone_number_id,
                message=message_bytes,
                metaApiVersion="v20.0",  # Required parameter
            )

            message_id = response.get("messageId")
            logger.debug(f"WhatsApp message sent successfully to {recipient_id}: {message_id}")

            return MessageResponse(success=True, message_id=message_id, platform="aws-eum", recipient_id=recipient_id)

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {recipient_id}: {e}")
            return MessageResponse(success=False, error=f"WhatsApp sending error: {e}")
