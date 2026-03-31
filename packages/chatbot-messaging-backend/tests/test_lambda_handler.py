# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for the Lambda handler.
"""

import json
import os
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from chatbot_messaging_backend.handlers.lambda_handler import (
    SendMessageRequest,
    UpdateMessageStatusRequest,
    app,
    extract_sender_id_from_jwt,
    health_check,
    lambda_handler,
    send_message,
    update_message_status,
)
from chatbot_messaging_backend.models.message import MessageStatus


class TestLambdaHandler:
    """Test cases for the Lambda handler."""

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

    def test_health_check_endpoint(self):
        """Test the health check endpoint returns correct response."""
        response = health_check()

        assert response["status"] == "healthy"
        assert response["service"] == "chatbot-messaging-backend"
        assert response["version"] == "1.0.0"

    def test_lambda_handler_health_check(self):
        """Test Lambda handler with health check request."""
        # Mock API Gateway event for health check
        event = {
            "httpMethod": "GET",
            "path": "/health",
            "headers": {},
            "queryStringParameters": None,
            "body": None,
            "requestContext": {"requestId": "test-request-id", "stage": "test"},
        }

        # Mock Lambda context
        context = Mock()
        context.aws_request_id = "test-request-id"
        context.function_name = "test-function"
        context.get_remaining_time_in_millis.return_value = 30000

        response = lambda_handler(event, context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "healthy"

    def test_lambda_handler_exception_handling(self):
        """Test Lambda handler handles exceptions gracefully."""
        # Mock API Gateway event that will cause an exception
        event = {
            "httpMethod": "GET",
            "path": "/nonexistent",
            "headers": {},
            "queryStringParameters": None,
            "body": None,
            "requestContext": {"requestId": "test-request-id", "stage": "test"},
        }

        # Mock Lambda context
        context = Mock()
        context.aws_request_id = "test-request-id"
        context.function_name = "test-function"
        context.get_remaining_time_in_millis.return_value = 30000

        # Mock app.resolve to raise an exception
        with patch.object(app, "resolve", side_effect=Exception("Test exception")):
            response = lambda_handler(event, context)

        assert response["statusCode"] == 500
        assert "Access-Control-Allow-Origin" in response["headers"]
        body = json.loads(response["body"])
        assert body["error"]["code"] == "INTERNAL_ERROR"

    def test_cors_headers_in_error_response(self):
        """Test that CORS headers are included in error responses."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {},
            "queryStringParameters": None,
            "body": None,
            "requestContext": {"requestId": "test-request-id", "stage": "test"},
        }

        context = Mock()
        context.aws_request_id = "test-request-id"
        context.function_name = "test-function"
        context.get_remaining_time_in_millis.return_value = 30000

        with patch.object(app, "resolve", side_effect=Exception("Test exception")):
            response = lambda_handler(event, context)

        headers = response["headers"]
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert "Content-Type" in headers
        assert "Access-Control-Allow-Headers" in headers
        assert "Access-Control-Allow-Methods" in headers


