# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for AgentCore client serialization."""

import json
from unittest.mock import MagicMock, patch

from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest

from virtual_assistant_messaging_lambda.services.agentcore_client import AgentCoreClient


class TestAgentCoreClient:
    """Test cases for AgentCore client."""

    def test_payload_serialization_uses_aliases(self):
        """Test that AgentCore client serializes payload with camelCase aliases."""
        # Create test request
        request = AgentCoreInvocationRequest(
            prompt="Hello, I need help with my reservation",
            actorId="user123",
            messageIds=["msg-456"],
            conversationId="conv-789",
            modelId="amazon.nova-lite-v1:0",
            temperature=0.7,
        )

        # Mock boto3 client
        mock_boto_client = MagicMock()
        mock_boto_client.invoke_agent_runtime.return_value = {"ResponseMetadata": {"RequestId": "test-request-id"}}

        with patch("boto3.client", return_value=mock_boto_client):
            client = AgentCoreClient("arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test")

            # Invoke the agent
            response = client.invoke_agent(request)

            # Verify the response
            assert response.success is True
            assert response.message_id == "msg-456"

            # Verify the payload was serialized with aliases
            mock_boto_client.invoke_agent_runtime.assert_called_once()
            call_kwargs = mock_boto_client.invoke_agent_runtime.call_args.kwargs

            # Decode the payload
            payload_bytes = call_kwargs["payload"]
            payload_str = payload_bytes.decode("utf-8")
            payload_dict = json.loads(payload_str)

            # Verify the payload uses camelCase aliases
            assert "actorId" in payload_dict
            assert "messageIds" in payload_dict
            assert "conversationId" in payload_dict
            assert "modelId" in payload_dict
            assert payload_dict["actorId"] == "user123"
            assert payload_dict["messageIds"] == ["msg-456"]
            assert payload_dict["conversationId"] == "conv-789"
            assert payload_dict["modelId"] == "amazon.nova-lite-v1:0"
            assert payload_dict["temperature"] == 0.7

            # Verify it does NOT use snake_case field names
            assert "actor_id" not in payload_dict
            assert "message_ids" not in payload_dict
            assert "conversation_id" not in payload_dict
            assert "model_id" not in payload_dict

    def test_payload_serialization_minimal_request(self):
        """Test serialization with minimal request (no optional fields)."""
        # Create minimal test request
        request = AgentCoreInvocationRequest(
            prompt="Hello",
            actorId="user123",
            messageIds=["msg-456"],
            conversationId="conv-789",
        )

        # Mock boto3 client
        mock_boto_client = MagicMock()
        mock_boto_client.invoke_agent_runtime.return_value = {"ResponseMetadata": {"RequestId": "test-request-id"}}

        with patch("boto3.client", return_value=mock_boto_client):
            client = AgentCoreClient("arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test")

            # Invoke the agent
            response = client.invoke_agent(request)

            # Verify the response
            assert response.success is True

            # Verify the payload was serialized correctly
            call_kwargs = mock_boto_client.invoke_agent_runtime.call_args.kwargs
            payload_bytes = call_kwargs["payload"]
            payload_str = payload_bytes.decode("utf-8")
            payload_dict = json.loads(payload_str)

            # Verify required fields are present with aliases
            assert payload_dict["prompt"] == "Hello"
            assert payload_dict["actorId"] == "user123"
            assert payload_dict["messageIds"] == ["msg-456"]
            assert payload_dict["conversationId"] == "conv-789"

            # Verify optional fields are null (not missing)
            assert payload_dict["modelId"] is None
            assert payload_dict["temperature"] is None
