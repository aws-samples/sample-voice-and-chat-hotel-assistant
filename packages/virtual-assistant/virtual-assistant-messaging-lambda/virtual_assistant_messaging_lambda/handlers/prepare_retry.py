# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler for preparing retry after AgentCore session busy error.

This handler:
1. Unmarks all processing messages (sets processing = false)
2. Sets waiting state to true
3. Increments retry count
4. Returns updated retry count for wait time calculation
"""

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize logger
logger = Logger()

# Initialize DynamoDB client
dynamodb = boto3.client("dynamodb")

# Get environment variables
MESSAGE_BUFFER_TABLE = os.environ["MESSAGE_BUFFER_TABLE"]


@logger.inject_lambda_context
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Prepare for retry after AgentCore session busy error.

    This handler unmarks processing messages and resets waiting state so that:
    1. New messages arriving during retry wait will be buffered
    2. The retry will re-evaluate the buffering window from ClearWaitingState
    3. All messages (original + new) will be processed together after retry

    Args:
        event: Contains user_id and retry_count
        context: Lambda context

    Returns:
        {
            "retry_count": int  # Incremented retry count
        }
    """
    user_id = event["user_id"]
    retry_count = event.get("retry_count", 0)

    logger.info(
        "Preparing retry for user",
        extra={
            "user_id": user_id,
            "retry_count": retry_count,
        },
    )

    try:
        # Get current buffer
        response = dynamodb.get_item(
            TableName=MESSAGE_BUFFER_TABLE,
            Key={"user_id": {"S": user_id}},
        )

        if "Item" not in response:
            logger.warning("No buffer found for user during retry preparation", extra={"user_id": user_id})
            return {"retry_count": retry_count + 1}

        # Get messages
        messages = response["Item"].get("messages", {}).get("L", [])

        # Unmark all processing messages
        updated_messages = []
        for msg in messages:
            msg_dict = msg["M"]
            # Set processing to false
            msg_dict["processing"] = {"BOOL": False}
            updated_messages.append({"M": msg_dict})

        # Update buffer: unmark messages and set waiting state to true
        dynamodb.update_item(
            TableName=MESSAGE_BUFFER_TABLE,
            Key={"user_id": {"S": user_id}},
            UpdateExpression="SET messages = :msgs, waiting_state = :true",
            ExpressionAttributeValues={
                ":msgs": {"L": updated_messages},
                ":true": {"BOOL": True},
            },
        )

        logger.info(
            "Prepared retry: unmarked messages and set waiting state",
            extra={
                "user_id": user_id,
                "message_count": len(updated_messages),
                "new_retry_count": retry_count + 1,
            },
        )

        return {"retry_count": retry_count + 1}

    except Exception as e:
        logger.exception(
            "Error preparing retry",
            extra={
                "user_id": user_id,
                "retry_count": retry_count,
                "error": str(e),
            },
        )
        raise
