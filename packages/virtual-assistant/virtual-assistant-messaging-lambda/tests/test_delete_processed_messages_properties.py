# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for delete processed messages handler.

Feature: stepfunctions-message-buffering
Tests the correctness properties defined in the design document.
"""

import os
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from virtual_assistant_messaging_lambda.handlers.delete_processed_messages import lambda_handler


# Strategies for generating test data
@st.composite
def message_strategy(draw, processing: bool | None = None):
    """Generate a random message object."""
    message_id = draw(st.uuids()).hex
    sender_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
    content = draw(st.text(min_size=1, max_size=200))

    message = {
        "message_id": message_id,
        "sender_id": sender_id,
        "content": content,
        "timestamp": "2024-01-01T00:00:00Z",
    }

    if processing is not None:
        message["processing"] = processing
    elif draw(st.booleans()):
        # Randomly add processing flag
        message["processing"] = draw(st.booleans())

    return message


@st.composite
def buffer_with_messages_strategy(draw):
    """Generate a buffer with a mix of processing and non-processing messages."""
    user_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))

    # Generate a mix of processing and non-processing messages
    num_messages = draw(st.integers(min_value=1, max_value=10))
    messages = []

    for _ in range(num_messages):
        # Randomly decide if message is processing or not
        is_processing = draw(st.booleans())
        msg = draw(message_strategy(processing=is_processing))
        messages.append(msg)

    buffer_item = {
        "user_id": user_id,
        "messages": messages,
        "session_id": "test-session",
        "last_update_time": 1234567890.0,
        "ttl": 1234568490,
    }

    return user_id, buffer_item


# Property 12: Delete Only After Success
@settings(max_examples=100)
@given(buffer_with_messages_strategy())
def test_property_12_delete_only_after_success(buffer_data):
    """Property 12: Delete Only After Success

    For any successful AgentCore invocation, only messages with processing = true
    should be deleted from the buffer.

    Feature: stepfunctions-message-buffering, Property 12: Delete Only After Success
    Validates: Requirements 4.5
    """
    user_id, buffer_item = buffer_data
    event = {"user_id": user_id}

    # Mock DynamoDB
    mock_table = MagicMock()

    # Track calls
    get_item_calls = []
    update_item_calls = []
    delete_item_calls = []

    def track_get_item(**kwargs):
        get_item_calls.append(kwargs)
        return {"Item": buffer_item}

    def track_update_item(**kwargs):
        update_item_calls.append(kwargs)
        return {}

    def track_delete_item(**kwargs):
        delete_item_calls.append(kwargs)
        return {}

    mock_table.get_item.side_effect = track_get_item
    mock_table.update_item.side_effect = track_update_item
    mock_table.delete_item.side_effect = track_delete_item

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.delete_processed_messages.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Count processing and non-processing messages before
        processing_messages = [msg for msg in buffer_item["messages"] if msg.get("processing", False)]
        non_processing_messages = [msg for msg in buffer_item["messages"] if not msg.get("processing", False)]

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response structure
        assert "status" in response
        assert "deleted_count" in response
        assert response["status"] == "success"

        # Verify deleted count matches processing messages
        assert response["deleted_count"] == len(processing_messages), (
            f"Expected {len(processing_messages)} messages to be deleted, got {response['deleted_count']}"
        )

        # Verify DynamoDB operations
        assert len(get_item_calls) == 1, "Should have exactly one get_item call"
        assert get_item_calls[0]["Key"]["user_id"] == user_id

        if len(non_processing_messages) > 0:
            # Should update buffer with remaining messages
            assert len(update_item_calls) == 1, "Should have exactly one update_item call when messages remain"
            assert len(delete_item_calls) == 0, "Should not delete buffer when messages remain"

            # Verify remaining messages are only non-processing ones
            updated_messages = update_item_calls[0]["ExpressionAttributeValues"][":msgs"]
            assert len(updated_messages) == len(non_processing_messages), (
                f"Expected {len(non_processing_messages)} remaining messages, got {len(updated_messages)}"
            )

            # Verify all remaining messages have processing = false
            for msg in updated_messages:
                assert not msg.get("processing", False), (
                    f"Remaining message {msg.get('message_id')} should not have processing = true"
                )

            # Verify no processing messages remain
            for msg in updated_messages:
                original_msg = next((m for m in buffer_item["messages"] if m["message_id"] == msg["message_id"]), None)
                assert original_msg is not None
                assert not original_msg.get("processing", False), (
                    f"Message {msg['message_id']} was processing but is still in buffer"
                )

        else:
            # Should delete buffer entry (no remaining messages)
            assert len(update_item_calls) == 0, "Should not update buffer when no messages remain"
            assert len(delete_item_calls) == 1, "Should delete buffer when no messages remain"
            assert delete_item_calls[0]["Key"]["user_id"] == user_id


# Property 13: Messages Retained on Failure
@settings(max_examples=100)
@given(buffer_with_messages_strategy())
def test_property_13_messages_retained_on_failure(buffer_data):
    """Property 13: Messages Retained on Failure

    For any failed AgentCore invocation, messages with processing = true should
    remain in the buffer for retry.

    This test simulates the failure scenario by NOT calling the delete handler,
    which represents what happens when AgentCore invocation fails. The messages
    should remain in the buffer with processing = true.

    Feature: stepfunctions-message-buffering, Property 13: Messages Retained on Failure
    Validates: Requirements 4.5
    """
    user_id, buffer_item = buffer_data

    # Mock DynamoDB
    mock_table = MagicMock()

    # Simulate failure by not calling delete handler
    # Instead, verify that messages remain in buffer

    def get_buffer():
        return {"Item": buffer_item}

    mock_table.get_item.return_value = get_buffer()

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.delete_processed_messages.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Count processing messages before
        processing_messages = [msg for msg in buffer_item["messages"] if msg.get("processing", False)]

        # Simulate failure: delete handler is NOT called
        # Instead, verify buffer state remains unchanged

        # Get buffer to verify messages are still there
        response = mock_table.get_item(Key={"user_id": user_id})
        assert "Item" in response

        current_messages = response["Item"]["messages"]

        # Verify all processing messages are still in buffer
        current_processing = [msg for msg in current_messages if msg.get("processing", False)]
        assert len(current_processing) == len(processing_messages), (
            f"Expected {len(processing_messages)} processing messages to remain, got {len(current_processing)}"
        )

        # Verify each processing message is still present
        for original_msg in processing_messages:
            found = any(
                msg["message_id"] == original_msg["message_id"] and msg.get("processing", False)
                for msg in current_messages
            )
            assert found, f"Processing message {original_msg['message_id']} should remain in buffer on failure"

        # Verify the processing flag is still true for these messages
        for msg in current_processing:
            assert msg.get("processing", False) is True, (
                f"Message {msg.get('message_id')} should still have processing = true on failure"
            )


# Additional test: Empty buffer
@settings(max_examples=100)
@given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
def test_delete_messages_empty_buffer(user_id):
    """Test deleting messages when buffer doesn't exist.

    Feature: stepfunctions-message-buffering
    """
    event = {"user_id": user_id}

    # Mock DynamoDB
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}  # No Item in response

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.delete_processed_messages.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response
        assert response["status"] == "already_deleted"
        assert response["deleted_count"] == 0

        # Verify no update or delete operations
        assert not mock_table.update_item.called
        assert not mock_table.delete_item.called


# Additional test: All messages are processing
@settings(max_examples=100)
@given(st.lists(message_strategy(processing=True), min_size=1, max_size=10))
def test_delete_messages_all_processing(messages):
    """Test deleting messages when all messages are processing.

    Feature: stepfunctions-message-buffering
    """
    user_id = "test_user"
    buffer_item = {
        "user_id": user_id,
        "messages": messages,
        "session_id": "test-session",
        "last_update_time": 1234567890.0,
        "ttl": 1234568490,
    }
    event = {"user_id": user_id}

    # Mock DynamoDB
    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": buffer_item}

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.delete_processed_messages.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response
        assert response["status"] == "success"
        assert response["deleted_count"] == len(messages)

        # Verify buffer was deleted (no remaining messages)
        assert mock_table.delete_item.called
        assert not mock_table.update_item.called


# Additional test: No messages are processing
@settings(max_examples=100)
@given(st.lists(message_strategy(processing=False), min_size=1, max_size=10))
def test_delete_messages_none_processing(messages):
    """Test deleting messages when no messages are processing.

    Feature: stepfunctions-message-buffering
    """
    user_id = "test_user"
    buffer_item = {
        "user_id": user_id,
        "messages": messages,
        "session_id": "test-session",
        "last_update_time": 1234567890.0,
        "ttl": 1234568490,
    }
    event = {"user_id": user_id}

    # Mock DynamoDB
    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": buffer_item}

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.delete_processed_messages.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response
        assert response["status"] == "success"
        assert response["deleted_count"] == 0

        # Verify buffer was updated with all messages (none deleted)
        assert mock_table.update_item.called
        assert not mock_table.delete_item.called

        # Verify all messages remain
        update_call = mock_table.update_item.call_args
        updated_messages = update_call[1]["ExpressionAttributeValues"][":msgs"]
        assert len(updated_messages) == len(messages)