class TestEnvironmentVariables:
    """Test environment variable validation."""

    def test_missing_dynamodb_table_name(self):
        """Test that missing DYNAMODB_TABLE_NAME raises ValueError."""
        from chatbot_messaging_backend.handlers.lambda_handler import get_environment_variables

        # Temporarily remove environment variable
        original_value = os.environ.get("DYNAMODB_TABLE_NAME")
        if "DYNAMODB_TABLE_NAME" in os.environ:
            del os.environ["DYNAMODB_TABLE_NAME"]

        # Set required SNS_TOPIC_ARN
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

        try:
            with pytest.raises(ValueError, match="DYNAMODB_TABLE_NAME environment variable is required"):
                get_environment_variables()
        finally:
            # Restore original value
            if original_value:
                os.environ["DYNAMODB_TABLE_NAME"] = original_value

    def test_missing_sns_topic_arn(self):
        """Test that missing SNS_TOPIC_ARN raises ValueError."""
        from chatbot_messaging_backend.handlers.lambda_handler import get_environment_variables

        # Set required DYNAMODB_TABLE_NAME
        os.environ["DYNAMODB_TABLE_NAME"] = "test-table"

        # Temporarily remove SNS_TOPIC_ARN
        original_value = os.environ.get("SNS_TOPIC_ARN")
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        try:
            with pytest.raises(ValueError, match="SNS_TOPIC_ARN environment variable is required"):
                get_environment_variables()
        finally:
            # Restore original value
            if original_value:
                os.environ["SNS_TOPIC_ARN"] = original_value

    def test_valid_environment_variables(self):
        """Test that valid environment variables are returned correctly."""
        from chatbot_messaging_backend.handlers.lambda_handler import get_environment_variables

        os.environ["DYNAMODB_TABLE_NAME"] = "test-table"
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"

        table_name, topic_arn = get_environment_variables()

        assert table_name == "test-table"
        assert topic_arn == "arn:aws:sns:us-east-1:123456789012:test-topic"

    def teardown_method(self):
        """Clean up environment variables."""
        # Restore environment variables for other tests
        os.environ["DYNAMODB_TABLE_NAME"] = "test-messages-table"
        os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:test-topic"


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

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("recipientId",)
        assert errors[0]["type"] == "missing"

    def test_missing_content(self):
        """Test request with missing content."""
        request_data = {"recipient_id": "user123"}

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("content",)
        assert errors[0]["type"] == "missing"

    def test_empty_recipient_id(self):
        """Test request with empty recipient_id."""
        request_data = {"recipient_id": "", "content": "Hello, world!"}

        # Pydantic allows empty strings by default, but our business logic should handle this
        request = SendMessageRequest.model_validate(request_data)
        assert request.recipient_id == ""

    def test_empty_content(self):
        """Test request with empty content."""
        request_data = {"recipient_id": "user123", "content": ""}

        # Pydantic allows empty strings by default, but our business logic should handle this
        request = SendMessageRequest.model_validate(request_data)
        assert request.content == ""

    def test_valid_request_with_model_parameters(self):
        """Test valid request data with optional model parameters."""
        request_data = {
            "recipient_id": "user123",
            "content": "Hello, world!",
            "modelId": "claude-3-haiku",
            "temperature": 0.7,
        }
        request = SendMessageRequest.model_validate(request_data)

        assert request.recipient_id == "user123"
        assert request.content == "Hello, world!"
        assert request.model_id == "claude-3-haiku"
        assert request.temperature == 0.7

    def test_valid_request_without_model_parameters(self):
        """Test valid request data without optional model parameters."""
        request_data = {"recipient_id": "user123", "content": "Hello, world!"}
        request = SendMessageRequest.model_validate(request_data)

        assert request.recipient_id == "user123"
        assert request.content == "Hello, world!"
        assert request.conversation_id is None
        assert request.model_id is None
        assert request.temperature is None

    def test_valid_request_with_conversation_id(self):
        """Test valid request with UUID conversation ID."""
        conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        request_data = {
            "recipient_id": "user456",
            "content": "Hello, world!",
            "conversationId": conversation_id,
        }
        request = SendMessageRequest.model_validate(request_data)

        assert request.recipient_id == "user456"
        assert request.content == "Hello, world!"
        assert request.conversation_id == conversation_id
        assert request.model_id is None
        assert request.temperature is None

    def test_invalid_conversation_id_format(self):
        """Test invalid conversation ID format."""
        request_data = {
            "recipient_id": "user456",
            "content": "Hello, world!",
            "conversationId": "not-a-uuid",
        }

        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)

        assert "conversationId must be a valid UUID" in str(exc_info.value)

    def test_temperature_validation_bounds(self):
        """Test temperature parameter validation bounds."""
        # Test valid temperature values
        valid_temps = [0.0, 0.5, 1.0, 1.5, 2.0]
        for temp in valid_temps:
            request_data = {"recipient_id": "user123", "content": "Hello!", "temperature": temp}
            request = SendMessageRequest.model_validate(request_data)
            assert request.temperature == temp

        # Test invalid temperature values (below 0.0)
        request_data = {"recipient_id": "user123", "content": "Hello!", "temperature": -0.1}
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)
        errors = exc_info.value.errors()
        assert any(error["type"] == "greater_than_equal" for error in errors)

        # Test invalid temperature values (above 2.0)
        request_data = {"recipient_id": "user123", "content": "Hello!", "temperature": 2.1}
        with pytest.raises(ValidationError) as exc_info:
            SendMessageRequest.model_validate(request_data)
        errors = exc_info.value.errors()
        assert any(error["type"] == "less_than_equal" for error in errors)


