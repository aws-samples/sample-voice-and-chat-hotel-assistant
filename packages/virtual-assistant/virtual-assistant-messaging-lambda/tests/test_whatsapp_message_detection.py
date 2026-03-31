# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for WhatsApp message detection and parsing functionality."""

import json
import os
from unittest.mock import patch

from virtual_assistant_messaging_lambda.handlers.message_processor import (
    is_eum_whatsapp_message,
    parse_whatsapp_message,
    process_message_record,
)
from virtual_assistant_messaging_lambda.models.sqs_events import ProcessingResult, SNSMessage


class TestWhatsAppMessageDetection:
    """Test cases for WhatsApp message detection and parsing."""

    def setup_method(self):
        """Set up test environment variables."""
        os.environ["AGENTCORE_RUNTIME_ARN"] = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-agent"
        os.environ["MESSAGING_API_ENDPOINT"] = "https://api.example.com"
        os.environ["MESSAGING_CLIENT_SECRET_ARN"] = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
        os.environ["AWS_REGION"] = "us-east-1"

    def teardown_method(self):
        """Clean up environment variables."""
        for var in ["AGENTCORE_RUNTIME_ARN", "MESSAGING_API_ENDPOINT", "MESSAGING_CLIENT_SECRET_ARN", "AWS_REGION"]:
            if var in os.environ:
                del os.environ[var]

    def test_is_eum_whatsapp_message_with_dict_message(self):
        """Test WhatsApp message detection with dict message format."""
        # Test with WhatsApp webhook data
        sns_message = SNSMessage(
            **{
                "Type": "Notification",
                "MessageId": "test-msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "Message": json.dumps({"whatsAppWebhookEntry": {"changes": []}}),
                "Timestamp": "2024-01-01T12:00:00Z",
            }
        )

        assert is_eum_whatsapp_message(sns_message) is True

    def test_is_eum_whatsapp_message_with_simulated_message(self):
        """Test WhatsApp message detection with simulated message."""
        # Test with regular simulated message
        sns_message = SNSMessage(
            **{
                "Type": "Notification",
                "MessageId": "test-msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "Message": json.dumps({"messageId": "test", "content": "hello"}),
                "Timestamp": "2024-01-01T12:00:00Z",
            }
        )

        assert is_eum_whatsapp_message(sns_message) is False

    def test_is_eum_whatsapp_message_with_invalid_json(self):
        """Test WhatsApp message detection with invalid JSON string."""
        sns_message = SNSMessage(
            **{
                "Type": "Notification",
                "MessageId": "test-msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "Message": "invalid-json-string",
                "Timestamp": "2024-01-01T12:00:00Z",
            }
        )

        assert is_eum_whatsapp_message(sns_message) is False

    def test_parse_whatsapp_message_success(self):
        """Test successful WhatsApp message parsing."""
        # Create realistic WhatsApp webhook data
        whatsapp_webhook = {
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "+1234567890",
                            "phone_number_id": "phone-123",
                            "waba_id": "waba-456",
                        },
                        "messages": [
                            {
                                "id": "wamid.123456789",
                                "from": "+1987654321",
                                "timestamp": "1704110400",
                                "type": "text",
                                "text": {"body": "Hello, I need help with my reservation"},
                            }
                        ],
                    },
                }
            ]
        }

        sns_message = SNSMessage(
            **{
                "Type": "Notification",
                "MessageId": "test-msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "Message": json.dumps({"whatsAppWebhookEntry": whatsapp_webhook}),
                "Timestamp": "2024-01-01T12:00:00Z",
            }
        )

        result = parse_whatsapp_message(sns_message)

        assert result is not None
        assert result.message_id == "wamid.123456789"
        assert result.sender_id == "+1987654321"
        assert result.recipient_id == "+1234567890"
        assert result.content == "Hello, I need help with my reservation"
        assert result.conversation_id == "whatsapp-conversation-1987654321-session-id"
        assert result.platform == "aws-eum"
        assert result.platform_metadata["phone_number_id"] == "phone-123"
        assert result.platform_metadata["waba_id"] == "waba-456"
        assert result.platform_metadata["display_phone_number"] == "+1234567890"
        assert result.model_id is None  # Let agent handle model configuration
        assert result.temperature is None  # Let agent handle temperature configuration

    def test_parse_whatsapp_message_no_text_messages(self):
        """Test WhatsApp message parsing with no text messages."""
        whatsapp_webhook = {
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "metadata": {"display_phone_number": "+1234567890"},
                        "messages": [
                            {"id": "wamid.image", "from": "+1987654321", "type": "image", "image": {"id": "image-123"}}
                        ],
                    },
                }
            ]
        }

        sns_message = SNSMessage(
            **{
                "Type": "Notification",
                "MessageId": "test-msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "Message": json.dumps({"whatsAppWebhookEntry": whatsapp_webhook}),
                "Timestamp": "2024-01-01T12:00:00Z",
            }
        )

        result = parse_whatsapp_message(sns_message)
        assert result is None

    def test_parse_whatsapp_message_no_webhook_entry(self):
        """Test WhatsApp message parsing with no webhook entry."""
        sns_message = SNSMessage(
            **{
                "Type": "Notification",
                "MessageId": "test-msg-123",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "Message": json.dumps({"someOtherField": "value"}),
                "Timestamp": "2024-01-01T12:00:00Z",
            }
        )

        result = parse_whatsapp_message(sns_message)
        assert result is None

    def test_process_message_record_with_whatsapp_message(self):
        """Test SQS record processing with WhatsApp message."""
        # Create WhatsApp webhook data
        whatsapp_webhook = {
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "metadata": {"display_phone_number": "+1234567890", "phone_number_id": "phone-123"},
                        "messages": [
                            {
                                "id": "wamid.whatsapp.test",
                                "from": "+1987654321",
                                "type": "text",
                                "text": {"body": "WhatsApp test message"},
                            }
                        ],
                    },
                }
            ]
        }

        # Create SQS record with WhatsApp SNS message
        sqs_record = {
            "messageId": "sqs-msg-whatsapp",
            "receiptHandle": "receipt-handle-whatsapp",
            "body": json.dumps(
                {
                    "Type": "Notification",
                    "MessageId": "sns-msg-whatsapp",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:whatsapp-topic",
                    "Subject": "WhatsApp Message",
                    "Message": json.dumps({"whatsAppWebhookEntry": whatsapp_webhook}),
                    "Timestamp": "2024-01-01T12:00:00Z",
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://example.com/cert",
                    "UnsubscribeURL": "https://example.com/unsubscribe",
                }
            ),
            "attributes": {},
            "messageAttributes": {},
            "md5OfBody": "test-md5",
            "eventSource": "aws:sqs",
            "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            "awsRegion": "us-east-1",
        }

        # Mock the async processing function to return the result directly
        mock_result = ProcessingResult(message_id="wamid.whatsapp.test", success=True)

        with (
            patch("virtual_assistant_messaging_lambda.handlers.message_processor._process_message_async") as mock_async,
            patch(
                "virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list"
            ) as mock_get_allow_list,
        ):
            mock_async.return_value = mock_result
            # Mock allow list to include the test phone number
            mock_get_allow_list.return_value = "+1987654321,+1555123456"

            # Should not raise exception
            process_message_record(sqs_record)

            # Verify async function was called
            mock_async.assert_called_once()

            # Verify the MessageEvent passed to async processing has WhatsApp data
            call_args = mock_async.call_args[0][0]  # Get the MessageEvent argument
            assert call_args.message_id == "wamid.whatsapp.test"
            assert call_args.sender_id == "+1987654321"
            assert call_args.content == "WhatsApp test message"
            assert call_args.conversation_id == "whatsapp-conversation-1987654321-session-id"
            assert call_args.platform == "aws-eum"
