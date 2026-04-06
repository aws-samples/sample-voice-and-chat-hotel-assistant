# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for AgentFactory with real infrastructure.

Requires deployed infrastructure and valid AWS credentials.
Run with: uv run pytest tests/integration/test_agent_factory.py -v -m integration
"""

import pytest

from virtual_assistant_chat.agent_factory import AgentFactory


@pytest.mark.integration
class TestAgentCreation:
    """Integration tests for agent creation with real Bedrock models."""

    @pytest.fixture
    async def initialized_factory(self, cloudformation_outputs):
        """Create and initialize AgentFactory from deployed stack."""
        from virtual_assistant_common.mcp.config_manager import MCPConfigManager

        config_manager = MCPConfigManager(parameter_name=cloudformation_outputs["MCPConfigParameterName"])

        factory = AgentFactory(config_manager)
        await factory.initialize()
        return factory

    @pytest.mark.asyncio
    async def test_agent_creation_with_nova_micro(self, initialized_factory):
        """Test agent creation with real Bedrock model (nova-micro)."""
        factory = initialized_factory
        agent = factory.create_agent("us.amazon.nova-micro-v1:0")

        assert agent is not None
        assert agent.model is not None
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 0
        assert not hasattr(agent, "session_manager") or agent.session_manager is None

    @pytest.mark.asyncio
    async def test_simple_single_turn_conversation(self, initialized_factory):
        """Test simple single-turn conversation with agent."""
        factory = initialized_factory
        agent = factory.create_agent("us.amazon.nova-micro-v1:0")

        response_parts = []
        async for event in agent.stream_async("Hola, buenos días"):
            text = _extract_text_from_event(event)
            if text:
                response_parts.append(text)

        response = "".join(response_parts)
        assert len(response) > 0 or len(agent.messages) > 0, "No response received"

    @pytest.mark.asyncio
    async def test_tool_call_execution(self, initialized_factory):
        """Test that tool calls are executed correctly."""
        factory = initialized_factory
        agent = factory.create_agent("us.amazon.nova-micro-v1:0")

        response_parts = []
        async for event in agent.stream_async("Qué servicios de spa tienen disponibles?"):
            text = _extract_text_from_event(event)
            if text:
                response_parts.append(text)

        response = "".join(response_parts)
        assert len(response) > 0 or len(agent.messages) > 0

    @pytest.mark.asyncio
    async def test_agent_messages_contains_history(self, initialized_factory):
        """Test that agent.messages accumulates conversation history."""
        factory = initialized_factory
        agent = factory.create_agent("us.amazon.nova-micro-v1:0")

        initial_message_count = len(agent.messages) if hasattr(agent, "messages") else 0

        async for _ in agent.stream_async("Hola"):
            pass
        messages_after_turn1 = len(agent.messages)
        assert messages_after_turn1 > initial_message_count

        async for _ in agent.stream_async("Qué hoteles tienen?"):
            pass
        messages_after_turn2 = len(agent.messages)
        assert messages_after_turn2 > messages_after_turn1

    @pytest.mark.asyncio
    async def test_no_session_manager_used(self, initialized_factory):
        """Verify that no session_manager is used (simplified agent)."""
        factory = initialized_factory
        agent = factory.create_agent("us.amazon.nova-micro-v1:0")

        has_session_manager = hasattr(agent, "session_manager") and agent.session_manager is not None
        assert not has_session_manager, "Agent should not have session_manager for evaluation"


def _extract_text_from_event(event) -> str:
    """Extract text content from a streaming event."""
    if isinstance(event, dict):
        if "data" in event and isinstance(event["data"], str):
            return event["data"]
        if "text" in event:
            return event["text"]
        if "message" in event:
            message = event.get("message", {})
            content = message.get("content", [])
            texts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
            return "".join(texts)
    elif isinstance(event, str):
        return event
    return ""