class TestJWTExtraction:
    """Test cases for JWT token extraction."""

    def test_extract_sender_id_from_jwt_with_claims(self):
        """Test extracting sender ID from JWT claims."""
        # Mock the app.current_event
        mock_event = Mock()
        mock_event.request_context = {"authorizer": {"claims": {"sub": "user123", "email": "user@example.com"}}}

        with patch.object(app, "current_event", mock_event, create=True):
            sender_id = extract_sender_id_from_jwt()
            assert sender_id == "user123"

    def test_extract_sender_id_from_jwt_with_direct_sub(self):
        """Test extracting sender ID from direct sub field."""
        mock_event = Mock()
        mock_event.request_context = {"authorizer": {"sub": "user456"}}

        with patch.object(app, "current_event", mock_event, create=True):
            sender_id = extract_sender_id_from_jwt()
            assert sender_id == "user456"

    def test_extract_sender_id_from_jwt_with_principal_id(self):
        """Test extracting sender ID from principalId field."""
        mock_event = Mock()
        mock_event.request_context = {"authorizer": {"principalId": "user789"}}

        with patch.object(app, "current_event", mock_event, create=True):
            sender_id = extract_sender_id_from_jwt()
            assert sender_id == "user789"

    def test_extract_sender_id_no_authorizer(self):
        """Test extraction fails when no authorizer context."""
        mock_event = Mock()
        mock_event.request_context = {}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

            with pytest.raises(UnauthorizedError, match="Missing authentication"):
                extract_sender_id_from_jwt()

    def test_extract_sender_id_no_request_context(self):
        """Test extraction fails when no request context."""
        mock_event = Mock()
        mock_event.request_context = None

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

            with pytest.raises(UnauthorizedError, match="Missing authentication"):
                extract_sender_id_from_jwt()

    def test_extract_sender_id_missing_sub_in_claims(self):
        """Test extraction fails when sub is missing from claims."""
        mock_event = Mock()
        mock_event.request_context = {"authorizer": {"claims": {"email": "user@example.com"}}}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

            with pytest.raises(UnauthorizedError, match="Invalid token: missing user ID"):
                extract_sender_id_from_jwt()

    def test_extract_sender_id_no_user_id_fields(self):
        """Test extraction fails when no user ID fields are present."""
        mock_event = Mock()
        mock_event.request_context = {"authorizer": {"some_other_field": "value"}}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

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

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_success(self, mock_extract_sender, mock_message_service_class):
        """Test successful message sending through Lambda handler."""
        # Setup mocks
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service

        # Create a mock message that would be returned by service.send_message
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_service.send_message.return_value = mock_message

        # Mock the current event
        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}

        with patch.object(app, "current_event", mock_event, create=True):
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
        mock_message_service_class.assert_called_once()
        mock_service.send_message.assert_called_once_with(
            sender_id="user123",
            recipient_id="user456",
            content="Hello, world!",
            conversation_id=None,
            model_id=None,
            temperature=None,
        )

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_invalid_request_body(self, mock_extract_sender):
        """Test send message with invalid request body."""
        mock_extract_sender.return_value = "user123"

        # Mock the current event with invalid body
        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456"}  # Missing content

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            with pytest.raises(BadRequestError):
                send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_unauthorized(self, mock_extract_sender):
        """Test send message with unauthorized request."""
        from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

        mock_extract_sender.side_effect = UnauthorizedError("Missing authentication")

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}

        with patch.object(app, "current_event", mock_event, create=True), pytest.raises(UnauthorizedError):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_service_runtime_error(self, mock_extract_sender, mock_message_service_class):
        """Test send message with service RuntimeError."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.send_message.side_effect = RuntimeError("Service operation failed")

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import InternalServerError

            with pytest.raises(InternalServerError, match="Service operation failed"):
                send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_service_value_error(self, mock_extract_sender, mock_message_service_class):
        """Test send message with service ValueError (validation error)."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.send_message.side_effect = ValueError("Invalid message data")

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            with pytest.raises(BadRequestError, match="Invalid message data"):
                send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_jwt_extraction_success(self, mock_extract_sender, mock_message_service_class):
        """Test that JWT extraction is properly handled in send_message."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_service.send_message.return_value = mock_message

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}

        with patch.object(app, "current_event", mock_event, create=True):
            response = send_message()

        # Verify JWT extraction was called
        mock_extract_sender.assert_called_once()

        # Verify service was called with extracted sender_id
        mock_service.send_message.assert_called_once_with(
            sender_id="user123",
            recipient_id="user456",
            content="Hello, world!",
            conversation_id=None,
            model_id=None,
            temperature=None,
        )

        # Verify response format (now returns tuple with status code)
        response_data, status_code = response
        assert status_code == 201
        assert response_data["messageId"] == "msg-123"

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_request_body_parsing(self, mock_extract_sender, mock_message_service_class):
        """Test that request body is properly parsed and passed to service."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_service.send_message.return_value = mock_message

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Test message"}

        with patch.object(app, "current_event", mock_event, create=True):
            send_message()

        # Verify service was called with parsed request data
        mock_service.send_message.assert_called_once_with(
            sender_id="user123",
            recipient_id="user456",
            content="Test message",
            conversation_id=None,
            model_id=None,
            temperature=None,
        )

    def test_send_message_missing_environment_variables(self):
        """Test send message with missing environment variables."""
        # Remove environment variables
        if "DYNAMODB_TABLE_NAME" in os.environ:
            del os.environ["DYNAMODB_TABLE_NAME"]
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        from aws_lambda_powertools.event_handler.exceptions import InternalServerError

        mock_event = Mock()
        mock_event.json_body = {"recipient_id": "user456", "content": "Hello, world!"}

        with (
            patch.object(app, "current_event", mock_event, create=True),
            patch(
                "chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt", return_value="user123"
            ),
            pytest.raises(InternalServerError),
        ):
            send_message()

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_with_model_parameters(self, mock_extract_sender, mock_message_service_class):
        """Test that model parameters are properly passed to the service."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_service.send_message.return_value = mock_message

        mock_event = Mock()
        mock_event.json_body = {
            "recipient_id": "user456",
            "content": "Hello with model params!",
            "modelId": "claude-3-haiku",
            "temperature": 0.7,
        }

        with patch.object(app, "current_event", mock_event, create=True):
            response = send_message()

        # Verify response
        response_data, status_code = response
        assert status_code == 201

        # Verify service was called with model parameters
        mock_service.send_message.assert_called_once_with(
            sender_id="user123",
            recipient_id="user456",
            content="Hello with model params!",
            conversation_id=None,
            model_id="claude-3-haiku",
            temperature=0.7,
        )

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_send_message_with_conversation_id(self, mock_extract_sender, mock_message_service_class):
        """Test that conversation ID is properly passed to the service."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "550e8400-e29b-41d4-a716-446655440000"
        mock_message.timestamp = "2023-01-01T12:00:00Z"
        mock_message.status = MessageStatus.SENT
        mock_service.send_message.return_value = mock_message

        mock_event = Mock()
        mock_event.json_body = {
            "recipient_id": "user456",
            "content": "Hello with conversation ID!",
            "conversationId": "550e8400-e29b-41d4-a716-446655440000",
        }

        with patch.object(app, "current_event", mock_event, create=True):
            response = send_message()

        # Verify response
        response_data, status_code = response
        assert status_code == 201
        assert response_data["conversationId"] == "550e8400-e29b-41d4-a716-446655440000"

        # Verify service was called with conversation ID
        mock_service.send_message.assert_called_once_with(
            sender_id="user123",
            recipient_id="user456",
            content="Hello with conversation ID!",
            conversation_id="550e8400-e29b-41d4-a716-446655440000",
            model_id=None,
            temperature=None,
        )


