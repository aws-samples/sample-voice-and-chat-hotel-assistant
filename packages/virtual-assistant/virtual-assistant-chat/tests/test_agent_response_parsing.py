#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration tests for agent response parsing with XML tags.

Tests verify that the agent correctly parses <message> and <thinking> tags
from model responses and only sends message content to users.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAgentResponseParsing:
    """Test suite for agent response parsing with XML tags."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, mock_agent_module):
        """Reset global state before and after each test."""
        # Reset global agent state
        mock_agent_module.agent = None
        mock_agent_module.current_session_id = None
        mock_agent_module.current_actor_id = None

        yield

        # Teardown
        mock_agent_module.agent = None
        mock_agent_module.current_session_id = None
        mock_agent_module.current_actor_id = None

    @pytest.mark.asyncio
    async def test_agent_parses_message_tags_from_model_response(self, mock_agent_module):
        """Test that agent correctly parses message tags from model response."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch.object(mock_agent_module, "platform_router", mock_platform_router),
            patch.object(mock_agent_module, "create_session_manager") as mock_create_session_manager,
            patch.object(mock_agent_module, "get_bedrock_boto_session") as mock_get_bedrock_session,
            patch.object(mock_agent_module, "BedrockModel") as mock_bedrock_model,
            patch.object(mock_agent_module, "Agent") as mock_agent_class,
            patch.object(mock_agent_module, "config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent that produces response with tags
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {
                    "message": {
                        "content": [
                            {
                                "text": "<message>Hello user, I can help you with your booking.</message>"
                                "<thinking>The user wants to make a reservation. I should ask for details.</thinking>"
                            }
                        ]
                    }
                }

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Act
            await mock_agent_module.process_user_message(
                user_message="I want to make a reservation",
                actor_id="test-actor",
                message_ids=["msg-1"],
                conversation_id="conv-1",
                model_id="test-model",
                temperature=0.2,
                session_id="session-1",
            )

            # Assert
            # Verify only message content was sent (no thinking)
            mock_platform_router.send_response.assert_called_once()
            call_args = mock_platform_router.send_response.call_args
            assert call_args[0][0] == "conv-1"  # conversation_id
            assert call_args[0][1] == "Hello user, I can help you with your booking."
            assert "thinking" not in call_args[0][1].lower()
            assert "reservation" not in call_args[0][1]  # Thinking content not included

    @pytest.mark.asyncio
    async def test_agent_handles_plain_text_responses(self, mock_agent_module):
        """Test backward compatibility with plain text responses."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch.object(mock_agent_module, "platform_router", mock_platform_router),
            patch.object(mock_agent_module, "create_session_manager") as mock_create_session_manager,
            patch.object(mock_agent_module, "get_bedrock_boto_session") as mock_get_bedrock_session,
            patch.object(mock_agent_module, "BedrockModel") as mock_bedrock_model,
            patch.object(mock_agent_module, "Agent") as mock_agent_class,
            patch.object(mock_agent_module, "config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent that produces plain text response
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Plain text response without any tags"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Act
            await mock_agent_module.process_user_message(
                user_message="Test",
                actor_id="test-actor",
                message_ids=["msg-1"],
                conversation_id="conv-1",
                model_id="test-model",
                temperature=0.2,
                session_id="session-1",
            )

            # Assert
            # Verify plain text was sent as-is
            mock_platform_router.send_response.assert_called_once()
            call_args = mock_platform_router.send_response.call_args
            assert call_args[0][0] == "conv-1"  # conversation_id
            assert call_args[0][1] == "Plain text response without any tags"

    @pytest.mark.asyncio
    async def test_agent_doesnt_send_empty_responses_thinking_only(self, mock_agent_module):
        """Test agent doesn't send empty responses when only thinking tags present."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch.object(mock_agent_module, "platform_router", mock_platform_router),
            patch.object(mock_agent_module, "create_session_manager") as mock_create_session_manager,
            patch.object(mock_agent_module, "get_bedrock_boto_session") as mock_get_bedrock_session,
            patch.object(mock_agent_module, "BedrockModel") as mock_bedrock_model,
            patch.object(mock_agent_module, "Agent") as mock_agent_class,
            patch.object(mock_agent_module, "config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent that produces thinking-only response
            mock_agent = MagicMock()

            async def mock_stream_generator():
                # First event: thinking only (before tool call)
                yield {
                    "message": {
                        "content": [
                            {
                                "text": "<thinking>I need to check availability. "
                                "I'll call the check_availability tool.</thinking>"
                            }
                        ]
                    }
                }
                # Second event: tool use (should be ignored by agent)
                yield {"toolUse": {"name": "check_availability", "input": {"hotel_id": "123"}}}
                # Third event: actual response after tool
                yield {"message": {"content": [{"text": "<message>I found availability for you.</message>"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Act
            await mock_agent_module.process_user_message(
                user_message="Check availability",
                actor_id="test-actor",
                message_ids=["msg-1"],
                conversation_id="conv-1",
                model_id="test-model",
                temperature=0.2,
                session_id="session-1",
            )

            # Assert
            # Verify only the actual message was sent (not the thinking-only response)
            mock_platform_router.send_response.assert_called_once()
            call_args = mock_platform_router.send_response.call_args
            assert call_args[0][0] == "conv-1"  # conversation_id
            assert call_args[0][1] == "I found availability for you."
            assert "thinking" not in call_args[0][1].lower()
            assert "check_availability" not in call_args[0][1]

    @pytest.mark.asyncio
    async def test_agent_handles_multiple_message_blocks(self, mock_agent_module):
        """Test agent correctly concatenates multiple message blocks."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch.object(mock_agent_module, "platform_router", mock_platform_router),
            patch.object(mock_agent_module, "create_session_manager") as mock_create_session_manager,
            patch.object(mock_agent_module, "get_bedrock_boto_session") as mock_get_bedrock_session,
            patch.object(mock_agent_module, "BedrockModel") as mock_bedrock_model,
            patch.object(mock_agent_module, "Agent") as mock_agent_class,
            patch.object(mock_agent_module, "config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent that produces response with multiple message blocks
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {
                    "message": {
                        "content": [
                            {
                                "text": "<message>First part of response.</message>"
                                "<thinking>Some internal reasoning.</thinking>"
                                "<message>Second part of response.</message>"
                            }
                        ]
                    }
                }

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Act
            await mock_agent_module.process_user_message(
                user_message="Tell me about hotels",
                actor_id="test-actor",
                message_ids=["msg-1"],
                conversation_id="conv-1",
                model_id="test-model",
                temperature=0.2,
                session_id="session-1",
            )

            # Assert
            # Verify both message blocks were concatenated with double newlines
            mock_platform_router.send_response.assert_called_once()
            call_args = mock_platform_router.send_response.call_args
            assert call_args[0][0] == "conv-1"  # conversation_id
            assert call_args[0][1] == "First part of response.\n\nSecond part of response."
            assert "thinking" not in call_args[0][1].lower()

    @pytest.mark.asyncio
    async def test_agent_handles_malformed_tags_gracefully(self, mock_agent_module, caplog):
        """Test agent handles malformed tags without crashing."""
        # Arrange
        mock_platform_router = AsyncMock()
        mock_platform_router.send_response.return_value = MagicMock(success=True)
        mock_platform_router.update_message_status.return_value = None

        with (
            patch.object(mock_agent_module, "platform_router", mock_platform_router),
            patch.object(mock_agent_module, "create_session_manager") as mock_create_session_manager,
            patch.object(mock_agent_module, "get_bedrock_boto_session") as mock_get_bedrock_session,
            patch.object(mock_agent_module, "BedrockModel") as mock_bedrock_model,
            patch.object(mock_agent_module, "Agent") as mock_agent_class,
            patch.object(mock_agent_module, "config_manager") as mock_config_manager,
        ):
            # Mock the dependencies for agent creation
            mock_create_session_manager.return_value = MagicMock()
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent that produces response with unclosed tag
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {
                    "message": {
                        "content": [{"text": "<message>Unclosed tag content"}]  # Missing closing tag
                    }
                }

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Clear any existing log records
            caplog.clear()

            # Act
            with caplog.at_level(logging.WARNING):
                await mock_agent_module.process_user_message(
                    user_message="Test",
                    actor_id="test-actor",
                    message_ids=["msg-1"],
                    conversation_id="conv-1",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="session-1",
                )

            # Assert
            # Verify content was still extracted (graceful handling)
            mock_platform_router.send_response.assert_called_once()
            call_args = mock_platform_router.send_response.call_args
            assert call_args[0][0] == "conv-1"  # conversation_id
            assert call_args[0][1] == "Unclosed tag content"

            # Verify warning was logged
            warning_logs = [record for record in caplog.records if record.levelno >= logging.WARNING]
            unclosed_warnings = [log for log in warning_logs if "unclosed" in log.message.lower()]
            assert len(unclosed_warnings) > 0, "Expected warning about unclosed tag"
