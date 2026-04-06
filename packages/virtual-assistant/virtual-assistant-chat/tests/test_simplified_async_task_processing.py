#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestSimplifiedAsyncTaskProcessing:
    """Test suite to verify simplified async task processing logic."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_and_teardown(self):
        """Reset global state before and after each test."""
        # Reset global agent state
        import virtual_assistant_chat.agent

        virtual_assistant_chat.agent.agent = None
        virtual_assistant_chat.agent.current_session_id = None
        virtual_assistant_chat.agent.current_actor_id = None

        yield

        # Teardown
        virtual_assistant_chat.agent.agent = None
        virtual_assistant_chat.agent.current_session_id = None
        virtual_assistant_chat.agent.current_actor_id = None

    @pytest.mark.asyncio
    async def test_simplified_async_task_creates_agent_once(self):
        """Test that simplified async task creates agent once per execution."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Hello from simplified async task"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert
            # Verify agent was created once
            mock_agent_class.assert_called_once()

            # Verify session manager was created with correct parameters
            mock_create_session_manager.assert_called_once_with("test-session-789", "test-actor")

            # Verify message was processed
            mock_platform_router.send_response.assert_called_once_with(
                "test-conv-456", "Hello from simplified async task"
            )

    @pytest.mark.asyncio
    async def test_simplified_async_task_validates_consistency(self):
        """Test that simplified async task validates session/actor consistency."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Response"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - First call creates agent
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Act - Second call with same session/actor should reuse agent
            await process_user_message(
                user_message="How are you?",
                actor_id="test-actor",
                message_id="test-msg-456",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert
            # Agent should be created only once
            assert mock_agent_class.call_count == 1
            # Agent should be used twice
            assert mock_agent.stream_async.call_count == 2

    @pytest.mark.asyncio
    async def test_simplified_async_task_processes_messages_directly(self):
        """Test that simplified async task processes messages directly within MCP context."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # Mix of message and tool events to verify direct processing
                yield {"toolUse": {"name": "get_hotels", "input": {}}}
                yield {"message": {"content": [{"text": "Processing your request..."}]}}
                yield {"toolResult": {"content": "Hotel data", "status": "success"}}
                yield {"message": {"content": [{"text": " Found 3 hotels for you."}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act
            await process_user_message(
                user_message="Find hotels",
                actor_id="test-actor",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert
            # Verify both message parts were sent (tool events ignored)
            assert mock_platform_router.send_response.call_count == 2
            calls = mock_platform_router.send_response.call_args_list

            assert calls[0][0][0] == "test-conv-456"
            assert calls[0][0][1] == "Processing your request..."

            assert calls[1][0][0] == "test-conv-456"
            assert calls[1][0][1] == " Found 3 hotels for you."

    @pytest.mark.asyncio
    async def test_simplified_async_task_handles_errors_gracefully(self):
        """Test that simplified async task handles errors gracefully."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent that raises an error
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Starting..."}]}}
                raise Exception("Simulated streaming error")

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await process_user_message(
                    user_message="Hello",
                    actor_id="test-actor",
                    message_id="test-msg-123",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="test-session-789",
                )

            # Verify the original error is re-raised
            assert "Simulated streaming error" in str(exc_info.value)

            # Verify error message was sent to user
            error_calls = [
                call for call in mock_platform_router.send_response.call_args_list if "trouble processing" in call[0][1]
            ]
            assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_simplified_async_task_removes_complex_logic(self):
        """Test that simplified async task removes complex agent reuse logic."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Simple response"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function and check the source code for simplification
            import inspect

            from virtual_assistant_chat.agent import process_user_message

            # Get the source code of the function
            source = inspect.getsource(process_user_message)

            # Assert that complex patterns are removed
            # No complex error handling with has_sent_message tracking
            assert "has_sent_message" not in source
            # No complex session context updates
            assert "update_session_context" not in source

            # Act - Verify the function still works
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert - Basic functionality still works
            mock_platform_router.send_response.assert_called_once_with("test-conv-456", "Simple response")

    @pytest.mark.asyncio
    async def test_simplified_async_task_ignores_tool_events_without_warnings(self, caplog):
        """Test that simplified async task ignores tool events without generating warnings."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch.dict(os.environ, {"MCP_CONFIG_PARAMETER": "/test/mcp/config"}),
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # Various tool events that should be ignored
                yield {"toolUse": {"name": "search", "input": {}}}
                yield {"toolResult": {"content": "result"}}
                yield {"current_tool_use": {"name": "search"}}
                yield {"completion": {"status": "complete"}}
                # Only this should be processed
                yield {"message": {"content": [{"text": "Final response"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Clear any existing log records
            caplog.clear()

            # Act
            with caplog.at_level(logging.WARNING):
                await process_user_message(
                    user_message="Search for something",
                    actor_id="test-actor",
                    message_id="test-msg-123",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="test-session-789",
                )

            # Assert
            # Only the message event should be processed
            mock_platform_router.send_response.assert_called_once_with("test-conv-456", "Final response")

            # No warnings should be logged for tool events (except expected MCP warning)
            warning_logs = [record for record in caplog.records if record.levelno >= logging.WARNING]
            tool_warnings = [
                log
                for log in warning_logs
                if "No MCP clients available" not in log.message
                and any(keyword in log.message.lower() for keyword in ["tool", "unexpected", "format"])
            ]
            assert len(tool_warnings) == 0, f"Found unexpected warnings: {[log.message for log in tool_warnings]}"

    @pytest.mark.asyncio
    async def test_simplified_async_task_opentelemetry_context(self):
        """Test that simplified async task sets up OpenTelemetry context correctly."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch("virtual_assistant_chat.agent.platform_router", mock_platform_router),
            patch("virtual_assistant_chat.agent.create_session_manager") as mock_create_session_manager,
            patch("virtual_assistant_chat.agent.get_bedrock_boto_session") as mock_get_bedrock_session,
            patch("virtual_assistant_chat.agent.BedrockModel") as mock_bedrock_model,
            patch("virtual_assistant_chat.agent.Agent") as mock_agent_class,
            patch("virtual_assistant_chat.agent.baggage") as mock_baggage,
            patch("virtual_assistant_chat.agent.otel_context") as mock_otel_context,
            patch("virtual_assistant_chat.agent.config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Mock OpenTelemetry
            mock_ctx = MagicMock()
            mock_baggage.set_baggage.return_value = mock_ctx

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Response with context"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert
            # Verify OpenTelemetry context was set up
            mock_baggage.set_baggage.assert_called_once_with("session.id", "test-session-789")
            mock_otel_context.attach.assert_called_once_with(mock_ctx)

            # Verify message was processed
            mock_platform_router.send_response.assert_called_once_with("test-conv-456", "Response with context")
