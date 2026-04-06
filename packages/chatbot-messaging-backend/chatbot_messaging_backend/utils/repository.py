# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""DynamoDB repository layer for message operations."""

import os
from typing import Optional

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from ..models.message import Message, MessageStatus

logger = Logger()


class MessageRepository:
    """Repository for DynamoDB message operations.

    Handles all DynamoDB operations for messages including create, update,
    and query operations with proper error handling and logging.
    """

    def __init__(self, table_name: Optional[str] = None, dynamodb_client=None):
        """Initialize the repository.

        Args:
            table_name: DynamoDB table name (defaults to environment variable)
            dynamodb_client: Optional DynamoDB client (for testing)
        """
        self.table_name = table_name or os.environ.get("DYNAMODB_TABLE_NAME", "chatbot-messages")
        self.dynamodb = dynamodb_client or boto3.client("dynamodb")

    def create_message(self, message: Message) -> Message:
        """Store a new message in DynamoDB.

        Args:
            message: Message instance to store

        Returns:
            The stored message

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            item = message.to_dynamodb_item()

            # Convert to DynamoDB format
            dynamodb_item = {
                "conversationId": {"S": item["conversationId"]},
                "timestamp": {"S": item["timestamp"]},
                "messageId": {"S": item["messageId"]},
                "senderId": {"S": item["senderId"]},
                "recipientId": {"S": item["recipientId"]},
                "content": {"S": item["content"]},
                "status": {"S": item["status"]},
                "createdAt": {"S": item["createdAt"]},
                "updatedAt": {"S": item["updatedAt"]},
            }

            self.dynamodb.put_item(
                TableName=self.table_name,
                Item=dynamodb_item,
                ConditionExpression="attribute_not_exists(messageId)",  # Prevent duplicates
            )

            logger.info(
                "Message created successfully",
                extra={
                    "message_id": message.message_id,
                    "conversation_id": message.conversation_id,
                    "table_name": self.table_name,
                },
            )

            return message

        except ClientError as e:
            logger.error(
                "Failed to create message",
                extra={"message_id": message.message_id, "error": str(e), "table_name": self.table_name},
            )
            raise

    def update_message_status(self, message_id: str, status: MessageStatus, updated_at: str) -> Optional[Message]:
        """Update message status by messageId using GSI.

        Args:
            message_id: Message ID to update
            status: New status value
            updated_at: Updated timestamp

        Returns:
            Updated message if found, None if not found

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            # First, query the GSI to find the message
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName="MessageIdIndex",
                KeyConditionExpression="messageId = :message_id",
                ExpressionAttributeValues={":message_id": {"S": message_id}},
            )

            if not response.get("Items"):
                logger.warning(
                    "Message not found for status update",
                    extra={"message_id": message_id, "table_name": self.table_name},
                )
                return None

            # Get the first (and should be only) item
            item = response["Items"][0]
            conversation_id = item["conversationId"]["S"]
            timestamp = item["timestamp"]["S"]

            # Update the message status
            update_response = self.dynamodb.update_item(
                TableName=self.table_name,
                Key={"conversationId": {"S": conversation_id}, "timestamp": {"S": timestamp}},
                UpdateExpression="SET #status = :status, updatedAt = :updated_at",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": {"S": status.value}, ":updated_at": {"S": updated_at}},
                ReturnValues="ALL_NEW",
            )

            # Convert back to Message object
            updated_item = update_response["Attributes"]
            message = Message.from_dynamodb_item(
                {
                    "messageId": updated_item["messageId"]["S"],
                    "conversationId": updated_item["conversationId"]["S"],
                    "senderId": updated_item["senderId"]["S"],
                    "recipientId": updated_item["recipientId"]["S"],
                    "content": updated_item["content"]["S"],
                    "status": updated_item["status"]["S"],
                    "timestamp": updated_item["timestamp"]["S"],
                    "createdAt": updated_item["createdAt"]["S"],
                    "updatedAt": updated_item["updatedAt"]["S"],
                }
            )

            logger.info(
                "Message status updated successfully",
                extra={"message_id": message_id, "new_status": status.value, "table_name": self.table_name},
            )

            return message

        except ClientError as e:
            logger.error(
                "Failed to update message status",
                extra={
                    "message_id": message_id,
                    "status": status.value,
                    "error": str(e),
                    "table_name": self.table_name,
                },
            )
            raise

    def query_messages(
        self, conversation_id: str, since_timestamp: Optional[str] = None, limit: int = 50
    ) -> list[Message]:
        """Query messages by conversationId with optional timestamp filtering.

        Args:
            conversation_id: Conversation ID to query
            since_timestamp: Optional timestamp to filter messages newer than this
            limit: Maximum number of messages to return

        Returns:
            List of messages ordered by timestamp (oldest first)

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            # Build the query parameters
            query_params = {
                "TableName": self.table_name,
                "KeyConditionExpression": "conversationId = :conversation_id",
                "ExpressionAttributeValues": {":conversation_id": {"S": conversation_id}},
                "Limit": limit,
                "ScanIndexForward": True,  # Sort by timestamp ascending (oldest first)
            }

            # Add timestamp filter if provided
            if since_timestamp:
                query_params["KeyConditionExpression"] += " AND #timestamp > :since_timestamp"
                query_params["ExpressionAttributeNames"] = {"#timestamp": "timestamp"}
                query_params["ExpressionAttributeValues"][":since_timestamp"] = {"S": since_timestamp}

            response = self.dynamodb.query(**query_params)

            # Convert DynamoDB items to Message objects
            messages = []
            for item in response.get("Items", []):
                message = Message.from_dynamodb_item(
                    {
                        "messageId": item["messageId"]["S"],
                        "conversationId": item["conversationId"]["S"],
                        "senderId": item["senderId"]["S"],
                        "recipientId": item["recipientId"]["S"],
                        "content": item["content"]["S"],
                        "status": item["status"]["S"],
                        "timestamp": item["timestamp"]["S"],
                        "createdAt": item["createdAt"]["S"],
                        "updatedAt": item["updatedAt"]["S"],
                    }
                )
                messages.append(message)

            logger.info(
                "Messages queried successfully",
                extra={
                    "conversation_id": conversation_id,
                    "message_count": len(messages),
                    "since_timestamp": since_timestamp,
                    "table_name": self.table_name,
                },
            )

            return messages

        except ClientError as e:
            logger.error(
                "Failed to query messages",
                extra={
                    "conversation_id": conversation_id,
                    "since_timestamp": since_timestamp,
                    "error": str(e),
                    "table_name": self.table_name,
                },
            )
            raise

    def get_message_by_id(self, message_id: str) -> Optional[Message]:
        """Get a single message by messageId using GSI.

        Args:
            message_id: Message ID to retrieve

        Returns:
            Message if found, None if not found

        Raises:
            ClientError: If DynamoDB operation fails
        """
        try:
            response = self.dynamodb.query(
                TableName=self.table_name,
                IndexName="MessageIdIndex",
                KeyConditionExpression="messageId = :message_id",
                ExpressionAttributeValues={":message_id": {"S": message_id}},
                Limit=1,
            )

            if not response.get("Items"):
                logger.debug("Message not found", extra={"message_id": message_id, "table_name": self.table_name})
                return None

            item = response["Items"][0]
            message = Message.from_dynamodb_item(
                {
                    "messageId": item["messageId"]["S"],
                    "conversationId": item["conversationId"]["S"],
                    "senderId": item["senderId"]["S"],
                    "recipientId": item["recipientId"]["S"],
                    "content": item["content"]["S"],
                    "status": item["status"]["S"],
                    "timestamp": item["timestamp"]["S"],
                    "createdAt": item["createdAt"]["S"],
                    "updatedAt": item["updatedAt"]["S"],
                }
            )

            logger.debug(
                "Message retrieved successfully", extra={"message_id": message_id, "table_name": self.table_name}
            )

            return message

        except ClientError as e:
            logger.error(
                "Failed to get message by ID",
                extra={"message_id": message_id, "error": str(e), "table_name": self.table_name},
            )
            raise
