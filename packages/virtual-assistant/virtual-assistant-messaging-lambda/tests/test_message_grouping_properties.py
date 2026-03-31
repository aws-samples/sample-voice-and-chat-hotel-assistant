# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for message grouping and batch processing.

Feature: chat-message-batching
Tests the correctness properties defined in the design document.
"""

import json
from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st
from virtual_assistant_common.models.messaging import MessageEvent, MessageGroup

from virtual_assistant_messaging_lambda.handlers.message_processor import group_messages_by_sender


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


@st.composite
def sqs_record_strategy(draw, message_event: MessageEvent):
    """Generate an SQS record containing a MessageEvent."""
    record_id = draw(st.uuids()).hex

    # Create SNS message wrapper with all required fields
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


# Property 1: Message Grouping by Sender
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=5), messages_per_sender=st.integers(min_value=1, max_value=5)
    )
)
def test_property_1_message_grouping_by_sender(batch_data):
    """Property 1: Message Grouping by Sender

    For any SQS batch containing messages, all messages with the same sender_id
    should be grouped together into a single MessageGroup, and no messages from
    different senders should appear in the same group.

    Feature: chat-message-batching, Property 1: Message Grouping by Sender
    Validates: Requirements 1.1, 1.5
    """
    records, expected_sender_ids = batch_data

    # Group messages
    groups = group_messages_by_sender(records)

    # Check that each group contains only messages from one sender
    for group in groups:
        sender_ids_in_group = {msg.sender_id for msg in group.messages}
        assert len(sender_ids_in_group) == 1, f"Group contains messages from multiple senders: {sender_ids_in_group}"

    # Check that all senders are represented
    grouped_sender_ids = {group.sender_id for group in groups}
    assert grouped_sender_ids == set(expected_sender_ids), "Not all senders are represented in groups"


# Property 2: Message Order Preservation
@settings(max_examples=100)
@given(st.lists(message_event_strategy(sender_id="test_sender"), min_size=2, max_size=10))
def test_property_2_message_order_preservation(messages):
    """Property 2: Message Order Preservation

    For any MessageGroup, the messages within the group should be ordered by
    timestamp in ascending order (earliest first).

    Feature: chat-message-batching, Property 2: Message Order Preservation
    Validates: Requirements 1.2
    """
    # Create SQS records from messages
    records = []
    for msg in messages:
        record = {
            "messageId": msg.message_id,
            "receiptHandle": "test-handle",
            "body": json.dumps(
                {
                    "Type": "Notification",
                    "MessageId": msg.message_id,
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                    "Subject": "",
                    "Message": json.dumps(msg.model_dump(by_alias=True)),
                    "Timestamp": msg.timestamp,
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://test.amazonaws.com/cert.pem",
                    "UnsubscribeURL": "https://test.amazonaws.com/unsubscribe",
                }
            ),
            "attributes": {"ApproximateReceiveCount": "1", "SentTimestamp": "1234567890"},
            "messageAttributes": {},
            "md5OfBody": "test-md5",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            "awsRegion": "us-east-1",
        }
        records.append(record)

    # Group messages
    groups = group_messages_by_sender(records)

    # Should have exactly one group since all messages have same sender
    assert len(groups) == 1, f"Expected 1 group, got {len(groups)}"

    group = groups[0]

    # Check that messages are sorted by timestamp
    timestamps = [msg.timestamp for msg in group.messages]
    assert timestamps == sorted(timestamps), f"Messages not sorted by timestamp: {timestamps}"


# Property 3: Message Content Combination
@settings(max_examples=100)
@given(st.lists(message_event_strategy(sender_id="test_sender"), min_size=1, max_size=5))
def test_property_3_message_content_combination(messages):
    """Property 3: Message Content Combination

    For any MessageGroup with multiple messages, the combined_content should equal
    the message contents joined with newline separators, preserving the order.

    Feature: chat-message-batching, Property 3: Message Content Combination
    Validates: Requirements 1.3
    """
    # Create message group directly
    group = MessageGroup(messages=sorted(messages, key=lambda m: m.timestamp))

    # Expected combined content
    expected_content = "\n".join(msg.content for msg in group.messages)

    # Check combined content
    assert group.combined_content == expected_content, "Combined content doesn't match expected"


# Property 4: Message ID Tracking
@settings(max_examples=100)
@given(st.lists(message_event_strategy(sender_id="test_sender"), min_size=1, max_size=10))
def test_property_4_message_id_tracking(messages):
    """Property 4: Message ID Tracking

    For any MessageGroup, the message_ids list should contain exactly the message
    IDs from all messages in the group, with no duplicates or omissions.

    Feature: chat-message-batching, Property 4: Message ID Tracking
    Validates: Requirements 1.4
    """
    # Create message group
    group = MessageGroup(messages=messages)

    # Expected message IDs
    expected_ids = [msg.message_id for msg in messages]

    # Check message IDs
    assert group.message_ids == expected_ids, "Message IDs don't match"
    assert len(group.message_ids) == len(set(group.message_ids)), "Duplicate message IDs found"


# Property 5: Single Invocation Per Sender
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=5), messages_per_sender=st.integers(min_value=1, max_value=5)
    )
)
def test_property_5_single_invocation_per_sender(batch_data):
    """Property 5: Single Invocation Per Sender

    For any batch processing operation, each unique sender_id should result in
    exactly one AgentCore Runtime invocation (one MessageGroup).

    Feature: chat-message-batching, Property 5: Single Invocation Per Sender
    Validates: Requirements 2.1
    """
    records, expected_sender_ids = batch_data

    # Group messages
    groups = group_messages_by_sender(records)

    # Check that we have one group per sender
    assert len(groups) == len(expected_sender_ids), f"Expected {len(expected_sender_ids)} groups, got {len(groups)}"

    # Check that each sender has exactly one group
    sender_counts = {}
    for group in groups:
        sender_id = group.sender_id
        sender_counts[sender_id] = sender_counts.get(sender_id, 0) + 1

    for sender_id, count in sender_counts.items():
        assert count == 1, f"Sender {sender_id} has {count} groups, expected 1"


# Property 21: Complete Batch Processing
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=5), messages_per_sender=st.integers(min_value=1, max_value=5)
    )
)
def test_property_21_complete_batch_processing(batch_data):
    """Property 21: Complete Batch Processing

    For any SQS batch, all messages in the batch should be processed (either
    successfully or marked as failed).

    Feature: chat-message-batching, Property 21: Complete Batch Processing
    Validates: Requirements 6.3
    """
    records, _ = batch_data

    # Group messages
    groups = group_messages_by_sender(records)

    # Count total messages in groups
    total_messages_in_groups = sum(len(group.messages) for group in groups)

    # Should equal number of records
    assert total_messages_in_groups == len(records), (
        f"Not all messages processed: {total_messages_in_groups} out of {len(records)}"
    )


# Property 23: WhatsApp Grouping by Phone
@settings(max_examples=100)
@given(st.lists(st.text(min_size=10, max_size=15, alphabet="0123456789+"), min_size=1, max_size=5, unique=True))
def test_property_23_whatsapp_grouping_by_phone(phone_numbers):
    """Property 23: WhatsApp Grouping by Phone

    For any batch containing WhatsApp messages, messages should be grouped by
    sanitized phone number (sender_id with special characters removed).

    Feature: chat-message-batching, Property 23: WhatsApp Grouping by Phone
    Validates: Requirements 7.1
    """
    # Create WhatsApp messages with different phone numbers
    records = []
    for phone in phone_numbers:
        # Create a WhatsApp-style message event
        message = MessageEvent(
            message_id=f"msg_{phone}",
            conversation_id=f"whatsapp-conversation-{phone.replace('+', '').replace('-', '')}-session-id",
            sender_id=phone,
            recipient_id="hotel_assistant",
            content=f"Message from {phone}",
            timestamp=datetime.now().isoformat(),
            platform="aws-eum",
        )

        # Create SQS record
        record = {
            "messageId": message.message_id,
            "receiptHandle": "test-handle",
            "body": json.dumps(
                {
                    "Type": "Notification",
                    "MessageId": message.message_id,
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                    "Subject": "",
                    "Message": json.dumps(message.model_dump(by_alias=True)),
                    "Timestamp": message.timestamp,
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://test.amazonaws.com/cert.pem",
                    "UnsubscribeURL": "https://test.amazonaws.com/unsubscribe",
                }
            ),
            "attributes": {"ApproximateReceiveCount": "1", "SentTimestamp": "1234567890"},
            "messageAttributes": {},
            "md5OfBody": "test-md5",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            "awsRegion": "us-east-1",
        }
        records.append(record)

    # Group messages
    groups = group_messages_by_sender(records)

    # Should have one group per unique phone number
    assert len(groups) == len(phone_numbers), f"Expected {len(phone_numbers)} groups, got {len(groups)}"

    # Each group should have messages from only one phone number
    for group in groups:
        phone_numbers_in_group = {msg.sender_id for msg in group.messages}
        assert len(phone_numbers_in_group) == 1, (
            f"Group contains messages from multiple phones: {phone_numbers_in_group}"
        )


# Property 24: Simulated Message Grouping
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=5), messages_per_sender=st.integers(min_value=1, max_value=5)
    )
)
def test_property_24_simulated_message_grouping(batch_data):
    """Property 24: Simulated Message Grouping

    For any batch containing simulated messages, messages should be grouped by
    the sender_id field.

    Feature: chat-message-batching, Property 24: Simulated Message Grouping
    Validates: Requirements 7.2
    """
    records, expected_sender_ids = batch_data

    # Group messages
    groups = group_messages_by_sender(records)

    # Check that we have one group per sender
    assert len(groups) == len(expected_sender_ids), f"Expected {len(expected_sender_ids)} groups, got {len(groups)}"

    # Check that each group's sender_id matches one of the expected senders
    grouped_sender_ids = {group.sender_id for group in groups}
    assert grouped_sender_ids == set(expected_sender_ids), "Grouped sender IDs don't match expected"


# Property 25: Message Data Preservation
@settings(max_examples=100)
@given(st.lists(message_event_strategy(sender_id="test_sender"), min_size=1, max_size=10))
def test_property_25_message_data_preservation(messages):
    """Property 25: Message Data Preservation

    For any message group, all original MessageEvent objects should be preserved
    in the messages list without modification.

    Feature: chat-message-batching, Property 25: Message Data Preservation
    Validates: Requirements 7.3
    """
    # Create message group
    group = MessageGroup(messages=messages)

    # Check that all messages are preserved
    assert len(group.messages) == len(messages), "Not all messages preserved"

    # Check that message data is unchanged
    for original, preserved in zip(messages, group.messages, strict=True):
        assert original.message_id == preserved.message_id, "Message ID changed"
        assert original.sender_id == preserved.sender_id, "Sender ID changed"
        assert original.content == preserved.content, "Content changed"
        assert original.timestamp == preserved.timestamp, "Timestamp changed"
        assert original.platform == preserved.platform, "Platform changed"


# Property 13: Grouping Idempotency
@settings(max_examples=100)
@given(
    batch_with_senders_strategy(
        num_senders=st.integers(min_value=1, max_value=3), messages_per_sender=st.integers(min_value=1, max_value=3)
    )
)
def test_property_13_grouping_idempotency(batch_data):
    """Property 13: Grouping Idempotency

    For any message that is retried by SQS, it should be grouped with the same
    sender's messages using the same grouping logic as the initial attempt.

    Feature: chat-message-batching, Property 13: Grouping Idempotency
    Validates: Requirements 4.2
    """
    records, _ = batch_data

    # Group messages first time
    groups1 = group_messages_by_sender(records)

    # Group messages second time (simulating retry)
    groups2 = group_messages_by_sender(records)

    # Should produce same grouping
    assert len(groups1) == len(groups2), "Different number of groups on retry"

    # Sort groups by sender_id for comparison
    groups1_sorted = sorted(groups1, key=lambda g: g.sender_id)
    groups2_sorted = sorted(groups2, key=lambda g: g.sender_id)

    for g1, g2 in zip(groups1_sorted, groups2_sorted, strict=True):
        assert g1.sender_id == g2.sender_id, "Different sender IDs on retry"
        assert len(g1.messages) == len(g2.messages), "Different message counts on retry"
        assert g1.message_ids == g2.message_ids, "Different message IDs on retry"
