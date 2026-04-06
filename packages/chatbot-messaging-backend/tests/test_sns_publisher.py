# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for SNS publisher utilities."""

import json
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from chatbot_messaging_backend.utils.sns_publisher import SNSPublisher


class TestSNSPublisher:
    """Test cases for SNSPublisher class."""

    @pytest.fixture
    def topic_arn(self):
        """Sample SNS topic ARN for testing."""
        return "arn:aws:sns:us-east-1:123456789012:test-topic"

    @pytest.fixture
    def publisher(self, topic_arn):
        """Create SNSPublisher instance for testing."""
        return SNSPublisher(topic_arn=topic_arn, region_name="us-east-1")

    @pytest.fixture
    def sample_message_data(self):
        """Sample message data for testing."""
        return {
            "messageId": "msg-123",
            "conversationId": "conv-456",
            "senderId": "user-789",
            "recipientId": "bot-001",
            "content": "Hello, world!",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "sent",
        }

    def test_init(self, topic_arn):
        """Test SNSPublisher initialization."""
        publisher = SNSPublisher(topic_arn=topic_arn, region_name="us-west-2")

        assert publisher.topic_arn == topic_arn
        assert publisher.region_name == "us-west-2"
        assert publisher._sns_client is None

    @patch("boto3.client")
    def test_sns_client_lazy_initialization(self, mock_boto_client, publisher):
        """Test that SNS client is lazily initialized."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        # First access should create client
        client1 = publisher.sns_client
        assert client1 == mock_client
        mock_boto_client.assert_called_once_with("sns", region_name="us-east-1")

        # Second access should return same client
        client2 = publisher.sns_client
        assert client2 == mock_client
        assert mock_boto_client.call_count == 1

    @patch("boto3.client")
    def test_publish_message_success(self, mock_boto_client, publisher, sample_message_data):
        """Test successful message publishing."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.publish.return_value = {"MessageId": "sns-msg-123"}

        result = publisher.publish_message(sample_message_data)

        assert result is True
        mock_client.publish.assert_called_once()

        # Verify publish call arguments
        call_args = mock_client.publish.call_args
        assert call_args[1]["TopicArn"] == publisher.topic_arn
        assert call_args[1]["Subject"] == "New message from user-789"

        # Verify message content
        message_content = json.loads(call_args[1]["Message"])
        assert message_content == sample_message_data

        # Verify message attributes
        attributes = call_args[1]["MessageAttributes"]
        assert attributes["messageType"]["StringValue"] == "chatbot_message"
        assert attributes["senderId"]["StringValue"] == "user-789"
        assert attributes["conversationId"]["StringValue"] == "conv-456"

    def test_publish_message_missing_fields(self, publisher):
        """Test publishing with missing required fields."""
        incomplete_data = {
            "messageId": "msg-123",
            "senderId": "user-789",
            # Missing other required fields
        }

        with pytest.raises(ValueError) as exc_info:
            publisher.publish_message(incomplete_data)

        assert "Missing required fields" in str(exc_info.value)
        assert "conversationId" in str(exc_info.value)
        assert "recipientId" in str(exc_info.value)

    @patch("boto3.client")
    def test_publish_message_client_error(self, mock_boto_client, publisher, sample_message_data):
        """Test handling of SNS client errors."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        error_response = {"Error": {"Code": "NotFound", "Message": "Topic does not exist"}}
        mock_client.publish.side_effect = ClientError(error_response, "Publish")

        with pytest.raises(ClientError):
            publisher.publish_message(sample_message_data)

    @patch("boto3.client")
    def test_publish_message_boto_core_error(self, mock_boto_client, publisher, sample_message_data):
        """Test handling of BotoCore errors."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.publish.side_effect = BotoCoreError()

        with pytest.raises(BotoCoreError):
            publisher.publish_message(sample_message_data)

    @patch("boto3.client")
    def test_publish_message_unexpected_error(self, mock_boto_client, publisher, sample_message_data):
        """Test handling of unexpected errors."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.publish.side_effect = Exception("Unexpected error")

        result = publisher.publish_message(sample_message_data)

        assert result is False

    @patch("boto3.client")
    def test_publish_message_from_model_success(self, mock_boto_client, publisher):
        """Test publishing from message model instance."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.publish.return_value = {"MessageId": "sns-msg-123"}

        # Create mock message model
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "conv-456"
        mock_message.sender_id = "user-789"
        mock_message.recipient_id = "bot-001"
        mock_message.content = "Hello from model!"
        mock_message.timestamp = "2024-01-01T12:00:00Z"
        mock_message.status = "sent"

        result = publisher.publish_message_from_model(mock_message)

        assert result is True
        mock_client.publish.assert_called_once()

        # Verify message content
        call_args = mock_client.publish.call_args
        message_content = json.loads(call_args[1]["Message"])
        assert message_content["messageId"] == "msg-123"
        assert message_content["content"] == "Hello from model!"

    def test_publish_message_from_model_missing_attributes(self, publisher):
        """Test publishing from model with missing attributes."""
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        # Missing other required attributes
        del mock_message.conversation_id

        with pytest.raises(ValueError) as exc_info:
            publisher.publish_message_from_model(mock_message)

        assert "Message model missing required attributes" in str(exc_info.value)

    @patch("boto3.client")
    def test_health_check_success(self, mock_boto_client, publisher):
        """Test successful health check."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.get_topic_attributes.return_value = {"Attributes": {}}

        result = publisher.health_check()

        assert result is True
        mock_client.get_topic_attributes.assert_called_once_with(TopicArn=publisher.topic_arn)

    @patch("boto3.client")
    def test_health_check_client_error(self, mock_boto_client, publisher):
        """Test health check with client error."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client

        error_response = {"Error": {"Code": "NotFound", "Message": "Topic does not exist"}}
        mock_client.get_topic_attributes.side_effect = ClientError(error_response, "GetTopicAttributes")

        result = publisher.health_check()

        assert result is False

    @patch("boto3.client")
    def test_health_check_unexpected_error(self, mock_boto_client, publisher):
        """Test health check with unexpected error."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.get_topic_attributes.side_effect = Exception("Unexpected error")

        result = publisher.health_check()

        assert result is False

    def test_required_fields_validation(self, publisher):
        """Test validation of all required fields."""
        base_data = {
            "messageId": "msg-123",
            "conversationId": "conv-456",
            "senderId": "user-789",
            "recipientId": "bot-001",
            "content": "Hello, world!",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "sent",
        }

        # Test each required field
        required_fields = ["messageId", "conversationId", "senderId", "recipientId", "content", "timestamp", "status"]

        for field in required_fields:
            incomplete_data = base_data.copy()
            del incomplete_data[field]

            with pytest.raises(ValueError) as exc_info:
                publisher.publish_message(incomplete_data)

            assert field in str(exc_info.value)

    @patch("boto3.client")
    def test_message_attributes_format(self, mock_boto_client, publisher, sample_message_data):
        """Test that message attributes are formatted correctly."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        mock_client.publish.return_value = {"MessageId": "sns-msg-123"}

        publisher.publish_message(sample_message_data)

        call_args = mock_client.publish.call_args
        attributes = call_args[1]["MessageAttributes"]

        # Verify all attributes have correct structure
        for _attr_name, attr_value in attributes.items():
            assert "DataType" in attr_value
            assert "StringValue" in attr_value
            assert attr_value["DataType"] == "String"

        # Verify specific attribute values
        assert attributes["messageType"]["StringValue"] == "chatbot_message"
        assert attributes["senderId"]["StringValue"] == sample_message_data["senderId"]
        assert attributes["conversationId"]["StringValue"] == sample_message_data["conversationId"]
