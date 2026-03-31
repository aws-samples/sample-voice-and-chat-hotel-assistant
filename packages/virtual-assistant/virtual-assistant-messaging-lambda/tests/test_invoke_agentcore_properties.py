# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for invoke AgentCore handler.

Feature: stepfunctions-message-buffering
Tests the correctness properties defined in the design document.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st
from virtual_assistant_common.exceptions import AgentCoreSessionBusyError

from virtual_assistant_messaging_lambda.handlers.invoke_agentcore import lambda_handler


# Strategies for generating test data
@st.composite
def event_strategy(draw):
    """Generate a Step Functions event for AgentCore invocation.

    Matches the format from PrepareProcessing Lambda output:
    {
        "user_id": str,
        "session_id": str,
        "marked_messages": {
            "processing_messages": [
                {
                    "message_id": str,
                    "content": str,
                    "timestamp": str,
                    "sender_id": str,
                    "conversation_id": str,
                    "platform": str
                }
            ],
            "message_count": int
        }
    }
    """
    user_id = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
    session_id = f"session-{draw(st.uuids()).hex}"

    # Generate messages in plain JSON format (as returned by PrepareProcessing)
    num_messages = draw(st.integers(min_value=1, max_value=10))
    processing_messages = []

    for _ in range(num_messages):
        message_id = draw(st.uuids()).hex
        content = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters="\n")))
        timestamp = "2026-01-13T14:14:41.473Z"

        processing_messages.append(
            {
                "message_id": message_id,
                "content": content,
                "timestamp": timestamp,
                "sender_id": user_id,
                "conversation_id": session_id,
                "platform": "aws-eum",
            }
        )

    return {
        "user_id": user_id,
        "session_id": session_id,
        "marked_messages": {"processing_messages": processing_messages, "message_count": len(processing_messages)},
    }


# Property 16: Combined Content Passed to AgentCore
@settings(max_examples=100)
@given(event_strategy())
def test_property_16_combined_content_passed_to_agentcore(event):
    """Property 16: Combined Content Passed to AgentCore

    For any AgentCore invocation, the combined message content from processing
    messages should be passed as the prompt.

    Feature: stepfunctions-message-buffering, Property 16: Combined Content Passed to AgentCore
    Validates: Requirements 5.1
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client
    mock_response = MagicMock()
    mock_response.success = True
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify AgentCore was invoked
        assert mock_agentcore_client.invoke_agent.called, "AgentCore should be invoked"

        # Get the invocation request
        invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]

        # Calculate expected combined content from processing messages
        expected_content = "\n".join(msg["content"] for msg in event["marked_messages"]["processing_messages"])

        # Verify combined content was passed as prompt
        assert invocation_request.prompt == expected_content, (
            f"Expected prompt to be '{expected_content}', got '{invocation_request.prompt}'"
        )

        # Verify response indicates success
        assert response["status"] == "success"


# Property 17: Message IDs Passed to AgentCore
@settings(max_examples=100)
@given(event_strategy())
def test_property_17_message_ids_passed_to_agentcore(event):
    """Property 17: Message IDs Passed to AgentCore

    For any AgentCore invocation, all message IDs from processing messages should
    be passed for status tracking.

    Feature: stepfunctions-message-buffering, Property 17: Message IDs Passed to AgentCore
    Validates: Requirements 5.2
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client
    mock_response = MagicMock()
    mock_response.success = True
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify AgentCore was invoked
        assert mock_agentcore_client.invoke_agent.called, "AgentCore should be invoked"

        # Get the invocation request
        invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]

        # Extract expected message IDs from processing messages
        expected_message_ids = [msg["message_id"] for msg in event["marked_messages"]["processing_messages"]]

        # Verify all message IDs were passed
        assert invocation_request.message_ids == expected_message_ids, (
            f"Expected message IDs {expected_message_ids}, got {invocation_request.message_ids}"
        )

        # Verify response contains message IDs
        assert response["message_ids"] == expected_message_ids


