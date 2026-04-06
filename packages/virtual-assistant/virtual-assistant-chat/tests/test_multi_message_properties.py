#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Property-based tests for multi-message processing in chat agent.

Tests the following properties:
- Property 9: Read Status for All Messages
- Property 16: Single Conversation Turn
- Property 17: Message ID List Acceptance
- Property 18: Single Response Per Group
- Property 19: Error Propagation to All Messages
"""

import contextlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Property test configuration
PROPERTY_TEST_ITERATIONS = 100


# Helper to create async generator from list
async def async_generator_from_list(items):
    """Convert a list to an async generator."""
    for item in items:
        yield item


# Helper to create async generator that raises an error
async def async_generator_with_error(error):
    """Create an async generator that raises an error."""
    raise error
    yield  # Never reached but needed for generator syntax


# Strategies for generating test data
@st.composite
def message_id_list(draw, min_size=1, max_size=10):
    """Generate a list of message IDs."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    return [f"msg-{draw(st.uuids())}" for _ in range(size)]


def setup_mcp_mocks():
    """Set up MCP environment mocks for testing."""
    env_patch = patch.dict(
        os.environ,
        {
            "AGENTCORE_MEMORY_ID": "testMemory-1234567890",
            "AWS_REGION": "us-east-1",
            "MCP_CONFIG_PARAMETER": "/test/mcp/config",
        },
    )
    load_config_patch = patch("virtual_assistant_common.mcp.config_manager.MCPConfigManager.load_config")
    load_prompt_patch = patch("virtual_assistant_common.mcp.prompt_loader.PromptLoader.load_prompt")
    mcp_client_patch = patch("strands.tools.mcp.MCPClient")
    session_manager_patch = patch(
        "bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager"
    )
    # Mock asyncio.run to avoid event loop conflicts
    asyncio_run_patch = patch("asyncio.run")

    env_patch.start()
    mock_load_config = load_config_patch.start()
    mock_load_prompt = load_prompt_patch.start()
    mock_mcp_client_class = mcp_client_patch.start()
    mock_session_manager_class = session_manager_patch.start()
    mock_asyncio_run = asyncio_run_patch.start()

    # Configure mocks
    mock_load_config.return_value = {}
    mock_load_prompt.return_value = "Test system prompt for chat assistant"
    mock_asyncio_run.return_value = "Test system prompt for chat assistant"

    mock_mcp_client = MagicMock()
    mock_mcp_client.__aenter__ = AsyncMock(return_value=mock_mcp_client)
    mock_mcp_client.__aexit__ = AsyncMock(return_value=None)
    mock_mcp_client_class.return_value = mock_mcp_client

    mock_session_manager = MagicMock()
    mock_session_manager_class.return_value = mock_session_manager

    # Clear module cache
    if "virtual_assistant_chat.agent" in sys.modules:
        del sys.modules["virtual_assistant_chat.agent"]

    return [env_patch, load_config_patch, load_prompt_patch, mcp_client_patch, session_manager_patch, asyncio_run_patch]


def cleanup_mcp_mocks(patches):
    """Clean up MCP environment mocks."""
    for p in patches:
        p.stop()


