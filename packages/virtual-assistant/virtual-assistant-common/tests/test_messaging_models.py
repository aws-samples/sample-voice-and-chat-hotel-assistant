# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for messaging models."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from virtual_assistant_common.models.messaging import (
    AgentInvocationPayload,
    MessageEvent,
    MessageGroup,
    MessageResponse,
    MessageStatus,
    PlatformMessage,
    SendMessageRequest,
    StatusUpdateRequest,
)


class TestMessageStatus:
    """Test MessageStatus enum."""

    def test_message_status_values(self):
        """Test that all expected status values are available."""
        assert MessageStatus.SENT == "sent"
        assert MessageStatus.DELIVERED == "delivered"
        assert MessageStatus.READ == "read"
        assert MessageStatus.FAILED == "failed"
        assert MessageStatus.WARNING == "warning"
        assert MessageStatus.DELETED == "deleted"


class TestMessageEvent:
    """Test MessageEvent model."""

    def test_message_event_creation(self):
        """Test creating a valid MessageEvent."""
        event = MessageEvent(
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
            sender_id="user-456",
            recipient_id="hotel-assistant",
            content="Hello, I need help with my reservation",
            timestamp="2024-01-01T12:00:00Z",
        )

        assert event.message_id == "msg-123"
        assert event.conversation_id == "user-456#hotel-assistant"
        assert event.sender_id == "user-456"
        assert event.recipient_id == "hotel-assistant"
        assert event.content == "Hello, I need help with my reservation"
        assert event.timestamp == "2024-01-01T12:00:00Z"
        assert event.platform == "web"  # default
        assert event.platform_metadata is None  # default

    def test_message_event_with_platform_metadata(self):
        """Test MessageEvent with platform-specific metadata."""
        metadata = {"phone_number": "+1234567890", "channel": "whatsapp"}
        event = MessageEvent(
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
            sender_id="user-456",
            recipient_id="hotel-assistant",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            platform="twilio",
            platform_metadata=metadata,
        )

        assert event.platform == "twilio"
        assert event.platform_metadata == metadata

    def test_message_event_with_model_params(self):
        """Test MessageEvent with model parameters."""
        event = MessageEvent(
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
            sender_id="user-456",
            recipient_id="hotel-assistant",
            content="Hello",
            timestamp="2024-01-01T12:00:00Z",
            model_id="amazon.nova-lite-v1:0",
            temperature=0.7,
        )

        assert event.model_id == "amazon.nova-lite-v1:0"
        assert event.temperature == 0.7

    def test_message_event_validation(self):
        """Test MessageEvent validation."""
        # Test missing required field
        with pytest.raises(ValidationError):
            MessageEvent(
                # message_id missing - should fail
                conversation_id="user-456#hotel-assistant",
                sender_id="user-456",
                recipient_id="hotel-assistant",
                content="Hello",
                timestamp="2024-01-01T12:00:00Z",
            )


class TestAgentInvocationPayload:
    """Test AgentInvocationPayload model."""

    def test_agent_invocation_payload_creation(self):
        """Test creating a valid AgentInvocationPayload."""
        payload = AgentInvocationPayload(
            prompt="Help me with my reservation",
            actor_id="user-456",
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
        )

        assert payload.prompt == "Help me with my reservation"
        assert payload.actor_id == "user-456"
        assert payload.message_id == "msg-123"
        assert payload.conversation_id == "user-456#hotel-assistant"
        assert payload.model_id is None  # default
        assert payload.temperature is None  # default

    def test_agent_invocation_payload_with_overrides(self):
        """Test AgentInvocationPayload with model overrides."""
        payload = AgentInvocationPayload(
            prompt="Help me with my reservation",
            actor_id="user-456",
            message_id="msg-123",
            conversation_id="user-456#hotel-assistant",
            model_id="claude-3-sonnet",
            temperature=0.7,
        )

        assert payload.model_id == "claude-3-sonnet"
        assert payload.temperature == 0.7


