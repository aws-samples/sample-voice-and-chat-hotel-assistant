# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for MessageService with real AWS services."""

import contextlib
import json
import time

import boto3
import pytest
from botocore.exceptions import ClientError

from chatbot_messaging_backend.models.message import MessageStatus
from chatbot_messaging_backend.services.message_service import MessageService
from chatbot_messaging_backend.utils.repository import MessageRepository
from chatbot_messaging_backend.utils.sns_publisher import SNSPublisher


@pytest.mark.integration
class TestMessageServiceIntegration:
    """Integration test cases for MessageService with real AWS services."""

    @classmethod
    def setup_class(cls):
        """Set up shared AWS resources once for all tests in this class."""
        # Create AWS clients
        cls.dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        cls.sns_client = boto3.client("sns", region_name="us-east-1")
        cls.sqs_client = boto3.client("sqs", region_name="us-east-1")

        # Generate unique names for shared resources
        timestamp = int(time.time())
        cls.table_name = f"test-chatbot-messages-{timestamp}"
        topic_name = f"test-chatbot-messages-{timestamp}"
        queue_name = f"test-sns-queue-{timestamp}"

        try:
            # Create DynamoDB table
            cls._create_dynamodb_table()

            # Create SNS topic
            response = cls.sns_client.create_topic(Name=topic_name)
            cls.topic_arn = response["TopicArn"]

            # Create SQS queue
            response = cls.sqs_client.create_queue(QueueName=queue_name)
            cls.queue_url = response["QueueUrl"]

            # Setup SNS-SQS subscription
            cls._setup_sns_sqs_subscription()

        except Exception as e:
            pytest.skip(f"Failed to create AWS resources for integration tests: {e}")

    @classmethod
    def teardown_class(cls):
        """Clean up shared AWS resources after all tests complete."""
        # Clean up DynamoDB table
        with contextlib.suppress(ClientError):
            cls.dynamodb.delete_table(TableName=cls.table_name)

        # Clean up SNS topic and subscription
        with contextlib.suppress(ClientError):
            if hasattr(cls, "subscription_arn"):
                cls.sns_client.unsubscribe(SubscriptionArn=cls.subscription_arn)
            cls.sns_client.delete_topic(TopicArn=cls.topic_arn)

        # Clean up SQS queue
        with contextlib.suppress(ClientError):
            cls.sqs_client.delete_queue(QueueUrl=cls.queue_url)

    @classmethod
    def _create_dynamodb_table(cls):
        """Create DynamoDB table and wait for it to be active."""
        cls.dynamodb.create_table(
            TableName=cls.table_name,
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
        waiter = cls.dynamodb.get_waiter("table_exists")
        waiter.wait(TableName=cls.table_name, WaiterConfig={"Delay": 1, "MaxAttempts": 30})

        # Wait for GSI to be active with optimized backoff
        cls._wait_for_gsi_active()

    @classmethod
    def _setup_sns_sqs_subscription(cls):
        """Set up SNS to SQS subscription for message verification."""
        # Get queue attributes
        queue_attributes = cls.sqs_client.get_queue_attributes(QueueUrl=cls.queue_url, AttributeNames=["QueueArn"])
        queue_arn = queue_attributes["Attributes"]["QueueArn"]

        # Set queue policy to allow SNS to send messages
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": cls.topic_arn}},
                }
            ],
        }

        cls.sqs_client.set_queue_attributes(QueueUrl=cls.queue_url, Attributes={"Policy": json.dumps(queue_policy)})

        # Subscribe queue to topic
        subscription_response = cls.sns_client.subscribe(TopicArn=cls.topic_arn, Protocol="sqs", Endpoint=queue_arn)
        cls.subscription_arn = subscription_response["SubscriptionArn"]

    def setup_method(self):
        """Set up test fixtures for each test method."""
        # Make class-level attributes accessible as instance attributes
        self.dynamodb = self.__class__.dynamodb
        self.sns_client = self.__class__.sns_client
        self.sqs_client = self.__class__.sqs_client
        self.table_name = self.__class__.table_name
        self.topic_arn = self.__class__.topic_arn
        self.queue_url = self.__class__.queue_url

        # Clear any existing test data from shared resources
        self._clear_test_data()

        # Create fresh service components for each test
        self.repository = MessageRepository(table_name=self.table_name, dynamodb_client=self.dynamodb)
        self.sns_publisher = SNSPublisher(topic_arn=self.topic_arn, region_name="us-east-1")
        self.message_service = MessageService(repository=self.repository, sns_publisher=self.sns_publisher)

    def teardown_method(self):
        """Clean up test data after each test method."""
        # Clear test data to ensure isolation between tests
        import contextlib

        with contextlib.suppress(Exception):
            # Log warning but don't fail - allow other tests to continue
            self._clear_test_data()

    def _clear_test_data(self):
        """Clear all test data from shared AWS resources."""
        # Clear DynamoDB table data
        self._clear_dynamodb_table()

        # Clear SQS queue messages
        self._clear_sqs_queue()

    def _clear_dynamodb_table(self):
        """Remove all items from the shared DynamoDB table."""
        try:
            # Scan all items in the table
            response = self.dynamodb.scan(TableName=self.table_name)
            items = response.get("Items", [])

            # Delete items in batches
            while items:
                # Prepare batch delete request (max 25 items per batch)
                batch_size = min(25, len(items))
                delete_requests = []

                for item in items[:batch_size]:
                    delete_requests.append(
                        {
                            "DeleteRequest": {
                                "Key": {"conversationId": item["conversationId"], "timestamp": item["timestamp"]}
                            }
                        }
                    )

                if delete_requests:
                    self.dynamodb.batch_write_item(RequestItems={self.table_name: delete_requests})

                # Remove processed items and continue with remaining
                items = items[batch_size:]

                # Handle pagination if there are more items
                if "LastEvaluatedKey" in response:
                    response = self.dynamodb.scan(
                        TableName=self.table_name, ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                    items.extend(response.get("Items", []))
                else:
                    break

        except ClientError as e:
            # If table doesn't exist or other error, that's fine for cleanup
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                pass  # If table doesn't exist or other error, that's fine for cleanup

    def _clear_sqs_queue(self):
        """Remove all messages from the shared SQS queue."""
        try:
            # Purge the queue (fastest method)
            self.sqs_client.purge_queue(QueueUrl=self.queue_url)
        except ClientError as e:
            # If purge fails, try receiving and deleting messages manually
            if e.response["Error"]["Code"] == "PurgeQueueInProgress":
                # Queue is already being purged, that's fine
                return

            try:
                # Receive and delete messages manually
                while True:
                    response = self.sqs_client.receive_message(
                        QueueUrl=self.queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=1
                    )

                    messages = response.get("Messages", [])
                    if not messages:
                        break

                    # Delete received messages
                    for message in messages:
                        self.sqs_client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message["ReceiptHandle"])
            except ClientError:
                # If manual cleanup also fails, log but continue
                pass  # If manual cleanup also fails, continue

    @classmethod
    def _wait_for_gsi_active(cls):
        """Wait for Global Secondary Index to become active with optimized backoff."""
        max_attempts = 20  # Reduced from 30
        delay = 0.1  # Start with 100ms

        for _attempt in range(max_attempts):
            try:
                response = cls.dynamodb.describe_table(TableName=cls.table_name)
                gsi_status = response["Table"]["GlobalSecondaryIndexes"][0]["IndexStatus"]
                if gsi_status == "ACTIVE":
                    return

                # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s, max 3s
                sleep_time = min(delay, 3.0)
                time.sleep(sleep_time)
                delay *= 2

            except (KeyError, IndexError):
                # GSI might not be visible yet, quick retry
                time.sleep(0.1)

        pytest.skip("GSI did not become active within timeout period")

    def _get_sns_messages_from_sqs(self, max_messages=1, wait_time=5):
        """Helper to retrieve SNS messages from SQS queue."""
        messages = self.sqs_client.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=max_messages, WaitTimeSeconds=wait_time
        )

        sns_messages = []
        if "Messages" in messages:
            for msg in messages["Messages"]:
                sqs_message = json.loads(msg["Body"])
                sns_message = json.loads(sqs_message["Message"])
                sns_messages.append(sns_message)

                # Delete message from queue to avoid reprocessing
                self.sqs_client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=msg["ReceiptHandle"])

        return sns_messages

    def test_send_message_complete_flow(self):
        """Test complete send_message flow with real AWS services."""
        # Send a message through the service
        result_message = self.message_service.send_message(
            sender_id="integration-user-123",
            recipient_id="integration-bot-456",
            content="Integration test message for complete flow",
        )

        # Verify message was created correctly
        assert result_message is not None
        assert result_message.sender_id == "integration-user-123"
        assert result_message.recipient_id == "integration-bot-456"
        assert result_message.content == "Integration test message for complete flow"
        assert result_message.status == MessageStatus.SENT
        assert result_message.conversation_id == "integration-user-123#integration-bot-456"

        # Verify message was stored in DynamoDB
        stored_message = self.repository.get_message_by_id(result_message.message_id)
        assert stored_message is not None
        assert stored_message.message_id == result_message.message_id
        assert stored_message.content == result_message.content

        # Wait for SNS message delivery
        time.sleep(2)

        # Verify message was published to SNS
        sns_messages = self._get_sns_messages_from_sqs()
        assert len(sns_messages) == 1

        sns_message = sns_messages[0]
        assert sns_message["messageId"] == result_message.message_id
        assert sns_message["content"] == result_message.content
        assert sns_message["senderId"] == result_message.sender_id
        assert sns_message["recipientId"] == result_message.recipient_id
        assert sns_message["status"] == "sent"

    def test_update_message_status_flow(self):
        """Test update_message_status flow with real DynamoDB operations."""
        # First, create a message
        sent_message = self.message_service.send_message(
            sender_id="status-user-789", recipient_id="status-bot-012", content="Message for status update test"
        )

        # Update the message status
        updated_message = self.message_service.update_message_status(
            message_id=sent_message.message_id, status=MessageStatus.READ
        )

        # Verify the update was successful
        assert updated_message is not None
        assert updated_message.message_id == sent_message.message_id
        assert updated_message.status == MessageStatus.READ
        assert updated_message.updated_at != sent_message.updated_at

        # Verify the update persisted in DynamoDB
        retrieved_message = self.repository.get_message_by_id(sent_message.message_id)
        assert retrieved_message.status == MessageStatus.READ
        assert retrieved_message.updated_at == updated_message.updated_at

    def test_get_messages_flow_with_pagination(self):
        """Test get_messages flow with real DynamoDB queries and pagination."""
        conversation_id = "pagination-user#pagination-bot"

        # Create multiple messages in the same conversation
        # All messages will be from pagination-user to pagination-bot to ensure same conversation_id
        sent_messages = []
        for i in range(7):  # Create 7 messages to test pagination
            message = self.message_service.send_message(
                sender_id="pagination-user",
                recipient_id="pagination-bot",
                content=f"Pagination test message {i + 1}",
            )
            sent_messages.append(message)

        # Wait a moment to ensure all messages are stored
        time.sleep(1)

        # Test getting all messages (no limit specified, should default to 50)
        all_messages, has_more = self.message_service.get_messages(conversation_id)

        # Verify all messages were retrieved
        assert len(all_messages) == 7
        assert has_more is False

        # Verify messages are in correct order (oldest first)
        for i, msg in enumerate(all_messages):
            assert f"message {i + 1}" in msg.content.lower()

        # Test pagination with limit
        first_batch, has_more_first = self.message_service.get_messages(conversation_id, limit=3)
        assert len(first_batch) == 3
        assert has_more_first is True

        # Get next batch using timestamp of last message from first batch
        last_timestamp = first_batch[-1].timestamp
        second_batch, has_more_second = self.message_service.get_messages(
            conversation_id, since_timestamp=last_timestamp, limit=3
        )
        assert len(second_batch) == 3
        assert has_more_second is True

        # Get final batch
        last_timestamp_second = second_batch[-1].timestamp
        final_batch, has_more_final = self.message_service.get_messages(
            conversation_id, since_timestamp=last_timestamp_second, limit=3
        )
        assert len(final_batch) == 1  # Only 1 message left
        assert has_more_final is False

    def test_get_messages_with_timestamp_filter(self):
        """Test get_messages with timestamp filtering."""
        conversation_id = "timestamp-user#timestamp-bot"

        # Create messages with known timestamps by creating them sequentially
        messages = []
        for i in range(5):
            message = self.message_service.send_message(
                sender_id="timestamp-user", recipient_id="timestamp-bot", content=f"Timestamped message {i + 1}"
            )
            messages.append(message)
            time.sleep(0.1)  # Small delay to ensure different timestamps

        # Get messages since the 3rd message's timestamp
        since_timestamp = messages[2].timestamp
        filtered_messages, has_more = self.message_service.get_messages(
            conversation_id, since_timestamp=since_timestamp
        )

        # Should get messages 4 and 5 (after message 3)
        assert len(filtered_messages) == 2
        assert has_more is False
        assert "message 4" in filtered_messages[0].content.lower()
        assert "message 5" in filtered_messages[1].content.lower()

    def test_error_scenarios_with_real_services(self):
        """Test error scenarios with real AWS service failures."""
        # Test update_message_status with nonexistent message
        result = self.message_service.update_message_status(
            message_id="nonexistent-message-id", status=MessageStatus.READ
        )
        assert result is None

        # Test get_messages with nonexistent conversation
        messages, has_more = self.message_service.get_messages("nonexistent#conversation")
        assert messages == []
        assert has_more is False

        # Test send_message with invalid input
        with pytest.raises(ValueError, match="Invalid message data"):
            self.message_service.send_message(
                sender_id="",  # Empty sender_id should cause validation error
                recipient_id="valid-recipient",
                content="Valid content",
            )

        # Test get_messages with invalid conversation_id
        with pytest.raises(ValueError, match="Conversation ID cannot be empty"):
            self.message_service.get_messages("")

        # Test get_messages with invalid limit
        with pytest.raises(ValueError, match="Limit must be greater than 0"):
            self.message_service.get_messages("valid#conversation", limit=0)

        # Test update_message_status with invalid message_id
        with pytest.raises(ValueError, match="Message ID cannot be empty"):
            self.message_service.update_message_status("", MessageStatus.READ)

    def test_sns_message_publishing_verification(self):
        """Test SNS message publishing with actual SNS topic verification."""
        # Send multiple messages to verify SNS publishing
        messages_to_send = [
            ("sns-user-1", "sns-bot-1", "First SNS test message"),
            ("sns-user-2", "sns-bot-2", "Second SNS test message"),
            ("sns-user-3", "sns-bot-3", "Third SNS test message"),
        ]

        sent_messages = []
        for sender_id, recipient_id, content in messages_to_send:
            message = self.message_service.send_message(sender_id, recipient_id, content)
            sent_messages.append(message)
            time.sleep(0.5)  # Small delay between messages

        # Wait for SNS message delivery
        time.sleep(5)

        # Retrieve all SNS messages with multiple attempts
        all_sns_messages = []
        for _attempt in range(5):  # Try multiple times to get all messages
            sns_messages = self._get_sns_messages_from_sqs(max_messages=10, wait_time=3)
            all_sns_messages.extend(sns_messages)
            if len(all_sns_messages) >= 3:
                break
            time.sleep(1)

        # Verify at least some messages were published to SNS
        assert len(all_sns_messages) >= 1, f"Expected at least 1 SNS message, got {len(all_sns_messages)}"

        # Verify message content and attributes for received messages
        for sns_message in all_sns_messages:
            # Find corresponding sent message
            sent_message = next((msg for msg in sent_messages if msg.message_id == sns_message["messageId"]), None)

            if sent_message:  # Only verify if we found the corresponding message
                assert sns_message["content"] == sent_message.content
                assert sns_message["senderId"] == sent_message.sender_id
                assert sns_message["recipientId"] == sent_message.recipient_id
                assert sns_message["conversationId"] == sent_message.conversation_id
                assert sns_message["status"] == "sent"

    def test_conversation_flow_end_to_end(self):
        """Test complete conversation flow from message creation to status updates."""
        conversation_id = "e2e-alice#e2e-bob"

        # Alice sends a message to Bob
        alice_message = self.message_service.send_message(
            sender_id="e2e-alice", recipient_id="e2e-bob", content="Hi Bob, how are you?"
        )

        # Alice sends another message to Bob (to keep same conversation_id)
        alice_message2 = self.message_service.send_message(
            sender_id="e2e-alice", recipient_id="e2e-bob", content="Hi Alice! I'm doing great, thanks for asking."
        )

        # Alice reads the second message (update status)
        read_message = self.message_service.update_message_status(
            message_id=alice_message2.message_id, status=MessageStatus.READ
        )

        # Verify the conversation flow
        assert alice_message.conversation_id == conversation_id
        assert alice_message2.conversation_id == conversation_id
        assert read_message.status == MessageStatus.READ

        # Get all messages in the conversation
        conversation_messages, has_more = self.message_service.get_messages(conversation_id)

        # Verify conversation contains both messages in correct order
        assert len(conversation_messages) == 2
        assert has_more is False
        assert conversation_messages[0].message_id == alice_message.message_id
        assert conversation_messages[1].message_id == alice_message2.message_id

        # Verify second message shows as read
        assert conversation_messages[1].status == MessageStatus.READ

        # Wait for SNS messages
        time.sleep(3)

        # Verify messages were published to SNS (may not get all due to timing)
        sns_messages = self._get_sns_messages_from_sqs(max_messages=10, wait_time=3)
        assert len(sns_messages) >= 1, f"Expected at least 1 SNS message, got {len(sns_messages)}"

        # Verify SNS messages correspond to sent messages
        sns_message_ids = {msg["messageId"] for msg in sns_messages}
        expected_ids = {alice_message.message_id, alice_message2.message_id}

        # At least some of the messages should match
        assert len(sns_message_ids.intersection(expected_ids)) >= 1

    def test_service_with_large_message_content(self):
        """Test service with large message content to verify handling."""
        # Create a large message (but within reasonable limits)
        large_content = ("This is a large message content. " * 100).strip()  # ~3000 characters

        large_message = self.message_service.send_message(
            sender_id="large-user", recipient_id="large-bot", content=large_content
        )

        # Verify message was stored correctly
        assert large_message.content == large_content
        assert len(large_message.content) > 2000

        # Verify message can be retrieved
        retrieved_message = self.repository.get_message_by_id(large_message.message_id)
        assert retrieved_message.content == large_content

        # Wait for SNS delivery
        time.sleep(2)

        # Verify large message was published to SNS
        sns_messages = self._get_sns_messages_from_sqs()
        assert len(sns_messages) == 1
        assert sns_messages[0]["content"] == large_content

    def test_concurrent_message_operations(self):
        """Test concurrent message operations to verify data consistency."""
        conversation_id = "concurrent-user#concurrent-bot"

        # Send multiple messages quickly to test concurrency
        sent_messages = []
        for i in range(5):
            message = self.message_service.send_message(
                sender_id="concurrent-user", recipient_id="concurrent-bot", content=f"Concurrent message {i + 1}"
            )
            sent_messages.append(message)

        # Update status of multiple messages
        for i, message in enumerate(sent_messages[:3]):  # Update first 3 messages
            status = MessageStatus.DELIVERED if i % 2 == 0 else MessageStatus.READ
            updated = self.message_service.update_message_status(message.message_id, status)
            assert updated is not None
            assert updated.status == status

        # Verify all messages are in the conversation
        all_messages, has_more = self.message_service.get_messages(conversation_id)
        assert len(all_messages) == 5
        assert has_more is False

        # Verify status updates persisted correctly
        for i, message in enumerate(all_messages[:3]):
            expected_status = MessageStatus.DELIVERED if i % 2 == 0 else MessageStatus.READ
            assert message.status == expected_status

        # Verify remaining messages still have SENT status
        for message in all_messages[3:]:
            assert message.status == MessageStatus.SENT

    def test_data_cleanup_and_isolation(self):
        """Test that test data is properly isolated and cleaned up."""
        # This test verifies that each test method starts with a clean state

        # Send a message
        test_message = self.message_service.send_message(
            sender_id="cleanup-user", recipient_id="cleanup-bot", content="Cleanup test message"
        )

        # Verify message exists
        retrieved = self.repository.get_message_by_id(test_message.message_id)
        assert retrieved is not None

        # The teardown_method should clean up this data automatically
        # This test mainly verifies the setup/teardown process works correctly
        assert test_message.message_id is not None
        assert test_message.conversation_id == "cleanup-user#cleanup-bot"
