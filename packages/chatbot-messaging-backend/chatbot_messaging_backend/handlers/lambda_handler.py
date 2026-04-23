# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Main Lambda handler for the chatbot messaging backend API.

This module implements the REST API endpoints using AWS Lambda Powertools
APIGatewayRestResolver for handling message operations.
"""

import json
import os
import uuid
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig, Response
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..models.message import MessageStatus
from ..services.message_service import MessageService
from ..utils.repository import MessageRepository
from ..utils.sns_publisher import SNSPublisher

# Initialize logger
logger = Logger()

# Initialize API Gateway REST resolver with CORS configuration
cors_config = CORSConfig(
    allow_origin="*",  # Allow all origins for development
    allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
    max_age=300,
    allow_credentials=False,  # Set to False when using wildcard origin
)

app = APIGatewayRestResolver(cors=cors_config)


class SendMessageRequest(BaseModel):
    """Request model for sending messages."""

    recipient_id: str = Field(alias="recipientId")
    content: str
    conversation_id: str | None = Field(default=None, alias="conversationId")
    model_id: str | None = Field(default=None, alias="modelId")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    model_config = {"populate_by_name": True}

    @field_validator("conversation_id")
    @classmethod
    def validate_conversation_id(cls, v: str | None) -> str | None:
        """Validate conversation ID is a valid UUID or legacy senderId#recipientId format."""
        if v is None:
            return v

        # Accept UUID format
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            pass

        # Accept legacy senderId#recipientId format
        if "#" in v:
            parts = v.split("#")
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                return v

        raise ValueError("conversationId must be a valid UUID or in format 'senderId#recipientId'")


class UpdateMessageStatusRequest(BaseModel):
    """Request model for updating message status."""

    status: MessageStatus


def get_environment_variables():
    """Get and validate required environment variables."""
    dynamodb_table_name = os.environ.get("DYNAMODB_TABLE_NAME")
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

    if not dynamodb_table_name:
        logger.error("DYNAMODB_TABLE_NAME environment variable is required")
        raise ValueError("DYNAMODB_TABLE_NAME environment variable is required")

    if not sns_topic_arn:
        logger.error("SNS_TOPIC_ARN environment variable is required")
        raise ValueError("SNS_TOPIC_ARN environment variable is required")

    return dynamodb_table_name, sns_topic_arn


@app.exception_handler(BadRequestError)
def handle_bad_request(ex: BadRequestError) -> Response:
    """Handle bad request errors with structured response."""
    logger.warning(f"Bad request: {ex}")
    return Response(
        status_code=400,
        content_type="application/json",
        body=json.dumps({"error": {"code": "BAD_REQUEST", "message": str(ex)}}),
    )


@app.exception_handler(UnauthorizedError)
def handle_unauthorized(ex: UnauthorizedError) -> Response:
    """Handle unauthorized errors with structured response."""
    logger.warning(f"Unauthorized request: {ex}")
    return Response(
        status_code=401,
        content_type="application/json",
        body=json.dumps({"error": {"code": "UNAUTHORIZED", "message": "Invalid or missing authentication"}}),
    )


@app.exception_handler(NotFoundError)
def handle_not_found(ex: NotFoundError) -> Response:
    """Handle not found errors with structured response."""
    logger.warning(f"Resource not found: {ex}")
    return Response(
        status_code=404,
        content_type="application/json",
        body=json.dumps({"error": {"code": "NOT_FOUND", "message": str(ex)}}),
    )


@app.exception_handler(InternalServerError)
def handle_internal_error(ex: InternalServerError) -> Response:
    """Handle internal server errors with structured response."""
    logger.error(f"Internal server error: {ex}")
    return Response(
        status_code=500,
        content_type="application/json",
        body=json.dumps({"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred"}}),
    )


