# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for mark messages as processing handler.

Feature: stepfunctions-message-buffering
Tests the correctness properties defined in the design document.
"""

import os
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from virtual_assistant_messaging_lambda.handlers.mark_messages_processing import lambda_handler


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
def event_strategy(draw):
    """Generate a Step Functions event with messages."""
    user_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))

    # Generate a mix of processing and non-processing messages
    num_messages = draw(st.integers(min_value=1, max_value=10))
    messages = []

    for _ in range(num_messages):
        # Randomly decide if message is processing or not
        is_processing = draw(st.booleans())
        msg = draw(message_strategy(processing=is_processing))
        messages.append(msg)

    return {"user_id": user_id, "messages": messages}


# Property 11: Messages Marked as Processing
@settings(max_examples=100)
@given(event_strategy())
def test_property_11_messages_marked_as_processing(event):
    """Property 11: Messages Marked as Processing

    For any workflow ready to invoke AgentCore, all non-processing messages should
    be marked with processing = true before invocation.

    Feature: stepfunctions-message-buffering, Property 11: Messages Marked as Processing
    Validates: Requirements 4.1
    """
    # Mock DynamoDB
    mock_table = MagicMock()

    # Track update_item calls
    update_calls = []

    def track_update_item(**kwargs):
        update_calls.append(kwargs)
        return {}

    mock_table.update_item.side_effect = track_update_item

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.mark_messages_processing.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Count non-processing messages before
        non_processing_before = [msg for msg in event["messages"] if not msg.get("processing", False)]

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response structure
        assert "processing_messages" in response
        assert "message_count" in response

        # Verify count matches non-processing messages
        assert response["message_count"] == len(non_processing_before), (
            f"Expected {len(non_processing_before)} messages to be marked, got {response['message_count']}"
        )

        # Verify DynamoDB was updated only if there were non-processing messages
        if len(non_processing_before) > 0:
            assert len(update_calls) == 1, (
                "Should have exactly one update_item call when there are non-processing messages"
            )

            update_call = update_calls[0]
            assert update_call["Key"]["user_id"] == event["user_id"]

            # Verify the updated messages list
            updated_messages = update_call["ExpressionAttributeValues"][":msgs"]
        else:
            # No non-processing messages, so no DynamoDB update should happen
            assert len(update_calls) == 0, "Should have no update_item calls when all messages are already processing"
            updated_messages = event["messages"]

        # All messages that were non-processing should now be processing
        for msg in updated_messages:
            original_msg = next((m for m in event["messages"] if m["message_id"] == msg["message_id"]), None)
            assert original_msg is not None, f"Message {msg['message_id']} not found in original messages"

            if not original_msg.get("processing", False):
                # This message was non-processing, should now be processing
                assert msg["processing"] is True, (
                    f"Message {msg['message_id']} was non-processing but is not marked as processing"
                )
            else:
                # This message was already processing, should remain processing
                assert msg["processing"] is True, (
                    f"Message {msg['message_id']} was already processing but is not marked as processing"
                )

        # Verify all returned processing_messages have processing = true
        for msg in response["processing_messages"]:
            assert msg.get("processing", False) is True, (
                f"Returned message {msg.get('message_id')} does not have processing = true"
            )


# Additional test: Empty messages list
@settings(max_examples=100)
@given(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
def test_mark_messages_empty_list(user_id):
    """Test marking messages when there are no messages in the buffer.

    Feature: stepfunctions-message-buffering
    """
    event = {"user_id": user_id, "messages": []}

    # Mock DynamoDB
    mock_table = MagicMock()

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.mark_messages_processing.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response
        assert response["processing_messages"] == []
        assert response["message_count"] == 0

        # Verify DynamoDB was not updated (no messages to mark)
        assert not mock_table.update_item.called, "Should not update DynamoDB when no messages to mark"


# Additional test: All messages already processing
@settings(max_examples=100)
@given(st.lists(message_strategy(processing=True), min_size=1, max_size=10))
def test_mark_messages_all_already_processing(messages):
    """Test marking messages when all messages are already processing.

    Feature: stepfunctions-message-buffering
    """
    user_id = "test_user"
    event = {"user_id": user_id, "messages": messages}

    # Mock DynamoDB
    mock_table = MagicMock()

    with (
        patch.dict(os.environ, {"MESSAGE_BUFFER_TABLE": "test-buffer-table"}),
        patch("virtual_assistant_messaging_lambda.handlers.mark_messages_processing.dynamodb") as mock_dynamodb,
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response - no new messages marked (count = 0), but all processing messages returned
        assert response["message_count"] == 0, f"Expected 0 newly marked messages, got {response['message_count']}"
        assert len(response["processing_messages"]) == len(messages), (
            f"Expected {len(messages)} processing messages returned, got {len(response['processing_messages'])}"
        )

        # Verify all returned messages have processing = true
        for msg in response["processing_messages"]:
            assert msg["processing"] is True
