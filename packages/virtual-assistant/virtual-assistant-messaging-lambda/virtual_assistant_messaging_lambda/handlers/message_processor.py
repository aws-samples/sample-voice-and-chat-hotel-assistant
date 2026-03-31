# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handler for processing hotel assistant messages from SQS queue."""

import asyncio
import json
import os
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.batch import BatchProcessor, EventType
from aws_lambda_powertools.utilities.parser import envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext

# Import shared models from virtual-assistant-common
from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest, MessageEvent, MessageGroup
from virtual_assistant_common.platforms.router import platform_router

from ..models.sqs_events import ProcessingResult, SNSMessage, SQSRecord
from ..services.agentcore_client import AgentCoreClient
from ..services.allow_list_validator import is_phone_allowed

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="HotelAssistantMessaging")

# Initialize SQS batch processor
processor = BatchProcessor(event_type=EventType.SQS)


def is_eum_whatsapp_message(sns_message: SNSMessage) -> bool:
    """Detect if SNS message contains EUM Social WhatsApp webhook data.

    Args:
        sns_message: SNS message to check

    Returns:
        True if message contains WhatsApp webhook data, False otherwise
    """
    try:
        # Check for EUM Social WhatsApp-specific fields in message
        message_data = sns_message.message
        if isinstance(message_data, dict):
            return "whatsAppWebhookEntry" in message_data
        elif isinstance(message_data, str):
            # Try to parse as JSON if it's a string
            try:
                parsed_data = json.loads(message_data)
                return "whatsAppWebhookEntry" in parsed_data
            except json.JSONDecodeError:
                return False
        return False
    except Exception as e:
        logger.debug(f"Error checking if message is WhatsApp: {e}")
        return False