# Property 18: Session ID Used
@settings(max_examples=100)
@given(event_strategy())
def test_property_18_session_id_used(event):
    """Property 18: Session ID Used

    For any AgentCore invocation, the user's session_id should be used as the
    conversation identifier.

    Feature: stepfunctions-message-buffering, Property 18: Session ID Used
    Validates: Requirements 5.3
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client
    mock_response = MagicMock()
    mock_response.success = True
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler
        lambda_handler(event, MagicMock())

        # Verify AgentCore was invoked
        assert mock_agentcore_client.invoke_agent.called, "AgentCore should be invoked"

        # Get the invocation request
        invocation_request = mock_agentcore_client.invoke_agent.call_args[0][0]

        # Verify session ID was used as conversation ID
        assert invocation_request.conversation_id == event["session_id"], (
            f"Expected conversation ID to be '{event['session_id']}', got '{invocation_request.conversation_id}'"
        )


# Property 19: Workflow Completes on Success
@settings(max_examples=100)
@given(event_strategy())
def test_property_19_workflow_completes_on_success(event):
    """Property 19: Workflow Completes on Success

    For any successful AgentCore invocation, the workflow should complete successfully.

    Feature: stepfunctions-message-buffering, Property 19: Workflow Completes on Success
    Validates: Requirements 5.4
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client with successful response
    mock_response = MagicMock()
    mock_response.success = True
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler
        response = lambda_handler(event, MagicMock())

        # Verify response indicates success
        assert response["status"] == "success", f"Expected status 'success', got '{response['status']}'"

        # Extract expected message IDs from processing messages
        expected_message_ids = [msg["message_id"] for msg in event["marked_messages"]["processing_messages"]]

        # Verify message IDs are returned
        assert response["message_ids"] == expected_message_ids


# Property 20: Retry on Failure
@settings(max_examples=100)
@given(event_strategy())
def test_property_20_retry_on_failure(event):
    """Property 20: Retry on Failure

    For any failed AgentCore invocation due to session busy, the workflow should
    raise AgentCoreSessionBusyError to trigger retry.

    Feature: stepfunctions-message-buffering, Property 20: Retry on Failure
    Validates: Requirements 5.5
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client with session busy error
    mock_response = MagicMock()
    mock_response.success = False
    mock_response.error = "Session is busy processing concurrent request"
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler and expect AgentCoreSessionBusyError
        exception_raised = False
        try:
            lambda_handler(event, MagicMock())
        except AgentCoreSessionBusyError as e:
            exception_raised = True
            # Verify error contains session ID
            assert e.session_id == event["session_id"], (
                f"Expected session ID '{event['session_id']}' in error, got '{e.session_id}'"
            )

        assert exception_raised, "Expected AgentCoreSessionBusyError to be raised"


# Property 21: Delivered Status
@settings(max_examples=100)
@given(event_strategy())
def test_property_21_delivered_status(event):
    """Property 21: Delivered Status

    For any message being processed, it should be marked as "delivered" before
    AgentCore invocation.

    Feature: stepfunctions-message-buffering, Property 21: Delivered Status
    Validates: Requirements 8.1
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client
    mock_response = MagicMock()
    mock_response.success = True
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler
        lambda_handler(event, MagicMock())

        # Extract expected message IDs from processing messages
        expected_message_ids = [msg["message_id"] for msg in event["marked_messages"]["processing_messages"]]

        # Verify all messages were marked as delivered
        assert mock_update_status.call_count == len(expected_message_ids), (
            f"Expected {len(expected_message_ids)} status updates, got {mock_update_status.call_count}"
        )

        # Verify each message was marked as delivered
        for message_id in expected_message_ids:
            # Check if this message_id was updated to "delivered"
            found = False
            for call in mock_update_status.call_args_list:
                if call[0][0] == message_id and call[0][1] == "delivered":
                    found = True
                    break
            assert found, f"Message {message_id} was not marked as delivered"


# Additional test: Non-session-busy error
@settings(max_examples=100)
@given(event_strategy())
def test_invoke_agentcore_other_error(event):
    """Test that non-session-busy errors are raised as generic exceptions.

    Feature: stepfunctions-message-buffering
    """
    # Mock platform router
    mock_update_status = AsyncMock()

    # Mock AgentCore client with generic error
    mock_response = MagicMock()
    mock_response.success = False
    mock_response.error = "Some other error occurred"
    mock_agentcore_client = MagicMock()
    mock_agentcore_client.invoke_agent.return_value = mock_response

    with (
        patch.dict(
            os.environ,
            {
                "BEDROCK_MODEL_ID": "test-model",
                "MODEL_TEMPERATURE": "0.2",
                "AGENTCORE_RUNTIME_ARN": "arn:aws:bedrock:us-east-1:123456789012:agent-runtime/test",
            },
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.platform_router.update_message_status",
            mock_update_status,
        ),
        patch(
            "virtual_assistant_messaging_lambda.handlers.invoke_agentcore.AgentCoreClient",
            return_value=mock_agentcore_client,
        ),
    ):
        # Execute handler and expect generic Exception
        session_busy_raised = False
        other_exception_raised = False
        error_message = ""

        try:
            lambda_handler(event, MagicMock())
        except AgentCoreSessionBusyError:
            session_busy_raised = True
        except Exception as e:
            other_exception_raised = True
            error_message = str(e)

        assert not session_busy_raised, "Should not raise AgentCoreSessionBusyError for non-session-busy errors"
        assert other_exception_raised, "Expected Exception to be raised"
        # Verify error message contains the original error
        assert "Some other error occurred" in error_message
