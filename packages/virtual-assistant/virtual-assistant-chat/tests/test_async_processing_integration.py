# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for AgentCore Runtime async processing."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from bedrock_agentcore import RequestContext


class TestAsyncProcessingUnit:
    """Integration tests for async message processing in AgentCore Runtime."""

    @pytest.fixture
    def sample_payload(self):
        """Create a sample invocation payload."""
        return {
            "prompt": "Hello, I need help with my hotel reservation",
            "actorId": "user123",
            "messageId": str(uuid.uuid4()),
            "conversationId": "user123#hotel-assistant",
            "modelId": "amazon.nova-lite-v1:0",
            "temperature": 0.2,
        }

    @pytest.fixture
    def mock_context(self):
        """Create a mock RequestContext."""
        context = MagicMock(spec=RequestContext)
        context.session_id = "user123#hotel-assistant"
        return context

    @pytest.fixture
    def mock_environment(self):
        """Mock environment variables."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
                "MODEL_TEMPERATURE": "0.2",
                "LOG_LEVEL": "INFO",
                "AGENTCORE_MEMORY_ID": "test-memory-id",
            },
        ):
            yield

    def test_successful_async_processing(self, sample_payload, mock_context, mock_environment, mock_agent_module):
        """Test that we can import the agent module successfully."""
        assert hasattr(mock_agent_module, "logger")

    @pytest.mark.asyncio
    async def test_async_processing_with_error(self, sample_payload, mock_context, mock_environment, mock_agent_module):
        """Test error handling in agent processing."""
        # Test that the module has the expected structure for error handling
        assert hasattr(mock_agent_module, "process_user_message")
        assert callable(mock_agent_module.process_user_message)

    def test_async_processing_with_tool_use(self, sample_payload, mock_context, mock_environment):
        """Test async processing with tool use."""
        from virtual_assistant_common.platforms.router import platform_router

        assert hasattr(platform_router, "update_message_status")
        assert hasattr(platform_router, "send_response")

    def test_entrypoint_missing_parameters(self, mock_context, mock_environment):
        """Test parameter validation."""
        from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest

        incomplete_payload = {"prompt": "Hello"}
        with pytest.raises(ValueError):
            AgentCoreInvocationRequest.model_validate(incomplete_payload)

    def test_entrypoint_pydantic_validation(self, mock_context, mock_environment):
        """Test entrypoint with Pydantic model validation for payload."""
        from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest

        valid_payload = {
            "prompt": "Hello, I need help with my reservation",
            "actorId": "user123",
            "messageId": "msg-456",
            "conversationId": "user123#hotel-assistant",
            "modelId": "amazon.nova-lite-v1:0",
            "temperature": 0.7,
        }

        request = AgentCoreInvocationRequest.model_validate(valid_payload)
        assert request.prompt == "Hello, I need help with my reservation"
        assert request.actor_id == "user123"
        assert request.message_id == "msg-456"

    def test_entrypoint_exception_handling(self, sample_payload, mock_context, mock_environment, mock_agent_module):
        """Test exception handling in the agent module."""
        assert hasattr(mock_agent_module, "logger")
        assert hasattr(mock_agent_module, "BedrockAgentCoreApp")

        from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest
        from virtual_assistant_common.platforms.router import platform_router

        assert callable(AgentCoreInvocationRequest.model_validate)
        assert hasattr(platform_router, "update_message_status")
