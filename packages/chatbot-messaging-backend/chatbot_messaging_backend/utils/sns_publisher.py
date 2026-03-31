# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""SNS publishing utilities for message events."""

import json
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import BotoCoreError, ClientError

logger = Logger()


class SNSPublisher:
    """Handles publishing messages to SNS topics."""

    def __init__(self, topic_arn: str, region_name: str = "us-east-1"):
        """
        Initialize SNS publisher.

        Args:
            topic_arn: ARN of the SNS topic to publish to
            region_name: AWS region name
        """
        self.topic_arn = topic_arn
        self.region_name = region_name
        self._sns_client = None

    @property
    def sns_client(self):
        """Lazy initialization of SNS client."""
        if self._sns_client is None:
            self._sns_client = boto3.client("sns", region_name=self.region_name)
        return self._sns_client

    def publish_message(self, message_data: dict[str, Any]) -> bool:
        """
        Publish a message to the SNS topic.

        Args:
            message_data: Dictionary containing message data with keys:
                - messageId: string
                - conversationId: string
                - senderId: string
                - recipientId: string
                - content: string
                - timestamp: ISO8601 string
                - status: string (typically "sent")

        Returns:
            bool: True if message was published successfully, False otherwise

        Raises:
            ValueError: If required message fields are missing
            ClientError: If SNS publish operation fails
        """
        try:
            # Validate required fields
            required_fields = [
                "messageId",
                "conversationId",
                "senderId",
                "recipientId",
                "content",
                "timestamp",
                "status",
            ]
            missing_fields = [field for field in required_fields if field not in message_data]

            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")

            # Format message according to SNS message structure specification
            sns_message = {
                "messageId": message_data["messageId"],
                "conversationId": message_data["conversationId"],
                "senderId": message_data["senderId"],
                "recipientId": message_data["recipientId"],
                "content": message_data["content"],
                "timestamp": message_data["timestamp"],
                "status": message_data["status"],
            }

            # Publish to SNS
            response = self.sns_client.publish(
                TopicArn=self.topic_arn,
                Message=json.dumps(sns_message),
                Subject=f"New message from {message_data['senderId']}",
                MessageAttributes={
                    "messageType": {"DataType": "String", "StringValue": "chatbot_message"},
                    "senderId": {"DataType": "String", "StringValue": message_data["senderId"]},
                    "recipientId": {"DataType": "String", "StringValue": message_data["recipientId"]},
                    "conversationId": {"DataType": "String", "StringValue": message_data["conversationId"]},
                },
            )

            message_id = response.get("MessageId")
            logger.info(
                "Message published to SNS successfully",
                extra={
                    "sns_message_id": message_id,
                    "conversation_id": message_data["conversationId"],
                    "message_id": message_data["messageId"],
                },
            )

            return True

        except ValueError as e:
            logger.error(
                "Invalid message data for SNS publishing", extra={"error": str(e), "message_data": message_data}
            )
            raise

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]

            logger.error(
                "SNS publish failed with client error",
                extra={
                    "error_code": error_code,
                    "error_message": error_message,
                    "topic_arn": self.topic_arn,
                    "message_id": message_data.get("messageId"),
                },
            )
            raise

        except BotoCoreError as e:
            logger.error(
                "SNS publish failed with boto core error",
                extra={"error": str(e), "topic_arn": self.topic_arn, "message_id": message_data.get("messageId")},
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during SNS publish",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "topic_arn": self.topic_arn,
                    "message_id": message_data.get("messageId"),
                },
            )
            return False

    def publish_message_from_model(self, message) -> bool:
        """
        Publish a message from a Message model instance.

        Args:
            message: Message model instance with required attributes

        Returns:
            bool: True if message was published successfully, False otherwise
        """
        try:
            message_data = {
                "messageId": message.message_id,
                "conversationId": message.conversation_id,
                "senderId": message.sender_id,
                "recipientId": message.recipient_id,
                "content": message.content,
                "timestamp": message.timestamp,
                "status": message.status,
            }

            return self.publish_message(message_data)

        except AttributeError as e:
            logger.error(
                "Message model missing required attributes",
                extra={"error": str(e), "message_type": type(message).__name__},
            )
            raise ValueError(f"Message model missing required attributes: {e}") from e

    def health_check(self) -> bool:
        """
        Check if SNS topic is accessible.

        Returns:
            bool: True if topic is accessible, False otherwise
        """
        try:
            # Try to get topic attributes to verify access
            self.sns_client.get_topic_attributes(TopicArn=self.topic_arn)
            return True

        except ClientError as e:
            logger.warning(
                "SNS health check failed",
                extra={
                    "error_code": e.response["Error"]["Code"],
                    "error_message": e.response["Error"]["Message"],
                    "topic_arn": self.topic_arn,
                },
            )
            return False

        except Exception as e:
            logger.warning(
                "SNS health check failed with unexpected error", extra={"error": str(e), "topic_arn": self.topic_arn}
            )
            return False
