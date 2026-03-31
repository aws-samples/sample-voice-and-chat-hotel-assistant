# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handler for invoking AgentCore with combined messages."""

import asyncio
import os
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from virtual_assistant_common.exceptions import AgentCoreSessionBusyError
from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest
from virtual_assistant_common.platforms.router import platform_router

from ..services.agentcore_client import AgentCoreClient

logger = Logger()


def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Invoke AgentCore with combined message batch.

    This handler receives marked messages from the Step Functions workflow,
    combines their content, marks all messages as delivered, invokes AgentCore,
    and returns success or raises AgentCoreSessionBusyError for retry.

    Args:
        event: Contains marked_messages (with processing_messages list), session_id, user_id, and optional task_token
        context: Lambda context

    Returns:
        Success response

    Raises:
        AgentCoreSessionBusyError: If session is busy (triggers Step Functions retry)

    Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2
    """
    user_id = None
    try:
        # Log the incoming event for debugging
        logger.debug(f"Received event: {event}")

        # Extract parameters from event
        user_id = event.get("user_id")
        session_id = event.get("session_id")
        marked_messages = event.get("marked_messages", {})
        processing_messages = marked_messages.get("processing_messages", [])
        task_token = event.get("task_token")  # Optional task token from Step Functions

        # Validate required parameters
        if not user_id:
            raise ValueError("Missing required parameter: user_id")
        if not session_id:
            raise ValueError("Missing required parameter: session_id")
        if not processing_messages:
            raise ValueError("No processing messages found in marked_messages")

        logger.info(f"Invoking AgentCore for user {user_id} with {len(processing_messages)} messages")
        if task_token:
            logger.debug("Task token present - Step Functions callback mode")
        else:
            logger.debug("No task token - direct invocation mode")

        # Messages are already in plain JSON format from PrepareProcessing Lambda
        # No need to extract from DynamoDB format
        logger.debug(f"Processing {len(processing_messages)} messages in plain JSON format")

        # Combine message content (join with newlines)
        combined_content = "\n".join(msg["content"] for msg in processing_messages if msg.get("content"))

        # Extract message IDs
        message_ids = [msg["message_id"] for msg in processing_messages if msg.get("message_id")]

        logger.debug(f"Message IDs: {message_ids}")
        logger.debug(f"Session ID: {session_id}")
        logger.debug(f"Combined content length: {len(combined_content)} characters")

        # Run async operations
        result = asyncio.run(_invoke_agentcore_async(combined_content, message_ids, session_id, user_id, task_token))

        logger.info(f"AgentCore invocation completed successfully for user {user_id}")
        return result

    except AgentCoreSessionBusyError:
        # Re-raise to trigger Step Functions retry
        logger.warning(f"AgentCore session busy for user {user_id or 'unknown'}, will retry")
        raise
    except Exception as e:
        logger.error(f"Failed to invoke AgentCore for user {user_id or 'unknown'}: {e}", exc_info=True)
        raise


async def _invoke_agentcore_async(
    combined_content: str, message_ids: list[str], session_id: str, user_id: str, task_token: str | None = None
) -> dict[str, Any]:
    """Invoke AgentCore asynchronously with message batch.

    Args:
        combined_content: Combined message content
        message_ids: List of message IDs
        session_id: AgentCore session ID
        user_id: User identifier
        task_token: Optional Step Functions task token

    Returns:
        Success response

    Raises:
        AgentCoreSessionBusyError: If session is busy
        Exception: If invocation fails

    Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2
    """
    # Mark all messages as delivered using platform router
    logger.debug(f"Marking {len(message_ids)} messages as delivered")
    for message_id in message_ids:
        await platform_router.update_message_status(message_id, "delivered")

    # Create AgentCore invocation request (reuse existing model)
    request_kwargs = {
        "prompt": combined_content,
        "actorId": user_id,
        "messageIds": message_ids,
        "conversationId": session_id,
    }

    # Add task_token if present (Step Functions invocation)
    if task_token:
        request_kwargs["taskToken"] = task_token

    # Add model configuration from environment if present
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if model_id:
        request_kwargs["modelId"] = model_id

    temperature_str = os.environ.get("MODEL_TEMPERATURE")
    if temperature_str:
        request_kwargs["temperature"] = float(temperature_str)

    request = AgentCoreInvocationRequest(**request_kwargs)
    logger.debug(f"Created AgentCore invocation request with {len(message_ids)} message IDs")

    # Invoke AgentCore (reuse existing client)
    agentcore_client = AgentCoreClient()
    response = agentcore_client.invoke_agent(request)

    logger.debug(f"AgentCore invocation response: {response}")

    if not response.success:
        error_msg = str(response.error) if response.error else "Unknown error"

        # Check if session is busy (concurrent invocation)
        # The client detects this from the agent's response body
        if "busy" in error_msg.lower() or "session is busy" in error_msg.lower():
            logger.warning(f"AgentCore session busy for session {session_id}")
            raise AgentCoreSessionBusyError(
                f"Session {session_id} is busy processing another request", session_id=session_id
            )

        # Other errors
        logger.error(f"AgentCore invocation failed: {error_msg}")
        raise Exception(f"AgentCore invocation failed: {error_msg}")

    logger.info(f"AgentCore invocation successful for session {session_id}")
    return {"status": "success", "message_ids": message_ids, "user_id": user_id}
