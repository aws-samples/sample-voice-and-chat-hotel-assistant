# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handler for buffering messages in DynamoDB and initiating Step Functions workflow."""

import json
import os
import time
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field
from virtual_assistant_common.models.messaging import MessageEvent

# Import parsing functions from message_processor
from .message_processor import is_eum_whatsapp_message, parse_whatsapp_message

# Initialize AWS Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="MessageBuffering")

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")


def convert_floats_to_decimal(obj: Any) -> Any:
    """Recursively convert float values to Decimal for DynamoDB compatibility.

    DynamoDB does not support Python float types - they must be converted to Decimal.
    This function recursively walks through dictionaries and lists to convert all floats.

    Args:
        obj: Object to convert (can be dict, list, float, or any other type)

    Returns:
        Object with all floats converted to Decimal
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj


class SNSMessage(BaseModel):
    """SNS message structure."""

    message_id: str = Field(alias="MessageId")
    message: str | dict = Field(alias="Message")
    timestamp: str = Field(alias="Timestamp")
    subject: str | None = Field(default=None, alias="Subject")


class SNSRecord(BaseModel):
    """SNS record structure."""

    event_source: str = Field(alias="EventSource")
    sns: SNSMessage = Field(alias="Sns")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Handle incoming messages from SNS and buffer them in DynamoDB.

    This handler:
    1. Parses SNS messages (WhatsApp or simulated)
    2. Writes each message to DynamoDB buffer with processing = false
    3. Atomically checks and sets waiting_state
    4. Starts Step Functions workflow if not already waiting

    Args:
        event: SNS event containing message records
        context: Lambda context

    Returns:
        Success response

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
    """
    try:
        # Debug: Log incoming event
        logger.debug(f"Received event with {len(event.get('Records', []))} records")
        logger.debug(f"Raw event: {json.dumps(event)}")

        # Get environment variables
        buffer_table_name = os.environ.get("MESSAGE_BUFFER_TABLE")
        state_machine_arn = os.environ.get("BATCHER_STATE_MACHINE_ARN")

        logger.debug(f"Environment - buffer_table: {buffer_table_name}, state_machine: {state_machine_arn}")

        if not buffer_table_name or not state_machine_arn:
            raise ValueError(
                "Missing required environment variables: MESSAGE_BUFFER_TABLE or BATCHER_STATE_MACHINE_ARN"
            )

        buffer_table = dynamodb.Table(buffer_table_name)

        # Process each SNS record
        records = event.get("Records", [])
        logger.info(f"Processing {len(records)} SNS records")
        processed_count = 0
        error_count = 0

        for record in records:
            try:
                # Parse SNS record
                sns_record = SNSRecord(**record)
                sns_message = sns_record.sns

                logger.debug(f"Processing SNS message: {sns_message.message_id}")
                logger.debug(f"SNS Subject: {sns_message.subject}")
                logger.debug(f"SNS Message type: {type(sns_message.message)}")

                # Parse message to MessageEvent
                message_event: MessageEvent | None = None

                # Detect message type and parse accordingly
                if is_eum_whatsapp_message(sns_message):
                    logger.debug("Detected WhatsApp message")
                    message_event = parse_whatsapp_message(sns_message)
                    if not message_event:
                        logger.warning("Failed to parse WhatsApp message, skipping")
                        logger.debug(f"SNS message: {sns_record.model_dump_json()}")
                        continue
                else:
                    logger.debug("Detected simulated message")
                    # Parse simulated message
                    message_data = sns_message.message
                    if isinstance(message_data, str):
                        logger.debug("Parsing message data as JSON string")
                        message_data = json.loads(message_data)

                    message_event = MessageEvent(**message_data)

                logger.info(f"Processing message {message_event.message_id} from user {message_event.sender_id}")
                logger.debug(
                    f"MessageEvent details - conversation_id: {message_event.conversation_id}, "
                    f"platform: {message_event.platform}, content_length: {len(message_event.content)}"
                )

                # Write message to DynamoDB buffer
                current_time = time.time()
                ttl = int(current_time + 600)  # 10 minutes TTL

                # Prepare message data with processing flag
                message_data = message_event.model_dump()
                message_data["processing"] = False

                # Convert floats to Decimal for DynamoDB compatibility
                message_data = convert_floats_to_decimal(message_data)

                logger.debug(
                    f"Writing to DynamoDB - user_id: {message_event.sender_id}, "
                    f"session_id: {message_event.conversation_id}, ttl: {ttl}"
                )

                # Write to buffer
                buffer_table.update_item(
                    Key={"user_id": message_event.sender_id},
                    UpdateExpression=(
                        "SET messages = list_append(if_not_exists(messages, :empty), :msg), "
                        "session_id = if_not_exists(session_id, :session), "
                        "last_update_time = :time, "
                        "#ttl = :ttl"
                    ),
                    ExpressionAttributeNames={
                        "#ttl": "ttl",
                    },
                    ExpressionAttributeValues={
                        ":empty": [],
                        ":msg": [message_data],
                        ":session": message_event.conversation_id,
                        ":time": Decimal(str(current_time)),
                        ":ttl": ttl,
                    },
                )

                logger.debug(f"Wrote message {message_event.message_id} to buffer for user {message_event.sender_id}")
                metrics.add_metric(name="MessagesBuffered", unit="Count", value=1)

                # Atomic check-and-set for waiting state
                logger.debug(f"Attempting to set waiting_state for user {message_event.sender_id}")
                try:
                    # Try to set waiting_state = true only if it doesn't exist or is false
                    buffer_table.update_item(
                        Key={"user_id": message_event.sender_id},
                        UpdateExpression="SET waiting_state = :true",
                        ConditionExpression="attribute_not_exists(waiting_state) OR waiting_state = :false",
                        ExpressionAttributeValues={
                            ":true": True,
                            ":false": False,
                        },
                    )

                    # If we get here, we successfully set waiting_state = true
                    logger.debug(f"Successfully set waiting_state=true for user {message_event.sender_id}")

                    # Start Step Functions workflow
                    execution_name = f"batch-{message_event.sender_id}-{int(current_time * 1000)}"
                    workflow_input = {"user_id": message_event.sender_id}

                    logger.debug(
                        f"Starting Step Functions execution - name: {execution_name}, "
                        f"input: {json.dumps(workflow_input)}"
                    )

                    response = sfn_client.start_execution(
                        stateMachineArn=state_machine_arn,
                        name=execution_name,
                        input=json.dumps(workflow_input),
                    )

                    logger.info(f"Started workflow {response['executionArn']} for user {message_event.sender_id}")
                    logger.debug(f"Workflow start time: {response.get('startDate')}")
                    metrics.add_metric(name="WorkflowsStarted", unit="Count", value=1)

                except ClientError as e:
                    error_code = e.response["Error"]["Code"]
                    logger.debug(f"DynamoDB conditional update error: {error_code}")

                    if error_code == "ConditionalCheckFailedException":
                        # Workflow already running for this user
                        logger.info(f"Workflow already running for user {message_event.sender_id}, message buffered")
                        metrics.add_metric(name="MessagesAddedToExistingWorkflow", unit="Count", value=1)
                    else:
                        # Other DynamoDB error
                        logger.error(f"DynamoDB error: {e.response['Error']}")
                        raise

                processed_count += 1

            except Exception as e:
                logger.error(f"Failed to process SNS record: {e}")
                logger.error(f"Error type: {type(e).__name__}")
                logger.debug(f"Failed record: {json.dumps(record)}")
                metrics.add_metric(name="MessageProcessingErrors", unit="Count", value=1)
                error_count += 1
                # Continue processing other messages
                continue

        logger.info(
            f"Batch processing completed - processed: {processed_count}, errors: {error_count}, total: {len(records)}"
        )
        return {"statusCode": 200, "body": json.dumps({"message": "Messages processed successfully"})}

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        metrics.add_metric(name="LambdaHandlerErrors", unit="Count", value=1)
        raise