class TestPlatformMessage:
    """Test PlatformMessage model."""

    def test_platform_message_creation(self):
        """Test creating a valid PlatformMessage."""
        message = PlatformMessage(
            content="Hello from web",
            sender_id="user-456",
            recipient_id="hotel-assistant",
            platform="web",
        )

        assert message.content == "Hello from web"
        assert message.sender_id == "user-456"
        assert message.recipient_id == "hotel-assistant"
        assert message.platform == "web"
        assert message.platform_specific_data is None  # default

    def test_platform_message_with_specific_data(self):
        """Test PlatformMessage with platform-specific data."""
        specific_data = {"webhook_id": "wh_123", "signature": "sig_456"}
        message = PlatformMessage(
            content="Hello from Twilio",
            sender_id="+1234567890",
            recipient_id="hotel-assistant",
            platform="twilio",
            platform_specific_data=specific_data,
        )

        assert message.platform == "twilio"
        assert message.platform_specific_data == specific_data


class TestMessageResponse:
    """Test MessageResponse model."""

    def test_message_response_success(self):
        """Test creating a successful MessageResponse."""
        response = MessageResponse(
            success=True,
            message_id="msg-123",
            data={"status": "sent", "timestamp": "2024-01-01T12:00:00Z"},
        )

        assert response.success is True
        assert response.message_id == "msg-123"
        assert response.error is None  # default
        assert response.data["status"] == "sent"

    def test_message_response_error(self):
        """Test creating an error MessageResponse."""
        response = MessageResponse(
            success=False,
            error="Failed to send message: API timeout",
        )

        assert response.success is False
        assert response.error == "Failed to send message: API timeout"
        assert response.message_id is None  # default
        assert response.data is None  # default


class TestStatusUpdateRequest:
    """Test StatusUpdateRequest model."""

    def test_status_update_request_creation(self):
        """Test creating a valid StatusUpdateRequest."""
        request = StatusUpdateRequest(
            message_id="msg-123",
            status=MessageStatus.READ,
        )

        assert request.message_id == "msg-123"
        assert request.status == MessageStatus.READ
        assert request.platform == "web"  # default

    def test_status_update_request_with_platform(self):
        """Test StatusUpdateRequest with specific platform."""
        request = StatusUpdateRequest(
            message_id="msg-123",
            status=MessageStatus.DELIVERED,
            platform="twilio",
        )

        assert request.platform == "twilio"


class TestSendMessageRequest:
    """Test SendMessageRequest model."""

    def test_send_message_request_creation(self):
        """Test creating a valid SendMessageRequest."""
        request = SendMessageRequest(
            recipient_id="user-456",
            content="Your reservation has been confirmed",
        )

        assert request.recipient_id == "user-456"
        assert request.content == "Your reservation has been confirmed"
        assert request.platform == "web"  # default
        assert request.platform_metadata is None  # default

    def test_send_message_request_with_metadata(self):
        """Test SendMessageRequest with platform metadata."""
        metadata = {"phone_number": "+1234567890"}
        request = SendMessageRequest(
            recipient_id="user-456",
            content="Your reservation has been confirmed",
            platform="twilio",
            platform_metadata=metadata,
        )

        assert request.platform == "twilio"
        assert request.platform_metadata == metadata


class TestAgentCoreInvocationRequest:
    """Test cases for AgentCoreInvocationRequest model."""

    def test_agentcore_invocation_request_creation(self):
        """Test basic AgentCoreInvocationRequest creation."""
        from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest

        request = AgentCoreInvocationRequest(
            prompt="Hello, I need help with my reservation",
            actorId="user123",
            messageIds=["msg-456"],
            conversationId="conv-789",
        )

        assert request.prompt == "Hello, I need help with my reservation"
        assert request.actor_id == "user123"
        assert request.message_ids == ["msg-456"]
        assert request.conversation_id == "conv-789"
        assert request.model_id is None
        assert request.temperature is None

    def test_agentcore_invocation_request_with_model_params(self):
        """Test AgentCoreInvocationRequest creation with model parameters."""
        from virtual_assistant_common.models.messaging import AgentCoreInvocationRequest

        request = AgentCoreInvocationRequest(
            prompt="Hello, I need help with my reservation",
            actorId="user123",
            messageIds=["msg-456"],
            conversationId="conv-789",
            modelId="amazon.nova-lite-v1:0",
            temperature=0.7,
        )

        assert request.prompt == "Hello, I need help with my reservation"
        assert request.actor_id == "user123"
        assert request.message_ids == ["msg-456"]
        assert request.conversation_id == "conv-789"
        assert request.model_id == "amazon.nova-lite-v1:0"
        assert request.temperature == 0.7


