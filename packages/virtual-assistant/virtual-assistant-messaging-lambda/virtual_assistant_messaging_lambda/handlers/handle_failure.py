# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handler for handling workflow failures and marking messages as failed."""

import asyncio
import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from virtual_assistant_common.platforms.router import platform_router

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
    """Handle workflow failure by marking messages as failed.

    This handler:
    1. Gets all processing messages from DynamoDB buffer
    2. Marks all processing messages as "failed" using platform router
    3. Logs error details with all message IDs
    4. Leaves messages in buffer for manual cleanup (TTL will clean up)

    Args:
        event: Contains user_id and error details
        context: Lambda context

    Returns:
        {
            "status": str,  # "success"
            "failed_count": int  # Number of messages marked as failed
        }

    Requirements: 7.5, 8.4
    """
    try:
        # Get environment variables
        buffer_table_name = os.environ.get("MESSAGE_BUFFER_TABLE")

        if not buffer_table_name:
            raise ValueError("Missing required environment variable: MESSAGE_BUFFER_TABLE")

        buffer_table = dynamodb.Table(buffer_table_name)

        # Extract parameters from event
        user_id = event.get("user_id")
        error_details = event.get("error", "Unknown error")

        if not user_id:
            raise ValueError("Missing required parameter: user_id")

        logger.error(
            f"Workflow failed for user {user_id}",
            extra={"user_id": user_id, "error": error_details},
        )

        # Get current buffer
        response = buffer_table.get_item(Key={"user_id": user_id})

        if "Item" not in response:
            # Buffer already cleaned up
            logger.warning(f"Buffer not found for user {user_id}, nothing to mark as failed")
            return {"status": "success", "failed_count": 0}

        # Get messages from buffer
        messages = response["Item"].get("messages", [])
        logger.info(f"Found {len(messages)} total messages in buffer for user {user_id}")

        # Filter to processing messages only
        processing_messages = [msg for msg in messages if msg.get("processing", False)]
        logger.info(f"Found {len(processing_messages)} processing messages to mark as failed")

        if not processing_messages:
            logger.warning(f"No processing messages found for user {user_id}")
            return {"status": "success", "failed_count": 0}

        # Extract message IDs for logging
        message_ids = [msg.get("message_id") for msg in processing_messages if msg.get("message_id")]
        logger.error(
            f"Marking {len(message_ids)} messages as failed for user {user_id}",
            extra={
                "user_id": user_id,
                "message_ids": message_ids,
                "error": error_details,
            },
        )

        # Run async operations to mark messages as failed
        asyncio.run(_mark_messages_failed_async(message_ids))

        logger.info(f"Successfully marked {len(message_ids)} messages as failed for user {user_id}")

        metrics.add_metric(name="MessagesMarkedFailed", unit="Count", value=len(message_ids))

        return {"status": "success", "failed_count": len(message_ids)}

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        metrics.add_metric(name="HandleFailureErrors", unit="Count", value=1)
        raise


async def _mark_messages_failed_async(message_ids: list[str]) -> dict[str, Any]:
    """Mark all messages as failed using platform router.

    Args:
        message_ids: List of message IDs to mark as failed

    Returns:
        Success response

    Requirements: 8.4
    """
    # Mark all messages as failed using platform router
    logger.debug(f"Marking {len(message_ids)} messages as failed")
    for message_id in message_ids:
        try:
            await platform_router.update_message_status(message_id, "failed")
            logger.debug(f"Marked message {message_id} as failed")
        except Exception as e:
            # Log error but continue with other messages
            logger.error(f"Failed to mark message {message_id} as failed: {e}")

    return {"status": "success"}
