# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Simple AgentCore Runtime client for invoking hotel assistant agents."""

import json
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest, AgentCoreInvocationResponse

logger = logging.getLogger(__name__)


class AgentCoreClient:
    """Simple client for invoking AgentCore Runtime asynchronously."""

    def __init__(self, runtime_arn: str | None = None, region: str | None = None):
        """Initialize AgentCore client.

        Args:
            runtime_arn: AgentCore Runtime ARN (defaults to env var)
            region: AWS region (defaults to env var or boto3 default)
        """
        self.runtime_arn = runtime_arn or os.environ.get("AGENTCORE_RUNTIME_ARN")
        if not self.runtime_arn:
            raise ValueError("AGENTCORE_RUNTIME_ARN environment variable or runtime_arn parameter required")

        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        # Initialize boto3 client for Bedrock AgentCore
        # This will use IAM role credentials automatically in Lambda
        self.client = boto3.client("bedrock-agentcore", region_name=self.region)

        logger.info(f"Initialized AgentCore client for runtime: {self.runtime_arn}")

    def invoke_agent(self, request: AgentCoreInvocationRequest) -> AgentCoreInvocationResponse:
        """Invoke AgentCore Runtime asynchronously.

        Args:
            request: Agent invocation request

        Returns:
            Agent invocation response indicating success/failure
        """
        try:
            # Use first message ID for logging and response tracking
            primary_message_id = request.message_ids[0] if request.message_ids else "unknown"
            logger.info(f"Invoking AgentCore Runtime for message group: {request.message_ids}")

            # Prepare the payload for AgentCore Runtime
            request_payload = json.dumps(request.model_dump(by_alias=True)).encode("utf-8")

            # Use the invoke_agent_runtime API for AgentCore Runtime
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.runtime_arn,
                contentType="application/json",
                accept="application/json",
                runtimeSessionId=request.conversation_id,
                runtimeUserId=request.actor_id,
                payload=request_payload,
            )

            # Agent returns AgentCoreInvocationResponse.model_dump()
            # Pydantic can parse JSON bytes directly from the response stream
            try:
                response_bytes = response["response"].read()
                agent_response = AgentCoreInvocationResponse.model_validate_json(response_bytes)
                logger.debug(
                    f"Agent response: success={agent_response.success}, message_id={agent_response.message_id}"
                )
                return agent_response
            except Exception as e:
                logger.warning(f"Failed to parse agent response: {e}")
                return AgentCoreInvocationResponse(
                    success=False,
                    message_id=primary_message_id,
                    error=f"Invalid agent response: {e}",
                )

        except (ClientError, BotoCoreError) as e:
            error_message = str(e)
            primary_message_id = request.message_ids[0] if request.message_ids else "unknown"
            logger.error(f"AgentCore invocation failed for message group {request.message_ids}: {error_message}")
            return AgentCoreInvocationResponse(
                success=False,
                message_id=primary_message_id,
                error=error_message,
            )

        except Exception as e:
            error_message = f"Unexpected error during AgentCore invocation: {str(e)}"
            logger.error(error_message)
            primary_message_id = request.message_ids[0] if request.message_ids else "unknown"
            return AgentCoreInvocationResponse(
                success=False,
                message_id=primary_message_id,
                error=error_message,
            )
