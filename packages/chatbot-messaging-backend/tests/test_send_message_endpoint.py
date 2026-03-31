# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the send_message endpoint.
"""

import os
from unittest.mock import Mock, patch

import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    UnauthorizedError,
)

from chatbot_messaging_backend.handlers.lambda_handler import (
    SendMessageRequest,
    extract_sender_id_from_jwt,
    send_message,
)
from chatbot_messaging_backend.models.message import MessageStatus


class TestSendMessageRequest:
    """Test cases for SendMessageRequest validation."""

    def test_valid_request(self):
        """Test valid request data."""
        request_data = {"recipient_id": "user123", "content": "Hello, world!"}
        request = SendMessageRequest.model_validate(request_data)

        assert request.recipient_id == "user123"
        assert request.content == "Hello, world!"

    def test_missing_recipient_id(self):
        """Test request with missing recipient_id."""
        request_data = {"content": "Hello, world!"}

        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("recipientId",)
        assert errors[0]["type"] == "missing"

    def test_missing_content(self):
        """Test request with missing content."""
        request_data = {"recipient_id": "user123"}

        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("content",)
        assert errors[0]["type"] == "missing"


class TestJWTExtraction:
    """Test cases for JWT token extraction."""

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_from_jwt_with_claims(self, mock_app):
        """Test extracting sender ID from JWT claims."""
        mock_app.current_event.request_context = {
            "authorizer": {"claims": {"sub": "user123", "email": "user@example.com"}}
        }

        sender_id = extract_sender_id_from_jwt()
        assert sender_id == "user123"

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_from_jwt_with_direct_sub(self, mock_app):
        """Test extracting sender ID from direct sub field."""
        mock_app.current_event.request_context = {"authorizer": {"sub": "user456"}}

        sender_id = extract_sender_id_from_jwt()
        assert sender_id == "user456"

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_from_jwt_with_principal_id(self, mock_app):
        """Test extracting sender ID from principalId field."""
        mock_app.current_event.request_context = {"authorizer": {"principalId": "user789"}}

        sender_id = extract_sender_id_from_jwt()
        assert sender_id == "user789"

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_no_authorizer(self, mock_app):
        """Test extraction fails when no authorizer context."""
        mock_app.current_event.request_context = {}

        with pytest.raises(UnauthorizedError, match="Missing authentication"):
            extract_sender_id_from_jwt()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_no_request_context(self, mock_app):
        """Test extraction fails when no request context."""
        mock_app.current_event.request_context = None

        with pytest.raises(UnauthorizedError, match="Missing authentication"):
            extract_sender_id_from_jwt()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_missing_sub_in_claims(self, mock_app):
        """Test extraction fails when sub is missing from claims."""
        mock_app.current_event.request_context = {"authorizer": {"claims": {"email": "user@example.com"}}}

        with pytest.raises(UnauthorizedError, match="Invalid token: missing user ID"):
            extract_sender_id_from_jwt()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_extract_sender_id_no_user_id_fields(self, mock_app):
        """Test extraction fails when no user ID fields are present."""
        mock_app.current_event.request_context = {"authorizer": {"some_other_field": "value"}}

        with pytest.raises(UnauthorizedError, match="Invalid token: missing user ID"):
            extract_sender_id_from_jwt()


class TestSendMessageEndpoint:
    """Test cases for the send_message endpoint."""

    def setup_method(self):
        """Set up test environment variables."""
        os.environ["DYNAMODB_TABLE_NAME"] = "test-messages-table"
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

    def teardown_method(self):
        """Clean up environment variables."""
        if "DYNAMODB_TABLE_NAME" in os.environ:
            del os.environ["DYNAMODB_TABLE_NAME"]
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageRepository")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.SNSPublisher")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_success(self, mock_app, mock_extract_sender, mock_sns_publisher_class, mock_repository_class):
        """Test successful message sending."""
        # Setup mocks
        mock_extract_sender.return_value = "user123"

        mock_repository = Mock()
        mock_repository_class.return_value = mock_repository

        mock_sns_publisher = Mock()
        mock_sns_publisher_class.return_value = mock_sns_publisher
        mock_sns_publisher.publish_message.return_value = True

        # Create a mock message that would be returned by repository.create_message
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_message.to_sns_message.return_value = {
            "messageId": "msg-123",
            "conversationId": "user123#user456",
            "senderId": "user123",
            "recipientId": "user456",
            "content": "Hello, world!",
            "timestamp": "2023-01-01T12:00:00Z",
            "status": "sent",
        }
        mock_repository.create_message.return_value = mock_message

        # Mock the current event
        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        response = send_message()

        # Verify response (now returns tuple with status code)
        response_data, status_code = response
        assert status_code == 201
        assert response_data["messageId"] == "msg-123"
        assert response_data["conversationId"] == "user123#user456"
        assert response_data["timestamp"] == "2023-01-01T12:00:00Z"
        assert response_data["status"] == "sent"

        # Verify mocks were called correctly
        mock_extract_sender.assert_called_once()
        mock_repository_class.assert_called_once_with(table_name="test-messages-table")
        mock_sns_publisher_class.assert_called_once_with(topic_arn="arn:aws:sns:us-east-1:123456789012:test-topic")
        mock_repository.create_message.assert_called_once()
        mock_sns_publisher.publish_message.assert_called_once()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_invalid_request_body(self, mock_app, mock_extract_sender):
        """Test send message with invalid request body."""
        mock_extract_sender.return_value = "user123"

        # Mock the current event with invalid body
        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456"}  # Missing content
        mock_app.current_event = mock_event

        with pytest.raises(BadRequestError):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_unauthorized(self, mock_app, mock_extract_sender):
        """Test send message with unauthorized request."""
        mock_extract_sender.side_effect = UnauthorizedError("Missing authentication")

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        with pytest.raises(UnauthorizedError):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageRepository")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.SNSPublisher")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_dynamodb_failure(
        self, mock_app, mock_extract_sender, mock_sns_publisher_class, mock_repository_class
    ):
        """Test send message with DynamoDB failure."""
        mock_extract_sender.return_value = "user123"

        mock_repository = Mock()
        mock_repository_class.return_value = mock_repository
        mock_repository.create_message.side_effect = Exception("DynamoDB error")

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        with pytest.raises(InternalServerError, match="Failed to store message"):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageRepository")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.SNSPublisher")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_sns_failure_does_not_fail_request(
        self, mock_app, mock_extract_sender, mock_sns_publisher_class, mock_repository_class
    ):
        """Test that SNS failure doesn't fail the entire request."""
        mock_extract_sender.return_value = "user123"

        mock_repository = Mock()
        mock_repository_class.return_value = mock_repository

        mock_sns_publisher = Mock()
        mock_sns_publisher_class.return_value = mock_sns_publisher
        mock_sns_publisher.publish_message.side_effect = Exception("SNS error")

        # Create a mock message
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_message.to_sns_message.return_value = {}
        mock_repository.create_message.return_value = mock_message

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        # Should not raise an exception despite SNS failure
        response = send_message()

        # Verify response is still returned (now returns tuple with status code)
        response_data, status_code = response
        assert status_code == 201
        assert response_data["messageId"] == "msg-123"
        assert response_data["conversationId"] == "user123#user456"

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageRepository")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.SNSPublisher")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_sns_returns_false(
        self, mock_app, mock_extract_sender, mock_sns_publisher_class, mock_repository_class
    ):
        """Test send message when SNS publish returns False."""
        mock_extract_sender.return_value = "user123"

        mock_repository = Mock()
        mock_repository_class.return_value = mock_repository

        mock_sns_publisher = Mock()
        mock_sns_publisher_class.return_value = mock_sns_publisher
        mock_sns_publisher.publish_message.return_value = False  # SNS publish failed

        # Create a mock message
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_message.to_sns_message.return_value = {}
        mock_repository.create_message.return_value = mock_message

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        with pytest.raises(InternalServerError, match="Failed to publish message"):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_empty_recipient_id(self, mock_app, mock_extract_sender):
        """Test send message with empty recipient_id."""
        mock_extract_sender.return_value = "user123"

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        # This should work at the Pydantic level but fail at the message creation level
        # The create_message function should validate empty recipient_id
        with pytest.raises(BadRequestError):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_empty_content(self, mock_app, mock_extract_sender):
        """Test send message with empty content."""
        mock_extract_sender.return_value = "user123"

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": ""}
        mock_app.current_event = mock_event

        # This should work at the Pydantic level but fail at the message creation level
        # The create_message function should validate empty content
        with pytest.raises(BadRequestError):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.app")
    def test_send_message_missing_environment_variables(self, mock_app, mock_extract_sender):
        """Test send message with missing environment variables."""
        # Remove environment variables
        if "DYNAMODB_TABLE_NAME" in os.environ:
            del os.environ["DYNAMODB_TABLE_NAME"]
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        mock_extract_sender.return_value = "user123"

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}
        mock_app.current_event = mock_event

        with pytest.raises(InternalServerError):
            send_message()
