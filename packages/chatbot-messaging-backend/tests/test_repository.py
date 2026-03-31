# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for MessageRepository with mocked DynamoDB."""

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from chatbot_messaging_backend.models.message import MessageStatus, create_message
from chatbot_messaging_backend.utils.repository import MessageRepository


class TestMessageRepository:
    """Test cases for MessageRepository class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_dynamodb = Mock()
        self.repository = MessageRepository(table_name="test-messages-table", dynamodb_client=self.mock_dynamodb)

        # Create a test message
        self.test_message = create_message(
            sender_id="user123", recipient_id="bot456", content="Hello, world!", message_id="test-message-id"
        )

    def test_init_with_defaults(self):
        """Test repository initialization with default values."""
        with patch.dict("os.environ", {"DYNAMODB_TABLE_NAME": "env-table"}), patch("boto3.client") as mock_boto_client:
            mock_client = Mock()
            mock_boto_client.return_value = mock_client

            repo = MessageRepository()
            assert repo.table_name == "env-table"
            assert repo.dynamodb == mock_client
            mock_boto_client.assert_called_once_with("dynamodb")

    def test_init_with_explicit_values(self):
        """Test repository initialization with explicit values."""
        mock_client = Mock()
        repo = MessageRepository(table_name="custom-table", dynamodb_client=mock_client)
        assert repo.table_name == "custom-table"
        assert repo.dynamodb == mock_client

    def test_create_message_success(self):
        """Test successful message creation."""
        # Setup mock response
        self.mock_dynamodb.put_item.return_value = {}

        # Call the method
        result = self.repository.create_message(self.test_message)

        # Verify the result
        assert result == self.test_message

        # Verify DynamoDB was called correctly
        self.mock_dynamodb.put_item.assert_called_once()
        call_args = self.mock_dynamodb.put_item.call_args

        assert call_args[1]["TableName"] == "test-messages-table"
        assert "Item" in call_args[1]
        assert "ConditionExpression" in call_args[1]

        # Verify the item structure
        item = call_args[1]["Item"]
        assert item["messageId"]["S"] == "test-message-id"
        # Should now be UUID format
        import uuid

        uuid.UUID(item["conversationId"]["S"])  # This will raise ValueError if not valid UUID
        assert item["content"]["S"] == "Hello, world!"
        assert item["status"]["S"] == "sent"

    def test_create_message_duplicate_error(self):
        """Test message creation with duplicate message ID."""
        # Setup mock to raise conditional check failed error
        error = ClientError(
            error_response={
                "Error": {"Code": "ConditionalCheckFailedException", "Message": "The conditional request failed"}
            },
            operation_name="PutItem",
        )
        self.mock_dynamodb.put_item.side_effect = error

        # Call should raise the error
        with pytest.raises(ClientError):
            self.repository.create_message(self.test_message)

    def test_create_message_other_error(self):
        """Test message creation with other DynamoDB errors."""
        # Setup mock to raise generic error
        error = ClientError(
            error_response={"Error": {"Code": "InternalServerError", "Message": "Internal server error"}},
            operation_name="PutItem",
        )
        self.mock_dynamodb.put_item.side_effect = error

        # Call should raise the error
        with pytest.raises(ClientError):
            self.repository.create_message(self.test_message)

    def test_update_message_status_success(self):
        """Test successful message status update."""
        # Setup mock responses
        query_response = {
            "Items": [
                {
                    "conversationId": {"S": "user123#bot456"},
                    "timestamp": {"S": "2024-01-01T12:00:00Z"},
                    "messageId": {"S": "test-message-id"},
                    "senderId": {"S": "user123"},
                    "recipientId": {"S": "bot456"},
                    "content": {"S": "Hello, world!"},
                    "status": {"S": "sent"},
                    "createdAt": {"S": "2024-01-01T12:00:00Z"},
                    "updatedAt": {"S": "2024-01-01T12:00:00Z"},
                }
            ]
        }

        update_response = {
            "Attributes": {
                "conversationId": {"S": "user123#bot456"},
                "timestamp": {"S": "2024-01-01T12:00:00Z"},
                "messageId": {"S": "test-message-id"},
                "senderId": {"S": "user123"},
                "recipientId": {"S": "bot456"},
                "content": {"S": "Hello, world!"},
                "status": {"S": "read"},
                "createdAt": {"S": "2024-01-01T12:00:00Z"},
                "updatedAt": {"S": "2024-01-01T12:30:00Z"},
            }
        }

        self.mock_dynamodb.query.return_value = query_response
        self.mock_dynamodb.update_item.return_value = update_response

        # Call the method
        result = self.repository.update_message_status(
            message_id="test-message-id", status=MessageStatus.READ, updated_at="2024-01-01T12:30:00Z"
        )

        # Verify the result
        assert result is not None
        assert result.message_id == "test-message-id"
        assert result.status == MessageStatus.READ
        assert result.updated_at == "2024-01-01T12:30:00Z"

        # Verify DynamoDB calls
        self.mock_dynamodb.query.assert_called_once()
        self.mock_dynamodb.update_item.assert_called_once()

    def test_update_message_status_not_found(self):
        """Test message status update when message not found."""
        # Setup mock to return empty result
        self.mock_dynamodb.query.return_value = {"Items": []}

        # Call the method
        result = self.repository.update_message_status(
            message_id="nonexistent-id", status=MessageStatus.READ, updated_at="2024-01-01T12:30:00Z"
        )

        # Verify the result
        assert result is None

        # Verify only query was called
        self.mock_dynamodb.query.assert_called_once()
        self.mock_dynamodb.update_item.assert_not_called()

    def test_update_message_status_query_error(self):
        """Test message status update with query error."""
        # Setup mock to raise error
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
            operation_name="Query",
        )
        self.mock_dynamodb.query.side_effect = error

        # Call should raise the error
        with pytest.raises(ClientError):
            self.repository.update_message_status(
                message_id="test-message-id", status=MessageStatus.READ, updated_at="2024-01-01T12:30:00Z"
            )

    def test_query_messages_success(self):
        """Test successful message querying."""
        # Setup mock response
        query_response = {
            "Items": [
                {
                    "conversationId": {"S": "user123#bot456"},
                    "timestamp": {"S": "2024-01-01T12:00:00Z"},
                    "messageId": {"S": "msg1"},
                    "senderId": {"S": "user123"},
                    "recipientId": {"S": "bot456"},
                    "content": {"S": "First message"},
                    "status": {"S": "sent"},
                    "createdAt": {"S": "2024-01-01T12:00:00Z"},
                    "updatedAt": {"S": "2024-01-01T12:00:00Z"},
                },
                {
                    "conversationId": {"S": "user123#bot456"},
                    "timestamp": {"S": "2024-01-01T12:01:00Z"},
                    "messageId": {"S": "msg2"},
                    "senderId": {"S": "bot456"},
                    "recipientId": {"S": "user123"},
                    "content": {"S": "Second message"},
                    "status": {"S": "delivered"},
                    "createdAt": {"S": "2024-01-01T12:01:00Z"},
                    "updatedAt": {"S": "2024-01-01T12:01:00Z"},
                },
            ]
        }

        self.mock_dynamodb.query.return_value = query_response

        # Call the method
        result = self.repository.query_messages(conversation_id="user123#bot456", limit=10)

        # Verify the result
        assert len(result) == 2
        assert result[0].message_id == "msg1"
        assert result[0].content == "First message"
        assert result[1].message_id == "msg2"
        assert result[1].content == "Second message"

        # Verify DynamoDB call
        self.mock_dynamodb.query.assert_called_once()
        call_args = self.mock_dynamodb.query.call_args[1]
        assert call_args["TableName"] == "test-messages-table"
        assert call_args["Limit"] == 10
        assert call_args["ScanIndexForward"] is True

    def test_query_messages_with_timestamp_filter(self):
        """Test message querying with timestamp filter."""
        # Setup mock response
        self.mock_dynamodb.query.return_value = {"Items": []}

        # Call the method
        self.repository.query_messages(
            conversation_id="user123#bot456", since_timestamp="2024-01-01T12:00:00Z", limit=25
        )

        # Verify DynamoDB call includes timestamp filter
        call_args = self.mock_dynamodb.query.call_args[1]
        assert "AND #timestamp > :since_timestamp" in call_args["KeyConditionExpression"]
        assert ":since_timestamp" in call_args["ExpressionAttributeValues"]
        assert call_args["ExpressionAttributeValues"][":since_timestamp"]["S"] == "2024-01-01T12:00:00Z"
        assert call_args["ExpressionAttributeNames"]["#timestamp"] == "timestamp"

    def test_query_messages_empty_result(self):
        """Test message querying with empty result."""
        # Setup mock to return empty result
        self.mock_dynamodb.query.return_value = {"Items": []}

        # Call the method
        result = self.repository.query_messages(conversation_id="nonexistent#conversation")

        # Verify the result
        assert result == []

    def test_query_messages_error(self):
        """Test message querying with DynamoDB error."""
        # Setup mock to raise error
        error = ClientError(
            error_response={"Error": {"Code": "ValidationException", "Message": "Invalid key condition"}},
            operation_name="Query",
        )
        self.mock_dynamodb.query.side_effect = error

        # Call should raise the error
        with pytest.raises(ClientError):
            self.repository.query_messages(conversation_id="user123#bot456")

    def test_get_message_by_id_success(self):
        """Test successful message retrieval by ID."""
        # Setup mock response
        query_response = {
            "Items": [
                {
                    "conversationId": {"S": "user123#bot456"},
                    "timestamp": {"S": "2024-01-01T12:00:00Z"},
                    "messageId": {"S": "test-message-id"},
                    "senderId": {"S": "user123"},
                    "recipientId": {"S": "bot456"},
                    "content": {"S": "Hello, world!"},
                    "status": {"S": "sent"},
                    "createdAt": {"S": "2024-01-01T12:00:00Z"},
                    "updatedAt": {"S": "2024-01-01T12:00:00Z"},
                }
            ]
        }

        self.mock_dynamodb.query.return_value = query_response

        # Call the method
        result = self.repository.get_message_by_id("test-message-id")

        # Verify the result
        assert result is not None
        assert result.message_id == "test-message-id"
        assert result.content == "Hello, world!"

        # Verify DynamoDB call
        self.mock_dynamodb.query.assert_called_once()
        call_args = self.mock_dynamodb.query.call_args[1]
        assert call_args["IndexName"] == "MessageIdIndex"
        assert call_args["Limit"] == 1

    def test_get_message_by_id_not_found(self):
        """Test message retrieval by ID when not found."""
        # Setup mock to return empty result
        self.mock_dynamodb.query.return_value = {"Items": []}

        # Call the method
        result = self.repository.get_message_by_id("nonexistent-id")

        # Verify the result
        assert result is None

    def test_get_message_by_id_error(self):
        """Test message retrieval by ID with DynamoDB error."""
        # Setup mock to raise error
        error = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Index not found"}},
            operation_name="Query",
        )
        self.mock_dynamodb.query.side_effect = error

        # Call should raise the error
        with pytest.raises(ClientError):
            self.repository.get_message_by_id("test-message-id")