# Property 9: Read Status for All Messages
@pytest.mark.asyncio
@settings(max_examples=PROPERTY_TEST_ITERATIONS, deadline=None)
@given(msg_ids=message_id_list(min_size=1, max_size=10))
async def test_property_9_read_status_for_all_messages(msg_ids):
    """
    Property 9: Read Status for All Messages
    For any message group processed by the Chat Agent, all message IDs should be
    marked with "read" status when processing begins.

    Validates: Requirements 3.2
    Feature: chat-message-batching, Property 9: Read Status for All Messages
    """
    patches = setup_mcp_mocks()

    try:
        # Import agent module with mocked MCP
        import virtual_assistant_chat.agent as agent_module

        # Mock platform_router
        with patch("virtual_assistant_chat.agent.platform_router") as mock_platform_router:
            mock_platform_router.update_message_status = AsyncMock()
            mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            # Mock Agent and its stream_async method
            with patch("virtual_assistant_chat.agent.Agent") as mock_agent_class:
                mock_agent_instance = MagicMock()
                # Return an async generator
                mock_agent_instance.stream_async = MagicMock(
                    return_value=async_generator_from_list([{"message": {"content": [{"text": "Test response"}]}}])
                )
                mock_agent_class.return_value = mock_agent_instance

                # Reset global agent state
                agent_module.agent = None
                agent_module.current_session_id = None
                agent_module.current_actor_id = None

                # Call process_user_message
                with contextlib.suppress(Exception):
                    await agent_module.process_user_message(
                        user_message="Test message",
                        actor_id="test-actor",
                        message_ids=msg_ids,
                        conversation_id="test-conv",
                        model_id="amazon.nova-lite-v1:0",
                        temperature=0.2,
                        session_id="test-session",
                    )

                # Verify all message IDs were marked as "read"
                read_calls = [
                    call for call in mock_platform_router.update_message_status.call_args_list if call[0][1] == "read"
                ]
                read_message_ids = {call[0][0] for call in read_calls}

                assert len(read_message_ids) == len(msg_ids)
                assert read_message_ids == set(msg_ids)
    finally:
        cleanup_mcp_mocks(patches)


# Property 16: Single Conversation Turn
@pytest.mark.asyncio
@settings(max_examples=PROPERTY_TEST_ITERATIONS, deadline=None)
@given(msg_ids=message_id_list(min_size=1, max_size=10), prompt=st.text(min_size=1, max_size=500))
async def test_property_16_single_conversation_turn(msg_ids, prompt):
    """
    Property 16: Single Conversation Turn
    For any combined prompt sent to the Chat Agent, it should be processed as a
    single conversation turn (one agent.stream_async call).

    Validates: Requirements 5.1
    Feature: chat-message-batching, Property 16: Single Conversation Turn
    """
    patches = setup_mcp_mocks()

    try:
        import virtual_assistant_chat.agent as agent_module

        with patch("virtual_assistant_chat.agent.platform_router") as mock_platform_router:
            mock_platform_router.update_message_status = AsyncMock()
            mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            with patch("virtual_assistant_chat.agent.Agent") as mock_agent_class:
                mock_agent_instance = MagicMock()
                mock_agent_instance.stream_async = MagicMock(
                    return_value=async_generator_from_list([{"message": {"content": [{"text": "Test response"}]}}])
                )
                mock_agent_class.return_value = mock_agent_instance

                agent_module.agent = None
                agent_module.current_session_id = None
                agent_module.current_actor_id = None

                with contextlib.suppress(Exception):
                    await agent_module.process_user_message(
                        user_message=prompt,
                        actor_id="test-actor",
                        message_ids=msg_ids,
                        conversation_id="test-conv",
                        model_id="amazon.nova-lite-v1:0",
                        temperature=0.2,
                        session_id="test-session",
                    )

                assert mock_agent_instance.stream_async.call_count == 1
                call_args = mock_agent_instance.stream_async.call_args
                assert call_args[0][0] == prompt
    finally:
        cleanup_mcp_mocks(patches)


# Property 17: Message ID List Acceptance
@pytest.mark.asyncio
@settings(max_examples=PROPERTY_TEST_ITERATIONS, deadline=None)
@given(msg_ids=message_id_list(min_size=1, max_size=20))
async def test_property_17_message_id_list_acceptance(msg_ids):
    """
    Property 17: Message ID List Acceptance
    For any list of message IDs (of any length > 0), the Chat Agent's
    process_user_message function should accept it without error.

    Validates: Requirements 5.2
    Feature: chat-message-batching, Property 17: Message ID List Acceptance
    """
    patches = setup_mcp_mocks()

    try:
        import virtual_assistant_chat.agent as agent_module

        with patch("virtual_assistant_chat.agent.platform_router") as mock_platform_router:
            mock_platform_router.update_message_status = AsyncMock()
            mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            with patch("virtual_assistant_chat.agent.Agent") as mock_agent_class:
                mock_agent_instance = MagicMock()
                mock_agent_instance.stream_async = MagicMock(
                    return_value=async_generator_from_list([{"message": {"content": [{"text": "Test response"}]}}])
                )
                mock_agent_class.return_value = mock_agent_instance

                agent_module.agent = None
                agent_module.current_session_id = None
                agent_module.current_actor_id = None

                exception_raised = False
                try:
                    await agent_module.process_user_message(
                        user_message="Test message",
                        actor_id="test-actor",
                        message_ids=msg_ids,
                        conversation_id="test-conv",
                        model_id="amazon.nova-lite-v1:0",
                        temperature=0.2,
                        session_id="test-session",
                    )
                except TypeError as e:
                    if "message_ids" in str(e):
                        exception_raised = True
                    else:
                        raise

                assert not exception_raised
    finally:
        cleanup_mcp_mocks(patches)