class TestAgentCoreInvocationResponse:
    """Test cases for AgentCoreInvocationResponse model."""

    def test_agentcore_invocation_response_success(self):
        """Test successful AgentCoreInvocationResponse."""
        from virtual_assistant_common.models.messaging import AgentCoreInvocationResponse

        response = AgentCoreInvocationResponse(success=True, message_id="msg-456", invocation_id="inv-123")

        assert response.success is True
        assert response.message_id == "msg-456"
        assert response.invocation_id == "inv-123"
        assert response.error is None

    def test_agentcore_invocation_response_failure(self):
        """Test failed AgentCoreInvocationResponse."""
        from virtual_assistant_common.models.messaging import AgentCoreInvocationResponse

        response = AgentCoreInvocationResponse(
            success=False, message_id="msg-456", error="AgentCore runtime unavailable"
        )

        assert response.success is False
        assert response.message_id == "msg-456"
        assert response.error == "AgentCore runtime unavailable"
        assert response.invocation_id is None


class TestMessageGroupProperties:
    """Property-based tests for MessageGroup.

    Feature: chat-message-batching
    These tests validate the correctness properties for message grouping.
    """

    # Hypothesis strategies for generating test data
    @staticmethod
    def message_event_strategy(
        sender_id: str | None = None,
        conversation_id: str | None = None,
        platform: str | None = None,
        timestamp_base: int = 1000000000,
    ):
        """Strategy for generating MessageEvent objects with controlled properties."""
        return st.builds(
            MessageEvent,
            message_id=st.text(
                min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
            ),
            conversation_id=st.just(conversation_id) if conversation_id else st.text(min_size=1, max_size=50),
            sender_id=st.just(sender_id) if sender_id else st.text(min_size=1, max_size=50),
            recipient_id=st.text(min_size=1, max_size=50),
            content=st.text(min_size=1, max_size=200),
            timestamp=st.integers(min_value=timestamp_base, max_value=timestamp_base + 1000000).map(
                lambda x: f"2024-01-01T{x % 24:02d}:{(x // 60) % 60:02d}:{x % 60:02d}Z"
            ),
            platform=st.just(platform) if platform else st.sampled_from(["web", "twilio", "aws-eum"]),
            platform_metadata=st.none() | st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50)),
            status=st.none() | st.sampled_from(["sent", "delivered", "read", "failed"]),
            model_id=st.none(),
            temperature=st.none(),
        )

    @given(
        st.lists(
            st.builds(
                MessageEvent,
                message_id=st.text(
                    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
                ),
                conversation_id=st.text(min_size=1, max_size=50),
                sender_id=st.text(min_size=1, max_size=50),
                recipient_id=st.text(min_size=1, max_size=50),
                content=st.text(min_size=1, max_size=200),
                timestamp=st.integers(min_value=1000000000, max_value=1000001000).map(
                    lambda x: f"2024-01-01T{x % 24:02d}:{(x // 60) % 60:02d}:{x % 60:02d}Z"
                ),
                platform=st.sampled_from(["web", "twilio", "aws-eum"]),
                platform_metadata=st.none() | st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50)),
                status=st.none() | st.sampled_from(["sent", "delivered", "read", "failed"]),
                model_id=st.none(),
                temperature=st.none(),
            ),
            min_size=1,
            max_size=20,
        )
    )
    def test_property_2_message_order_preservation(self, messages):
        """Property 2: Message Order Preservation.

        Feature: chat-message-batching, Property 2: Messages within group ordered by timestamp

        For any MessageGroup, the messages within the group should be ordered by
        timestamp in ascending order (earliest first).

        **Validates: Requirements 1.2**
        """
        # Sort messages by timestamp to create expected order
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)

        # Create MessageGroup with sorted messages
        group = MessageGroup(messages=sorted_messages)

        # Verify messages are in timestamp order
        for i in range(len(group.messages) - 1):
            assert group.messages[i].timestamp <= group.messages[i + 1].timestamp, (
                f"Messages not in timestamp order: {group.messages[i].timestamp} > {group.messages[i + 1].timestamp}"
            )

    @given(
        st.lists(
            st.builds(
                MessageEvent,
                message_id=st.text(
                    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
                ),
                conversation_id=st.text(min_size=1, max_size=50),
                sender_id=st.text(min_size=1, max_size=50),
                recipient_id=st.text(min_size=1, max_size=50),
                content=st.text(min_size=1, max_size=200),
                timestamp=st.text(min_size=1, max_size=50),
                platform=st.sampled_from(["web", "twilio", "aws-eum"]),
                platform_metadata=st.none(),
                status=st.none(),
                model_id=st.none(),
                temperature=st.none(),
            ),
            min_size=1,
            max_size=20,
        )
    )
    def test_property_3_message_content_combination(self, messages):
        """Property 3: Message Content Combination.

        Feature: chat-message-batching, Property 3: Combined content equals messages joined with newlines

        For any MessageGroup with multiple messages, the combined_content should equal
        the message contents joined with newline separators, preserving the order.

        **Validates: Requirements 1.3**
        """
        group = MessageGroup(messages=messages)

        # Calculate expected combined content
        expected_content = "\n".join(msg.content for msg in messages)

        # Verify combined content matches
        assert group.combined_content == expected_content, (
            f"Combined content mismatch:\nExpected: {expected_content}\nActual: {group.combined_content}"
        )

    @given(
        st.lists(
            st.builds(
                MessageEvent,
                message_id=st.text(
                    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
                ),
                conversation_id=st.text(min_size=1, max_size=50),
                sender_id=st.text(min_size=1, max_size=50),
                recipient_id=st.text(min_size=1, max_size=50),
                content=st.text(min_size=1, max_size=200),
                timestamp=st.text(min_size=1, max_size=50),
                platform=st.sampled_from(["web", "twilio", "aws-eum"]),
                platform_metadata=st.none(),
                status=st.none(),
                model_id=st.none(),
                temperature=st.none(),
            ),
            min_size=1,
            max_size=20,
        )
    )
    def test_property_4_message_id_tracking(self, messages):
        """Property 4: Message ID Tracking.

        Feature: chat-message-batching, Property 4: All message IDs present with no duplicates

        For any MessageGroup, the message_ids list should contain exactly the message
        IDs from all messages in the group, with no duplicates or omissions.

        **Validates: Requirements 1.4**
        """
        group = MessageGroup(messages=messages)

        # Get expected message IDs
        expected_ids = [msg.message_id for msg in messages]

        # Verify all message IDs are present in the same order
        assert group.message_ids == expected_ids, (
            f"Message IDs mismatch:\nExpected: {expected_ids}\nActual: {group.message_ids}"
        )

        # Verify the count matches (all IDs preserved, even if duplicates exist in input)
        assert len(group.message_ids) == len(messages), "Message ID count mismatch"

    @given(
        st.lists(
            st.builds(
                MessageEvent,
                message_id=st.text(
                    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))
                ),
                conversation_id=st.text(min_size=1, max_size=50),
                sender_id=st.text(min_size=1, max_size=50),
                recipient_id=st.text(min_size=1, max_size=50),
                content=st.text(min_size=1, max_size=200),
                timestamp=st.text(min_size=1, max_size=50),
                platform=st.sampled_from(["web", "twilio", "aws-eum"]),
                platform_metadata=st.none() | st.dictionaries(st.text(min_size=1, max_size=20), st.text(max_size=50)),
                status=st.none() | st.sampled_from(["sent", "delivered", "read", "failed"]),
                model_id=st.none(),
                temperature=st.none(),
            ),
            min_size=1,
            max_size=20,
        )
    )
    def test_property_25_message_data_preservation(self, messages):
        """Property 25: Message Data Preservation.

        Feature: chat-message-batching, Property 25: Original MessageEvent objects preserved

        For any message group, all original MessageEvent objects should be preserved
        in the messages list without modification.

        **Validates: Requirements 7.3**
        """
        # Create a copy of messages for comparison
        original_messages = [msg.model_copy() for msg in messages]

        group = MessageGroup(messages=messages)

        # Verify all messages are preserved
        assert len(group.messages) == len(original_messages), "Message count mismatch"

        # Verify each message is preserved without modification
        for i, (original, preserved) in enumerate(zip(original_messages, group.messages, strict=True)):
            assert preserved.message_id == original.message_id, f"Message {i} ID changed"
            assert preserved.content == original.content, f"Message {i} content changed"
            assert preserved.sender_id == original.sender_id, f"Message {i} sender_id changed"
            assert preserved.conversation_id == original.conversation_id, f"Message {i} conversation_id changed"
            assert preserved.timestamp == original.timestamp, f"Message {i} timestamp changed"
            assert preserved.platform == original.platform, f"Message {i} platform changed"
            assert preserved.platform_metadata == original.platform_metadata, f"Message {i} platform_metadata changed"
            assert preserved.status == original.status, f"Message {i} status changed"
