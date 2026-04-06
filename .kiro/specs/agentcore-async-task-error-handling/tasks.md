# Implementation Tasks: AgentCore Async Task Error Handling

## Overview

This document outlines the implementation tasks for adding proper error handling
and retry logic to AgentCore async task processing using Step Functions task
token pattern with loop-back mechanism.

## Current Implementation Status

After analyzing the codebase, the following components are **already
implemented**:

- ✅ AgentCore agent with async task processing
- ✅ InvokeAgentCore Lambda handler
- ✅ AgentCoreInvocationRequest/Response models
- ✅ Step Functions state machine with retry logic
- ✅ Loop-back mechanism (DeleteProcessedMessages → GetMessages)
- ✅ PrepareRetry and PrepareProcessing handlers
- ✅ Message buffering in DynamoDB

**What's Missing**: Task token integration for async task completion callbacks.

## Task Breakdown

- [x] 1. Implement Core Task Token Support ✅ **COMPLETED**
  - [x] 1.1 Update AgentCoreInvocationRequest Model ✅
    - Add optional `task_token: str | None = None` field to model
    - Add field description for Step Functions callbacks
    - _Requirements: 8.1_
    - _File:
      `packages/virtual-assistant/virtual-assistant-common/virtual_assistant_common/models/messaging.py`_
  - [x] 1.2 Add Step Functions Client and Task Token Support to Agent Module ✅
    - Add `boto3` import for Step Functions client at module level
    - Create `get_sfn_client()` function for lazy initialization
    - Add `task_token: str | None = None` parameter to `process_user_message()`
      signature
    - Extract `task_token` from payload in `invoke()` entrypoint
    - Pass `task_token` to `process_user_message()` when creating async task
    - **Fixed**: Changed from direct `sfn_client` usage to `get_sfn_client()`
      calls for proper lazy initialization
    - _Requirements: 8.1, 8.2, 8.3_
    - _File:
      `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`_
  - [x] 1.3 Implement Success Callback in Agent ✅
    - After successful message processing (after
      `async for event in agent.stream_async()` loop)
    - Add success callback with retry logic (3 attempts, exponential backoff:
      1s, 2s, 4s)
    - Send `SendTaskSuccess` with `task_token`, `message_ids`, and `user_id`
    - Log callback success/failure appropriately
    - Don't raise exception on callback failure (best-effort)
    - **Fixed**: Uses `get_sfn_client()` for proper client initialization
    - _Requirements: 8.4, 9.1, 9.3_
    - _File:
      `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`_
  - [x] 1.4 Implement Failure Callback in Agent ✅
    - In exception handler of `process_user_message()` after existing error
      handling
    - Add failure callback with retry logic (3 attempts, exponential backoff:
      1s, 2s, 4s)
    - Send `SendTaskFailure` with `task_token`, error type, and sanitized error
      message
    - Log callback success/failure appropriately
    - **Fixed**: Uses `get_sfn_client()` for proper client initialization
    - _Requirements: 8.5, 9.2, 9.3_
    - _File:
      `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`_
  - [x] 1.5 Unit Tests for Agent Callbacks ✅
    - Test success callback sent after successful processing
    - Test callback retry logic (3 attempts with exponential backoff)
    - Test failure callback sent on exception
    - Test callback includes correct message_ids and user_id
    - Test callback error handling (best-effort, doesn't crash)
    - Test backward compatibility (task_token=None)
    - **Fixed**: Updated tests to mock `get_sfn_client()` instead of
      `sfn_client`
    - **All 7 tests passing**
    - _Requirements: 8.4, 8.5, 9.1, 9.2, 9.3_
    - _File:
      `packages/virtual-assistant/virtual-assistant-chat/tests/test_agent_callbacks.py`
      (new)_
  - [x] 1.6 Update InvokeAgentCore Lambda to Extract and Pass Task Token ✅
    - Extract `task_token` from event (optional, may be None)
    - Add `task_token` to `request_kwargs` if present
    - Maintain backward compatibility when `task_token` is None
    - **All 5 tests passing**
    - _Requirements: 8.1, 8.2_
    - _File:
      `packages/virtual-assistant/virtual-assistant-messaging-lambda/virtual_assistant_messaging_lambda/handlers/invoke_agentcore.py`_
  - [x] 1.7 Unit Tests for InvokeAgentCore Lambda
    - Test task_token extraction from event when present
    - Test Lambda works correctly when task_token is None
    - Test task_token passed to AgentCore client when present
    - Test task_token not passed when absent
    - Test return value consistent regardless of task_token presence
    - _Requirements: 8.1, 8.2_
    - _File:
      `packages/virtual-assistant/virtual-assistant-messaging-lambda/tests/test_invoke_agentcore.py`_

- [x] 2. Update Step Functions State Machine for Task Token Integration
  - [x] 2.1 Update InvokeAgentCore State to Use Task Token Pattern
    - Change `invoke_agentcore` to use `IntegrationPattern.WAIT_FOR_TASK_TOKEN`
    - Add `task_token: sfn.JsonPath.task_token` to payload
    - Set timeout to 4 minutes
    - Update to use JSONata mode (`.jsonata()` method)
    - _Requirements: 8.1, 8.2, 8.5_
    - _File:
      `packages/infra/stack/stack_constructs/message_buffering_construct.py`_
  - [x] 2.2 Add CheckIfMessagesExist State
    - Create JSONata Pass state after `GetMessages`
    - Check if `$count($states.input.buffer_data.Item.messages.L) > 0`
    - Output `has_messages` boolean and `messages` list
    - _Requirements: 9.5.2, 9.5.3_
    - _File:
      `packages/infra/stack/stack_constructs/message_buffering_construct.py`_
  - [x] 2.3 Add ClearWaitingState State
    - Create DynamoDB UpdateItem state to set `waiting_state = false`
    - Use JSONata mode with execution variable `$user_id`
    - Add success state after clearing waiting state
    - _Requirements: 9.6.1, 9.6.2, 9.6.3_
    - _File:
      `packages/infra/stack/stack_constructs/message_buffering_construct.py`_
  - [x] 2.4 Implement Loop-Back from DeleteProcessedMessages to GetMessages
    - Connect `delete_processed_messages.next(get_messages)`
    - Connect `get_messages.next(check_if_messages_exist)`
    - Add choice: if `has_messages == false` → `clear_waiting_state`, else →
      `check_message_age`
    - Connect `clear_waiting_state.next(sfn.Succeed())`
    - _Requirements: 9.5.1, 9.5.2, 9.5.3, 9.6.4_
    - _File:
      `packages/infra/stack/stack_constructs/message_buffering_construct.py`_
  - [x] 2.5 Add Step Functions Permissions to InvokeAgentCore Lambda
    - Add IAM policy for `states:SendTaskSuccess` and `states:SendTaskFailure`
    - Use wildcard resource `"*"` (task tokens are opaque)
    - Add CDK Nag suppression for `AwsSolutions-IAM5` with explanation
    - _Requirements: 8.1, 9.5_
    - _File:
      `packages/infra/stack/stack_constructs/message_buffering_construct.py`_

- [ ] 3. Implement Integration Testing
  - [ ] 3.1 Integration Test - End-to-End Success Flow
    - Send 3 messages to SNS topic
    - Verify workflow starts and waits for callback
    - Verify async task processes messages
    - Verify success callback sent
    - Verify messages deleted from buffer
    - Verify workflow exits cleanly
    - Verify waiting_state cleared
    - _Requirements: 8.3, 8.4, 9.1, 9.6.2_
    - _File:
      `packages/virtual-assistant/virtual-assistant-messaging-lambda/tests/integration/test_task_token_flow.py`
      (new)_
  - [ ] 3.2 Integration Test - Loop-Back Processing
    - Send 3 messages
    - During processing, send 2 more messages
    - Verify first batch processed
    - Verify workflow loops back to GetMessages
    - Verify second batch processed
    - Verify workflow exits after second batch
    - Verify single workflow execution (no concurrent workflows)
    - _Requirements: 9.5.1, 9.5.2, 9.5.4, 9.5.5_
    - _File:
      `packages/virtual-assistant/virtual-assistant-messaging-lambda/tests/integration/test_loop_back.py`
      (new)_
  - [ ] 3.3 Integration Test - Async Task Failure and Retry
    - Send messages
    - Simulate agent failure (mock MCP error)
    - Verify failure callback sent
    - Verify PrepareRetry executed
    - Verify exponential backoff timing (2s, 4s, 8s)
    - Verify retry processes messages successfully
    - Verify messages deleted after successful retry
    - _Requirements: 4.2, 4.3, 4.4, 8.5, 9.2_
    - _File:
      `packages/virtual-assistant/virtual-assistant-messaging-lambda/tests/integration/test_failure_retry.py`
      (new)_
  - [ ] 3.4 Integration Test - Task Token Timeout
    - Send messages
    - Simulate agent hang (no callback sent)
    - Verify workflow times out after 4 minutes
    - Verify workflow goes to DLQ
    - Verify messages remain in buffer with processing=true
    - Verify TTL eventually cleans up
    - _Requirements: 8.5_
    - _File:
      `packages/virtual-assistant/virtual-assistant-messaging-lambda/tests/integration/test_timeout.py`
      (new)_

- [ ] 4. Documentation and Deployment
  - [ ] 4.1 Update Architecture Documentation
    - Update message processing flow diagram with task token pattern
    - Add task token pattern explanation
    - Document loop-back mechanism
    - Update error handling section with callback retry logic
    - _File: `documentation/architecture.md`_
  - [ ] 4.2 Deploy to Development Environment
    - Run `uv run ruff check --fix && uv run ruff format` on modified Python
      files
    - Run unit tests: `uv run pytest`
    - Build Lambda packages:
      `pnpm exec nx build virtual-assistant-messaging-lambda`
    - Synthesize CDK: `pnpm exec nx run infra:synth`
    - Review changes: `pnpm exec nx diff infra`
    - Deploy: `pnpm exec nx deploy infra`
    - Run integration tests
    - Monitor CloudWatch logs and metrics

## Task Dependencies

```
Task 1 (Core Implementation)
├─ Task 1.1 (Model changes, independent)
├─ Task 1.2 → Task 1.3 → Task 1.4 (Agent changes, sequential)
├─ Task 1.5 (Unit tests for agent, depends on 1.2-1.4)
├─ Task 1.6 (Lambda changes, depends on 1.1)
└─ Task 1.7 (Unit tests for Lambda, depends on 1.6)

Task 2 (State Machine)
├─ Task 2.1 (Task token pattern, independent)
├─ Task 2.2 (CheckIfMessagesExist, independent)
├─ Task 2.3 (ClearWaitingState, independent)
├─ Task 2.4 (Loop-back, depends on 2.2, 2.3)
└─ Task 2.5 (IAM permissions, independent)

Task 3 (Integration Testing)
├─ Task 3.1 (E2E success, depends on Task 1, 2)
├─ Task 3.2 (Loop-back test, depends on Task 1, 2)
├─ Task 3.3 (Failure retry, depends on Task 1, 2)
└─ Task 3.4 (Timeout test, depends on Task 1, 2)

Task 4 (Deployment)
├─ Task 4.1 (Architecture docs, independent)
└─ Task 4.2 (Dev deployment, depends on all previous tasks)
```

## Estimated Total Effort

- **Task 1**: 5.5 hours (7 subtasks including unit tests)
- **Task 2**: 3 hours (5 subtasks)
- **Task 3**: 12 hours (4 integration tests)
- **Task 4**: 2 hours (documentation + deployment)

**Total**: ~22.5 hours (~3 days for one developer)

## Success Criteria

- [ ] All unit tests pass with >85% coverage
- [ ] All integration tests pass consistently
- [ ] No CDK Nag violations
- [ ] Documentation updated and reviewed
- [ ] Development deployment successful
- [ ] Message processing latency within acceptable range (<5 seconds)
- [ ] No message loss during or after deployment
- [ ] Retry mechanism working correctly (verified in logs)
- [ ] Loop-back mechanism processing buffered messages correctly
- [ ] Task token callbacks sent successfully (verified in CloudWatch logs)
