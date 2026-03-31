# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for message buffer handler.

Feature: stepfunctions-message-buffering
Tests the correctness properties defined in the design document.
"""

import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from hypothesis import given, settings
from hypothesis import strategies as st
from virtual_assistant_common.models.messaging import MessageEvent

from virtual_assistant_messaging_lambda.handlers.message_buffer_handler import lambda_handler


# Strategies for generating test data
@st.composite
def message_event_strategy(draw, sender_id: str | None = None, platform: str = "web"):
    """Generate a random MessageEvent."""
    if sender_id is None:
        sender_id = draw(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))
        )

    message_id = draw(st.uuids()).hex
    recipient_id = draw(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))
    )
    content = draw(st.text(min_size=1, max_size=200))

    # Generate timestamp
    base_time = datetime.now()
    offset = draw(st.integers(min_value=0, max_value=3600))
    timestamp = (base_time + timedelta(seconds=offset)).isoformat()

    conversation_id = f"{sender_id}#{recipient_id}"

    return MessageEvent(
        message_id=message_id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content,
        timestamp=timestamp,
        platform=platform,
    )


def create_sns_event(message_event: MessageEvent) -> dict:
    """Create a properly formatted SNS event for testing.

    This creates an SNS event that the Powertools SnsEnvelope can parse.
    """
    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:us-east-1:123456789012:test-topic:subscription-id",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": "test-sns-message-id",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                    "Subject": None,  # Can be None
                    "Message": json.dumps(message_event.model_dump(by_alias=True)),
                    "Timestamp": message_event.timestamp,
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://test.amazonaws.com/cert.pem",
                    "UnsubscribeURL": "https://test.amazonaws.com/unsubscribe",
                },
            }
        ]
    }


# Property 1: Message Buffer Write
@settings(max_examples=100)
@given(message_event_strategy())
def test_property_1_message_buffer_write(message_event):
    """Property 1: Message Buffer Write

    For any incoming message, the Message Handler Lambda should write it to the
    DynamoDB buffer with all required fields.

    Feature: stepfunctions-message-buffering, Property 1: Message Buffer Write
    Validates: Requirements 1.2
    """
    # Create SNS event
    sns_event = create_sns_event(message_event)

    # Mock DynamoDB and Step Functions
    mock_table = MagicMock()
    mock_sfn_client = MagicMock()

    # Track update_item calls
    update_calls = []

    def track_update_item(**kwargs):
        update_calls.append(kwargs)
        # First call (message write) succeeds
        if len(update_calls) == 1:
            return {}
        # Second call (waiting state) raises ConditionalCheckFailedException
        raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")

    mock_table.update_item.side_effect = track_update_item

    with (
        patch.dict(
            os.environ,
            {
                "MESSAGE_BUFFER_TABLE": "test-buffer-table",
                "BATCHER_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.dynamodb") as mock_dynamodb,
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.sfn_client", mock_sfn_client),
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(sns_event, MagicMock())

        # Verify response
        assert response["statusCode"] == 200

        # Verify message was written to buffer
        assert len(update_calls) >= 1, "update_item should be called at least once"

        # Check first call (message write)
        first_call = update_calls[0]
        assert first_call["Key"]["user_id"] == message_event.sender_id

        # Verify the message data includes processing flag
        msg_list = first_call["ExpressionAttributeValues"][":msg"]
        assert len(msg_list) == 1
        msg_data = msg_list[0]
        assert msg_data["processing"] is False
        assert msg_data["message_id"] == message_event.message_id
        assert msg_data["sender_id"] == message_event.sender_id
        assert msg_data["content"] == message_event.content

        # Verify TTL is set
        assert ":ttl" in first_call["ExpressionAttributeValues"]
        ttl = first_call["ExpressionAttributeValues"][":ttl"]
        assert isinstance(ttl, int)
        assert ttl > time.time()  # TTL should be in the future


# Property 2: Waiting State Check
@settings(max_examples=100)
@given(message_event_strategy())
def test_property_2_waiting_state_check(message_event):
    """Property 2: Waiting State Check

    For any incoming message, the Message Handler Lambda should check the user's
    waiting state in DynamoDB before starting a workflow.

    Feature: stepfunctions-message-buffering, Property 2: Waiting State Check
    Validates: Requirements 1.3, 7.1
    """
    # Create SNS event
    sns_event = create_sns_event(message_event)

    # Mock DynamoDB and Step Functions
    mock_table = MagicMock()
    mock_sfn_client = MagicMock()

    update_calls = []

    def track_update_item(**kwargs):
        update_calls.append(kwargs)
        # First call (message write) succeeds
        if len(update_calls) == 1:
            return {}
        # Second call (waiting state check) succeeds
        return {}

    mock_table.update_item.side_effect = track_update_item

    with (
        patch.dict(
            os.environ,
            {
                "MESSAGE_BUFFER_TABLE": "test-buffer-table",
                "BATCHER_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.dynamodb") as mock_dynamodb,
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.sfn_client", mock_sfn_client),
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        lambda_handler(sns_event, MagicMock())

        # Verify waiting state check happened (second update_item call)
        assert len(update_calls) >= 2, "Should have at least 2 update_item calls (message write + waiting state check)"

        # Check second call (waiting state check)
        second_call = update_calls[1]
        assert second_call["Key"]["user_id"] == message_event.sender_id

        # Verify conditional expression checks waiting_state
        assert "ConditionExpression" in second_call
        condition = second_call["ConditionExpression"]
        assert "waiting_state" in condition


# Property 3: Conditional Workflow Start
@settings(max_examples=100)
@given(message_event_strategy())
def test_property_3_conditional_workflow_start(message_event):
    """Property 3: Conditional Workflow Start

    For any user with no waiting workflow, the Message Handler Lambda should set
    the waiting state and start a new Step Functions execution.

    Feature: stepfunctions-message-buffering, Property 3: Conditional Workflow Start
    Validates: Requirements 1.4, 7.3
    """
    # Create SNS event
    sns_event = create_sns_event(message_event)

    # Mock DynamoDB and Step Functions
    mock_table = MagicMock()
    mock_sfn_client = MagicMock()

    # Simulate successful waiting state update (no workflow running)
    mock_table.update_item.return_value = {}

    with (
        patch.dict(
            os.environ,
            {
                "MESSAGE_BUFFER_TABLE": "test-buffer-table",
                "BATCHER_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.dynamodb") as mock_dynamodb,
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.sfn_client", mock_sfn_client),
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        lambda_handler(sns_event, MagicMock())

        # Verify Step Functions workflow was started
        assert mock_sfn_client.start_execution.called, "Step Functions workflow should be started"

        # Verify workflow input contains user_id
        call_args = mock_sfn_client.start_execution.call_args
        workflow_input = json.loads(call_args[1]["input"])
        assert workflow_input["user_id"] == message_event.sender_id


# Property 4: No Duplicate Workflows
@settings(max_examples=100)
@given(message_event_strategy())
def test_property_4_no_duplicate_workflows(message_event):
    """Property 4: No Duplicate Workflows

    For any user with an active waiting workflow, the Message Handler Lambda
    should not start a new workflow.

    Feature: stepfunctions-message-buffering, Property 4: No Duplicate Workflows
    Validates: Requirements 1.5, 7.2
    """
    # Create SNS event
    sns_event = create_sns_event(message_event)

    # Mock DynamoDB and Step Functions
    mock_table = MagicMock()
    mock_sfn_client = MagicMock()

    update_calls = []

    def track_update_item(**kwargs):
        update_calls.append(kwargs)
        # First call (message write) succeeds
        if len(update_calls) == 1:
            return {}
        # Second call (waiting state) fails - workflow already running
        raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")

    mock_table.update_item.side_effect = track_update_item

    with (
        patch.dict(
            os.environ,
            {
                "MESSAGE_BUFFER_TABLE": "test-buffer-table",
                "BATCHER_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.dynamodb") as mock_dynamodb,
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.sfn_client", mock_sfn_client),
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Execute handler
        response = lambda_handler(sns_event, MagicMock())

        # Verify response is still successful
        assert response["statusCode"] == 200

        # Verify Step Functions workflow was NOT started
        assert not mock_sfn_client.start_execution.called, "Step Functions workflow should NOT be started"


# Property 5: Waiting State Atomicity
@settings(max_examples=100)
@given(st.lists(message_event_strategy(sender_id="test_user"), min_size=2, max_size=5))
def test_property_5_waiting_state_atomicity(messages):
    """Property 5: Waiting State Atomicity

    For any concurrent message arrivals for the same user, only one Lambda should
    successfully set the waiting state and start a workflow.

    Feature: stepfunctions-message-buffering, Property 5: Waiting State Atomicity
    Validates: Requirements 7.4
    """
    # Simulate concurrent Lambda invocations for the same user
    # We'll track how many times the workflow is started

    workflow_start_count = 0
    update_call_count = 0

    def mock_update_item(**kwargs):
        nonlocal update_call_count, workflow_start_count
        update_call_count += 1

        # First call for each message (message write) succeeds
        if update_call_count % 2 == 1:
            return {}

        # Second call (waiting state check)
        # Only the first message's waiting state check succeeds
        if workflow_start_count == 0:
            workflow_start_count += 1
            return {}
        else:
            # Subsequent messages fail the conditional check
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")

    mock_table = MagicMock()
    mock_table.update_item.side_effect = mock_update_item

    mock_sfn_client = MagicMock()

    with (
        patch.dict(
            os.environ,
            {
                "MESSAGE_BUFFER_TABLE": "test-buffer-table",
                "BATCHER_STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123456789012:stateMachine:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.dynamodb") as mock_dynamodb,
        patch("virtual_assistant_messaging_lambda.handlers.message_buffer_handler.sfn_client", mock_sfn_client),
    ):
        mock_dynamodb.Table.return_value = mock_table

        # Process all messages (simulating concurrent invocations)
        for message in messages:
            sns_event = create_sns_event(message)
            lambda_handler(sns_event, MagicMock())

        # Verify only one workflow was started
        assert mock_sfn_client.start_execution.call_count == 1, (
            f"Expected exactly 1 workflow start, got {mock_sfn_client.start_execution.call_count}"
        )
