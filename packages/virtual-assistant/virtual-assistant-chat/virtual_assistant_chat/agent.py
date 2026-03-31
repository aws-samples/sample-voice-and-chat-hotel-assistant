#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Virtual Assistant Chat Agent

This module implements a conversational AI agent using Amazon Bedrock AgentCore
and Strands SDK. The agent processes user messages asynchronously and maintains
conversation state through AgentCore Memory.

Key features:
- Async message processing with immediate response
- Session and actor consistency validation
- MCP tool integration for hotel services
- Optimized logging and error handling
- Sensitive information sanitization
- MCP connections kept alive for AgentCore Runtime session lifetime (up to 8 hours)

AgentCore Runtime Session Lifecycle:
- Sessions run in isolated microVMs with dedicated resources
- Each session can last up to 8 hours (default)
- Multiple invocations reuse the same runtimeSessionId
- Idle timeout of 15 minutes (default) terminates inactive sessions
- State and connections persist within a session across invocations
"""

import asyncio
import logging
import os

import boto3
from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from opentelemetry import baggage
from opentelemetry import context as otel_context
from virtual_assistant_common.mcp import MCPConfigManager
from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest, AgentCoreInvocationResponse
from virtual_assistant_common.platforms.router import platform_router
from virtual_assistant_common.utils.response_parser import parse_response

from .agent_factory import AgentFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Step Functions client for task token callbacks (lazy initialized)
sfn_client = None


def get_sfn_client():
    """Get or create Step Functions client (lazy initialization).

    Returns:
        boto3.client: Step Functions client
    """
    global sfn_client
    if sfn_client is None:
        sfn_client = boto3.client("stepfunctions")
    return sfn_client


# Global variables for AgentCore Runtime session
# These persist across multiple invocations within the same session (up to 8 hours)
current_session_id = None
current_actor_id = None
agent = None

# Initialize AgentFactory at module level (single source of truth for MCP + prompt)
config_manager = MCPConfigManager()
factory = AgentFactory(config_manager)
asyncio.run(factory.initialize())


def validate_configuration():
    """Validate required environment variables.

    Returns:
        tuple: (memory_id, aws_region)

    Raises:
        ValueError: If required environment variables are missing
    """
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")
    if not memory_id:
        raise ValueError("AGENTCORE_MEMORY_ID environment variable is required")

    aws_region = os.getenv("AWS_REGION")
    if not aws_region:
        raise ValueError("AWS_REGION environment variable is required")

    return memory_id, aws_region


def create_session_manager(session_id: str, actor_id: str):
    """Create SessionManager for specific session/actor combination.

    Args:
        session_id: Unique session identifier
        actor_id: Unique actor identifier

    Returns:
        AgentCoreMemorySessionManager: Configured session manager
    """
    memory_id, aws_region = validate_configuration()

    config = AgentCoreMemoryConfig(memory_id=memory_id, session_id=session_id, actor_id=actor_id)

    return AgentCoreMemorySessionManager(agentcore_memory_config=config, region_name=aws_region)


# Create the app instance
app = BedrockAgentCoreApp()


@app.async_task
async def process_user_message(
    user_message: str,
    actor_id: str,
    message_ids: list[str],
    conversation_id: str,
    model_id: str,
    temperature: float,
    session_id: str,
    task_token: str | None = None,
):
    """Process user message with agent and MCP connections persisting for session lifetime.

    AgentCore Runtime sessions can last up to 8 hours with multiple invocations.
    The agent and MCP connections are created once per session and reused across
    all messages in that session.

    Args:
        user_message: The user's input message
        actor_id: Unique identifier for the user/actor
        message_ids: List of message IDs for status tracking
        conversation_id: Conversation identifier (matches session_id)
        model_id: Bedrock model identifier
        temperature: Model temperature setting
        session_id: Session identifier for memory management
        task_token: Optional Step Functions task token for async callback
    """
    global agent, current_session_id, current_actor_id

    try:
        # Update all message statuses to read immediately
        logger.info(f"Updating {len(message_ids)} message(s) status to 'read': {message_ids}")
        for message_id in message_ids:
            await platform_router.update_message_status(message_id, "read")

        # Set up OpenTelemetry context
        ctx = baggage.set_baggage("session.id", session_id)
        otel_context.attach(ctx)

        # Create agent once per session, validate consistency
        if agent is None:
            logger.info(f"Creating agent for session {session_id[:8]}... (will persist for session lifetime)")

            # Create session manager
            session_manager = create_session_manager(session_id, actor_id)

            # Create agent via AgentFactory (single source of truth for MCP + prompt)
            agent = factory.create_agent(
                model_id=model_id,
                region=os.getenv("AWS_REGION", "us-east-1"),
                temperature=temperature,
                session_manager=session_manager,
            )

            current_session_id = session_id
            current_actor_id = actor_id
            logger.info("Agent created via AgentFactory (session will persist up to 8 hours)")
        else:
            # Validate session/actor hasn't changed (critical error if it has)
            if current_session_id != session_id:
                raise RuntimeError(f"Session ID changed within execution: {current_session_id} -> {session_id}")
            if current_actor_id != actor_id:
                raise RuntimeError(f"Actor ID changed within execution: {current_actor_id} -> {actor_id}")

            logger.debug(f"Reusing agent for session {session_id[:8]}... (MCP connections still active)")

        # Process message with agent (MCP connections are alive)
        logger.debug(f"Processing message group with {len(message_ids)} message(s): {message_ids}")

        async for event in agent.stream_async(user_message):
            # Only process message events, ignore tool events completely
            if "message" in event:
                text = []
                message_content = event.get("message", {}).get("content", [])

                for content in message_content:
                    if isinstance(content, dict) and "text" in content:
                        text.append(content["text"])

                raw_message = "".join(text)
                if raw_message.strip():
                    # Parse response to extract <message> content and discard <thinking>
                    parsed_message = parse_response(raw_message)

                    # Only send if there's actual content (handles thinking-only responses)
                    if parsed_message.strip():
                        response_result = await platform_router.send_response(conversation_id, parsed_message)
                        if not response_result.success:
                            logger.error(
                                f"Failed to send response for message group {message_ids}: {response_result.error}"
                            )

            # Ignore all other event types (toolUse, toolResult, etc.) - let them pass through

        logger.debug(f"Completed processing message group: {message_ids}")

        # Send success callback to Step Functions (only if task_token present)
        if task_token:
            try:
                import json

                # Retry callback send with exponential backoff
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        get_sfn_client().send_task_success(
                            taskToken=task_token,
                            output=json.dumps({"status": "success", "message_ids": message_ids, "user_id": actor_id}),
                        )
                        logger.info(f"Sent success callback for message group {message_ids}")
                        break
                    except Exception as retry_error:
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                            logger.warning(
                                f"Callback send failed (attempt {attempt + 1}/{max_retries}), "
                                f"retrying in {wait_time}s: {retry_error}"
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            raise
            except Exception as callback_error:
                logger.error(f"Failed to send success callback after {max_retries} attempts: {callback_error}")
                # Don't raise - processing succeeded, callback is best-effort

    except Exception as e:
        # Log error with sanitized information
        sanitized_error = str(e).replace(actor_id, "[ACTOR_ID]").replace(session_id, "[SESSION_ID]")
        logger.error(f"Failed to process message group {message_ids}: {sanitized_error}")

        # Send failure callback to Step Functions (only if task_token present)
        if task_token:
            try:
                # Retry callback send with exponential backoff
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        get_sfn_client().send_task_failure(
                            taskToken=task_token, error="AsyncTaskProcessingError", cause=sanitized_error
                        )
                        logger.info(f"Sent failure callback for message group {message_ids}")
                        break
                    except Exception as retry_error:
                        if attempt < max_retries - 1:
                            wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                            logger.warning(
                                f"Callback send failed (attempt {attempt + 1}/{max_retries}), "
                                f"retrying in {wait_time}s: {retry_error}"
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            raise
            except Exception as callback_error:
                logger.error(f"Failed to send failure callback after {max_retries} attempts: {callback_error}")

        # Send generic error message to user
        try:
            error_msg = "I'm sorry, I'm having trouble processing your request right now. Please try again later."
            await platform_router.send_response(conversation_id, error_msg)
        except Exception as msg_error:
            logger.error(f"Failed to send error message for message group {message_ids}: {str(msg_error)}")

        # Mark all messages as failed
        logger.info(f"Marking {len(message_ids)} message(s) as failed: {message_ids}")
        for message_id in message_ids:
            try:
                await platform_router.update_message_status(message_id, "failed")
            except Exception as status_error:
                logger.error(f"Failed to update status for message {message_id}: {str(status_error)}")

        # Re-raise the original exception
        raise


@app.entrypoint
async def invoke(payload, context: RequestContext):
    """Main entrypoint for AgentCore invocations.

    Starts async message processing and returns immediately to avoid timeouts.
    Extracts session_id from context and actor_id from payload for proper
    session management with AgentCore Memory.

    Args:
        payload: Request payload containing message and actor information
        context: AgentCore request context with session information

    Returns:
        dict: Status response indicating processing started or error
    """
    try:
        # Parse and validate payload using Pydantic model
        request = AgentCoreInvocationRequest.model_validate(payload)
        logger.info(f"Parsed agent invocation request for {len(request.message_ids)} message(s): {request.message_ids}")
    except Exception as e:
        # Log error with sanitized message (don't expose payload contents)
        logger.error(f"Invalid payload format - validation failed: {type(e).__name__}")
        return AgentCoreInvocationResponse(
            success=False,
            message_id="unknown",
            error="Invalid request format",
        ).model_dump()

    # Extract session_id and actor_id for agent creation
    # session_id comes from context.session_id (runtimeSessionId from AgentCore)
    # actor_id comes from payload (until SDK exposes runtimeUserId)
    session_id = context.session_id
    actor_id = request.actor_id

    # Extract optional task_token from payload
    task_token = request.task_token

    if task_token:
        logger.debug("Task token present - Step Functions callback mode enabled")
    else:
        logger.debug("No task token - direct invocation mode (backward compatible)")

    # Log request details
    logger.info(f"Processing request for message group: {request.message_ids}")
    logger.debug(f"Session: {session_id}, Actor: {actor_id}, Conversation: {request.conversation_id}")

    # Validate that payload conversation_id matches context session_id
    if request.conversation_id != session_id:
        logger.warning(
            "Payload conversation_id doesn't match context session_id - using context session_id for consistency"
        )

    # Check if there are existing async tasks running
    task_info = app.get_async_task_info()
    if task_info and task_info.get("active_count", 0) > 0:
        active_count = task_info["active_count"]
        logger.warning(f"Session {session_id} is busy processing {active_count} task(s)")
        # Return response using AgentCoreInvocationResponse model
        # The client will parse this and detect the session_busy condition
        return AgentCoreInvocationResponse(
            success=False,
            message_id=request.message_ids[0] if request.message_ids else "unknown",
            error=f"Session is busy processing {active_count} task(s)",
            response_body={
                "status": "session_busy",
                "active_tasks": active_count,
            },
        ).model_dump()

    # Extract model configuration with defaults
    model_id = request.model_id or os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")
    temperature = request.temperature or float(os.getenv("MODEL_TEMPERATURE", "0.2"))

    logger.debug(f"Using model: {model_id}, Temperature: {temperature}")

    try:
        # Start async task for message processing
        logger.debug(f"Starting async processing for message group: {request.message_ids}")

        # Create task with error handling
        task = asyncio.create_task(
            process_user_message(
                user_message=request.prompt,
                actor_id=actor_id,
                message_ids=request.message_ids,
                conversation_id=session_id,
                model_id=model_id,
                temperature=temperature,
                session_id=session_id,
                task_token=task_token,
            )
        )

        # Add done callback for task error handling
        def task_done_callback(task):
            if task.exception():
                logger.error(f"Task failed for message group {request.message_ids}: {task.exception()}")

        task.add_done_callback(task_done_callback)

        # Return success response using AgentCoreInvocationResponse model
        return AgentCoreInvocationResponse(
            success=True,
            message_id=request.message_ids[0] if request.message_ids else "unknown",
            response_body={
                "status": "processing_started",
                "message_count": len(request.message_ids),
            },
        ).model_dump()

    except Exception as e:
        # Sanitize error message for logging
        sanitized_error = str(e).replace(actor_id, "[ACTOR_ID]").replace(session_id, "[SESSION_ID]")
        logger.error(f"Failed to start processing for message group {request.message_ids}: {sanitized_error}")
        # Return error response using AgentCoreInvocationResponse model
        return AgentCoreInvocationResponse(
            success=False,
            message_id=request.message_ids[0] if request.message_ids else "unknown",
            error="Failed to start message processing",
        ).model_dump()


if __name__ == "__main__":
    app.run()
