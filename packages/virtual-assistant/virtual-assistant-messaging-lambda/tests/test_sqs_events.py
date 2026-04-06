# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for SQS event models."""

import json

from virtual_assistant_messaging_lambda.models.sqs_events import (
    ProcessingResult,
    SNSMessage,
    SQSEvent,
    SQSRecord,
)


class TestSQSEventModels:
    """Test cases for SQS event models."""

    def test_sqs_record_parsing(self):
        """Test SQS record parsing from Lambda event."""
        record_data = {
            "messageId": "test-msg-123",
            "receiptHandle": "test-receipt-handle",
            "body": "test message body",
            "attributes": {"ApproximateReceiveCount": "1"},
            "messageAttributes": {},
            "md5OfBody": "test-md5",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            "awsRegion": "us-east-1",
        }

        record = SQSRecord(**record_data)

        assert record.message_id == "test-msg-123"
        assert record.receipt_handle == "test-receipt-handle"
        assert record.body == "test message body"
        assert record.event_source == "aws:sqs"
        assert record.aws_region == "us-east-1"

    def test_sqs_event_parsing(self):
        """Test SQS event parsing with multiple records."""
        event_data = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "receiptHandle": "handle-1",
                    "body": "body-1",
                    "attributes": {},
                    "messageAttributes": {},
                    "md5OfBody": "md5-1",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:queue-1",
                    "awsRegion": "us-east-1",
                },
                {
                    "messageId": "msg-2",
                    "receiptHandle": "handle-2",
                    "body": "body-2",
                    "attributes": {},
                    "messageAttributes": {},
                    "md5OfBody": "md5-2",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:queue-2",
                    "awsRegion": "us-east-1",
                },
            ]
        }

        event = SQSEvent(**event_data)

        assert len(event.records) == 2
        assert event.records[0].message_id == "msg-1"
        assert event.records[1].message_id == "msg-2"

    def test_sns_message_parsing(self):
        """Test SNS message parsing from SQS body."""
        sns_data = {
            "Type": "Notification",
            "MessageId": "sns-msg-123",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
            "Subject": "Test Subject",
            "Message": json.dumps({"message_id": "hotel-msg-456", "content": "Hello world", "sender_id": "user123"}),
            "Timestamp": "2024-01-01T12:00:00.000Z",
            "SignatureVersion": "1",
            "Signature": "test-signature",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
            "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/unsubscribe",
        }

        message = SNSMessage(**sns_data)

        assert message.type == "Notification"
        assert message.message_id == "sns-msg-123"
        assert message.topic_arn == "arn:aws:sns:us-east-1:123456789012:test-topic"
        assert message.subject == "Test Subject"

        # Message should be parsed as JSON
        assert isinstance(message.message, dict)
        assert message.message["message_id"] == "hotel-msg-456"
        assert message.message["content"] == "Hello world"

    def test_sns_message_string_message(self):
        """Test SNS message with string (non-JSON) message."""
        sns_data = {
            "Type": "Notification",
            "MessageId": "sns-msg-456",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
            "Message": "Plain text message",
            "Timestamp": "2024-01-01T12:00:00.000Z",
            "SignatureVersion": "1",
            "Signature": "test-signature",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
            "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/unsubscribe",
        }

        message = SNSMessage(**sns_data)

        assert message.message == "Plain text message"
        assert message.subject == ""  # Default empty subject

    def test_sns_message_invalid_json(self):
        """Test SNS message with invalid JSON in message field."""
        sns_data = {
            "Type": "Notification",
            "MessageId": "sns-msg-789",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
            "Message": "invalid json {",
            "Timestamp": "2024-01-01T12:00:00.000Z",
            "SignatureVersion": "1",
            "Signature": "test-signature",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
            "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/unsubscribe",
        }

        message = SNSMessage(**sns_data)

        # Should fall back to string value for invalid JSON
        assert message.message == "invalid json {"

    def test_processing_result_success(self):
        """Test ProcessingResult for successful processing."""
        result = ProcessingResult(
            message_id="test-msg-123", success=True, agent_response={"status": "completed", "response": "Hello!"}
        )

        assert result.message_id == "test-msg-123"
        assert result.success is True
        assert result.error is None
        assert result.agent_response["status"] == "completed"

    def test_processing_result_failure(self):
        """Test ProcessingResult for failed processing."""
        result = ProcessingResult(message_id="test-msg-456", success=False, error="AgentCore unavailable")

        assert result.message_id == "test-msg-456"
        assert result.success is False
        assert result.error == "AgentCore unavailable"
        assert result.agent_response is None

    def test_complete_sqs_sns_flow(self):
        """Test complete flow from SQS event to SNS message parsing."""
        # Create a complete SQS event with SNS message
        hotel_message = {
            "message_id": "hotel-msg-789",
            "conversation_id": "user789#hotel-assistant",
            "sender_id": "user789",
            "recipient_id": "hotel-assistant",
            "content": "I need help with my booking",
            "timestamp": "2024-01-01T12:00:00Z",
            "platform": "web",
        }

        sns_message_data = {
            "Type": "Notification",
            "MessageId": "sns-msg-789",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:hotel-messages",
            "Subject": "New Hotel Message",
            "Message": json.dumps(hotel_message),
            "Timestamp": "2024-01-01T12:00:00.000Z",
            "SignatureVersion": "1",
            "Signature": "test-signature",
            "SigningCertURL": "https://sns.us-east-1.amazonaws.com/cert.pem",
            "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/unsubscribe",
        }

        sqs_event_data = {
            "Records": [
                {
                    "messageId": "sqs-msg-789",
                    "receiptHandle": "receipt-handle-789",
                    "body": json.dumps(sns_message_data),
                    "attributes": {"ApproximateReceiveCount": "1"},
                    "messageAttributes": {},
                    "md5OfBody": "test-md5",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:hotel-message-queue",
                    "awsRegion": "us-east-1",
                }
            ]
        }

        # Parse the complete flow
        sqs_event = SQSEvent(**sqs_event_data)
        sqs_record = sqs_event.records[0]
        sns_message = SNSMessage(**json.loads(sqs_record.body))

        # Verify the complete parsing chain
        assert len(sqs_event.records) == 1
        assert sqs_record.message_id == "sqs-msg-789"
        assert sns_message.message_id == "sns-msg-789"
        assert sns_message.message["message_id"] == "hotel-msg-789"
        assert sns_message.message["content"] == "I need help with my booking"
