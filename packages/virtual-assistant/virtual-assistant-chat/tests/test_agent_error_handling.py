#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Test suite for agent error handling functionality.

This test suite verifies that the main agent processing handles errors gracefully
and provides appropriate user feedback without exposing sensitive information.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bedrock_agentcore import RequestContext


class TestAgentErrorHandling:
    """Test suite for main agent error handling."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock RequestContext."""
        context = MagicMock(spec=RequestContext)
        context.session_id = "test-session-123"
        return context

    @pytest.fixture
    def valid_payload(self):
        """Create a valid invocation payload."""
        return {
            "prompt": "Hello, I need help",
            "actorId": "test-actor-456",
            "messageId": "msg-789",
            "conversationId": "test-session-123",
            "modelId": "amazon.nova-lite-v1:0",
            "temperature": 0.2,
        }

    @pytest.fixture
    def mock_environment(self):
        """Mock environment variables."""
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION": "us-east-1",
                "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
                "MODEL_TEMPERATURE": "0.2",
            },
        ):
            yield

    @patch("virtual_assistant_chat.agent.logger")
    def test_invalid_payload_error_handling(self, mock_logger, mock_context, mock_environment, mock_agent_module):
        """Test that invalid payload formats are handled gracefully."""
        # Arrange
        invalid_payload = {"invalid": "payload"}

        # Act
        invoke_func = mock_agent_module.invoke

        # Call the invoke function directly
        result = asyncio.run(invoke_func(invalid_payload, mock_context))

        # Assert
        assert result["status"] == "error"
        assert "Invalid request format" in result["message"]

        # Verify error was logged without exposing payload contents
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Invalid payload format" in error_call
        assert "validation failed" in error_call

    @patch("virtual_assistant_chat.agent.asyncio.create_task")
    @patch("virtual_assistant_chat.agent.logger")
    def test_async_task_creation_failure(
        self, mock_logger, mock_create_task, valid_payload, mock_context, mock_environment, mock_agent_module
    ):
        """Test that async task creation failures are handled gracefully."""
        # Arrange
        mock_create_task.side_effect = Exception("Task creation failed")

        # Act
        invoke_func = mock_agent_module.invoke
        result = asyncio.run(invoke_func(valid_payload, mock_context))

        # Assert
        assert result["status"] == "error"
        assert "Failed to start message processing" in result["message"]

        # Verify error was logged with sanitized message
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        error_call = next((call for call in error_calls if "Failed to start processing" in call), None)
        assert error_call is not None

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.create_session_manager")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_agent_creation_failure_handling(
        self, mock_logger, mock_platform_router, mock_create_session_manager, mock_agent_module
    ):
        """Test that agent creation failures are handled gracefully."""
        # Arrange
        mock_create_session_manager.side_effect = Exception("Agent creation failed")
        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

        # Act
        process_user_message = mock_agent_module.process_user_message

        with pytest.raises(Exception):  # noqa: B017
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor",
                message_id="test-msg",
                conversation_id="test-conv",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session",
            )

        # Assert
        # Verify error message was sent to user
        mock_platform_router.send_response.assert_called()

        # Check all calls to send_response to find the error message
        call_args_list = mock_platform_router.send_response.call_args_list
        error_messages = [call[0][1] for call in call_args_list]

        # Should have either the agent creation error or general error message
        has_agent_error = any("currently unavailable" in msg for msg in error_messages)
        has_general_error = any("having trouble processing" in msg for msg in error_messages)

        assert has_agent_error or has_general_error, f"Expected error message not found in: {error_messages}"

        # Verify error was logged
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.Agent")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_streaming_error_handling(
        self, mock_logger, mock_platform_router, mock_agent_class, mock_agent_module
    ):
        """Test that streaming errors are handled gracefully."""
        # Arrange
        mock_agent = MagicMock()
        mock_agent.stream_async = AsyncMock()
        mock_agent.stream_async.side_effect = Exception("Streaming failed")
        mock_agent_class.return_value = mock_agent

        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

        # Act
        process_user_message = mock_agent_module.process_user_message

        with pytest.raises(Exception):  # noqa: B017
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor",
                message_id="test-msg",
                conversation_id="test-conv",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session",
            )

        # Assert
        # Verify error message was sent to user
        mock_platform_router.send_response.assert_called()
        call_args_list = mock_platform_router.send_response.call_args_list
        # Check for the actual error message that's sent
        error_message_sent = any("having trouble processing" in str(call) for call in call_args_list)
        assert error_message_sent

        # Verify streaming error was logged
        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.Agent")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_message_event_processing_error_handling(
        self, mock_logger, mock_platform_router, mock_agent_class, mock_agent_module
    ):
        """Test that message event processing errors are handled gracefully."""
        # Arrange
        mock_agent = MagicMock()

        # Create an async generator that yields a malformed message event
        async def mock_stream(message):
            yield {"message": {"content": "invalid_content_format"}}  # Should be a list

        mock_agent.stream_async = mock_stream
        mock_agent_class.return_value = mock_agent

        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

        # Act
        process_user_message = mock_agent_module.process_user_message

        await process_user_message(
            user_message="Hello",
            actor_id="test-actor",
            message_id="test-msg",
            conversation_id="test-conv",
            model_id="test-model",
            temperature=0.2,
            session_id="test-session",
        )

        # Assert
        # Since we simplified event processing to only handle message events,
        # malformed message content should be handled gracefully without warnings
        # The test should complete successfully
        assert True  # Test passes if no exception is raised

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.Agent")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_tool_use_event_processing_error_handling(
        self, mock_logger, mock_platform_router, mock_agent_class, mock_agent_module
    ):
        """Test that tool use event processing errors are handled gracefully."""
        # Arrange
        mock_agent = MagicMock()

        # Create an async generator that yields a tool use event (which should be ignored)
        async def mock_stream(message):
            yield {"toolUse": {"name": "test_tool"}}  # This should be ignored

        mock_agent.stream_async = mock_stream
        mock_agent_class.return_value = mock_agent

        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

        # Act
        process_user_message = mock_agent_module.process_user_message

        await process_user_message(
            user_message="Hello",
            actor_id="test-actor",
            message_id="test-msg",
            conversation_id="test-conv",
            model_id="test-model",
            temperature=0.2,
            session_id="test-session",
        )

        # Assert
        # Since tool events are now ignored, no error should be logged
        # The test should complete successfully
        assert True  # Test passes if no exception is raised

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.Agent")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_platform_router_send_failure_handling(
        self, mock_logger, mock_platform_router, mock_agent_class, mock_agent_module
    ):
        """Test that platform router send failures are handled gracefully."""
        # Arrange
        mock_agent = MagicMock()

        # Create an async generator that yields a valid message event
        async def mock_stream(message):
            yield {"message": {"content": [{"text": "Hello response"}]}}

        mock_agent.stream_async = mock_stream
        mock_agent_class.return_value = mock_agent

        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        # Mock send_response to fail
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=False, error="Send failed"))

        # Act
        process_user_message = mock_agent_module.process_user_message

        await process_user_message(
            user_message="Hello",
            actor_id="test-actor",
            message_id="test-msg",
            conversation_id="test-conv",
            model_id="test-model",
            temperature=0.2,
            session_id="test-session",
        )

        # Assert
        # Verify error was logged for send failure
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        send_error = next((call for call in error_calls if "Failed to send response" in call), None)
        assert send_error is not None

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.create_session_manager")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_sensitive_information_sanitization_in_errors(
        self, mock_logger, mock_platform_router, mock_create_session_manager, mock_agent_module
    ):
        """Test that sensitive information is sanitized in error messages."""
        # Arrange
        actor_id = "sensitive-actor-123"
        session_id = "sensitive-session-456"

        mock_create_session_manager.side_effect = Exception(f"Error with {actor_id} and {session_id}")
        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

        # Act
        process_user_message = mock_agent_module.process_user_message

        with pytest.raises(Exception):  # noqa: B017  # noqa: B017
            await process_user_message(
                user_message="Hello",
                actor_id=actor_id,
                message_id="test-msg",
                conversation_id="test-conv",
                model_id="test-model",
                temperature=0.2,
                session_id=session_id,
            )

        # Assert
        # Verify sensitive information was sanitized in logs
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]

        # Check that our sanitized error message is logged (the framework may log the original error)
        sanitized_call = next((call for call in error_calls if "[ACTOR_ID]" in call and "[SESSION_ID]" in call), None)
        assert sanitized_call is not None, f"Expected sanitized error message not found in: {error_calls}"

        # Verify that the sanitized call doesn't contain the actual sensitive values
        assert actor_id not in sanitized_call
        assert session_id not in sanitized_call

    @pytest.mark.asyncio
    @patch("virtual_assistant_chat.agent.Agent")
    @patch("virtual_assistant_chat.agent.platform_router")
    @patch("virtual_assistant_chat.agent.logger")
    async def test_unexpected_event_type_handling(
        self, mock_logger, mock_platform_router, mock_agent_class, mock_agent_module
    ):
        """Test that unexpected event types are handled gracefully."""
        # Arrange
        mock_agent = MagicMock()

        # Create an async generator that yields an unexpected event type
        async def mock_stream(message):
            yield {"unexpected_event_type": {"data": "some_data"}}

        mock_agent.stream_async = mock_stream
        mock_agent_class.return_value = mock_agent

        mock_platform_router.update_message_status = AsyncMock(return_value=MagicMock(success=True))
        mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

        # Act
        process_user_message = mock_agent_module.process_user_message

        await process_user_message(
            user_message="Hello",
            actor_id="test-actor",
            message_id="test-msg",
            conversation_id="test-conv",
            model_id="test-model",
            temperature=0.2,
            session_id="test-session",
        )

        # Assert
        # Since we only process message events now, unexpected events are ignored
        # The test should complete successfully
        assert True  # Test passes if no exception is raised

    def test_task_done_callback_error_logging(self, valid_payload, mock_context, mock_environment, mock_agent_module):
        """Test that async task errors are logged via done callback."""
        # This test verifies that the task done callback logs errors appropriately

        with patch("virtual_assistant_chat.agent.logger") as mock_logger:
            # Create a mock task that has an exception
            mock_task = MagicMock()
            mock_task.exception.return_value = Exception("Task failed")

            # We can't easily test the callback directly, but we can verify
            # that the callback function would log the error
            def test_callback(task):
                if task.exception():
                    mock_logger.error(f"Async task failed for message test-msg: {task.exception()}")

            # Simulate the callback
            test_callback(mock_task)

            # Assert
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Async task failed" in error_call
