# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for Step Functions task token callback functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAgentCallbacks:
    """Test Step Functions task token callback functionality."""

    @pytest.mark.asyncio
    async def test_success_callback_sent_after_processing(self, mock_agent_module):
        """Test that success callback is sent after successful message processing."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        mock_sfn.send_task_success = MagicMock()

        # Mock platform router
        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            # Mock agent streaming
            mock_agent = MagicMock()

            async def mock_stream(message):
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = mock_stream

            # Mock the global agent variable, get_sfn_client, and session state
            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-789"),
                patch.object(mock_agent_module, "current_actor_id", "user-123"),
            ):
                # Call process_user_message with task_token
                await mock_agent_module.process_user_message(
                    user_message="test message",
                    actor_id="user-123",
                    message_ids=["msg-1", "msg-2"],
                    conversation_id="conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="session-789",
                    task_token="test-token-123",
                )

                # Verify success callback was sent
                mock_sfn.send_task_success.assert_called_once()
                call_args = mock_sfn.send_task_success.call_args
                assert call_args[1]["taskToken"] == "test-token-123"

                # Verify output contains expected data
                output = json.loads(call_args[1]["output"])
                assert output["status"] == "success"
                assert output["message_ids"] == ["msg-1", "msg-2"]
                assert output["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_callback_retry_logic(self, mock_agent_module):
        """Test callback retry logic with exponential backoff."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        # Simulate failures on first 2 attempts, success on 3rd
        mock_sfn.send_task_success = MagicMock(side_effect=[Exception("Network error"), Exception("Timeout"), None])

        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            mock_agent = MagicMock()

            async def mock_stream(message):
                yield {"message": {"content": [{"text": "Hello"}]}}

            mock_agent.stream_async = mock_stream

            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-789"),
                patch.object(mock_agent_module, "current_actor_id", "user-123"),
                patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            ):
                await mock_agent_module.process_user_message(
                    user_message="test",
                    actor_id="user-123",
                    message_ids=["msg-1"],
                    conversation_id="conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="session-789",
                    task_token="test-token",
                )

                # Verify 3 attempts were made
                assert mock_sfn.send_task_success.call_count == 3

                # Verify exponential backoff: 1s, 2s
                assert mock_sleep.call_count == 2
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls == [1, 2]

    @pytest.mark.asyncio
    async def test_failure_callback_sent_on_exception(self, mock_agent_module):
        """Test that failure callback is sent when processing fails."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        mock_sfn.send_task_failure = MagicMock()

        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock()

            # Mock agent that raises exception
            mock_agent = MagicMock()

            async def mock_stream(message):
                raise Exception("Processing failed")
                yield  # Make it an async generator (unreachable but needed for syntax)

            mock_agent.stream_async = mock_stream

            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-789"),
                patch.object(mock_agent_module, "current_actor_id", "user-123"),
            ):
                # Call should raise exception
                with pytest.raises(Exception, match="Processing failed"):
                    await mock_agent_module.process_user_message(
                        user_message="test",
                        actor_id="user-123",
                        message_ids=["msg-1"],
                        conversation_id="conv-456",
                        model_id="test-model",
                        temperature=0.2,
                        session_id="session-789",
                        task_token="test-token",
                    )

                # Verify failure callback was sent
                mock_sfn.send_task_failure.assert_called_once()
                call_args = mock_sfn.send_task_failure.call_args
                assert call_args[1]["taskToken"] == "test-token"
                assert call_args[1]["error"] == "AsyncTaskProcessingError"
                assert "Processing failed" in call_args[1]["cause"]

    @pytest.mark.asyncio
    async def test_callback_includes_correct_data(self, mock_agent_module):
        """Test that callback includes correct message_ids and user_id."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        mock_sfn.send_task_success = MagicMock()

        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            mock_agent = MagicMock()

            async def mock_stream(message):
                yield {"message": {"content": [{"text": "Response"}]}}

            mock_agent.stream_async = mock_stream

            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-123"),
                patch.object(mock_agent_module, "current_actor_id", "user-456"),
            ):
                await mock_agent_module.process_user_message(
                    user_message="test",
                    actor_id="user-456",
                    message_ids=["msg-a", "msg-b", "msg-c"],
                    conversation_id="conv-789",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="session-123",
                    task_token="token-xyz",
                )

                # Verify callback data
                call_args = mock_sfn.send_task_success.call_args
                output = json.loads(call_args[1]["output"])
                assert output["message_ids"] == ["msg-a", "msg-b", "msg-c"]
                assert output["user_id"] == "user-456"

    @pytest.mark.asyncio
    async def test_callback_error_handling_best_effort(self, mock_agent_module):
        """Test that callback errors don't crash processing (best-effort)."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        # All callback attempts fail
        mock_sfn.send_task_success = MagicMock(side_effect=Exception("Network error"))

        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            mock_agent = MagicMock()

            async def mock_stream(message):
                yield {"message": {"content": [{"text": "Success"}]}}

            mock_agent.stream_async = mock_stream

            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-789"),
                patch.object(mock_agent_module, "current_actor_id", "user-123"),
                patch("asyncio.sleep", new_callable=AsyncMock),
            ):
                # Should not raise exception even though callback fails
                await mock_agent_module.process_user_message(
                    user_message="test",
                    actor_id="user-123",
                    message_ids=["msg-1"],
                    conversation_id="conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="session-789",
                    task_token="test-token",
                )

                # Verify 3 attempts were made
                assert mock_sfn.send_task_success.call_count == 3

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_task_token(self, mock_agent_module):
        """Test backward compatibility when task_token is None."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        mock_sfn.send_task_success = MagicMock()

        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock(return_value=MagicMock(success=True))

            mock_agent = MagicMock()

            async def mock_stream(message):
                yield {"message": {"content": [{"text": "Response"}]}}

            mock_agent.stream_async = mock_stream

            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-789"),
                patch.object(mock_agent_module, "current_actor_id", "user-123"),
            ):
                # Call without task_token
                await mock_agent_module.process_user_message(
                    user_message="test",
                    actor_id="user-123",
                    message_ids=["msg-1"],
                    conversation_id="conv-456",
                    model_id="test-model",
                    temperature=0.2,
                    session_id="session-789",
                    task_token=None,  # No task token
                )

                # Verify no callback was sent
                mock_sfn.send_task_success.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_callback_backward_compatibility(self, mock_agent_module):
        """Test that failure callback is not sent when task_token is None."""
        # Mock Step Functions client
        mock_sfn = MagicMock()
        mock_sfn.send_task_failure = MagicMock()

        with patch("virtual_assistant_common.platforms.router.platform_router") as mock_router:
            mock_router.update_message_status = AsyncMock()
            mock_router.send_response = AsyncMock()

            mock_agent = MagicMock()

            async def mock_stream(message):
                raise Exception("Processing failed")
                yield  # Make it an async generator (unreachable but needed for syntax)

            mock_agent.stream_async = mock_stream

            with (
                patch.object(mock_agent_module, "agent", mock_agent),
                patch.object(mock_agent_module, "get_sfn_client", return_value=mock_sfn),
                patch.object(mock_agent_module, "current_session_id", "session-789"),
                patch.object(mock_agent_module, "current_actor_id", "user-123"),
            ):
                # Call should raise exception
                with pytest.raises(Exception, match="Processing failed"):
                    await mock_agent_module.process_user_message(
                        user_message="test",
                        actor_id="user-123",
                        message_ids=["msg-1"],
                        conversation_id="conv-456",
                        model_id="test-model",
                        temperature=0.2,
                        session_id="session-789",
                        task_token=None,  # No task token
                    )

                # Verify no failure callback was sent
                mock_sfn.send_task_failure.assert_not_called()
