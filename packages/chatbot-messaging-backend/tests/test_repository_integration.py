# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for MessageRepository with actual DynamoDB."""

import contextlib
import time

import boto3
import pytest
from botocore.exceptions import ClientError

from chatbot_messaging_backend.models.message import MessageStatus, create_message
from chatbot_messaging_backend.utils.repository import MessageRepository


@pytest.mark.integration
class TestMessageRepositoryIntegration:
    """Integration test cases for MessageRepository with real DynamoDB."""

    def setup_method(self):
        """Set up test fixtures with real DynamoDB."""
        # Create DynamoDB client
        self.dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        self.table_name = f"test-chatbot-messages-{int(time.time())}"

        # Create the table
        try:
            self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "conversationId", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "conversationId", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"},
                    {"AttributeName": "messageId", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "MessageIdIndex",
                        "KeySchema": [{"AttributeName": "messageId", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

            # Wait for table to be active
            waiter = self.dynamodb.get_waiter("table_exists")
            waiter.wait(TableName=self.table_name, WaiterConfig={"Delay": 1, "MaxAttempts": 30})

            # Wait for GSI to be active
            self._wait_for_gsi_active()

        except Exception as e:
            pytest.skip(f"Failed to create DynamoDB table for integration test: {e}")

        # Create repository
        self.repository = MessageRepository(table_name=self.table_name, dynamodb_client=self.dynamodb)

    def teardown_method(self):
        """Clean up after tests."""
        with contextlib.suppress(ClientError):
            # Delete the table
            self.dynamodb.delete_table(TableName=self.table_name)

    def _wait_for_gsi_active(self):
        """Wait for Global Secondary Index to become active."""
        max_attempts = 30
        for _attempt in range(max_attempts):
            try:
                response = self.dynamodb.describe_table(TableName=self.table_name)
                gsi_status = response["Table"]["GlobalSecondaryIndexes"][0]["IndexStatus"]
                if gsi_status == "ACTIVE":
                    return
                time.sleep(1)
            except (KeyError, IndexError):
                time.sleep(1)

        pytest.skip("GSI did not become active within timeout period")

    def test_create_and_retrieve_message(self):
        """Test creating a message and retrieving it."""
        # Create a test message
        message = create_message(
            sender_id="user123",
            recipient_id="bot456",
            content="Hello, integration test!",
            message_id="integration-test-msg",
        )

        # Store the message
        stored_message = self.repository.create_message(message)

        # Verify the stored message
        assert stored_message == message

        # Retrieve the message by ID
        retrieved_message = self.repository.get_message_by_id("integration-test-msg")

        # Verify the retrieved message
        assert retrieved_message is not None
        assert retrieved_message.message_id == "integration-test-msg"
        assert retrieved_message.content == "Hello, integration test!"
        assert retrieved_message.sender_id == "user123"
        assert retrieved_message.recipient_id == "bot456"
        assert retrieved_message.status == MessageStatus.SENT

    def test_update_message_status_flow(self):
        """Test the complete message status update flow."""
        # Create and store a message
        message = create_message(
            sender_id="user456", recipient_id="bot789", content="Status update test", message_id="status-test-msg"
        )
        self.repository.create_message(message)

        # Update the message status
        updated_message = self.repository.update_message_status(
            message_id="status-test-msg", status=MessageStatus.READ, updated_at="2024-01-01T13:00:00Z"
        )

        # Verify the update
        assert updated_message is not None
        assert updated_message.message_id == "status-test-msg"
        assert updated_message.status == MessageStatus.READ
        assert updated_message.updated_at == "2024-01-01T13:00:00Z"

        # Verify the update persisted
        retrieved_message = self.repository.get_message_by_id("status-test-msg")
        assert retrieved_message.status == MessageStatus.READ
        assert retrieved_message.updated_at == "2024-01-01T13:00:00Z"

    def test_query_messages_conversation_flow(self):
        """Test querying messages for a conversation."""
        conversation_id = "user789#bot123"

        # Create multiple messages in the same conversation
        messages = []
        for i in range(5):
            message = create_message(
                sender_id="user789" if i % 2 == 0 else "bot123",
                recipient_id="bot123" if i % 2 == 0 else "user789",
                content=f"Message {i + 1}",
                message_id=f"conv-msg-{i + 1}",
            )
            # Manually set timestamps to ensure ordering and use consistent conversation_id
            message.timestamp = f"2024-01-01T12:0{i}:00Z"
            message.created_at = message.timestamp
            message.updated_at = message.timestamp
            message.conversation_id = conversation_id  # Force same conversation ID for all messages
            messages.append(message)
            self.repository.create_message(message)

        # Query all messages in the conversation
        retrieved_messages = self.repository.query_messages(conversation_id=conversation_id, limit=10)

        # Verify the results
        assert len(retrieved_messages) == 5

        # Verify messages are ordered by timestamp (oldest first)
        for i, msg in enumerate(retrieved_messages):
            assert msg.message_id == f"conv-msg-{i + 1}"
            assert msg.content == f"Message {i + 1}"
            assert msg.conversation_id == conversation_id

    def test_query_messages_with_timestamp_filter(self):
        """Test querying messages with timestamp filtering."""
        conversation_id = "user999#bot888"

        # Create messages with different timestamps
        timestamps = ["2024-01-01T10:00:00Z", "2024-01-01T11:00:00Z", "2024-01-01T12:00:00Z", "2024-01-01T13:00:00Z"]

        for i, timestamp in enumerate(timestamps):
            message = create_message(
                sender_id="user999",
                recipient_id="bot888",
                content=f"Timestamped message {i + 1}",
                message_id=f"ts-msg-{i + 1}",
            )
            message.timestamp = timestamp
            message.created_at = timestamp
            message.updated_at = timestamp
            self.repository.create_message(message)

        # Query messages since 11:30 (should get last 2 messages)
        filtered_messages = self.repository.query_messages(
            conversation_id=conversation_id, since_timestamp="2024-01-01T11:30:00Z", limit=10
        )

        # Verify the results
        assert len(filtered_messages) == 2
        assert filtered_messages[0].message_id == "ts-msg-3"
        assert filtered_messages[1].message_id == "ts-msg-4"

    def test_query_nonexistent_conversation(self):
        """Test querying a conversation that doesn't exist."""
        messages = self.repository.query_messages(conversation_id="nonexistent#conversation", limit=10)

        assert messages == []

    def test_update_nonexistent_message_status(self):
        """Test updating status of a message that doesn't exist."""
        result = self.repository.update_message_status(
            message_id="nonexistent-message", status=MessageStatus.READ, updated_at="2024-01-01T12:00:00Z"
        )

        assert result is None

    def test_get_nonexistent_message_by_id(self):
        """Test retrieving a message that doesn't exist."""
        result = self.repository.get_message_by_id("nonexistent-message")

        assert result is None

    def test_multiple_status_updates(self):
        """Test multiple status updates on the same message."""
        # Create a message
        message = create_message(
            sender_id="user111",
            recipient_id="bot222",
            content="Multiple status updates test",
            message_id="multi-status-msg",
        )
        self.repository.create_message(message)

        # Update status to delivered
        updated1 = self.repository.update_message_status(
            message_id="multi-status-msg", status=MessageStatus.DELIVERED, updated_at="2024-01-01T12:01:00Z"
        )
        assert updated1.status == MessageStatus.DELIVERED

        # Update status to read
        updated2 = self.repository.update_message_status(
            message_id="multi-status-msg", status=MessageStatus.READ, updated_at="2024-01-01T12:02:00Z"
        )
        assert updated2.status == MessageStatus.READ
        assert updated2.updated_at == "2024-01-01T12:02:00Z"

        # Verify final state
        final_message = self.repository.get_message_by_id("multi-status-msg")
        assert final_message.status == MessageStatus.READ
        assert final_message.updated_at == "2024-01-01T12:02:00Z"

    def test_conversation_with_mixed_senders(self):
        """Test a conversation with messages from both participants."""
        conversation_id = "alice#bob"

        # Create messages from both participants
        alice_message = create_message(
            sender_id="alice", recipient_id="bob", content="Hi Bob!", message_id="alice-msg-1"
        )
        alice_message.timestamp = "2024-01-01T12:00:00Z"
        alice_message.created_at = alice_message.timestamp
        alice_message.updated_at = alice_message.timestamp
        alice_message.conversation_id = conversation_id  # Force same conversation ID

        bob_message = create_message(
            sender_id="bob", recipient_id="alice", content="Hello Alice!", message_id="bob-msg-1"
        )
        bob_message.timestamp = "2024-01-01T12:01:00Z"
        bob_message.created_at = bob_message.timestamp
        bob_message.updated_at = bob_message.timestamp
        bob_message.conversation_id = conversation_id  # Force same conversation ID

        # Store both messages
        self.repository.create_message(alice_message)
        self.repository.create_message(bob_message)

        # Query the conversation
        messages = self.repository.query_messages(conversation_id=conversation_id)

        # Verify both messages are retrieved in correct order
        assert len(messages) == 2
        assert messages[0].sender_id == "alice"
        assert messages[0].content == "Hi Bob!"
        assert messages[1].sender_id == "bob"
        assert messages[1].content == "Hello Alice!"

    def test_query_with_limit(self):
        """Test querying messages with a limit."""
        conversation_id = "user_limit#bot_limit"

        # Create more messages than the limit
        for i in range(10):
            message = create_message(
                sender_id="user_limit",
                recipient_id="bot_limit",
                content=f"Limited message {i + 1}",
                message_id=f"limit-msg-{i + 1}",
            )
            message.timestamp = f"2024-01-01T12:{i:02d}:00Z"
            message.created_at = message.timestamp
            message.updated_at = message.timestamp
            self.repository.create_message(message)

        # Query with a limit of 5
        limited_messages = self.repository.query_messages(conversation_id=conversation_id, limit=5)

        # Verify only 5 messages are returned
        assert len(limited_messages) == 5

        # Verify they are the first 5 messages (oldest first)
        for i, msg in enumerate(limited_messages):
            assert msg.message_id == f"limit-msg-{i + 1}"