# Property 18: Single Response Per Group
@pytest.mark.asyncio
@settings(max_examples=PROPERTY_TEST_ITERATIONS, deadline=None)
@given(msg_ids=message_id_list(min_size=1, max_size=10))
async def test_property_18_single_response_per_group(msg_ids):
    """
    Property 18: Single Response Per Group
    For any message group processed by the Chat Agent, exactly one response should
    be sent via platform_router.send_response.

    Validates: Requirements 5.3
    Feature: chat-message-batching, Property 18: Single Response Per Group
    """
    patches = setup_mcp_mocks()

    try:
        import virtual_assistant_chat.agent as agent_module

        with patch("virtual_assistant_chat.agent.platform_router") as mock_platform_router:
            mock_platform_router.update_message_status = AsyncMock()
            mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            with patch("virtual_assistant_chat.agent.Agent") as mock_agent_class:
                mock_agent_instance = MagicMock()
                mock_agent_instance.stream_async = MagicMock(
                    return_value=async_generator_from_list([{"message": {"content": [{"text": "Test response"}]}}])
                )
                mock_agent_class.return_value = mock_agent_instance

                agent_module.agent = None
                agent_module.current_session_id = None
                agent_module.current_actor_id = None

                with contextlib.suppress(Exception):
                    await agent_module.process_user_message(
                        user_message="Test message",
                        actor_id="test-actor",
                        message_ids=msg_ids,
                        conversation_id="test-conv",
                        model_id="amazon.nova-lite-v1:0",
                        temperature=0.2,
                        session_id="test-session",
                    )

                assert mock_platform_router.send_response.call_count == 1
    finally:
        cleanup_mcp_mocks(patches)


# Property 19: Error Propagation to All Messages
@pytest.mark.asyncio
@settings(max_examples=PROPERTY_TEST_ITERATIONS, deadline=None)
@given(msg_ids=message_id_list(min_size=1, max_size=10))
async def test_property_19_error_propagation_to_all_messages(msg_ids):
    """
    Property 19: Error Propagation to All Messages
    For any error encountered by the Chat Agent during processing, all message IDs
    in the group should be marked as "failed".

    Validates: Requirements 5.4
    Feature: chat-message-batching, Property 19: Error Propagation to All Messages
    """
    patches = setup_mcp_mocks()

    try:
        import virtual_assistant_chat.agent as agent_module

        with patch("virtual_assistant_chat.agent.platform_router") as mock_platform_router:
            mock_platform_router.update_message_status = AsyncMock()
            mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            with patch("virtual_assistant_chat.agent.Agent") as mock_agent_class:
                mock_agent_instance = MagicMock()
                # Return an async generator that raises an error
                mock_agent_instance.stream_async = MagicMock(
                    return_value=async_generator_with_error(RuntimeError("Test error"))
                )
                mock_agent_class.return_value = mock_agent_instance

                agent_module.agent = None
                agent_module.current_session_id = None
                agent_module.current_actor_id = None

                with pytest.raises(RuntimeError):
                    await agent_module.process_user_message(
                        user_message="Test message",
                        actor_id="test-actor",
                        message_ids=msg_ids,
                        conversation_id="test-conv",
                        model_id="amazon.nova-lite-v1:0",
                        temperature=0.2,
                        session_id="test-session",
                    )

                failed_calls = [
                    call for call in mock_platform_router.update_message_status.call_args_list if call[0][1] == "failed"
                ]
                failed_message_ids = {call[0][0] for call in failed_calls}

                assert len(failed_message_ids) == len(msg_ids)
                assert failed_message_ids == set(msg_ids)
    finally:
        cleanup_mcp_mocks(patches)
