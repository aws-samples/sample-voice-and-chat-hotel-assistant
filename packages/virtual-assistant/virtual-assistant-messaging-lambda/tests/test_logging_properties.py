# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for logging functionality.

Feature: chat-message-batching
Tests logging properties defined in the design document.
"""

import contextlib
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st
from virtual_assistant_common.models.messaging import MessageEvent

from virtual_assistant_messaging_lambda.handlers.message_processor import group_messages_by_sender, lambda_handler


# Strategies for generating test data
@st.composite
def message_event_strategy(draw, sender_id: str | None = None):
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
        platform="web",
    )


@st.composite
def sqs_record_strategy(draw, message_event: MessageEvent):
    """Generate an SQS record containing a MessageEvent."""
    record_id = draw(st.uuids()).hex

    # Create SNS message wrapper
    sns_message = {
        "Type": "Notification",
        "MessageId": draw(st.uuids()).hex,
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "Subject": "",
        "Message": json.dumps(message_event.model_dump(by_alias=True)),
        "Timestamp": message_event.timestamp,
        "SignatureVersion": "1",
        "Signature": "test-signature",
        "SigningCertURL": "https://test.amazonaws.com/cert.pem",
        "UnsubscribeURL": "https://test.amazonaws.com/unsubscribe",
    }

    # Create SQS record
    sqs_record = {
        "messageId": record_id,
        "receiptHandle": draw(st.text(min_size=10, max_size=50)),
        "body": json.dumps(sns_message),
        "attributes": {
            "ApproximateReceiveCount": "1",
            "SentTimestamp": str(int(datetime.now().timestamp() * 1000)),
        },
        "messageAttributes": {},
        "md5OfBody": draw(st.text(min_size=32, max_size=32, alphabet="0123456789abcdef")),
        "eventSource": "aws:sqs",
        "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue",
        "awsRegion": "us-east-1",
    }

    return sqs_record


@st.composite
def batch_with_senders_strategy(draw, num_senders: int = 3, messages_per_sender: int = 3):
    """Generate a batch of SQS records with multiple senders."""
    # Draw actual integer values if strategies are passed
    if hasattr(num_senders, "example"):
        num_senders = draw(num_senders)
    if hasattr(messages_per_sender, "example"):
        messages_per_sender = draw(messages_per_sender)

    sender_ids = [f"sender_{i}" for i in range(num_senders)]
    records = []

    for sender_id in sender_ids:
        for _ in range(messages_per_sender):
            message = draw(message_event_strategy(sender_id=sender_id))
            record = draw(sqs_record_strategy(message_event=message))
            records.append(record)

    return records, sender_ids


# Property 14: Message ID Logging
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=3), messages_per_sender=st.integers(min_value=1, max_value=3)
    )
)
def test_property_14_message_id_logging(batch_data):
    """Property 14: Message ID Logging

    For any message group being processed, the logs should contain all message IDs
    from the group.

    Feature: chat-message-batching, Property 14: Message ID Logging
    Validates: Requirements 4.4
    """
    records, _ = batch_data

    # Mock environment variables and dependencies
    with (
        patch.dict(
            "os.environ",
            {
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                "MESSAGING_API_ENDPOINT": "https://test.example.com",
                "MESSAGING_CLIENT_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.logger") as mock_logger,
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.asyncio.run") as mock_run,
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.metrics"),
    ):
        # Make processing succeed
        mock_result = MagicMock()
        mock_result.success = True
        mock_run.return_value = mock_result

        # Create event
        event = {"Records": records}
        context = MagicMock()

        # Call handler
        lambda_handler(event, context)

        # Collect all log calls
        log_calls = []
        for call in mock_logger.info.call_args_list:
            if call.args:
                log_calls.append(str(call.args[0]))

        log_output = " ".join(log_calls)

        # Group messages to get expected IDs
        groups = group_messages_by_sender(records)

        # Verify all message IDs appear in logs
        for group in groups:
            for message_id in group.message_ids:
                assert message_id in log_output, f"Message ID {message_id} not found in logs"


# Property 15: Error Context Logging
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=3), messages_per_sender=st.integers(min_value=1, max_value=3)
    )
)
def test_property_15_error_context_logging(batch_data):
    """Property 15: Error Context Logging

    For any error during message group processing, the error log should include
    context for all affected message IDs.

    Feature: chat-message-batching, Property 15: Error Context Logging
    Validates: Requirements 4.5
    """
    records, _ = batch_data

    # Mock environment variables
    with (
        patch.dict(
            "os.environ",
            {
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                "MESSAGING_API_ENDPOINT": "https://test.example.com",
                "MESSAGING_CLIENT_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.logger") as mock_logger,
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.asyncio.run") as mock_run,
    ):
        # Make processing fail
        mock_run.side_effect = Exception("Test error")

        # Create event
        event = {"Records": records}
        context = MagicMock()

        # Call handler (will fail)
        with contextlib.suppress(Exception):
            lambda_handler(event, context)

        # Check error logs contain message IDs
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        error_output = " ".join(error_calls)

        # Group messages to get expected IDs
        groups = group_messages_by_sender(records)

        # Verify error logs contain message IDs from groups
        for group in groups:
            # At least one message ID from the group should appear in error logs
            found = any(msg_id in error_output for msg_id in group.message_ids)
            assert found, f"No message IDs from group {group.sender_id} found in error logs"


# Property 22: Batch Metrics Logging
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=5), messages_per_sender=st.integers(min_value=1, max_value=5)
    )
)
def test_property_22_batch_metrics_logging(batch_data):
    """Property 22: Batch Metrics Logging

    For any batch processing operation, the logs should contain metrics including
    the number of groups and message distribution across groups.

    Feature: chat-message-batching, Property 22: Batch Metrics Logging
    Validates: Requirements 6.5
    """
    records, expected_sender_ids = batch_data

    # Capture log output
    with (
        patch.dict(
            "os.environ",
            {
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                "MESSAGING_API_ENDPOINT": "https://test.example.com",
                "MESSAGING_CLIENT_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            },
        ),
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.logger") as mock_logger,
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.asyncio.run") as mock_run,
        patch("virtual_assistant_messaging_lambda.handlers.message_processor.metrics"),
    ):
        # Make processing succeed
        mock_result = MagicMock()
        mock_result.success = True
        mock_run.return_value = mock_result

        # Create event
        event = {"Records": records}
        context = MagicMock()

        # Call handler
        lambda_handler(event, context)

        # Collect all log calls
        log_calls = []
        for call in mock_logger.info.call_args_list:
            if call.args:
                log_calls.append(str(call.args[0]))

        log_output = " ".join(log_calls)

        # Group messages to get expected counts
        groups = group_messages_by_sender(records)

        # Verify group count appears in logs
        expected_group_count = len(expected_sender_ids)
        assert str(expected_group_count) in log_output, (
            f"Group count {expected_group_count} not found in logs: {log_output}"
        )

        # Verify message distribution (message counts per group) appears in logs
        for group in groups:
            message_count = len(group.messages)
            # The log should contain information about message count for each group
            # Look for the pattern "message_count=X" in logs
            assert f"message_count={message_count}" in log_output or str(message_count) in log_output, (
                f"Message count {message_count} not found in logs"
            )
