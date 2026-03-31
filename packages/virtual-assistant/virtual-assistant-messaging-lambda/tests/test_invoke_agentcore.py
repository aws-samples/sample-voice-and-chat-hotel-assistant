# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for InvokeAgentCore Lambda handler task token functionality."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInvokeAgentCoreTaskToken:
    """Test task token extraction and passing in InvokeAgentCore Lambda."""

    def test_task_token_extraction_when_present(self):
        """Test that task_token is extracted from event when present."""
        # Mock platform router
        mock_update_status = AsyncMock()

        # Mock AgentCore client
        mock_response = MagicMock()
        mock_response.success = True
        mock_agentcore_client = MagicMock()
        mock_agentcore_client.invoke_agent.return_value = mock_response

        # Event with task_token
        event = {
            "user_id": "user-123",
            "session_id": "session-456",
            "task_token": "test-token-xyz",
            "marked_messages": {
                "processing_messages": [
                    {
                        "message_id": "msg-1",
                        "content": "Hello",
                        "timestamp": "2026-01-13T14:14:41.473Z",
                        "sender_id": "user-123",
                        "conversation_id": "session-456",
                        "platform": "web",
                    }
                ],
                "message_count": 1,
            },
        }

        with (
            patch.dict(
                os.environ,
                {
                    "BEDROCK_MODEL_ID": "test-model",
                    "MODEL_TEMPERATURE": "0.2",
                    "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                },
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
                mock_update_status,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            from virtual_assistant_messaging_lambda.handlers.invoke_agentcore import lambda_handler

            # Execute handler
            response = lambda_handler(event, MagicMock())

            # Verify AgentCore was invoked
            assert mock_agentcore_client.invoke_agent.called

            # Get the invocation request
            invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]

            # Verify task_token was passed
            assert invocation_request.task_token == "test-token-xyz"

            # Verify response is successful
            assert response["status"] == "success"

    def test_lambda_works_without_task_token(self):
        """Test that Lambda works correctly when task_token is None."""
        # Mock platform router
        mock_update_status = AsyncMock()

        # Mock AgentCore client
        mock_response = MagicMock()
        mock_response.success = True
        mock_agentcore_client = MagicMock()
        mock_agentcore_client.invoke_agent.return_value = mock_response

        # Event without task_token
        event = {
            "user_id": "user-123",
            "session_id": "session-456",
            # No task_token
            "marked_messages": {
                "processing_messages": [
                    {
                        "message_id": "msg-1",
                        "content": "Hello",
                        "timestamp": "2026-01-13T14:14:41.473Z",
                        "sender_id": "user-123",
                        "conversation_id": "session-456",
                        "platform": "web",
                    }
                ],
                "message_count": 1,
            },
        }

        with (
            patch.dict(
                os.environ,
                {
                    "BEDROCK_MODEL_ID": "test-model",
                    "MODEL_TEMPERATURE": "0.2",
                    "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                },
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
                mock_update_status,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            from virtual_assistant_messaging_lambda.handlers.invoke_agentcore import lambda_handler

            # Execute handler
            response = lambda_handler(event, MagicMock())

            # Verify AgentCore was invoked
            assert mock_agentcore_client.invoke_agent.called

            # Get the invocation request
            invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]

            # Verify task_token is None
            assert invocation_request.task_token is None

            # Verify response is successful
            assert response["status"] == "success"

    def test_task_token_passed_to_agentcore_when_present(self):
        """Test that task_token is passed to AgentCore client when present."""
        # Mock platform router
        mock_update_status = AsyncMock()

        # Mock AgentCore client
        mock_response = MagicMock()
        mock_response.success = True
        mock_agentcore_client = MagicMock()
        mock_agentcore_client.invoke_agent.return_value = mock_response

        # Event with task_token
        event = {
            "user_id": "user-456",
            "session_id": "session-789",
            "task_token": "token-abc-123",
            "marked_messages": {
                "processing_messages": [
                    {
                        "message_id": "msg-2",
                        "content": "Test message",
                        "timestamp": "2026-01-13T14:14:41.473Z",
                        "sender_id": "user-456",
                        "conversation_id": "session-789",
                        "platform": "web",
                    }
                ],
                "message_count": 1,
            },
        }

        with (
            patch.dict(
                os.environ,
                {
                    "BEDROCK_MODEL_ID": "test-model",
                    "MODEL_TEMPERATURE": "0.2",
                    "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                },
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
                mock_update_status,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            from virtual_assistant_messaging_lambda.handlers.invoke_agentcore import lambda_handler

            # Execute handler
            lambda_handler(event, MagicMock())

            # Verify AgentCore was invoked with task_token
            invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]
            assert invocation_request.task_token == "token-abc-123"

    def test_task_token_not_passed_when_absent(self):
        """Test that task_token is not passed when absent from event."""
        # Mock platform router
        mock_update_status = AsyncMock()

        # Mock AgentCore client
        mock_response = MagicMock()
        mock_response.success = True
        mock_agentcore_client = MagicMock()
        mock_agentcore_client.invoke_agent.return_value = mock_response

        # Event without task_token
        event = {
            "user_id": "user-789",
            "session_id": "session-abc",
            "marked_messages": {
                "processing_messages": [
                    {
                        "message_id": "msg-3",
                        "content": "Another test",
                        "timestamp": "2026-01-13T14:14:41.473Z",
                        "sender_id": "user-789",
                        "conversation_id": "session-abc",
                        "platform": "web",
                    }
                ],
                "message_count": 1,
            },
        }

        with (
            patch.dict(
                os.environ,
                {
                    "BEDROCK_MODEL_ID": "test-model",
                    "MODEL_TEMPERATURE": "0.2",
                    "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                },
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
                mock_update_status,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            from virtual_assistant_messaging_lambda.handlers.invoke_agentcore import lambda_handler

            # Execute handler
            lambda_handler(event, MagicMock())

            # Verify AgentCore was invoked without task_token
            invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]
            assert invocation_request.task_token is None

    def test_return_value_consistent_with_task_token(self):
        """Test that return value is consistent regardless of task_token presence."""
        # Mock platform router
        mock_update_status = AsyncMock()

        # Mock AgentCore client
        mock_response = MagicMock()
        mock_response.success = True
        mock_agentcore_client = MagicMock()
        mock_agentcore_client.invoke_agent.return_value = mock_response

        # Event with task_token
        event_with_token = {
            "user_id": "user-123",
            "session_id": "session-456",
            "task_token": "test-token",
            "marked_messages": {
                "processing_messages": [
                    {
                        "message_id": "msg-1",
                        "content": "Hello",
                        "timestamp": "2026-01-13T14:14:41.473Z",
                        "sender_id": "user-123",
                        "conversation_id": "session-456",
                        "platform": "web",
                    }
                ],
                "message_count": 1,
            },
        }

        # Event without task_token
        event_without_token = {
            "user_id": "user-123",
            "session_id": "session-456",
            "marked_messages": {
                "processing_messages": [
                    {
                        "message_id": "msg-1",
                        "content": "Hello",
                        "timestamp": "2026-01-13T14:14:41.473Z",
                        "sender_id": "user-123",
                        "conversation_id": "session-456",
                        "platform": "web",
                    }
                ],
                "message_count": 1,
            },
        }

        with (
            patch.dict(
                os.environ,
                {
                    "BEDROCK_MODEL_ID": "test-model",
                    "MODEL_TEMPERATURE": "0.2",
                    "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
                },
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
                mock_update_status,
            ),
            patch(
                "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
                return_value=mock_agentcore_client,
            ),
        ):
            from virtual_assistant_messaging_lambda.handlers.invoke_agentcore import lambda_handler

            # Execute with token
            response_with_token = lambda_handler(event_with_token, MagicMock())

            # Execute without token
            response_without_token = lambda_handler(event_without_token, MagicMock())

            # Verify both responses have same structure
            assert response_with_token["status"] == response_without_token["status"]
            assert response_with_token["message_ids"] == response_without_token["message_ids"]
            assert response_with_token["user_id"] == response_without_token["user_id"]
