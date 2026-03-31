# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for VirtualAssistant agent class with multi-language support.

This module tests the VirtualAssistant class including the on_enter() hook
for native greeting delivery. The multi-language system prompt comes from
the MCP server and is tested there.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestVirtualAssistantClass:
    """Test VirtualAssistant agent class."""

    def test_virtual_assistant_initialization(self):
        """Test VirtualAssistant initialization with instructions."""
        from virtual_assistant_livekit.agent import VirtualAssistant

        instructions = "Test instructions for virtual assistant"

        with patch("virtual_assistant_livekit.agent.Agent.__init__") as mock_super_init:
            mock_super_init.return_value = None
            agent = VirtualAssistant(instructions=instructions)

            # Verify Agent.__init__ was called with instructions
            mock_super_init.assert_called_once_with(instructions=instructions)
            assert agent is not None

    def test_virtual_assistant_initialization_with_custom_greeting(self):
        """Test VirtualAssistant initialization with custom greeting."""
        from virtual_assistant_livekit.agent import VirtualAssistant

        instructions = "Test instructions"
        custom_greeting = "Hello! I'm your assistant."

        with patch("virtual_assistant_livekit.agent.Agent.__init__") as mock_super_init:
            mock_super_init.return_value = None
            agent = VirtualAssistant(instructions=instructions, greeting=custom_greeting)

            # Verify custom greeting is stored
            assert agent._greeting == custom_greeting

    @pytest.mark.asyncio
    async def test_on_enter_calls_generate_reply(self):
        """Test on_enter() calls generate_reply with greeting."""
        from virtual_assistant_livekit.agent import VirtualAssistant

        instructions = "Test instructions"

        # Mock session
        mock_session = AsyncMock()

        with patch("virtual_assistant_livekit.agent.Agent.__init__") as mock_super_init:
            mock_super_init.return_value = None
            agent = VirtualAssistant(instructions=instructions)

            # Patch the session property to return our mock
            with patch.object(VirtualAssistant, "session", new_callable=lambda: property(lambda self: mock_session)):
                # Call on_enter
                await agent.on_enter()

                # Verify generate_reply was called
                mock_session.generate_reply.assert_called_once()

                # Verify greeting includes default Spanish text
                call_args = mock_session.generate_reply.call_args
                greeting = call_args.kwargs.get("instructions", "")
                assert "¡Hola!" in greeting
                assert "asistente virtual" in greeting

    @pytest.mark.asyncio
    async def test_on_enter_includes_multi_language_instructions(self):
        """Test greeting includes multi-language instructions."""
        from virtual_assistant_livekit.agent import VirtualAssistant

        instructions = "Test instructions"

        # Mock session
        mock_session = AsyncMock()

        with patch("virtual_assistant_livekit.agent.Agent.__init__") as mock_super_init:
            mock_super_init.return_value = None
            agent = VirtualAssistant(instructions=instructions)

            # Patch the session property to return our mock
            with patch.object(VirtualAssistant, "session", new_callable=lambda: property(lambda self: mock_session)):
                # Call on_enter
                await agent.on_enter()

                # Verify greeting is in Spanish (default for hotel use case)
                call_args = mock_session.generate_reply.call_args
                greeting = call_args.kwargs.get("instructions", "")

                # Check for Spanish greeting components
                assert "¡Hola!" in greeting
                assert "asistente virtual" in greeting
                assert "¿En qué puedo asistirle hoy?" in greeting

    @pytest.mark.asyncio
    async def test_on_enter_uses_custom_greeting(self):
        """Test on_enter() uses custom greeting when provided."""
        from virtual_assistant_livekit.agent import VirtualAssistant

        instructions = "Test instructions"
        custom_greeting = "Hello! How can I help you today?"

        # Mock session
        mock_session = AsyncMock()

        with patch("virtual_assistant_livekit.agent.Agent.__init__") as mock_super_init:
            mock_super_init.return_value = None
            agent = VirtualAssistant(instructions=instructions, greeting=custom_greeting)

            # Patch the session property to return our mock
            with patch.object(VirtualAssistant, "session", new_callable=lambda: property(lambda self: mock_session)):
                # Call on_enter
                await agent.on_enter()

                # Verify generate_reply was called with custom greeting
                call_args = mock_session.generate_reply.call_args
                greeting = call_args.kwargs.get("instructions", "")
                assert greeting == custom_greeting

    @pytest.mark.asyncio
    async def test_on_enter_handles_errors_gracefully(self):
        """Test on_enter() handles errors without crashing."""
        from virtual_assistant_livekit.agent import VirtualAssistant

        instructions = "Test instructions"

        # Mock session that raises error
        mock_session = AsyncMock()
        mock_session.generate_reply.side_effect = Exception("Test error")

        with patch("virtual_assistant_livekit.agent.Agent.__init__") as mock_super_init:
            mock_super_init.return_value = None
            agent = VirtualAssistant(instructions=instructions)

            # Patch the session property to return our mock
            with patch.object(VirtualAssistant, "session", new_callable=lambda: property(lambda self: mock_session)):
                # Call on_enter - should not raise exception
                await agent.on_enter()

                # Verify generate_reply was attempted
                mock_session.generate_reply.assert_called_once()
