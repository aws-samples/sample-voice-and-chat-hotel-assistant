#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestSessionActorValidation:
    """Test suite to verify session/actor validation logic."""

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
    async def test_agent_creation_sets_session_and_actor(self):
        """Test that creating a new agent sets the global session_id and actor_id."""
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
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function and module
            import virtual_assistant_chat.agent
            from virtual_assistant_chat.agent import process_user_message

            # Verify initial state
            assert virtual_assistant_chat.agent.current_session_id is None
            assert virtual_assistant_chat.agent.current_actor_id is None
            assert virtual_assistant_chat.agent.agent is None

            # Act
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert
            assert virtual_assistant_chat.agent.current_session_id == "test-session-789"
            assert virtual_assistant_chat.agent.current_actor_id == "test-actor-123"
            assert virtual_assistant_chat.agent.agent is not None

    @pytest.mark.asyncio
    async def test_agent_reuse_with_same_session_and_actor(self):
        """Test that agent is reused when session_id and actor_id remain the same."""
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
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - First call creates agent
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Verify agent was created
            assert mock_agent_class.call_count == 1
            first_agent_instance = mock_agent

            # Act - Second call with same session/actor should reuse agent
            await process_user_message(
                user_message="How are you?",
                actor_id="test-actor-123",
                message_id="test-msg-456",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert - Agent class should not be called again (reused existing)
            assert mock_agent_class.call_count == 1
            # Verify the same agent instance is used
            assert first_agent_instance.stream_async.call_count == 2

    @pytest.mark.asyncio
    async def test_session_id_change_raises_runtime_error(self):
        """Test that changing session_id during execution raises RuntimeError."""
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
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - First call creates agent
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Act & Assert - Second call with different session_id should raise RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                await process_user_message(
                    user_message="How are you?",
                    actor_id="test-actor-123",
                    message_id="test-msg-456",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="different-session-999",  # Different session_id
                )

            # Verify the error message contains expected information
            assert "Session ID changed within execution" in str(exc_info.value)
            assert "test-session-789" in str(exc_info.value)
            assert "different-session-999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_actor_id_change_raises_runtime_error(self):
        """Test that changing actor_id during execution raises RuntimeError."""
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
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - First call creates agent
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Act & Assert - Second call with different actor_id should raise RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                await process_user_message(
                    user_message="How are you?",
                    actor_id="different-actor-999",  # Different actor_id
                    message_id="test-msg-456",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="test-session-789",
                )

            # Verify the error message contains expected information
            assert "Actor ID changed within execution" in str(exc_info.value)
            assert "test-actor-123" in str(exc_info.value)
            assert "different-actor-999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_both_session_and_actor_change_raises_session_error_first(self):
        """Test that when both session_id and actor_id change, session error is raised first."""
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
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - First call creates agent
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Act & Assert - Second call with both different session_id and actor_id
            # Should raise session error first (since session check comes first in code)
            with pytest.raises(RuntimeError) as exc_info:
                await process_user_message(
                    user_message="How are you?",
                    actor_id="different-actor-999",  # Different actor_id
                    message_id="test-msg-456",
                    conversation_id="test-conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="different-session-999",  # Different session_id
                )

            # Verify the session error is raised first
            assert "Session ID changed within execution" in str(exc_info.value)
            assert "test-session-789" in str(exc_info.value)
            assert "different-session-999" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_global_variables_are_properly_tracked(self):
        """Test that global variables current_session_id and current_actor_id are properly tracked."""
        # Arrange
        import virtual_assistant_chat.agent

        # Verify initial state
        assert virtual_assistant_chat.agent.current_session_id is None
        assert virtual_assistant_chat.agent.current_actor_id is None
        assert virtual_assistant_chat.agent.agent is None

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
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - Process first message
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert - Global variables should be set
            assert virtual_assistant_chat.agent.current_session_id == "test-session-789"
            assert virtual_assistant_chat.agent.current_actor_id == "test-actor-123"
            assert virtual_assistant_chat.agent.agent is not None

            # Store reference to first agent
            first_agent = virtual_assistant_chat.agent.agent

            # Act - Process second message with same session/actor
            await process_user_message(
                user_message="How are you?",
                actor_id="test-actor-123",
                message_id="test-msg-456",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert - Global variables should remain the same
            assert virtual_assistant_chat.agent.current_session_id == "test-session-789"
            assert virtual_assistant_chat.agent.current_actor_id == "test-actor-123"
            assert virtual_assistant_chat.agent.agent is first_agent  # Same agent instance

    @pytest.mark.asyncio
    async def test_agent_creation_once_per_execution(self):
        """Test that agent is created only once per execution with proper session context."""
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
            mock_session_manager = MagicMock()
            mock_create_session_manager.return_value = mock_session_manager
            mock_get_bedrock_session.return_value = MagicMock()
            mock_bedrock_model.return_value = MagicMock()

            # Mock config_manager.load_config() to return empty dict (no MCP servers)
            mock_config_manager.load_config.return_value = {}

            # Create mock agent
            mock_agent = MagicMock()

            async def mock_stream_generator():
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = MagicMock(side_effect=lambda msg: mock_stream_generator())
            mock_agent_class.return_value = mock_agent

            # Import the function
            from virtual_assistant_chat.agent import process_user_message

            # Act - Process multiple messages in same execution
            await process_user_message(
                user_message="Hello",
                actor_id="test-actor-123",
                message_id="test-msg-123",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            await process_user_message(
                user_message="How are you?",
                actor_id="test-actor-123",
                message_id="test-msg-456",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            await process_user_message(
                user_message="What can you do?",
                actor_id="test-actor-123",
                message_id="test-msg-789",
                conversation_id="test-conv-456",
                model_id="test-model",
                temperature=0.2,
                session_id="test-session-789",
            )

            # Assert - Agent should be created only once
            assert mock_agent_class.call_count == 1

            # Assert - SessionManager should be created only once with correct parameters
            assert mock_create_session_manager.call_count == 1
            mock_create_session_manager.assert_called_with("test-session-789", "test-actor-123")

            # Assert - Agent should be called with the session manager
            mock_agent_class.assert_called_once()
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["session_manager"] is mock_session_manager

            # Assert - Same agent instance used for all calls
            assert mock_agent.stream_async.call_count == 3