def parse_whatsapp_message(sns_message: SNSMessage) -> MessageEvent | None:
    """Parse WhatsApp message into existing MessageEvent format.

    Args:
        sns_message: SNS message containing WhatsApp webhook data

    Returns:
        MessageEvent if parsing successful, None otherwise
    """
    try:
        logger.debug("Starting WhatsApp message parsing")
        message_data = sns_message.message
        logger.debug(f"Message data type: {type(message_data)}")

        # Handle both dict and string message formats
        if isinstance(message_data, str):
            logger.debug("Parsing message data as JSON string")
            message_data = json.loads(message_data)

        logger.debug(
            f"Message data keys: {list(message_data.keys()) if isinstance(message_data, dict) else 'Not a dict'}"
        )
        webhook_entry = message_data.get("whatsAppWebhookEntry")
        if not webhook_entry:
            logger.debug("No whatsAppWebhookEntry found in message")
            return None

        # Parse webhook entry if it's a string
        if isinstance(webhook_entry, str):
            logger.debug("Parsing webhook entry as JSON string")
            webhook_entry = json.loads(webhook_entry)

        logger.debug(f"Webhook entry type: {type(webhook_entry)}")
        logger.debug(
            f"Webhook entry keys: {list(webhook_entry.keys()) if isinstance(webhook_entry, dict) else 'Not a dict'}"
        )

        # Navigate WhatsApp webhook structure
        changes = webhook_entry.get("changes", [])
        logger.debug(f"Found {len(changes)} changes in webhook")
        for i, change in enumerate(changes):
            logger.debug(f"Change {i} field: {change.get('field')}")
            if change.get("field") == "messages":
                value = change.get("value", {})
                messages = value.get("messages", [])
                logger.debug(f"Found {len(messages)} messages in change")

                for j, message in enumerate(messages):
                    logger.debug(f"Message {j} type: {message.get('type')}")
                    if message.get("type") == "text":
                        logger.debug("Found text message, processing...")
                        # Extract metadata for phone number information
                        metadata = value.get("metadata", {})
                        display_phone_number = metadata.get("display_phone_number", "")
                        sender_phone = message["from"]
                        message_content = message["text"]["body"]

                        logger.debug(f"Creating MessageEvent for WhatsApp message ID: {message['id']}")
                        # Log phone number and message content at DEBUG level only (Requirements 8.1, 8.2)
                        logger.debug(f"WhatsApp message from phone: {sender_phone}")
                        logger.debug(f"WhatsApp message content: {message_content}")

                        # Generate conversation ID that meets both AgentCore Runtime and Memory requirements:
                        # - Runtime: 33-256 chars
                        # - Memory: 1-100 chars, pattern [a-zA-Z0-9][a-zA-Z0-9-_]*
                        # Format: whatsapp-conversation-{sanitized_phone_number}-session-id
                        # Remove + and other special characters from phone number for pattern compliance
                        sanitized_phone = sender_phone.replace("+", "").replace("-", "").replace(" ", "")
                        conversation_id = f"whatsapp-conversation-{sanitized_phone}-session-id"

                        # Ensure minimum length of 33 characters by padding if necessary
                        if len(conversation_id) < 33:
                            # Add padding with zeros to reach minimum length
                            padding_needed = 33 - len(conversation_id)
                            conversation_id = (
                                f"whatsapp-conversation-{sanitized_phone}-session-{'0' * padding_needed}id"
                            )

                        logger.debug(f"Generated conversation ID: {conversation_id} (length: {len(conversation_id)})")

                        # Convert to existing MessageEvent format
                        return MessageEvent(
                            message_id=message["id"],
                            sender_id=sender_phone,
                            recipient_id=display_phone_number,
                            content=message_content,
                            conversation_id=conversation_id,
                            timestamp=sns_message.timestamp,
                            platform="aws-eum",
                            platform_metadata={
                                "waba_id": metadata.get("waba_id"),
                                "phone_number_id": metadata.get("phone_number_id"),
                                "display_phone_number": display_phone_number,
                                "message_type": "text",
                            },
                        )

        logger.debug("No text messages found in WhatsApp webhook")
        return None

    except Exception as e:
        # Requirement 7.4: Log raw message for debugging when SNS message parsing fails
        logger.error(f"Failed to parse WhatsApp message: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.debug(f"Raw SNS message for debugging: {sns_message.model_dump()}")
        return None


def group_messages_by_sender(records: list[dict[str, Any]]) -> list[MessageGroup]:
    """Group SQS records by sender.

    This function parses SQS records to extract MessageEvent objects, then groups
    them by sender_id. Messages within each group are sorted by timestamp.

    Args:
        records: List of SQS records from batch event

    Returns:
        List of MessageGroup objects, one per unique sender

    Requirements: 1.1, 1.2, 1.5
    """
    # Dictionary to collect messages by sender_id
    messages_by_sender: dict[str, list[MessageEvent]] = {}

    for record in records:
        try:
            # Parse SQS record
            sqs_record = SQSRecord(**record)
            logger.debug(f"Parsing SQS record: {sqs_record.message_id}")

            # Parse SNS message from SQS body
            sns_message = SNSMessage(**json.loads(sqs_record.body))

            # Detect message type and parse accordingly
            message_event: MessageEvent | None = None

            if is_eum_whatsapp_message(sns_message):
                logger.debug("Detected WhatsApp message in grouping")
                # Parse WhatsApp message
                whatsapp_event = parse_whatsapp_message(sns_message)
                if whatsapp_event:
                    # Check if phone number is allowed
                    if is_phone_allowed(whatsapp_event.sender_id):
                        message_event = whatsapp_event
                    else:
                        logger.debug(f"Skipping blocked phone number in grouping: {whatsapp_event.sender_id}")
                        continue
                else:
                    logger.warning("Failed to parse WhatsApp message in grouping, skipping")
                    continue
            else:
                logger.debug("Detected simulated message in grouping")
                # Parse simulated message
                message_data = sns_message.message
                if isinstance(message_data, str):
                    message_data = json.loads(message_data)
                message_event = MessageEvent(**message_data)

            # Group by sender_id
            if message_event:
                sender_id = message_event.sender_id
                if sender_id not in messages_by_sender:
                    messages_by_sender[sender_id] = []
                messages_by_sender[sender_id].append(message_event)
                logger.debug(f"Added message {message_event.message_id} to group for sender {sender_id}")

        except Exception as e:
            logger.error(f"Failed to parse record in grouping: {e}")
            logger.debug(f"Failed record: {record}")
            # Skip invalid records - they will be handled by error handling in main flow
            continue

    # Create MessageGroup objects with sorted messages
    message_groups: list[MessageGroup] = []
    for sender_id, messages in messages_by_sender.items():
        # Sort messages by timestamp within each group
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        message_group = MessageGroup(messages=sorted_messages)
        message_groups.append(message_group)
        logger.debug(
            f"Created message group for sender {sender_id} with {len(sorted_messages)} messages: "
            f"{[m.message_id for m in sorted_messages]}"
        )

    logger.info(f"Grouped {len(records)} records into {len(message_groups)} message groups")
    return message_groups


def process_message_record(record: dict[str, Any]) -> None:
    """Process individual SQS message record.

    This function processes a single SQS record containing an SNS message
    with hotel assistant message data. It detects whether the message is from
    WhatsApp (EUM Social) or the simulated messaging backend, parses accordingly,
    and processes through the existing AgentCore flow.

    Args:
        record: SQS record containing SNS message

    Raises:
        Exception: If message processing fails (triggers SQS retry)
    """
    try:
        # Parse SQS record
        sqs_record = SQSRecord(**record)
        logger.debug(f"Processing SQS record: {sqs_record.message_id}")

        # Parse SNS message from SQS body
        sns_message = SNSMessage(**json.loads(sqs_record.body))
        logger.debug(f"Parsed SNS message: {sns_message.message_id}")

        # Detect message type and parse accordingly
        if is_eum_whatsapp_message(sns_message):
            logger.info("Detected EUM Social WhatsApp message")
            # Parse EUM Social WhatsApp message format
            whatsapp_event = parse_whatsapp_message(sns_message)
            logger.debug(f"WhatsApp parsing result: {whatsapp_event is not None}")
            if whatsapp_event:
                logger.debug(f"Parsed WhatsApp message ID: {whatsapp_event.message_id}")
                logger.debug(f"WhatsApp sender: {whatsapp_event.sender_id}")

                # Check if phone number is allowed
                is_allowed = is_phone_allowed(whatsapp_event.sender_id)
                logger.debug(f"Phone number allowed: {is_allowed}")
                if not is_allowed:
                    # Requirement 7.2: Log blocked phone numbers at DEBUG level only
                    logger.info("WhatsApp message blocked: phone number not in allow list")
                    logger.debug(f"Blocked phone number: {whatsapp_event.sender_id}")
                    return

                logger.debug(f"Processing WhatsApp message: {whatsapp_event.message_id}")
                logger.debug(f"WhatsApp message from phone: {whatsapp_event.sender_id}")
                event = whatsapp_event
            else:
                logger.warning("Failed to parse WhatsApp message, skipping")
                return
        else:
            logger.info("Detected simulated messaging backend message")
            # Existing simulation message handling
            try:
                message_data = sns_message.message
                if isinstance(message_data, str):
                    message_data = json.loads(message_data)
                event = MessageEvent(**message_data)
                logger.debug(f"Processing simulated message: {event.message_id}")
                logger.debug(f"Simulated message from sender: {event.sender_id}")
            except Exception as parse_error:
                # Enhanced error logging for simulated message parsing
                logger.error(f"Failed to parse simulated message: {parse_error}")
                logger.error(f"Error type: {type(parse_error).__name__}")
                logger.debug(f"Raw SNS message for debugging: {sns_message.model_dump()}")
                raise

        # Process the message asynchronously using existing flow
        try:
            result = asyncio.run(_process_message_async(event))
        except Exception as async_error:
            logger.error(f"Async processing failed for message {event.message_id}: {str(async_error)}")
            raise

        if not result.success:
            logger.error(f"Message processing failed: {result.error}")
            raise Exception(f"Message processing failed: {result.error}")

        logger.info(f"Successfully processed message: {event.message_id}")
        metrics.add_metric(name="MessagesProcessed", unit="Count", value=1)

        # Add specific metrics based on current platform
        current_platform = platform_router.get_current_platform()
        if current_platform == "aws-eum":
            metrics.add_metric(name="WhatsAppMessagesProcessed", unit="Count", value=1)
        else:
            metrics.add_metric(name="SimulatedMessagesProcessed", unit="Count", value=1)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON in SQS record: {str(e)}")
        logger.error(f"JSON decode error type: {type(e).__name__}")
        # Log raw record for debugging (Requirement 7.4)
        logger.debug(f"Raw SQS record for debugging: {record}")
        metrics.add_metric(name="MessageProcessingErrors", unit="Count", value=1)
        # Re-raise to trigger SQS retry behavior
        raise Exception(f"Invalid JSON format: {str(e)}") from e
    except Exception as e:
        logger.error(f"Failed to process SQS record: {str(e)}")
        logger.error(f"Processing error type: {type(e).__name__}")

        # Log additional error context if available
        if hasattr(e, "response"):
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", "Unknown error")
            logger.error(f"AWS Error Code: {error_code}, Message: {error_message}")

        # Log raw record for debugging (Requirement 7.4)
        logger.debug(f"Raw SQS record for debugging: {record}")

        metrics.add_metric(name="MessageProcessingErrors", unit="Count", value=1)
        # Re-raise to trigger SQS retry behavior
        raise


async def _process_message_async(event: MessageEvent) -> ProcessingResult:
    """Process message event asynchronously using wrapper functions for different backends.

    Note: This function currently processes single messages but will be updated to handle
    MessageGroup objects in the message batching implementation.

    Args:
        event: Message event to process

    Returns:
        Processing result with success status and details

    Requirements: 2.1, 2.2, 2.3, 3.1, 3.3, 3.4
    """
    try:
        # Update message status to delivered using platform router
        logger.debug(f"Updating message {event.message_id} status to delivered")
        await platform_router.update_message_status(event.message_id, "delivered")

        # Create AgentCore invocation request
        request = AgentCoreInvocationRequest(
            prompt=event.content,
            actorId=event.sender_id,
            messageIds=[event.message_id],  # Now a list for batching support
            conversationId=event.conversation_id,
            modelId=event.model_id,
            temperature=event.temperature,
        )

        # Invoke AgentCore Runtime asynchronously
        logger.debug(f"Invoking AgentCore Runtime for message {event.message_id}")
        agentcore_client = AgentCoreClient()
        agent_response = agentcore_client.invoke_agent(request)

        logger.debug(f"AgentCore invocation completed for message {event.message_id}")

        # Check if agent invocation was successful
        if not agent_response.success:
            error_msg = f"AgentCore invocation failed: {getattr(agent_response, 'error', 'Unknown error')}"
            logger.error(error_msg)

            # Log additional error details if available
            if hasattr(agent_response, "error_code"):
                logger.error(f"AgentCore error code: {agent_response.error_code}")
            if hasattr(agent_response, "error_details"):
                logger.error(f"AgentCore error details: {agent_response.error_details}")

            # Update message status to failed using platform router
            try:
                await platform_router.update_message_status(event.message_id, "failed")
            except Exception as status_error:
                logger.error(f"Failed to update message status to failed: {str(status_error)}")
                logger.error(f"Status update error type: {type(status_error).__name__}")

            return ProcessingResult(
                message_id=event.message_id,
                success=False,
                error=error_msg,
            )

        # Send response using wrapper
        response_content = getattr(agent_response, "content", "")
        if response_content:
            logger.debug(f"Sending response for message {event.message_id}")
            # Log response content at DEBUG level only (Requirement 8.2)
            logger.debug(f"Response content: {response_content}")

            response_result = await platform_router.send_response(event.conversation_id, response_content)
            response_sent = response_result.success

            if response_sent:
                # Mark message as read if response was sent successfully
                await platform_router.update_message_status(event.message_id, "read")
                logger.info(f"Response sent successfully for message {event.message_id}")
            else:
                # Mark message as failed if response couldn't be sent
                await platform_router.update_message_status(event.message_id, "failed")
                logger.error(f"Failed to send response for message {event.message_id}")

                # Log additional context for platform-specific failures
                current_platform = platform_router.get_current_platform()
                if current_platform == "aws-eum":
                    logger.error("WhatsApp response sending failed - check EUM Social configuration and permissions")
                    logger.debug(f"Failed WhatsApp response to phone: {event.sender_id}")
        else:
            logger.warning(f"No response content from AgentCore for message {event.message_id}")
            response_str = agent_response.model_dump() if hasattr(agent_response, "model_dump") else str(agent_response)
            logger.debug(f"AgentCore response object: {response_str}")

        return ProcessingResult(
            message_id=event.message_id,
            success=True,
            agent_response=agent_response.model_dump(),
        )

    except Exception as e:
        logger.error(f"Error processing message {event.message_id}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")

        # Log additional error context
        if hasattr(e, "response"):
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", "Unknown error")
            logger.error(f"AWS Error Code: {error_code}, Message: {error_message}")

        # Log conversation context for debugging
        logger.debug(f"Failed message conversation ID: {event.conversation_id}")
        current_platform = platform_router.get_current_platform()
        if current_platform == "aws-eum":
            logger.debug(f"WhatsApp processing failure for phone: {event.sender_id}")
        else:
            logger.debug(f"Simulated message processing failure for sender: {event.sender_id}")

        # Update message status to failed using platform router
        try:
            await platform_router.update_message_status(event.message_id, "failed")
        except Exception as status_error:
            logger.error(f"Failed to update message status to failed: {str(status_error)}")
            logger.error(f"Status update error type: {type(status_error).__name__}")

        return ProcessingResult(
            message_id=event.message_id,
            success=False,
            error=str(e),
        )


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@event_parser(model=MessageEvent, envelope=envelopes.SnsSqsEnvelope)
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler_with_envelope(events: list[MessageEvent], context: LambdaContext) -> dict[str, Any]:
    """Lambda handler using Powertools SnsSqsEnvelope for automatic parsing.

    This handler automatically parses SQS messages containing SNS notifications
    and extracts MessageEvent objects using Lambda Powertools envelopes.

    Args:
        events: List of parsed MessageEvent objects from SQS/SNS
        context: Lambda execution context

    Returns:
        Batch processing results with any failed items
    """
    try:
        logger.debug(f"Processing {len(events)} parsed message events")

        # Debug: Log the parsed events to see what we received
        for i, event in enumerate(events):
            logger.debug(f"Parsed event {i}: {event}")
            logger.debug(f"Event {i} model dump: {event.model_dump()}")

        # Validate environment variables
        _validate_environment()

        failed_items = []
        successful_count = 0

        for event in events:
            try:
                logger.debug(f"Processing message: {event.message_id}")

                # Process the message asynchronously
                result = asyncio.run(_process_message_async(event))

                if result.success:
                    successful_count += 1
                    logger.debug(f"Successfully processed message: {event.message_id}")
                else:
                    logger.error(f"Failed to process message {event.message_id}: {result.error}")
                    failed_items.append({"itemIdentifier": event.message_id})

            except Exception as e:
                logger.error(f"Failed to process message {event.message_id}: {str(e)}")
                failed_items.append({"itemIdentifier": event.message_id})

        # Log batch processing summary
        failed_count = len(failed_items)
        logger.info(f"Batch processing completed: {successful_count} successful, {failed_count} failed")

        metrics.add_metric(name="BatchesProcessed", unit="Count", value=1)
        metrics.add_metric(name="SuccessfulMessages", unit="Count", value=successful_count)
        metrics.add_metric(name="FailedMessages", unit="Count", value=failed_count)

        return {"batchItemFailures": failed_items}

    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        metrics.add_metric(name="LambdaHandlerErrors", unit="Count", value=1)
        return {"batchItemFailures": []}


@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Main Lambda handler for SQS batch processing.

    This handler processes batches of SQS messages containing SNS notifications
    about new hotel assistant messages. Messages are grouped by sender_id and
    each group is processed together in a single AgentCore Runtime invocation.

    Args:
        event: SQS batch event containing message records
        context: Lambda execution context

    Returns:
        Batch processing results with any failed items

    Requirements: 2.1, 4.1, 6.3
    """
    try:
        records = event.get("Records", [])
        logger.debug(f"Processing SQS batch with {len(records)} records")

        # Validate environment variables
        _validate_environment()

        # Group messages by sender
        message_groups = group_messages_by_sender(records)
        logger.info(f"Processing {len(message_groups)} message groups from {len(records)} records")

        # Log message group details (Requirements 4.4, 6.5)
        logger.info(f"Batch contains {len(message_groups)} message groups")
        for i, group in enumerate(message_groups):
            # Sanitize sender_id for logging (remove sensitive phone number details)
            sanitized_sender = group.sender_id[:4] + "***" if len(group.sender_id) > 4 else "***"
            logger.info(
                f"Group {i + 1}: sender={sanitized_sender}, "
                f"message_count={len(group.messages)}, "
                f"message_ids={group.message_ids}"
            )

        # Track failed message IDs
        failed_message_ids: list[str] = []
        successful_count = 0

        # Process each message group
        for group in message_groups:
            try:
                logger.debug(
                    f"Processing message group for sender {group.sender_id} "
                    f"with {len(group.messages)} messages: {group.message_ids}"
                )

                # Process the message group asynchronously
                result = asyncio.run(_process_message_async(group.messages[0]))

                if result.success:
                    successful_count += len(group.messages)
                    logger.debug(f"Successfully processed message group with IDs: {group.message_ids}")
                else:
                    logger.error(f"Failed to process message group: {result.error}")
                    # Add all message IDs from the group to failed items
                    failed_message_ids.extend(group.message_ids)

            except Exception as e:
                logger.error(f"Failed to process message group for sender {group.sender_id}: {str(e)}")
                logger.error(f"Group processing error type: {type(e).__name__}")
                # Log error context with all affected message IDs (Requirements 4.5)
                logger.error(
                    f"Error context - affected message IDs: {group.message_ids}, "
                    f"sender: {group.sender_id}, "
                    f"message_count: {len(group.messages)}"
                )

                # Add all message IDs from the group to failed items
                failed_message_ids.extend(group.message_ids)

        # Convert failed message IDs to SQS batch item failures format
        failed_items = [{"itemIdentifier": msg_id} for msg_id in failed_message_ids]
        failed_count = len(failed_message_ids)

        logger.info(
            f"Batch processing completed: {successful_count} messages successful, "
            f"{failed_count} messages failed across {len(message_groups)} groups"
        )

        metrics.add_metric(name="BatchesProcessed", unit="Count", value=1)
        metrics.add_metric(name="MessageGroupsProcessed", unit="Count", value=len(message_groups))
        metrics.add_metric(name="SuccessfulMessages", unit="Count", value=successful_count)
        metrics.add_metric(name="FailedMessages", unit="Count", value=failed_count)

        return {"batchItemFailures": failed_items}

    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        metrics.add_metric(name="LambdaHandlerErrors", unit="Count", value=1)
        # Return empty result to avoid reprocessing entire batch
        return {"batchItemFailures": []}


def _validate_environment() -> None:
    """Validate required environment variables based on configuration.

    When EUM Social is configured (EUM_SOCIAL_PHONE_NUMBER_ID present), only
    require EUM Social and AgentCore variables. When messaging backend is
    configured, only require messaging backend and AgentCore variables.

    Raises:
        ValueError: If required environment variables are missing
    """
    # AgentCore is always required
    agentcore_vars = ["AGENTCORE_RUNTIME_ARN"]

    # Check if EUM Social is configured
    eum_social_phone_id = os.environ.get("EUM_SOCIAL_PHONE_NUMBER_ID")

    if eum_social_phone_id:
        # EUM Social configuration - require EUM Social and AgentCore variables
        logger.debug("WhatsApp integration enabled - validating EUM Social configuration")

        required_vars = agentcore_vars + ["EUM_SOCIAL_PHONE_NUMBER_ID"]

        # Optional EUM Social variables (log but don't require)
        whatsapp_vars = {
            "EUM_SOCIAL_CROSS_ACCOUNT_ROLE": os.environ.get("EUM_SOCIAL_CROSS_ACCOUNT_ROLE"),
            "WHATSAPP_ALLOW_LIST_PARAMETER": os.environ.get("WHATSAPP_ALLOW_LIST_PARAMETER"),
        }

        if whatsapp_vars["EUM_SOCIAL_CROSS_ACCOUNT_ROLE"]:
            logger.debug("Cross-account role configured for EUM Social")
        else:
            logger.debug("Using same-account credentials for EUM Social")

        if whatsapp_vars["WHATSAPP_ALLOW_LIST_PARAMETER"]:
            logger.debug(f"WhatsApp allow list parameter: {whatsapp_vars['WHATSAPP_ALLOW_LIST_PARAMETER']}")
        else:
            logger.debug("Using default WhatsApp allow list parameter")

    else:
        # Messaging backend configuration - require messaging and AgentCore variables
        logger.debug("WhatsApp integration disabled - validating messaging backend configuration")

        required_vars = agentcore_vars + [
            "MESSAGING_API_ENDPOINT",
            "MESSAGING_CLIENT_SECRET_ARN",
        ]

    # Check for missing required variables
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    logger.info("Environment validation passed")


# Health check function for monitoring
def health_check() -> dict[str, Any]:
    """Perform health check of Lambda function dependencies.

    Returns:
        Health status information
    """
    try:
        # Check environment variables
        _validate_environment()

        # Check AgentCore client initialization
        AgentCoreClient()  # Just verify it can be initialized

        return {
            "status": "healthy",
            "environment": "valid",
            "timestamp": "2024-01-01T12:00:00Z",  # Placeholder timestamp
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2024-01-01T12:00:00Z",  # Placeholder timestamp
        }
