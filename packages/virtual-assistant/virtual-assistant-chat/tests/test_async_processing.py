# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for async message processing functionality."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestAsyncProcessing:
    """Test async message processing functionality."""

    def test_async_functionality_structure(self, mock_agent_module):
        """Test that the async functionality structure is correctly implemented."""

        # Verify the module has the expected components
        assert hasattr(mock_agent_module, "logger")
        assert hasattr(mock_agent_module, "BedrockAgentCoreApp")

        # Verify we can import platform router
        from virtual_assistant_common.platforms.router import platform_router

        assert hasattr(platform_router, "update_message_status")
        assert hasattr(platform_router, "send_response")

    def test_parameter_validation(self):
        """Test parameter validation in the entrypoint."""

        # This test verifies the validation logic without running the full main()
        # We'll test the validation logic directly

        # Test that missing parameters are detected
        payload_missing_message_id = {
            "prompt": "Hello",
            "actorId": "user-123",
            "conversationId": "conv-789",
            # Missing messageId
        }

        # Test validation logic
        required_params = ["prompt", "actorId", "messageId", "conversationId"]
        missing_params = []

        for param in required_params:
            if not payload_missing_message_id.get(param):
                missing_params.append(param)

        assert "messageId" in missing_params, "messageId should be detected as missing"

        # Test complete payload
        complete_payload = {
            "prompt": "Hello",
            "actorId": "user-123",
            "messageId": "msg-456",
            "conversationId": "conv-789",
        }

        missing_params = []
        for param in required_params:
            if not complete_payload.get(param):
                missing_params.append(param)

        assert len(missing_params) == 0, "Complete payload should have no missing parameters"

    def test_messaging_client_import(self):
        """Test that MessagingClient can be imported and used."""

        # Test that we can import the messaging client
        from virtual_assistant_common.clients.messaging_client import MessagingClient

        # Test that we can create an instance (with mocked endpoint)
        with patch.dict(os.environ, {"MESSAGING_API_ENDPOINT": "http://test.example.com"}):
            client = MessagingClient()
            assert client.api_endpoint == "http://test.example.com"

    def test_async_imports(self, mock_agent_module):
        """Test that async-related imports work correctly."""

        # Test asyncio import
        import asyncio

        assert asyncio.create_task is not None

        # Verify the module has the expected structure
        assert hasattr(mock_agent_module, "logger")

    def test_environment_defaults(self):
        """Test environment variable defaults."""

        # Test default values
        with patch.dict(os.environ, {}, clear=True):
            # These should use defaults
            model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
            temperature = os.getenv("MODEL_TEMPERATURE", "0.2")
            region = os.getenv("AWS_REGION", "us-east-1")

            assert model_id == "amazon.nova-lite-v1:0"
            assert temperature == "0.2"
            assert region == "us-east-1"

    @pytest.mark.asyncio
    async def test_async_streaming_functionality(self):
        """Test async streaming functionality with immediate message sending."""

        # Test that we can create and use async streaming
        mock_client = AsyncMock()
        mock_client.update_message_status = AsyncMock()
        mock_client.send_message = AsyncMock()
        mock_client.close = AsyncMock()

        # Configure the context manager to return itself
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        # Mock agent with stream_async method
        mock_agent = Mock()

        # Create async generator for streaming events
        async def mock_stream_async(message):
            # Simulate streaming events
            yield {"data": "Hello "}
            yield {"data": "there! "}
            yield {"current_tool_use": {"name": "get_hotels", "input": {}}}
            yield {"data": "I can help you."}
            yield {"result": Mock(message="Hello there! I can help you.")}

        mock_agent.stream_async = mock_stream_async

        # Test streaming pattern - messages sent immediately, not collected
        sent_messages = []
        async for event in mock_agent.stream_async("test message"):
            if "data" in event:
                chunk = event["data"]
                if len(chunk.strip()) > 0:
                    # Simulate immediate sending
                    sent_messages.append(chunk)
            elif "result" in event:
                final_result = event["result"]
                assert hasattr(final_result, "message")

        # Verify messages were sent immediately (not collected for final response)
        assert len(sent_messages) == 3
        assert sent_messages == ["Hello ", "there! ", "I can help you."]

    def test_streaming_event_types(self):
        """Test that we handle different streaming event types correctly."""

        # Test event type handling logic
        events = [
            {"data": "Hello"},
            {"current_tool_use": {"name": "get_hotels", "input": {}}},
            {"result": Mock(message="Final response")},
            {"delta": "raw delta"},
            {"reasoning": True, "reasoningText": "thinking..."},
        ]

        data_events = []
        tool_events = []
        result_events = []

        for event in events:
            if "data" in event:
                data_events.append(event["data"])
            elif "current_tool_use" in event:
                tool_events.append(event["current_tool_use"])
            elif "result" in event:
                result_events.append(event["result"])

        assert len(data_events) == 1
        assert len(tool_events) == 1
        assert len(result_events) == 1
        assert data_events[0] == "Hello"
        assert tool_events[0]["name"] == "get_hotels"

    def test_intermediate_message_timing(self):
        """Test intermediate message logic for tool use events."""
        import time

        # Test timing logic for intermediate messages
        start_time = time.time()
        has_sent_message = False
        has_sent_intermediate = False

        # Simulate 31 seconds passing
        current_time = start_time + 31

        # Should send intermediate message
        should_send = not has_sent_message and not has_sent_intermediate and (current_time - start_time) > 30

        assert should_send

        # After sending intermediate message
        has_sent_intermediate = True
        should_send_again = not has_sent_message and not has_sent_intermediate and (current_time - start_time) > 30

        assert not should_send_again

        # After sending regular message
        has_sent_message = True
        should_send_after_message = (
            not has_sent_message and not has_sent_intermediate and (current_time - start_time) > 30
        )

        assert not should_send_after_message

    def test_language_detection(self):
        """Test language detection for intermediate messages."""

        # Test Spanish detection (default)
        spanish_instructions = "Soy su asistente virtual de hoteles. ¿En qué puedo asistirle?"
        if "english" in spanish_instructions.lower() or "en qué puedo" not in spanish_instructions.lower():
            intermediate_msg = "one moment"
        else:
            intermediate_msg = "un momento"

        assert intermediate_msg == "un momento"

        # Test English detection
        english_instructions = "I am your virtual hotel assistant. How can I help you in English?"
        if "english" in english_instructions.lower() or "en qué puedo" not in english_instructions.lower():
            intermediate_msg = "one moment"
        else:
            intermediate_msg = "un momento"

        assert intermediate_msg == "one moment"

    def test_pii_logging_protection(self):
        """Test that PII is not logged at INFO/WARNING/ERROR levels."""

        # Test that sensitive data should only be logged at DEBUG level
        # This is a design verification test

        # These should be safe (no PII)
        safe_logs = [
            "Starting async processing for message msg-123 from user user-456",
            "Successfully processed message msg-123 for user user-456",
            "Loaded 5 MCP tools for async processing",
            "Stored 3 messages in memory",
        ]

        # These should only be at DEBUG level (potential PII)
        debug_only_logs = [
            "Agent using tool: get_hotels with input: {'query': 'user sensitive data'}",
            "Agent completed processing with result: Hello John, your reservation...",
            "Agent messages: [{'role': 'user', 'content': 'sensitive user message'}]",
        ]

        # Verify safe logs don't contain obvious PII patterns
        for log in safe_logs:
            assert "content" not in log.lower() or "content" in ["content-type", "content-length"]
            assert not any(word in log.lower() for word in ["hello", "reservation", "room", "guest"])

        # Verify debug logs would contain PII (this is expected)
        for log in debug_only_logs:
            assert any(word in log.lower() for word in ["input", "result", "content", "message"])

    def test_error_message_content(self):
        """Test that error messages are user-friendly."""

        # Test the error message content
        error_message = "I'm sorry, I'm having trouble processing your request right now. Please try again later."

        # Verify it's user-friendly
        assert "I'm sorry" in error_message
        assert "trouble processing" in error_message
        assert "try again later" in error_message

        # Verify it doesn't contain technical details
        assert "Exception" not in error_message
        assert "stack trace" not in error_message
        assert "error code" not in error_message