@app.exception_handler(Exception)
def handle_generic_exception(ex: Exception) -> Response:
    """Handle any unhandled exceptions with structured response."""
    logger.error(f"Unhandled exception: {ex}", exc_info=True)
    return Response(
        status_code=500,
        content_type="application/json",
        body=json.dumps({"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}}),
    )


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint to verify service is running."""
    logger.info("Health check requested")
    return {"status": "healthy", "service": "chatbot-messaging-backend", "version": "1.0.0"}


def extract_sender_id_from_jwt() -> str:
    """Extract senderId from JWT token claims using priority list.

    Priority order for sender ID extraction:
    1. 'username' - for user authentication with username (access tokens)
    2. 'cognito:username' - for user authentication with username (ID tokens)
    3. 'client_id' - for machine-to-machine authentication (access tokens)
    4. 'sub' - fallback UUID for user authentication or client_id (both token types)

    Returns:
        str: The sender ID from the JWT token

    Raises:
        UnauthorizedError: If token is missing or invalid
    """
    # Get the JWT claims from the API Gateway event context
    # In API Gateway with Cognito authorizer, claims are available in the request context
    request_context = app.current_event.request_context

    if not request_context or "authorizer" not in request_context:
        logger.warning("No authorizer context found in request")
        raise UnauthorizedError("Missing authentication")

    authorizer = request_context["authorizer"]

    # Extract claims
    if "claims" in authorizer:
        claims = authorizer["claims"]

        # Priority list for sender ID extraction
        sender_id_candidates = [
            ("username", claims.get("username")),
            ("cognito:username", claims.get("cognito:username")),
            ("client_id", claims.get("client_id")),
            ("sub", claims.get("sub")),
        ]

        for claim_name, claim_value in sender_id_candidates:
            if claim_value:
                logger.info("Using sender ID from claim", extra={"claim": claim_name, "sender_id": claim_value})
                return claim_value

        logger.warning("No valid sender ID found in JWT claims", extra={"available_claims": list(claims.keys())})
        raise UnauthorizedError("Invalid token: missing user ID")

    # Fallback for different authorizer formats
    sender_id = authorizer.get("sub") or authorizer.get("principalId")
    if not sender_id:
        logger.warning("No sender ID found in authorizer context")
        raise UnauthorizedError("Invalid token: missing user ID")

    return sender_id


@app.post("/messages")
def send_message() -> dict[str, Any]:
    """Send a new message.

    Extracts senderId from JWT token, validates request body,
    and delegates business logic to MessageService.

    Returns:
        dict: Message details including messageId, conversationId, timestamp, and status

    Raises:
        BadRequestError: If request validation fails
        UnauthorizedError: If JWT token is invalid
        InternalServerError: If database or SNS operations fail
    """
    try:
        # Extract senderId from JWT token
        sender_id = extract_sender_id_from_jwt()
        logger.info("Processing send message request", extra={"sender_id": sender_id})

        # Parse and validate request body
        try:
            request_data = SendMessageRequest.model_validate(app.current_event.json_body)
        except ValidationError as e:
            logger.warning("Request validation failed", extra={"errors": e.errors()})
            raise BadRequestError(f"Invalid request: {e}") from e

        # Get environment variables
        dynamodb_table_name, sns_topic_arn = get_environment_variables()

        # Initialize repository, SNS publisher, and service
        repository = MessageRepository(table_name=dynamodb_table_name)
        sns_publisher = SNSPublisher(topic_arn=sns_topic_arn)
        message_service = MessageService(repository=repository, sns_publisher=sns_publisher)

        # Delegate business logic to service
        try:
            stored_message = message_service.send_message(
                sender_id=sender_id,
                recipient_id=request_data.recipient_id,
                content=request_data.content,
                conversation_id=request_data.conversation_id,
                model_id=request_data.model_id,
                temperature=request_data.temperature,
            )
        except ValueError as e:
            logger.warning("Service validation failed", extra={"error": str(e)})
            raise BadRequestError(str(e)) from e
        except RuntimeError as e:
            logger.error("Service operation failed", extra={"error": str(e)})
            raise InternalServerError(str(e)) from e

        # Return message details with 201 Created status code
        response = {
            "messageId": stored_message.message_id,
            "conversationId": stored_message.conversation_id,
            "timestamp": stored_message.timestamp,
            "status": stored_message.status.value,
        }

        logger.info("Send message request completed successfully", extra={"message_id": stored_message.message_id})
        return response, 201

    except (BadRequestError, UnauthorizedError, InternalServerError):
        # Re-raise these as they have proper HTTP status codes
        raise
    except Exception as e:
        logger.error("Unexpected error in send_message", extra={"error": str(e)}, exc_info=True)
        raise InternalServerError("An unexpected error occurred") from e


@app.put("/messages/<message_id>/status")
def update_message_status(message_id: str) -> dict[str, Any]:
    """Update message status by messageId.

    Args:
        message_id: The message ID from the URL path

    Returns:
        dict: Updated message status information

    Raises:
        BadRequestError: If request validation fails or messageId is invalid
        NotFoundError: If message is not found
        InternalServerError: If database operations fail
    """
    try:
        logger.info("Processing update message status request", extra={"message_id": message_id})

        # Parse and validate request body
        try:
            request_data = UpdateMessageStatusRequest.model_validate(app.current_event.json_body)
        except ValidationError as e:
            logger.warning("Request validation failed", extra={"errors": e.errors(), "message_id": message_id})
            raise BadRequestError(f"Invalid request: {e}") from e

        # Get environment variables
        dynamodb_table_name, sns_topic_arn = get_environment_variables()

        # Initialize repository, SNS publisher, and service
        repository = MessageRepository(table_name=dynamodb_table_name)
        sns_publisher = SNSPublisher(topic_arn=sns_topic_arn)
        message_service = MessageService(repository=repository, sns_publisher=sns_publisher)

        # Delegate business logic to service
        try:
            updated_message = message_service.update_message_status(message_id=message_id, status=request_data.status)

            if updated_message is None:
                logger.warning("Message not found for status update", extra={"message_id": message_id})
                raise NotFoundError(f"Message with ID '{message_id}' not found")

        except ValueError as e:
            logger.warning("Service validation failed", extra={"error": str(e), "message_id": message_id})
            raise BadRequestError(str(e)) from e
        except RuntimeError as e:
            logger.error("Service operation failed", extra={"error": str(e), "message_id": message_id})
            raise InternalServerError(str(e)) from e

        # Return updated message status
        response = {
            "messageId": updated_message.message_id,
            "status": updated_message.status.value,
            "updatedAt": updated_message.updated_at,
        }

        logger.info("Update message status request completed successfully", extra={"message_id": message_id})
        return response

    except (BadRequestError, NotFoundError, InternalServerError):
        # Re-raise these as they have proper HTTP status codes
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in update_message_status",
            extra={"error": str(e), "message_id": message_id},
            exc_info=True,
        )
        raise InternalServerError("An unexpected error occurred") from e


@app.get("/conversations/<conversation_id>/messages")
def get_messages(conversation_id: str) -> dict[str, Any]:
    """Get messages for a conversation with optional timestamp filtering.

    Args:
        conversation_id: The conversation ID from the URL path (URL-encoded)

    Returns:
        dict: Paginated list of messages with hasMore indicator

    Raises:
        BadRequestError: If request validation fails or conversationId is invalid
        UnauthorizedError: If JWT token is invalid
        InternalServerError: If database operations fail
    """
    try:
        # URL-decode the conversation_id parameter
        import urllib.parse

        decoded_conversation_id = urllib.parse.unquote(conversation_id)

        # Extract senderId from JWT token for authorization
        sender_id = extract_sender_id_from_jwt()
        logger.info(
            "Processing get messages request",
            extra={"conversation_id": decoded_conversation_id, "sender_id": sender_id},
        )

        # Parse optional query parameters
        query_params = app.current_event.query_string_parameters or {}
        since_timestamp = query_params.get("since")
        limit_str = query_params.get("limit", "50")

        # Validate and parse limit
        try:
            limit = int(limit_str)
        except ValueError:
            logger.warning("Invalid limit parameter", extra={"limit": limit_str, "conversation_id": conversation_id})
            raise BadRequestError("Invalid limit parameter: must be a number") from None

        # Get environment variables
        dynamodb_table_name, sns_topic_arn = get_environment_variables()

        # Initialize repository, SNS publisher, and service
        repository = MessageRepository(table_name=dynamodb_table_name)
        sns_publisher = SNSPublisher(topic_arn=sns_topic_arn)
        message_service = MessageService(repository=repository, sns_publisher=sns_publisher)

        # Delegate business logic to service
        try:
            messages, has_more = message_service.get_messages(
                conversation_id=decoded_conversation_id, since_timestamp=since_timestamp, limit=limit
            )
        except ValueError as e:
            logger.warning(
                "Service validation failed", extra={"error": str(e), "conversation_id": decoded_conversation_id}
            )
            raise BadRequestError(str(e)) from e
        except RuntimeError as e:
            logger.error(
                "Service operation failed", extra={"error": str(e), "conversation_id": decoded_conversation_id}
            )
            raise InternalServerError(str(e)) from e

        # Convert messages to response format
        message_list = []
        for message in messages:
            message_list.append(
                {
                    "messageId": message.message_id,
                    "conversationId": message.conversation_id,
                    "senderId": message.sender_id,
                    "recipientId": message.recipient_id,
                    "content": message.content,
                    "status": message.status.value,
                    "timestamp": message.timestamp,
                }
            )

        # Return paginated response
        response = {"messages": message_list, "hasMore": has_more}

        logger.info(
            "Get messages request completed successfully",
            extra={
                "conversation_id": decoded_conversation_id,
                "message_count": len(message_list),
                "has_more": has_more,
            },
        )
        return response

    except (BadRequestError, UnauthorizedError, InternalServerError):
        # Re-raise these as they have proper HTTP status codes
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in get_messages",
            extra={"error": str(e), "conversation_id": conversation_id},
            exc_info=True,
        )
        raise InternalServerError("An unexpected error occurred") from e


def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """
    Main Lambda handler function.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    # Get and validate environment variables at runtime
    dynamodb_table_name, sns_topic_arn = get_environment_variables()

    logger.info(
        "Processing API Gateway request",
        extra={
            "request_id": context.aws_request_id,
            "function_name": context.function_name,
            "remaining_time": context.get_remaining_time_in_millis(),
            "dynamodb_table": dynamodb_table_name,
            "sns_topic": sns_topic_arn,
        },
    )

    try:
        return app.resolve(event, context)
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            },
            "body": json.dumps({"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}}),
        }
