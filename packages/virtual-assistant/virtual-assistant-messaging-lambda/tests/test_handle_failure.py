# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for handle_failure Lambda handler."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from virtual_assistant_messaging_lambda.handlers.handle_failure import lambda_handler


@pytest.fixture
def mock_env():
    """Set up environment variables for tests."""
    with patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}):
        yield


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table."""
    with patch("virtual_assistant_messaging_lambda.handlers.handle_failure.dynamodb") as mock_db:
        mock_table = MagicMock()
        mock_db.Table.return_value = mock_table
        yield mock_table


@pytest.fixture
def mock_platform_router():
    """Mock platform router."""
    with patch("virtual_assistant_messaging_lambda.handlers.handle_failure.platform_router") as mock_router:
        mock_router.update_message_status = AsyncMock()
        yield mock_router


def test_handle_failure_marks_processing_messages_as_failed(mock_env, mock_dynamodb_table, mock_platform_router):
    """Test that handle_failure marks all processing messages as failed.

    Requirements: 7.5, 8.4
    """
    # Setup test data
    user_id = "test-user-123"
    error_details = "AgentCore invocation failed after retries"

    # Mock DynamoDB response with processing messages
    mock_dynamodb_table.get_item.return_value = {
        "Item": {
            "user_id": user_id,
            "messages": [
                {"message_id": "msg-1", "content": "Hello", "processing": True},
                {"message_id": "msg-2", "content": "World", "processing": True},
                {"message_id": "msg-3", "content": "New message", "processing": False},
            ],
        }
    }

    # Create event
    event = {"user_id": user_id, "error": error_details}

    # Call handler
    result = lambda_handler(event, MagicMock())

    # Verify result
    assert result["status"] == "success"
    assert result["failed_count"] == 2

    # Verify platform router was called for processing messages only
    assert mock_platform_router.update_message_status.call_count == 2
    mock_platform_router.update_message_status.assert_any_call("msg-1", "failed")
    mock_platform_router.update_message_status.assert_any_call("msg-2", "failed")


def test_handle_failure_with_no_processing_messages(mock_env, mock_dynamodb_table, mock_platform_router):
    """Test handle_failure when no processing messages exist.

    Requirements: 7.5, 8.4
    """
    # Setup test data
    user_id = "test-user-123"

    # Mock DynamoDB response with no processing messages
    mock_dynamodb_table.get_item.return_value = {
        "Item": {
            "user_id": user_id,
            "messages": [
                {"message_id": "msg-1", "content": "Hello", "processing": False},
                {"message_id": "msg-2", "content": "World", "processing": False},
            ],
        }
    }

    # Create event
    event = {"user_id": user_id, "error": "Some error"}

    # Call handler
    result = lambda_handler(event, MagicMock())

    # Verify result
    assert result["status"] == "success"
    assert result["failed_count"] == 0

    # Verify platform router was not called
    assert mock_platform_router.update_message_status.call_count == 0


def test_handle_failure_with_empty_buffer(mock_env, mock_dynamodb_table, mock_platform_router):
    """Test handle_failure when buffer doesn't exist.

    Requirements: 7.5, 8.4
    """
    # Setup test data
    user_id = "test-user-123"

    # Mock DynamoDB response with no item
    mock_dynamodb_table.get_item.return_value = {}

    # Create event
    event = {"user_id": user_id, "error": "Some error"}

    # Call handler
    result = lambda_handler(event, MagicMock())

    # Verify result
    assert result["status"] == "success"
    assert result["failed_count"] == 0

    # Verify platform router was not called
    assert mock_platform_router.update_message_status.call_count == 0


def test_handle_failure_logs_error_details(mock_env, mock_dynamodb_table, mock_platform_router):
    """Test that handle_failure logs error details with message IDs.

    Requirements: 7.5
    """
    # Setup test data
    user_id = "test-user-123"
    error_details = "Timeout after 3 retries"

    # Mock DynamoDB response
    mock_dynamodb_table.get_item.return_value = {
        "Item": {
            "user_id": user_id,
            "messages": [
                {"message_id": "msg-1", "content": "Hello", "processing": True},
            ],
        }
    }

    # Create event
    event = {"user_id": user_id, "error": error_details}

    # Call handler with logger mock
    with patch("virtual_assistant_messaging_lambda.handlers.handle_failure.logger") as mock_logger:
        result = lambda_handler(event, MagicMock())

        # Verify error was logged with details
        assert mock_logger.error.call_count >= 1

        # Check that error details were logged
        error_calls = [call for call in mock_logger.error.call_args_list]
        assert any(error_details in str(call) or "user_id" in str(call) for call in error_calls)

    # Verify result
    assert result["status"] == "success"
    assert result["failed_count"] == 1


def test_handle_failure_continues_on_individual_message_failure(mock_env, mock_dynamodb_table, mock_platform_router):
    """Test that handle_failure continues marking messages even if one fails.

    Requirements: 7.5, 8.4
    """
    # Setup test data
    user_id = "test-user-123"

    # Mock DynamoDB response
    mock_dynamodb_table.get_item.return_value = {
        "Item": {
            "user_id": user_id,
            "messages": [
                {"message_id": "msg-1", "content": "Hello", "processing": True},
                {"message_id": "msg-2", "content": "World", "processing": True},
                {"message_id": "msg-3", "content": "Test", "processing": True},
            ],
        }
    }

    # Mock platform router to fail on second message
    async def mock_update_status(message_id: str, status: str):
        if message_id == "msg-2":
            raise Exception("Failed to update status")

    mock_platform_router.update_message_status.side_effect = mock_update_status

    # Create event
    event = {"user_id": user_id, "error": "Some error"}

    # Call handler
    result = lambda_handler(event, MagicMock())

    # Verify result - should still succeed
    assert result["status"] == "success"
    assert result["failed_count"] == 3

    # Verify platform router was called for all messages
    assert mock_platform_router.update_message_status.call_count == 3


def test_handle_failure_missing_user_id(mock_env, mock_dynamodb_table, mock_platform_router):
    """Test handle_failure raises error when user_id is missing.

    Requirements: 7.5
    """
    # Create event without user_id
    event = {"error": "Some error"}

    # Call handler and expect error
    with pytest.raises(ValueError, match="Missing required parameter: user_id"):
        lambda_handler(event, MagicMock())


def test_handle_failure_missing_environment_variable(mock_dynamodb_table, mock_platform_router):
    """Test handle_failure raises error when environment variable is missing.

    Requirements: 7.5
    """
    # Create event
    event = {"user_id": "test-user-123", "error": "Some error"}

    # Call handler without environment variable
    with pytest.raises(ValueError, match="Missing required environment variable: MESSAGE_BUFFER_TABLE"):
        lambda_handler(event, MagicMock())
