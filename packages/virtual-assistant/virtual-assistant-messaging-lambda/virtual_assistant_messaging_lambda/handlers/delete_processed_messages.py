# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handler for deleting processed messages from DynamoDB buffer."""

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
    """Delete processed messages from DynamoDB buffer.

    This handler:
    1. Gets current buffer from DynamoDB
    2. Filters out messages where processing = true
    3. If remaining messages exist, updates buffer
    4. If no remaining messages, deletes buffer entry

    Args:
        event: Contains user_id
        context: Lambda context

    Returns:
        {
            "status": str,  # "success" or "already_deleted"
            "deleted_count": int  # Number of messages deleted
        }

    Requirements: 4.5
    """
    try:
        # Get environment variables
        buffer_table_name = os.environ.get("MESSAGE_BUFFER_TABLE")

        if not buffer_table_name:
            raise ValueError("Missing required environment variable: MESSAGE_BUFFER_TABLE")

        buffer_table = dynamodb.Table(buffer_table_name)

        # Extract parameters from event
        user_id = event.get("user_id")

        if not user_id:
            raise ValueError("Missing required parameter: user_id")

        logger.info(f"Deleting processed messages for user {user_id}")

        # Get current buffer
        response = buffer_table.get_item(Key={"user_id": user_id})

        if "Item" not in response:
            # Buffer already cleaned up
            logger.info(f"Buffer already deleted for user {user_id}")
            return {"status": "already_deleted", "deleted_count": 0}

        # Get messages from buffer
        messages = response["Item"].get("messages", [])
        logger.info(f"Found {len(messages)} total messages in buffer for user {user_id}")

        # Filter out processed messages (processing = true)
        remaining_messages = [msg for msg in messages if not msg.get("processing", False)]
        deleted_count = len(messages) - len(remaining_messages)

        logger.info(f"Deleting {deleted_count} processed messages, {len(remaining_messages)} remaining")

        if remaining_messages:
            # Update buffer with only non-processed messages
            buffer_table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET messages = :msgs",
                ExpressionAttributeValues={":msgs": remaining_messages},
            )
            logger.info(f"Updated buffer for user {user_id} with {len(remaining_messages)} remaining messages")
        else:
            # No remaining messages, delete the buffer entry
            buffer_table.delete_item(Key={"user_id": user_id})
            logger.info(f"Deleted buffer entry for user {user_id} (no remaining messages)")

        metrics.add_metric(name="ProcessedMessagesDeleted", unit="Count", value=deleted_count)

        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        metrics.add_metric(name="DeleteProcessedMessagesErrors", unit="Count", value=1)
        raise
