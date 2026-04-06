# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Lambda handler for preparing messages for processing.

This handler atomically marks all non-processing messages as processing (sets processing = true).

CRITICAL: Does NOT clear waiting_state - that is handled by ClearWaitingState state
when no messages remain after DeleteProcessedMessages loops back.
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
    Prepare messages for processing by marking them as processing.

    This handler marks all non-processing messages as processing = true.

    CRITICAL: Always reads fresh from DynamoDB to avoid race conditions where messages
    arrive between GetMessages and PrepareProcessing states.

    NOTE: Does NOT clear waiting_state - that is handled by ClearWaitingState state
    when no messages remain after DeleteProcessedMessages loops back.

    Args:
        event: Contains user_id, session_id (optional - will read from buffer if not provided)
        context: Lambda context

    Returns:
        {
            "processing_messages": list[dict],  # Messages marked as processing
            "message_count": int
        }
    """
    user_id = event["user_id"]
    session_id = event.get("session_id")  # May be None in retry flow

    logger.info(
        "Preparing messages for processing",
        extra={
            "user_id": user_id,
            "session_id": session_id,
        },
    )

    try:
        # CRITICAL: Read fresh from DynamoDB to catch any messages that arrived
        # between GetMessages and PrepareProcessing states
        response = dynamodb.get_item(
            TableName=MESSAGE_BUFFER_TABLE,
            Key={"user_id": {"S": user_id}},
        )

        if "Item" not in response:
            logger.warning(
                "No buffer found for user during prepare processing",
                extra={"user_id": user_id},
            )
            return {"processing_messages": [], "message_count": 0}

        # Get session_id from buffer if not provided (retry flow)
        if not session_id:
            session_id = response["Item"].get("session_id", {}).get("S")
            logger.info(
                "Retrieved session_id from buffer",
                extra={
                    "user_id": user_id,
                    "session_id": session_id,
                },
            )

        # Get messages from fresh read
        messages = response["Item"].get("messages", {}).get("L", [])

        logger.info(
            "Read fresh messages from buffer",
            extra={
                "user_id": user_id,
                "total_messages": len(messages),
            },
        )

        # Filter to non-processing messages
        non_processing = []
        all_messages = []

        for msg in messages:
            msg_dict = msg["M"]
            is_processing = msg_dict.get("processing", {}).get("BOOL", False)

            if not is_processing:
                # Mark as processing
                msg_dict["processing"] = {"BOOL": True}
                non_processing.append(msg_dict)

            all_messages.append({"M": msg_dict})

        if not non_processing:
            logger.warning(
                "No non-processing messages found",
                extra={
                    "user_id": user_id,
                    "total_messages": len(messages),
                },
            )
            # Still need to keep waiting_state = true so workflow continues
            # ClearWaitingState will clear it when no messages remain
            return {"processing_messages": [], "message_count": 0}

        # Update messages with processing flags
        # NOTE: Do NOT clear waiting_state here - it should only be cleared by
        # ClearWaitingState state when no messages remain after DeleteProcessedMessages
        dynamodb.update_item(
            TableName=MESSAGE_BUFFER_TABLE,
            Key={"user_id": {"S": user_id}},
            UpdateExpression="SET messages = :msgs",
            ExpressionAttributeValues={
                ":msgs": {"L": all_messages},
            },
        )

        # Convert DynamoDB format to simple dict for AgentCore invocation
        processing_messages = []
        for msg in non_processing:
            processing_messages.append(
                {
                    "message_id": msg["message_id"]["S"],
                    "content": msg["content"]["S"],
                    "timestamp": msg["timestamp"]["S"],
                    "sender_id": msg["sender_id"]["S"],
                    "conversation_id": msg["conversation_id"]["S"],
                    "platform": msg["platform"]["S"],
                }
            )

        logger.info(
            "Prepared messages for processing",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "processing_count": len(processing_messages),
            },
        )

        return {
            "processing_messages": processing_messages,
            "message_count": len(processing_messages),
        }

    except Exception as e:
        logger.exception(
            "Error preparing messages for processing",
            extra={
                "user_id": user_id,
                "session_id": session_id,
                "error": str(e),
            },
        )
        raise
