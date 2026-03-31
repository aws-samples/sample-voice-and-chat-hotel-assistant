#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestEventStreamProcessing:
    """Test suite to verify simplified event stream processing that only handles message events."""

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
    async def test_message_events_are_processed(self):
        """Test that message events are properly processed and sent to platform router."""
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

            # Create mock agent that produces message events
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Hello, I can help you with hotel bookings."}]}}
                yield {"message": {"content": [{"text": " What would you like to know?"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import and call the function
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
            # Verify message status was updated
            mock_platform_router.update_message_status.assert_called_once_with("test-msg-123", "read")

            # Verify both message parts were sent
            assert mock_platform_router.send_response.call_count == 2
            calls = mock_platform_router.send_response.call_args_list

            # Check first message
            assert calls[0][0][0] == "test-conv-456"  # conversation_id
            assert calls[0][0][1] == "Hello, I can help you with hotel bookings."

            # Check second message
            assert calls[1][0][0] == "test-conv-456"  # conversation_id
            assert calls[1][0][1] == " What would you like to know?"

    @pytest.mark.asyncio
    async def test_tool_events_are_ignored_without_warnings(self, caplog):
        """Test that tool events (toolUse, toolResult) are ignored and don't generate warnings."""
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

            # Create mock agent that produces tool events and message events
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # Tool use event - should be ignored
                yield {"toolUse": {"name": "get_hotels", "input": {"location": "Miami"}}}
                # Tool result event - should be ignored
                yield {"toolResult": {"content": "Found 5 hotels in Miami"}}
                # Current tool use event - should be ignored
                yield {"current_tool_use": {"name": "get_hotels", "input": {"location": "Miami"}}}
                # Message event - should be processed
                yield {"message": {"content": [{"text": "I found 5 hotels in Miami for you."}]}}
                # Completion event - should be ignored
                yield {"completion": {"status": "complete"}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import and call the function
            from virtual_assistant_chat.agent import process_user_message

            # Clear any existing log records
            caplog.clear()

            # Act
            with caplog.at_level(logging.WARNING):
                await process_user_message(
                    user_message="Find hotels in Miami",
                    actor_id="test-actor",
                    message_id="test-msg-123",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="test-session-789",
                )

            # Assert
            # Verify only the message event was processed
            mock_platform_router.send_response.assert_called_once_with(
                "test-conv-456", "I found 5 hotels in Miami for you."
            )

            # Verify no warnings were logged for tool events
            warning_logs = [record for record in caplog.records if record.levelno >= logging.WARNING]
            tool_warnings = [
                log
                for log in warning_logs
                if any(
                    keyword in log.message.lower() for keyword in ["unexpected content format", "tooluse", "toolresult"]
                )
                and "no mcp clients available" not in log.message.lower()  # Exclude expected MCP warning
                and "no mcp clients available" not in log.message.lower()  # Exclude expected MCP warning
            ]
            assert len(tool_warnings) == 0, (
                f"Found unexpected tool-related warnings: {[log.message for log in tool_warnings]}"
            )

    @pytest.mark.asyncio
    async def test_empty_message_events_are_handled(self):
        """Test that empty message events are handled gracefully without sending empty responses."""
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

            # Create mock agent that produces empty message events
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # Empty message event
                yield {"message": {"content": [{"text": ""}]}}
                # Whitespace-only message event
                yield {"message": {"content": [{"text": "   "}]}}
                # Valid message event
                yield {"message": {"content": [{"text": "This is a valid response."}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import and call the function
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
            # Verify only the non-empty message was sent
            mock_platform_router.send_response.assert_called_once_with("test-conv-456", "This is a valid response.")

    @pytest.mark.asyncio
    async def test_mixed_event_stream_processing(self, caplog):
        """Test processing a realistic mixed stream of events with tools and messages."""
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

            # Create mock agent that produces a realistic event stream
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # Agent starts thinking
                yield {"current_tool_use": {"name": "search_hotels", "input": {"city": "New York"}}}
                # Tool execution
                yield {"toolUse": {"name": "search_hotels", "input": {"city": "New York"}}}
                yield {"toolResult": {"content": "Found 10 hotels", "status": "success"}}
                # Agent responds with first part
                yield {"message": {"content": [{"text": "I found 10 great hotels in New York."}]}}
                # Agent uses another tool
                yield {"current_tool_use": {"name": "get_availability", "input": {"hotel_id": "123"}}}
                yield {"toolUse": {"name": "get_availability", "input": {"hotel_id": "123"}}}
                yield {"toolResult": {"content": "Available rooms: 5", "status": "success"}}
                # Agent continues response
                yield {"message": {"content": [{"text": " The Plaza Hotel has 5 rooms available."}]}}
                # Completion
                yield {"completion": {"status": "complete"}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())

            # Import and call the function
            from virtual_assistant_chat.agent import process_user_message

            # Clear any existing log records
            caplog.clear()

            # Act
            with caplog.at_level(logging.WARNING):
                await process_user_message(
                    user_message="Find hotels in New York",
                    actor_id="test-actor",
                    message_id="test-msg-123",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="test-session-789",
                )

            # Assert
            # Verify both message parts were sent
            assert mock_platform_router.send_response.call_count == 2
            calls = mock_platform_router.send_response.call_args_list

            assert calls[0][0][0] == "test-conv-456"  # conversation_id
            assert calls[0][0][1] == "I found 10 great hotels in New York."
            assert calls[1][0][0] == "test-conv-456"  # conversation_id
            assert calls[1][0][1] == " The Plaza Hotel has 5 rooms available."

            # Verify no warnings were logged for any events (except expected MCP warning)
            warning_logs = [record for record in caplog.records if record.levelno >= logging.WARNING]
            unexpected_warnings = [log for log in warning_logs if "No MCP clients available" not in log.message]
            assert len(unexpected_warnings) == 0, (
                f"Found unexpected warnings: {[log.message for log in unexpected_warnings]}"
            )

    @pytest.mark.asyncio
    async def test_malformed_message_events_are_handled(self, caplog):
        """Test that malformed message events are handled gracefully."""
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

            # Create mock agent that produces malformed message events
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # Message with missing content
                yield {"message": {}}
                # Message with non-dict content
                yield {"message": {"content": ["not a dict"]}}
                # Message with dict content but no text
                yield {"message": {"content": [{"type": "image"}]}}
                # Valid message
                yield {"message": {"content": [{"text": "This works fine."}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())

            # Import and call the function
            from virtual_assistant_chat.agent import process_user_message

            # Clear any existing log records
            caplog.clear()

            # Act
            with caplog.at_level(logging.DEBUG):
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
            # Verify only the valid message was sent
            mock_platform_router.send_response.assert_called_once_with("test-conv-456", "This works fine.")

            # Verify no warnings were logged (malformed content is silently ignored)
            warning_logs = [record for record in caplog.records if record.levelno >= logging.WARNING]
            content_warnings = [log for log in warning_logs if "unexpected content format" in log.message.lower()]
            assert len(content_warnings) == 0, (
                f"Found unexpected content format warnings: {[log.message for log in content_warnings]}"
            )
