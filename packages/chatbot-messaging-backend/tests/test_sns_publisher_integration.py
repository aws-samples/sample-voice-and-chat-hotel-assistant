# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for SNS publisher utilities using real AWS SNS."""

import contextlib
import json
import time

import boto3
import pytest
from botocore.exceptions import ClientError

from chatbot_messaging_backend.utils.sns_publisher import SNSPublisher


@pytest.mark.integration
class TestSNSPublisherIntegration:
    """Integration test cases for SNSPublisher class using real AWS SNS."""

    @pytest.fixture
    def sns_topic_arn(self):
        """Create a real SNS topic for testing."""
        sns_client = boto3.client("sns", region_name="us-east-1")

        # Create topic with unique name
        topic_name = f"test-chatbot-messages-{int(time.time())}"
        response = sns_client.create_topic(Name=topic_name)
        topic_arn = response["TopicArn"]

        yield topic_arn

        # Cleanup: Delete the topic
        with contextlib.suppress(ClientError):
            sns_client.delete_topic(TopicArn=topic_arn)

    @pytest.fixture
    def sqs_queue_url(self):
        """Create a real SQS queue for testing SNS subscriptions."""
        sqs_client = boto3.client("sqs", region_name="us-east-1")

        # Create queue with unique name
        queue_name = f"test-sns-queue-{int(time.time())}"
        response = sqs_client.create_queue(QueueName=queue_name)
        queue_url = response["QueueUrl"]

        yield queue_url

        # Cleanup: Delete the queue
        with contextlib.suppress(ClientError):
            sqs_client.delete_queue(QueueUrl=queue_url)

    @pytest.fixture
    def publisher(self, sns_topic_arn):
        """Create SNSPublisher instance with real topic."""
        return SNSPublisher(topic_arn=sns_topic_arn, region_name="us-east-1")

    @pytest.fixture
    def sample_message_data(self):
        """Sample message data for testing."""
        return {
            "messageId": "msg-integration-123",
            "conversationId": "conv-integration-456",
            "senderId": "user-integration-789",
            "recipientId": "bot-integration-001",
            "content": "Integration test message",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "sent",
        }

    def test_publish_message_integration(self, publisher, sample_message_data, sns_topic_arn, sqs_queue_url):
        """Test publishing message to real SNS topic."""
        # Subscribe SQS queue to SNS topic to capture messages
        sns_client = boto3.client("sns", region_name="us-east-1")
        sqs_client = boto3.client("sqs", region_name="us-east-1")

        # Get queue attributes for subscription
        queue_attributes = sqs_client.get_queue_attributes(QueueUrl=sqs_queue_url, AttributeNames=["QueueArn"])
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
                    "Condition": {"ArnEquals": {"aws:SourceArn": sns_topic_arn}},
                }
            ],
        }

        sqs_client.set_queue_attributes(QueueUrl=sqs_queue_url, Attributes={"Policy": json.dumps(queue_policy)})

        # Subscribe queue to topic
        subscription_response = sns_client.subscribe(TopicArn=sns_topic_arn, Protocol="sqs", Endpoint=queue_arn)
        subscription_arn = subscription_response["SubscriptionArn"]

        try:
            # Publish message
            result = publisher.publish_message(sample_message_data)
            assert result is True

            # Wait a moment for message delivery
            time.sleep(2)

            # Verify message was published by checking SQS queue
            messages = sqs_client.receive_message(QueueUrl=sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)

            assert "Messages" in messages, "No messages received in SQS queue"
            assert len(messages["Messages"]) == 1

            # Parse SNS message from SQS
            sqs_message = json.loads(messages["Messages"][0]["Body"])
            sns_message = json.loads(sqs_message["Message"])

            # Verify message content
            assert sns_message == sample_message_data

            # Verify message attributes
            message_attributes = sqs_message.get("MessageAttributes", {})
            assert message_attributes["messageType"]["Value"] == "chatbot_message"
            assert message_attributes["senderId"]["Value"] == sample_message_data["senderId"]
            assert message_attributes["conversationId"]["Value"] == sample_message_data["conversationId"]

        finally:
            # Cleanup subscription
            with contextlib.suppress(ClientError):
                sns_client.unsubscribe(SubscriptionArn=subscription_arn)

    def test_publish_message_from_model_integration(self, publisher, sns_topic_arn, sqs_queue_url):
        """Test publishing from message model to real SNS topic."""

        # Create mock message model
        class MockMessage:
            def __init__(self):
                self.message_id = "msg-model-123"
                self.conversation_id = "conv-model-456"
                self.sender_id = "user-model-789"
                self.recipient_id = "bot-model-001"
                self.content = "Message from model integration test"
                self.timestamp = "2024-01-01T13:00:00Z"
                self.status = "sent"

        mock_message = MockMessage()

        # Subscribe SQS queue to SNS topic
        sns_client = boto3.client("sns", region_name="us-east-1")
        sqs_client = boto3.client("sqs", region_name="us-east-1")

        queue_attributes = sqs_client.get_queue_attributes(QueueUrl=sqs_queue_url, AttributeNames=["QueueArn"])
        queue_arn = queue_attributes["Attributes"]["QueueArn"]

        # Set queue policy
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": sns_topic_arn}},
                }
            ],
        }

        sqs_client.set_queue_attributes(QueueUrl=sqs_queue_url, Attributes={"Policy": json.dumps(queue_policy)})

        subscription_response = sns_client.subscribe(TopicArn=sns_topic_arn, Protocol="sqs", Endpoint=queue_arn)
        subscription_arn = subscription_response["SubscriptionArn"]

        try:
            # Publish message from model
            result = publisher.publish_message_from_model(mock_message)
            assert result is True

            # Wait for message delivery
            time.sleep(2)

            # Verify message was published
            messages = sqs_client.receive_message(QueueUrl=sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)

            assert "Messages" in messages

            sqs_message = json.loads(messages["Messages"][0]["Body"])
            sns_message = json.loads(sqs_message["Message"])

            # Verify message content matches model attributes
            assert sns_message["messageId"] == mock_message.message_id
            assert sns_message["content"] == mock_message.content
            assert sns_message["senderId"] == mock_message.sender_id

        finally:
            # Cleanup subscription
            with contextlib.suppress(ClientError):
                sns_client.unsubscribe(SubscriptionArn=subscription_arn)

    def test_health_check_integration(self, publisher):
        """Test health check with real SNS topic."""
        result = publisher.health_check()
        assert result is True

    def test_health_check_nonexistent_topic(self):
        """Test health check with nonexistent topic."""
        fake_arn = "arn:aws:sns:us-east-1:123456789012:nonexistent-topic"
        publisher = SNSPublisher(topic_arn=fake_arn, region_name="us-east-1")

        result = publisher.health_check()
        assert result is False

    def test_multiple_message_publishing(self, publisher, sns_topic_arn, sqs_queue_url):
        """Test publishing multiple messages in sequence."""
        # Subscribe SQS queue to SNS topic
        sns_client = boto3.client("sns", region_name="us-east-1")
        sqs_client = boto3.client("sqs", region_name="us-east-1")

        queue_attributes = sqs_client.get_queue_attributes(QueueUrl=sqs_queue_url, AttributeNames=["QueueArn"])
        queue_arn = queue_attributes["Attributes"]["QueueArn"]

        # Set queue policy
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": sns_topic_arn}},
                }
            ],
        }

        sqs_client.set_queue_attributes(QueueUrl=sqs_queue_url, Attributes={"Policy": json.dumps(queue_policy)})

        subscription_response = sns_client.subscribe(TopicArn=sns_topic_arn, Protocol="sqs", Endpoint=queue_arn)
        subscription_arn = subscription_response["SubscriptionArn"]

        try:
            # Publish multiple messages
            messages_to_send = []
            for i in range(3):
                message_data = {
                    "messageId": f"msg-multi-{i}",
                    "conversationId": "conv-multi-test",
                    "senderId": f"user-{i}",
                    "recipientId": "bot-multi",
                    "content": f"Message number {i}",
                    "timestamp": f"2024-01-01T1{i}:00:00Z",
                    "status": "sent",
                }
                messages_to_send.append(message_data)

                result = publisher.publish_message(message_data)
                assert result is True

            # Wait for message delivery
            time.sleep(3)

            # Verify all messages were published
            all_messages = []
            for _ in range(5):  # Try multiple times to get all messages
                messages = sqs_client.receive_message(QueueUrl=sqs_queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=2)

                if "Messages" in messages:
                    for msg in messages["Messages"]:
                        sqs_message = json.loads(msg["Body"])
                        sns_message = json.loads(sqs_message["Message"])
                        all_messages.append(sns_message)

                        # Delete message from queue
                        sqs_client.delete_message(QueueUrl=sqs_queue_url, ReceiptHandle=msg["ReceiptHandle"])

                if len(all_messages) >= 3:
                    break

            assert len(all_messages) == 3, f"Expected 3 messages, got {len(all_messages)}"

            # Verify all messages were received correctly
            received_message_ids = {msg["messageId"] for msg in all_messages}
            expected_message_ids = {msg["messageId"] for msg in messages_to_send}
            assert received_message_ids == expected_message_ids

        finally:
            # Cleanup subscription
            with contextlib.suppress(ClientError):
                sns_client.unsubscribe(SubscriptionArn=subscription_arn)

    def test_message_attributes_integration(self, publisher, sample_message_data, sns_topic_arn, sqs_queue_url):
        """Test that message attributes are correctly set in integration."""
        # Subscribe SQS queue to SNS topic
        sns_client = boto3.client("sns", region_name="us-east-1")
        sqs_client = boto3.client("sqs", region_name="us-east-1")

        queue_attributes = sqs_client.get_queue_attributes(QueueUrl=sqs_queue_url, AttributeNames=["QueueArn"])
        queue_arn = queue_attributes["Attributes"]["QueueArn"]

        # Set queue policy
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": sns_topic_arn}},
                }
            ],
        }

        sqs_client.set_queue_attributes(QueueUrl=sqs_queue_url, Attributes={"Policy": json.dumps(queue_policy)})

        subscription_response = sns_client.subscribe(TopicArn=sns_topic_arn, Protocol="sqs", Endpoint=queue_arn)
        subscription_arn = subscription_response["SubscriptionArn"]

        try:
            # Publish message
            result = publisher.publish_message(sample_message_data)
            assert result is True

            # Wait for message delivery
            time.sleep(2)

            # Verify message attributes
            messages = sqs_client.receive_message(QueueUrl=sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)

            sqs_message = json.loads(messages["Messages"][0]["Body"])

            # Check SNS message attributes
            assert "MessageAttributes" in sqs_message
            attributes = sqs_message["MessageAttributes"]

            assert attributes["messageType"]["Value"] == "chatbot_message"
            assert attributes["senderId"]["Value"] == sample_message_data["senderId"]
            assert attributes["conversationId"]["Value"] == sample_message_data["conversationId"]

            # Verify all attributes have correct type
            for _attr_name, attr_value in attributes.items():
                assert attr_value["Type"] == "String"

        finally:
            # Cleanup subscription
            with contextlib.suppress(ClientError):
                sns_client.unsubscribe(SubscriptionArn=subscription_arn)

    def test_error_handling_integration(self):
        """Test error handling with invalid topic ARN."""
        # Use invalid topic ARN format
        invalid_arn = "invalid-arn-format"
        publisher = SNSPublisher(topic_arn=invalid_arn, region_name="us-east-1")

        message_data = {
            "messageId": "msg-error-test",
            "conversationId": "conv-error-test",
            "senderId": "user-error",
            "recipientId": "bot-error",
            "content": "Error test message",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "sent",
        }

        # Should raise ClientError due to invalid ARN
        with pytest.raises(ClientError):
            publisher.publish_message(message_data)
