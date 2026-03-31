# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Message service containing business logic for message operations.

This service layer encapsulates the core business logic for message handling,
making it framework-agnostic and easier to test. The Lambda handlers act as
thin wrappers that handle HTTP concerns while delegating business logic to
this service.
"""

from typing import Optional

from aws_lambda_powertools import Logger

from ..models.message import Message, MessageStatus, create_message, generate_iso8601_timestamp
from ..utils.repository import MessageRepository
from ..utils.sns_publisher import SNSPublisher

logger = Logger()


class MessageService:
    """Service class for message business logic operations."""

    def __init__(self, repository: MessageRepository, sns_publisher: SNSPublisher):
        """
        Initialize the message service.

        Args:
            repository: MessageRepository instance for database operations
            sns_publisher: SNSPublisher instance for SNS operations
        """
        self.repository = repository
        self.sns_publisher = sns_publisher

    def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        conversation_id: str | None = None,
        model_id: str | None = None,
        temperature: float | None = None,
    ) -> Message:
        """
        Send a new message.

        This method encapsulates the business logic for sending a message:
        1. Create a message instance with validation
        2. Store the message in the database
        3. Publish the message to SNS for processing

        Args:
            sender_id: ID of the message sender
            recipient_id: ID of the message recipient
            content: Message content
            conversation_id: Optional conversation ID (UUID format)
            model_id: Optional AI model ID for processing
            temperature: Optional temperature parameter for AI model

        Returns:
            Message: The stored message instance

        Raises:
            ValueError: If input validation fails
            RuntimeError: If database or SNS operations fail
        """
        logger.info("Processing send message request", extra={"sender_id": sender_id, "recipient_id": recipient_id})

        # Create message instance with validation
        try:
            message = create_message(
                sender_id=sender_id, recipient_id=recipient_id, content=content, conversation_id=conversation_id
            )
        except ValueError as e:
            logger.warning(
                "Message creation validation failed",
                extra={"sender_id": sender_id, "recipient_id": recipient_id, "error": str(e)},
            )
            raise ValueError(f"Invalid message data: {e}") from e

        logger.info(
            "Created message instance",
            extra={
                "message_id": message.message_id,
                "conversation_id": message.conversation_id,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
            },
        )

        # Store message in database
        try:
            stored_message = self.repository.create_message(message)
            logger.info("Message stored in database", extra={"message_id": message.message_id})
        except Exception as e:
            logger.error(
                "Failed to store message in database", extra={"error": str(e), "message_id": message.message_id}
            )
            raise RuntimeError("Failed to store message") from e

        # Publish message to SNS
        try:
            sns_message_data = stored_message.to_sns_message()

            # Add model parameters to SNS message if provided
            if model_id is not None:
                sns_message_data["modelId"] = model_id
            if temperature is not None:
                sns_message_data["temperature"] = temperature

            success = self.sns_publisher.publish_message(sns_message_data)
            if not success:
                logger.error("SNS publish returned False", extra={"message_id": message.message_id})
                raise RuntimeError("Failed to publish message")
            logger.info("Message published to SNS", extra={"message_id": message.message_id})
        except RuntimeError:
            # Re-raise RuntimeError for SNS failures
            raise
        except Exception as e:
            logger.error("Failed to publish message to SNS", extra={"error": str(e), "message_id": message.message_id})
            # Note: We don't raise here as the message is already stored
            # In a production system, you might want to implement a retry mechanism
            logger.warning("Message stored but SNS publish failed - message may not be processed by agents")

        logger.info("Send message request completed successfully", extra={"message_id": stored_message.message_id})
        return stored_message

    def get_messages(
        self, conversation_id: str, since_timestamp: Optional[str] = None, limit: int = 50
    ) -> tuple[list[Message], bool]:
        """
        Get messages for a conversation with optional timestamp filtering.

        This method encapsulates the business logic for retrieving messages:
        1. Validate the conversation ID and parameters
        2. Query messages from the database with filtering
        3. Determine if there are more messages available (pagination)

        Args:
            conversation_id: ID of the conversation to retrieve messages for
            since_timestamp: Optional timestamp to filter messages newer than this
            limit: Maximum number of messages to return (default: 50)

        Returns:
            tuple[list[Message], bool]: A tuple containing the list of messages and a boolean
                                      indicating if there are more messages available

        Raises:
            ValueError: If input validation fails
            RuntimeError: If database operations fail
        """
        logger.info(
            "Processing get messages request",
            extra={"conversation_id": conversation_id, "since_timestamp": since_timestamp, "limit": limit},
        )

        # Validate conversation ID
        if not conversation_id or not conversation_id.strip():
            logger.warning("Empty or invalid conversationId provided")
            raise ValueError("Conversation ID cannot be empty")

        conversation_id = conversation_id.strip()

        # Validate limit
        if limit <= 0:
            logger.warning("Invalid limit provided", extra={"limit": limit})
            raise ValueError("Limit must be greater than 0")

        if limit > 100:
            logger.warning("Limit too high, capping at 100", extra={"limit": limit})
            limit = 100

        # Query messages from database
        try:
            # Request one extra message to determine if there are more
            query_limit = limit + 1
            messages = self.repository.query_messages(
                conversation_id=conversation_id, since_timestamp=since_timestamp, limit=query_limit
            )

            # Determine if there are more messages
            has_more = len(messages) > limit
            if has_more:
                # Remove the extra message
                messages = messages[:limit]

            logger.info(
                "Get messages request completed successfully",
                extra={
                    "conversation_id": conversation_id,
                    "message_count": len(messages),
                    "has_more": has_more,
                },
            )

            return messages, has_more

        except Exception as e:
            logger.error(
                "Failed to retrieve messages from database",
                extra={"error": str(e), "conversation_id": conversation_id, "since_timestamp": since_timestamp},
            )
            raise RuntimeError("Failed to retrieve messages") from e

    def update_message_status(self, message_id: str, status: MessageStatus) -> Optional[Message]:
        """
        Update the status of an existing message.

        This method encapsulates the business logic for updating message status:
        1. Validate the message ID
        2. Generate updated timestamp
        3. Update the message status in the database

        Args:
            message_id: ID of the message to update
            status: New status for the message

        Returns:
            Optional[Message]: The updated message instance, or None if message not found

        Raises:
            ValueError: If input validation fails
            RuntimeError: If database operations fail
        """
        logger.info("Processing update message status request", extra={"message_id": message_id})

        # Validate message ID
        if not message_id or not message_id.strip():
            logger.warning("Empty or invalid messageId provided")
            raise ValueError("Message ID cannot be empty")

        message_id = message_id.strip()

        # Generate updated timestamp
        updated_at = generate_iso8601_timestamp()

        # Update message status in database
        try:
            updated_message = self.repository.update_message_status(
                message_id=message_id, status=status, updated_at=updated_at
            )

            if updated_message is None:
                logger.warning("Message not found for status update", extra={"message_id": message_id})
                return None

            logger.info(
                "Message status updated successfully",
                extra={"message_id": message_id, "new_status": status.value},
            )
            return updated_message

        except Exception as e:
            logger.error(
                "Failed to update message status in database",
                extra={"error": str(e), "message_id": message_id, "status": status.value},
            )
            raise RuntimeError("Failed to update message status") from e
