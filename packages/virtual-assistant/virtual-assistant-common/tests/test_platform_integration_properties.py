# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for platform integration.

Feature: chat-message-batching
Tests platform router integration with multiple message IDs.
"""

from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from virtual_assistant_common.models.messaging import MessageEvent, MessageResponse
from virtual_assistant_common.platforms.router import PlatformRouter


# Generators for test data
@st.composite
def message_event_strategy(draw):
    """Generate random MessageEvent objects."""
    message_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
    sender_id = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
    conversation_id = f"{sender_id}#hotel-assistant"
    content = draw(st.text(min_size=1, max_size=500))

    return MessageEvent(
        message_id=message_id,
        conversation_id=conversation_id,
        sender_id=sender_id,
        recipient_id="hotel-assistant",
        content=content,
        timestamp="2024-01-01T12:00:00Z",
        platform="web",
    )


@st.composite
def message_id_list_strategy(draw):
    """Generate list of message IDs."""
    count = draw(st.integers(min_value=1, max_value=10))
    return [
        draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
        for _ in range(count)
    ]


class TestPlatformIntegrationProperties:
    """Property-based tests for platform integration."""

    @pytest.mark.asyncio
    @given(message_event=message_event_strategy())
    async def test_property_26_platform_router_for_responses(self, message_event):
        """Property 26: Platform Router for Responses.

        For any response sent by the Chat Agent, it should be sent using
        platform_router.send_response.

        Feature: chat-message-batching, Property 26: Platform Router for Responses
        Validates: Requirements 7.4
        """
        router = PlatformRouter()

        # Mock the platform handler
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.send_response.return_value = MessageResponse(success=True, message_id="response-123")
            mock_get_platform.return_value = mock_platform

            # Send response through router
            response = await router.send_response(message_event.conversation_id, "Test response")

            # Verify platform router was used
            assert response.success is True
            mock_platform.send_response.assert_called_once_with(message_event.conversation_id, "Test response")

    @pytest.mark.asyncio
    @given(message_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
    async def test_property_27_platform_router_for_status_updates_single(self, message_id):
        """Property 27: Platform Router for Status Updates (single message).

        For any message status update with a single message ID, it should be
        performed using platform_router.update_message_status.

        Feature: chat-message-batching, Property 27: Platform Router for Status Updates
        Validates: Requirements 7.5
        """
        router = PlatformRouter()

        # Mock the platform handler
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.update_message_status.return_value = MessageResponse(success=True, message_id=message_id)
            mock_get_platform.return_value = mock_platform

            # Update status through router
            response = await router.update_message_status(message_id, "read")

            # Verify platform router was used
            assert response.success is True
            mock_platform.update_message_status.assert_called_once_with(message_id, "read")

    @pytest.mark.asyncio
    @given(message_ids=message_id_list_strategy())
    async def test_property_27_platform_router_for_status_updates_multiple(self, message_ids):
        """Property 27: Platform Router for Status Updates (multiple messages).

        For any message status update with multiple message IDs, it should be
        performed using platform_router.update_message_status with a list.

        Feature: chat-message-batching, Property 27: Platform Router for Status Updates
        Validates: Requirements 7.5
        """
        router = PlatformRouter()

        # Mock the platform handler
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.update_message_status.return_value = MessageResponse(
                success=True, data={"updated_count": len(message_ids), "message_ids": message_ids}
            )
            mock_get_platform.return_value = mock_platform

            # Update status through router with list of message IDs
            response = await router.update_message_status(message_ids, "delivered")

            # Verify platform router was used with list
            assert response.success is True
            mock_platform.update_message_status.assert_called_once_with(message_ids, "delivered")

            # Verify all message IDs were included
            if response.data:
                assert response.data.get("updated_count") == len(message_ids)
                assert response.data.get("message_ids") == message_ids

    @pytest.mark.asyncio
    @given(message_ids=message_id_list_strategy(), status=st.sampled_from(["delivered", "read", "failed"]))
    async def test_property_27_status_update_consistency(self, message_ids, status):
        """Property 27: Status update consistency across platforms.

        For any list of message IDs and any valid status, the platform router
        should consistently route to the current platform and handle the update.

        Feature: chat-message-batching, Property 27: Platform Router for Status Updates
        Validates: Requirements 7.5
        """
        router = PlatformRouter()

        # Mock the platform handler
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.update_message_status.return_value = MessageResponse(
                success=True, data={"updated_count": len(message_ids), "message_ids": message_ids}
            )
            mock_get_platform.return_value = mock_platform

            # Update status through router
            response = await router.update_message_status(message_ids, status)

            # Verify routing to current platform
            mock_get_platform.assert_called_once_with(router._current_platform)

            # Verify platform handler was called with correct parameters
            mock_platform.update_message_status.assert_called_once_with(message_ids, status)

            # Verify response indicates success
            assert response.success is True

    @pytest.mark.asyncio
    @given(
        conversation_id=st.text(
            min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "P"))
        ),
        content=st.text(min_size=1, max_size=1000),
    )
    async def test_property_26_response_routing_consistency(self, conversation_id, content):
        """Property 26: Response routing consistency.

        For any conversation ID and content, the platform router should
        consistently route responses to the current platform.

        Feature: chat-message-batching, Property 26: Platform Router for Responses
        Validates: Requirements 7.4
        """
        router = PlatformRouter()

        # Mock the platform handler
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.send_response.return_value = MessageResponse(success=True, message_id="response-id")
            mock_get_platform.return_value = mock_platform

            # Send response through router
            response = await router.send_response(conversation_id, content)

            # Verify routing to current platform
            mock_get_platform.assert_called_once_with(router._current_platform)

            # Verify platform handler was called with correct parameters
            mock_platform.send_response.assert_called_once_with(conversation_id, content)

            # Verify response indicates success
            assert response.success is True

    @pytest.mark.asyncio
    @given(message_ids=message_id_list_strategy())
    async def test_property_27_error_handling_for_status_updates(self, message_ids):
        """Property 27: Error handling for status updates.

        For any list of message IDs, if the platform handler fails, the router
        should return an error response without crashing.

        Feature: chat-message-batching, Property 27: Platform Router for Status Updates
        Validates: Requirements 7.5
        """
        router = PlatformRouter()

        # Mock the platform handler to raise an exception
        with patch.object(router, "get_platform") as mock_get_platform:
            mock_platform = AsyncMock()
            mock_platform.update_message_status.side_effect = Exception("Platform error")
            mock_get_platform.return_value = mock_platform

            # Update status through router - should handle error gracefully
            response = await router.update_message_status(message_ids, "read")

            # Verify error response
            assert response.success is False
            assert "error" in response.error.lower() or "status update error" in response.error.lower()
