# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handler for marking messages as processing in DynamoDB buffer."""

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="MessageBuffering")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Mark non-processing messages as processing in DynamoDB buffer.

    This handler:
    1. Gets all messages from the buffer
    2. Filters to non-processing messages
    3. Updates each message to set processing = true in DynamoDB
    4. Returns the messages that were marked

    Args:
        event: Contains user_id and messages from Step Functions
        context: Lambda context

    Returns:
        {
            "processing_messages": list[dict],  # Messages marked as processing
            "message_count": int
        }

    Requirements: 4.1
    """
    try:
        # Get environment variables
        buffer_table_name = os.environ.get("MESSAGE_BUFFER_TABLE")

        if not buffer_table_name:
            raise ValueError("Missing required environment variable: MESSAGE_BUFFER_TABLE")

        buffer_table = dynamodb.Table(buffer_table_name)

        # Extract parameters from event
        user_id = event.get("user_id")
        messages = event.get("messages", [])

        if not user_id:
            raise ValueError("Missing required parameter: user_id")

        logger.info(f"Marking messages as processing for user {user_id}, total messages: {len(messages)}")

        # Filter to non-processing messages
        non_processing = [msg for msg in messages if not msg.get("processing", False)]

        logger.info(f"Found {len(non_processing)} non-processing messages to mark")

        if not non_processing:
            # No new messages to mark, but return all processing messages
            processing_messages = [msg for msg in messages if msg.get("processing", False)]
            return {"processing_messages": processing_messages, "message_count": 0}

        # Mark all non-processing messages as processing = true
        # We need to update the entire messages list in DynamoDB
        updated_messages = []
        for msg in messages:
            if not msg.get("processing", False):
                # Mark as processing
                msg_copy = msg.copy()
                msg_copy["processing"] = True
                updated_messages.append(msg_copy)
            else:
                # Keep existing processing messages as-is
                updated_messages.append(msg)

        # Update DynamoDB with the modified messages list
        buffer_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET messages = :msgs",
            ExpressionAttributeValues={":msgs": updated_messages},
        )

        logger.info(f"Successfully marked {len(non_processing)} messages as processing for user {user_id}")
        metrics.add_metric(name="MessagesMarkedAsProcessing", unit="Count", value=len(non_processing))

        # Return ALL processing messages, but count reflects newly marked ones
        processing_messages = [msg for msg in updated_messages if msg.get("processing", True)]

        return {"processing_messages": processing_messages, "message_count": len(non_processing)}

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        metrics.add_metric(name="MarkMessagesProcessingErrors", unit="Count", value=1)
        raise