class TestUpdateMessageStatusRequest:
    """Test cases for UpdateMessageStatusRequest validation."""

    def test_valid_request(self):
        """Test valid request data."""
        request_data = {"status": "read"}
        request = UpdateMessageStatusRequest.model_validate(request_data)

        assert request.status == MessageStatus.READ

    def test_valid_status_values(self):
        """Test all valid status values."""
        valid_statuses = ["sent", "delivered", "read", "failed", "warning", "deleted"]

        for status in valid_statuses:
            request_data = {"status": status}
            request = UpdateMessageStatusRequest.model_validate(request_data)
            assert request.status.value == status

    def test_missing_status(self):
        """Test request with missing status."""
        request_data = {}

        with pytest.raises(ValidationError) as exc_info:
            UpdateMessageStatusRequest.model_validate(request_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("status",)
        assert errors[0]["type"] == "missing"

    def test_invalid_status(self):
        """Test request with invalid status value."""
        request_data = {"status": "invalid_status"}

        with pytest.raises(ValidationError) as exc_info:
            UpdateMessageStatusRequest.model_validate(request_data)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("status",)


class TestUpdateMessageStatusEndpoint:
    """Test cases for the update_message_status endpoint."""

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

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    def test_update_message_status_success(self, mock_message_service_class):
        """Test successful message status update through Lambda handler."""
        # Setup mocks
        mock_service = Mock()
        mock_message_service_class.return_value = mock_service

        # Create a mock updated message
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.status = MessageStatus.READ
        mock_message.updated_at = "2023-01-01T12:30:00Z"
        mock_service.update_message_status.return_value = mock_message

        # Mock the current event
        mock_event = Mock()
        mock_event.json_body = {"status": "read"}

        with patch.object(app, "current_event", mock_event, create=True):
            response = update_message_status("msg-123")

        # Verify response
        assert response["messageId"] == "msg-123"
        assert response["status"] == "read"
        assert response["updatedAt"] == "2023-01-01T12:30:00Z"

        # Verify mocks were called correctly
        mock_message_service_class.assert_called_once()
        mock_service.update_message_status.assert_called_once_with(message_id="msg-123", status=MessageStatus.READ)

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    def test_update_message_status_not_found(self, mock_message_service_class):
        """Test update message status when message is not found."""
        # Setup mocks
        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.update_message_status.return_value = None  # Message not found

        # Mock the current event
        mock_event = Mock()
        mock_event.json_body = {"status": "read"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import NotFoundError

            with pytest.raises(NotFoundError, match="Message with ID 'msg-123' not found"):
                update_message_status("msg-123")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    def test_update_message_status_service_value_error(self, mock_message_service_class):
        """Test update message status with service ValueError (validation error)."""
        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.update_message_status.side_effect = ValueError("Message ID cannot be empty")

        mock_event = Mock()
        mock_event.json_body = {"status": "read"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            with pytest.raises(BadRequestError, match="Message ID cannot be empty"):
                update_message_status("")

    def test_update_message_status_invalid_request_body(self):
        """Test update message status with invalid request body."""
        mock_event = Mock()
        mock_event.json_body = {"status": "invalid_status"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            with pytest.raises(BadRequestError):
                update_message_status("msg-123")

    def test_update_message_status_missing_status(self):
        """Test update message status with missing status in request body."""
        mock_event = Mock()
        mock_event.json_body = {}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            with pytest.raises(BadRequestError):
                update_message_status("msg-123")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    def test_update_message_status_service_runtime_error(self, mock_message_service_class):
        """Test update message status with service RuntimeError."""
        # Setup mocks
        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.update_message_status.side_effect = RuntimeError("Service operation failed")

        # Mock the current event
        mock_event = Mock()
        mock_event.json_body = {"status": "read"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import InternalServerError

            with pytest.raises(InternalServerError, match="Service operation failed"):
                update_message_status("msg-123")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageRepository")
    def test_update_message_status_all_valid_statuses(self, mock_repository_class):
        """Test update message status with all valid status values."""
        valid_statuses = ["sent", "delivered", "read", "failed", "warning", "deleted"]

        for status in valid_statuses:
            # Setup mocks
            mock_repository = Mock()
            mock_repository_class.return_value = mock_repository

            # Create a mock updated message
            mock_message = Mock()
            mock_message.message_id = "msg-123"
            mock_message.status = MessageStatus(status)
            mock_message.updated_at = "2023-01-01T12:30:00Z"
            mock_repository.update_message_status.return_value = mock_message

            # Mock the current event
            mock_event = Mock()
            mock_event.json_body = {"status": status}

            with patch.object(app, "current_event", mock_event, create=True):
                response = update_message_status("msg-123")

            # Verify response
            assert response["messageId"] == "msg-123"
            assert response["status"] == status
            assert response["updatedAt"] == "2023-01-01T12:30:00Z"

    def test_update_message_status_missing_environment_variables(self):
        """Test update message status with missing environment variables."""
        # Remove environment variables
        if "DYNAMODB_TABLE_NAME" in os.environ:
            del os.environ["DYNAMODB_TABLE_NAME"]
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        mock_event = Mock()
        mock_event.json_body = {"status": "read"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import InternalServerError

            with pytest.raises(InternalServerError):
                update_message_status("msg-123")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageRepository")
    def test_update_message_status_strips_whitespace_from_message_id(self, mock_repository_class):
        """Test that whitespace is stripped from message ID."""
        # Setup mocks
        mock_repository = Mock()
        mock_repository_class.return_value = mock_repository

        # Create a mock updated message
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.status = MessageStatus.READ
        mock_message.updated_at = "2023-01-01T12:30:00Z"
        mock_repository.update_message_status.return_value = mock_message

        # Mock the current event
        mock_event = Mock()
        mock_event.json_body = {"status": "read"}

        with patch.object(app, "current_event", mock_event, create=True):
            response = update_message_status("  msg-123  ")  # Message ID with whitespace

        # Verify response
        assert response["messageId"] == "msg-123"

        # Verify that the repository was called with stripped message ID
        call_args = mock_repository.update_message_status.call_args
        assert call_args[1]["message_id"] == "msg-123"  # Should be stripped


class TestGetMessagesEndpoint:
    """Test cases for the get_messages endpoint."""

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

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_success(self, mock_extract_sender, mock_message_service_class):
        """Test successful message retrieval through Lambda handler."""
        # Setup mocks
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service

        # Create mock messages
        mock_messages = []
        for i in range(3):
            mock_message = Mock()
            mock_message.message_id = f"msg-{i}"
            mock_message.conversation_id = "user123#user456"
            mock_message.sender_id = "user123" if i % 2 == 0 else "user456"
            mock_message.recipient_id = "user456" if i % 2 == 0 else "user123"
            mock_message.content = f"Message {i}"
            mock_message.status = MessageStatus.SENT
            mock_message.timestamp = f"2023-01-01T12:0{i}:00Z"
            mock_messages.append(mock_message)

        mock_service.get_messages.return_value = (mock_messages, False)

        # Mock the current event
        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            response = get_messages("user123#user456")

        # Verify response
        assert "messages" in response
        assert "hasMore" in response
        assert len(response["messages"]) == 3
        assert response["hasMore"] is False

        # Verify first message structure
        first_message = response["messages"][0]
        assert first_message["messageId"] == "msg-0"
        assert first_message["conversationId"] == "user123#user456"
        assert first_message["senderId"] == "user123"
        assert first_message["recipientId"] == "user456"
        assert first_message["content"] == "Message 0"
        assert first_message["status"] == "sent"
        assert first_message["timestamp"] == "2023-01-01T12:00:00Z"

        # Verify mocks were called correctly
        mock_extract_sender.assert_called_once()
        mock_message_service_class.assert_called_once()
        mock_service.get_messages.assert_called_once_with(
            conversation_id="user123#user456", since_timestamp=None, limit=50
        )

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_with_query_parameters(self, mock_extract_sender, mock_message_service_class):
        """Test get messages with query parameters."""
        # Setup mocks
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.get_messages.return_value = ([], True)

        # Mock the current event with query parameters
        mock_event = Mock()
        mock_event.query_string_parameters = {"since": "2023-01-01T12:00:00Z", "limit": "10"}

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            response = get_messages("user123#user456")

        # Verify response
        assert response["messages"] == []
        assert response["hasMore"] is True

        # Verify service was called with query parameters
        mock_service.get_messages.assert_called_once_with(
            conversation_id="user123#user456", since_timestamp="2023-01-01T12:00:00Z", limit=10
        )

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_invalid_limit_parameter(self, mock_extract_sender, mock_message_service_class):
        """Test get messages with invalid limit parameter."""
        mock_extract_sender.return_value = "user123"

        # Mock the current event with invalid limit
        mock_event = Mock()
        mock_event.query_string_parameters = {"limit": "invalid"}

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            with pytest.raises(BadRequestError, match="Invalid limit parameter: must be a number"):
                get_messages("user123#user456")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_unauthorized(self, mock_extract_sender):
        """Test get messages with unauthorized request."""
        from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

        mock_extract_sender.side_effect = UnauthorizedError("Missing authentication")

        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            with pytest.raises(UnauthorizedError):
                get_messages("user123#user456")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_service_value_error(self, mock_extract_sender, mock_message_service_class):
        """Test get messages with service ValueError (validation error)."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.get_messages.side_effect = ValueError("Conversation ID cannot be empty")

        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import BadRequestError

            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            with pytest.raises(BadRequestError, match="Conversation ID cannot be empty"):
                get_messages("")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_service_runtime_error(self, mock_extract_sender, mock_message_service_class):
        """Test get messages with service RuntimeError."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.get_messages.side_effect = RuntimeError("Failed to retrieve messages")

        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import InternalServerError

            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            with pytest.raises(InternalServerError, match="Failed to retrieve messages"):
                get_messages("user123#user456")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_default_limit(self, mock_extract_sender, mock_message_service_class):
        """Test get messages with default limit when no limit parameter provided."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.get_messages.return_value = ([], False)

        # Mock the current event without limit parameter
        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            get_messages("user123#user456")

        # Verify service was called with default limit
        mock_service.get_messages.assert_called_once_with(
            conversation_id="user123#user456", since_timestamp=None, limit=50
        )

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_empty_query_parameters(self, mock_extract_sender, mock_message_service_class):
        """Test get messages with empty query parameters dict."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service
        mock_service.get_messages.return_value = ([], False)

        # Mock the current event with empty query parameters
        mock_event = Mock()
        mock_event.query_string_parameters = {}

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            get_messages("user123#user456")

        # Verify service was called with default values
        mock_service.get_messages.assert_called_once_with(
            conversation_id="user123#user456", since_timestamp=None, limit=50
        )

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_has_more_true(self, mock_extract_sender, mock_message_service_class):
        """Test get messages when there are more messages available."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service

        # Create mock messages
        mock_messages = [Mock() for _ in range(5)]
        for i, msg in enumerate(mock_messages):
            msg.message_id = f"msg-{i}"
            msg.conversation_id = "user123#user456"
            msg.sender_id = "user123"
            msg.recipient_id = "user456"
            msg.content = f"Message {i}"
            msg.status = MessageStatus.SENT
            msg.timestamp = f"2023-01-01T12:0{i}:00Z"

        mock_service.get_messages.return_value = (mock_messages, True)

        mock_event = Mock()
        mock_event.query_string_parameters = {"limit": "5"}

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            response = get_messages("user123#user456")

        # Verify response
        assert len(response["messages"]) == 5
        assert response["hasMore"] is True

    def test_get_messages_missing_environment_variables(self):
        """Test get messages with missing environment variables."""
        # Remove environment variables
        if "DYNAMODB_TABLE_NAME" in os.environ:
            del os.environ["DYNAMODB_TABLE_NAME"]
        if "SNS_TOPIC_ARN" in os.environ:
            del os.environ["SNS_TOPIC_ARN"]

        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from aws_lambda_powertools.event_handler.exceptions import InternalServerError

            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            with (
                patch(
                    "chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt",
                    return_value="user123",
                ),
                pytest.raises(InternalServerError),
            ):
                get_messages("user123#user456")

    @patch("chatbot_messaging_backend.handlers.lambda_handler.MessageService")
    @patch("chatbot_messaging_backend.handlers.lambda_handler.extract_sender_id_from_jwt")
    def test_get_messages_response_format(self, mock_extract_sender, mock_message_service_class):
        """Test that get messages returns the correct response format."""
        mock_extract_sender.return_value = "user123"

        mock_service = Mock()
        mock_message_service_class.return_value = mock_service

        # Create a single mock message with all fields
        mock_message = Mock()
        mock_message.message_id = "msg-123"
        mock_message.conversation_id = "user123#user456"
        mock_message.sender_id = "user123"
        mock_message.recipient_id = "user456"
        mock_message.content = "Hello, world!"
        mock_message.status = MessageStatus.READ
        mock_message.timestamp = "2023-01-01T12:00:00Z"

        mock_service.get_messages.return_value = ([mock_message], False)

        mock_event = Mock()
        mock_event.query_string_parameters = None

        with patch.object(app, "current_event", mock_event, create=True):
            from chatbot_messaging_backend.handlers.lambda_handler import get_messages

            response = get_messages("user123#user456")

        # Verify response structure
        assert isinstance(response, dict)
        assert "messages" in response
        assert "hasMore" in response
        assert isinstance(response["messages"], list)
        assert isinstance(response["hasMore"], bool)

        # Verify message structure
        message = response["messages"][0]
        expected_fields = ["messageId", "conversationId", "senderId", "recipientId", "content", "status", "timestamp"]
        for field in expected_fields:
            assert field in message

        # Verify field values
        assert message["messageId"] == "msg-123"
        assert message["conversationId"] == "user123#user456"
        assert message["senderId"] == "user123"
        assert message["recipientId"] == "user456"
        assert message["content"] == "Hello, world!"
        assert message["status"] == "read"
        assert message["timestamp"] == "2023-01-01T12:00:00Z"
