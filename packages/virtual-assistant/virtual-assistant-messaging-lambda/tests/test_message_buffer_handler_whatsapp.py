# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for message buffer handler with WhatsApp messages.

Feature: stepfunctions-message-buffering
Tests WhatsApp message parsing and buffering integration.
"""

import json
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from virtual_assistant_messaging_lambda.handlers.message_buffer_handler import lambda_handler


def create_whatsapp_sns_event(phone_number: str = "56941162278", message_content: str = "Hola") -> dict:
    """Create a realistic WhatsApp SNS event from AWS EUM Social.

    This matches the actual structure from production logs.
    """
    whatsapp_webhook = {
        "id": "1113145347627771",
        "changes": [
            {
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "18555729598",
                        "phone_number_id": "784808018052479",
                    },
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": phone_number}],
                    "messages": [
                        {
                            "from": phone_number,
                            "id": f"wamid.test_{phone_number}",
                            "timestamp": "1767977197",
                            "text": {"body": message_content},
                            "type": "text",
                        }
                    ],
                },
                "field": "messages",
            }
        ],
    }

    sns_message = {
        "context": {
            "MetaWabaIds": [
                {
                    "wabaId": "1113145347627771",
                    "arn": "arn:aws:social-messaging:us-east-1:319165777784:waba/8c81ef9ba1574abc9afafaf4df2f4a8b",
                }
            ],
            "MetaPhoneNumberIds": [
                {
                    "metaPhoneNumberId": "784808018052479",
                    "arn": (
                        "arn:aws:social-messaging:us-east-1:319165777784:"
                        "phone-number-id/059016fc97384778a41ccb4134abf555"
                    ),
                }
            ],
        },
        "whatsAppWebhookEntry": json.dumps(whatsapp_webhook),
        "aws_account_id": "319165777784",
        "message_timestamp": "2026-01-09T16:46:38.759216290Z",
    }

    return {
        "Records": [
            {
                "EventSource": "aws:sns",
                "EventVersion": "1.0",
                "EventSubscriptionArn": "arn:aws:sns:us-east-1:123456789012:whatsapp-messages:subscription-id",
                "Sns": {
                    "Type": "Notification",
                    "MessageId": "test-sns-message-id",
                    "TopicArn": "arn:aws:sns:us-east-1:123456789012:whatsapp-messages",
                    "Subject": None,  # WhatsApp messages have no subject
                    "Message": json.dumps(sns_message),
                    "Timestamp": "2026-01-09T16:46:38.788Z",
                    "SignatureVersion": "1",
                    "Signature": "test-signature",
                    "SigningCertURL": "https://test.amazonaws.com/cert.pem",
                    "UnsubscribeURL": "https://test.amazonaws.com/unsubscribe",
                    "MessageAttributes": {},
                },
            }
        ]
    }


class TestWhatsAppMessageBuffering:
    """Test WhatsApp message buffering functionality."""

    def test_whatsapp_message_parsing_and_buffering(self):
        """Test that WhatsApp messages are correctly parsed and buffered.

        This test verifies:
        1. WhatsApp webhook structure is correctly parsed
        2. MessageEvent is created with correct fields
        3. Message is written to DynamoDB buffer
        4. Float values (timestamps) are converted to Decimal
        """
        # Create WhatsApp SNS event
        event = create_whatsapp_sns_event(phone_number="56941162278", message_content="Hola")

        # Mock DynamoDB and Step Functions
        mock_table = MagicMock()
        mock_sfn_client = MagicMock()

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
            response = lambda_handler(event, MagicMock())

            # Verify response
            assert response["statusCode"] == 200

            # Verify message was written to buffer
            assert len(update_calls) >= 1, "update_item should be called at least once"

            # Check first call (message write)
            first_call = update_calls[0]
            assert first_call["Key"]["user_id"] == "56941162278"

            # Verify the message data
            msg_list = first_call["ExpressionAttributeValues"][":msg"]
            assert len(msg_list) == 1
            msg_data = msg_list[0]

            # Verify MessageEvent fields
            assert msg_data["processing"] is False
            assert msg_data["sender_id"] == "56941162278"
            assert msg_data["recipient_id"] == "18555729598"
            assert msg_data["content"] == "Hola"
            assert msg_data["platform"] == "aws-eum"
            assert "message_id" in msg_data
            assert "conversation_id" in msg_data

            # Verify conversation_id format (should be sanitized phone number)
            conversation_id = msg_data["conversation_id"]
            assert conversation_id.startswith("whatsapp-conversation-")
            assert "56941162278" in conversation_id
            assert len(conversation_id) >= 33  # Minimum length requirement

            # Verify TTL is set and is an integer
            assert ":ttl" in first_call["ExpressionAttributeValues"]
            ttl = first_call["ExpressionAttributeValues"][":ttl"]
            assert isinstance(ttl, int)

            # Verify last_update_time is a Decimal (not float)
            assert ":time" in first_call["ExpressionAttributeValues"]
            time_value = first_call["ExpressionAttributeValues"][":time"]
            assert isinstance(time_value, Decimal), f"Expected Decimal, got {type(time_value)}"

    def test_whatsapp_message_with_special_characters(self):
        """Test WhatsApp message with special characters in content."""
        event = create_whatsapp_sns_event(phone_number="56941162278", message_content="¡Hola! ¿Cómo estás? 😊")

        mock_table = MagicMock()
        mock_sfn_client = MagicMock()

        update_calls = []

        def track_update_item(**kwargs):
            update_calls.append(kwargs)
            if len(update_calls) == 1:
                return {}
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

            response = lambda_handler(event, MagicMock())

            assert response["statusCode"] == 200
            assert len(update_calls) >= 1

            # Verify special characters are preserved
            msg_data = update_calls[0]["ExpressionAttributeValues"][":msg"][0]
            assert msg_data["content"] == "¡Hola! ¿Cómo estás? 😊"

    def test_whatsapp_message_starts_workflow(self):
        """Test that WhatsApp message starts Step Functions workflow when no workflow is running."""
        event = create_whatsapp_sns_event()

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

            response = lambda_handler(event, MagicMock())

            assert response["statusCode"] == 200

            # Verify Step Functions workflow was started
            assert mock_sfn_client.start_execution.called
            call_args = mock_sfn_client.start_execution.call_args
            workflow_input = json.loads(call_args[1]["input"])
            assert workflow_input["user_id"] == "56941162278"

    def test_multiple_whatsapp_messages_same_user(self):
        """Test multiple WhatsApp messages from same user are buffered correctly."""
        # Create two messages from same user
        event1 = create_whatsapp_sns_event(phone_number="56941162278", message_content="Hola")
        event2 = create_whatsapp_sns_event(phone_number="56941162278", message_content="¿Cómo estás?")

        mock_table = MagicMock()
        mock_sfn_client = MagicMock()

        update_calls = []

        def track_update_item(**kwargs):
            update_calls.append(kwargs)
            # First message: message write succeeds, waiting state succeeds
            if len(update_calls) <= 2:
                return {}
            # Second message: message write succeeds, waiting state fails (workflow running)
            if len(update_calls) == 3:
                return {}
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

            # Process first message
            response1 = lambda_handler(event1, MagicMock())
            assert response1["statusCode"] == 200

            # Process second message
            response2 = lambda_handler(event2, MagicMock())
            assert response2["statusCode"] == 200

            # Verify both messages were written
            assert len(update_calls) >= 4  # 2 messages × 2 updates each

            # Verify workflow was started only once
            assert mock_sfn_client.start_execution.call_count == 1

    def test_whatsapp_message_with_different_phone_formats(self):
        """Test WhatsApp messages with different phone number formats."""
        phone_numbers = [
            "56941162278",  # No country code prefix
            "+56941162278",  # With + prefix
            "1234567890",  # US format
        ]

        for phone in phone_numbers:
            event = create_whatsapp_sns_event(phone_number=phone)

            mock_table = MagicMock()
            mock_sfn_client = MagicMock()

            # Use list to track calls (avoid closure issues)
            call_tracker = {"calls": []}

            def make_track_update_item(tracker):
                def track_update_item(**kwargs):
                    tracker["calls"].append(kwargs)
                    if len(tracker["calls"]) == 1:
                        return {}
                    raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem")

                return track_update_item

            mock_table.update_item.side_effect = make_track_update_item(call_tracker)

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

                response = lambda_handler(event, MagicMock())

                assert response["statusCode"] == 200
                assert len(call_tracker["calls"]) >= 1

                # Verify phone number is used as user_id
                msg_data = call_tracker["calls"][0]["ExpressionAttributeValues"][":msg"][0]
                assert msg_data["sender_id"] == phone


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
