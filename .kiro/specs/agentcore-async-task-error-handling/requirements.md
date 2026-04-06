# Requirements Document: AgentCore Async Task Error Handling

## Introduction

This feature implements proper error handling and retry logic for AgentCore
async task failures. Currently, when the `process_user_message` async task fails
after the entrypoint returns success, messages are incorrectly deleted by the
Step Functions workflow. This spec restores the retry capability that was lost
during the migration from SQS-based message processing to Step Functions-based
message buffering.

## Glossary

- **AgentCore_Runtime**: Amazon Bedrock AgentCore service that executes the chat
  agent
- **Async_Task**: Background task started by `@app.async_task` decorator that
  processes messages
- **Entrypoint**: Main `invoke()` function that receives AgentCore invocations
  and returns immediately
- **Message_Buffer**: DynamoDB table storing messages temporarily per user
- **Step_Functions_Workflow**: State machine that orchestrates message buffering
  and batching
- **Processing_Flag**: Boolean flag on messages indicating they are being
  processed
- **Task_Callback**: Mechanism to detect async task failures and propagate
  errors
- **Retry_Policy**: Configuration for retrying failed message processing
- **Message_Status**: Status of a message (delivered, read, failed)
- **Platform_Router**: Service for updating message status across platforms

## Requirements

### Requirement 1: Async Task Error Detection

**User Story:** As a system operator, I want to detect when async task
processing fails, so that messages are not incorrectly deleted.

#### Acceptance Criteria

1. WHEN an async task raises an exception, THEN THE System SHALL detect the
   failure
2. WHEN an async task fails, THEN THE System SHALL capture the error details
3. WHEN an async task fails, THEN THE System SHALL prevent the workflow from
   deleting messages
4. THE Error_Detection SHALL work for all exception types
5. THE Error_Detection SHALL not block the Entrypoint from returning

### Requirement 2: Prevent Concurrent Workflows During Async Processing

**User Story:** As a system operator, I want to prevent multiple workflows for
the same user while async task is processing, so that messages are processed in
order and not lost.

#### Acceptance Criteria

1. WHEN an Async_Task is processing, THEN THE Processing_Flag SHALL remain true
2. WHEN new messages arrive during async processing, THEN THE System SHALL
   buffer them without starting a new workflow
3. WHEN an Async_Task completes successfully, THEN THE Processing_Flag SHALL be
   cleared
4. WHEN an Async_Task fails, THEN THE Processing_Flag SHALL remain true for
   retry
5. THE System SHALL maintain a single workflow per user at all times

### Requirement 3: Error Propagation to Step Functions

**User Story:** As a system operator, I want async task failures to be
communicated to Step Functions, so that the workflow can handle retries
properly.

#### Acceptance Criteria

1. WHEN an Async_Task fails, THEN THE System SHALL notify the
   Step_Functions_Workflow
2. WHEN notifying the workflow, THEN THE System SHALL include error details
3. WHEN notifying the workflow, THEN THE System SHALL include the user_id for
   message identification
4. THE notification SHALL happen asynchronously without blocking other
   operations
5. THE notification SHALL use a reliable delivery mechanism

### Requirement 4: Message Retention on Failure

**User Story:** As a chat user, I want my messages to be retried when processing
fails, so that I don't lose my messages due to transient errors.

#### Acceptance Criteria

1. WHEN an Async_Task fails, THEN messages SHALL remain in the Message_Buffer
   with processing flag set to true
2. WHEN messages remain in buffer, THEN they SHALL be available for retry
3. WHEN messages are retained, THEN their Message_Status SHALL be marked as
   "failed"
4. THE System SHALL not delete messages until processing succeeds
5. THE System SHALL preserve message order during retries

### Requirement 5: Retry Logic with Exponential Backoff

**User Story:** As a system operator, I want failed message processing to be
retried with exponential backoff, so that transient errors can be recovered
automatically.

#### Acceptance Criteria

1. WHEN an Async_Task fails, THEN THE System SHALL retry processing
2. THE first retry SHALL wait 2 seconds
3. THE second retry SHALL wait 4 seconds
4. THE third retry SHALL wait 8 seconds
5. THE System SHALL retry up to 6 times before giving up

### Requirement 6: Retry State Management

**User Story:** As a system operator, I want retry state to be managed properly,
so that retries don't interfere with new messages.

#### Acceptance Criteria

1. WHEN preparing for retry, THEN THE System SHALL unmark processing messages
2. WHEN preparing for retry, THEN THE System SHALL reset the Processing_Flag
3. WHEN new messages arrive during retry, THEN they SHALL be added to the
   Message_Buffer
4. WHEN retry completes, THEN new messages SHALL be processed in the next batch
5. THE Retry_Policy SHALL be tracked per user

### Requirement 7: Final Failure Handling

**User Story:** As a system operator, I want to know when message processing
fails permanently, so that I can investigate and take corrective action.

#### Acceptance Criteria

1. WHEN all retries are exhausted, THEN THE System SHALL mark messages as
   permanently failed
2. WHEN messages are permanently failed, THEN they SHALL remain in
   Message_Buffer for manual review
3. WHEN messages are permanently failed, THEN THE System SHALL log detailed
   error information
4. WHEN messages are permanently failed, THEN THE System SHALL send a
   notification
5. THE TTL SHALL eventually clean up permanently failed messages

### Requirement 8: Task Token Callback Implementation

**User Story:** As a developer, I want Step Functions to wait for async task
completion, so that messages are only deleted after successful processing.

#### Acceptance Criteria

1. WHEN invoking AgentCore_Runtime, THEN THE Step_Functions_Workflow SHALL pass
   a Task_Callback token to the Lambda
2. WHEN the Lambda starts an Async_Task, THEN it SHALL pass the Task_Callback
   token to the task
3. WHEN the Lambda returns, THEN THE Step_Functions_Workflow SHALL wait for
   Task_Callback
4. WHEN an Async_Task completes successfully, THEN it SHALL send success
   callback with token
5. WHEN an Async_Task fails, THEN it SHALL send failure callback with token and
   error details

### Requirement 9: Step Functions Wait for Task Token

**User Story:** As a system operator, I want Step Functions to wait for async
task completion, so that the workflow proceeds only after processing finishes.

#### Acceptance Criteria

1. WHEN InvokeAgentCore state executes, THEN it SHALL use waitForTaskToken
   integration pattern
2. WHEN waiting for token, THEN THE Step_Functions_Workflow SHALL pause workflow
   execution
3. WHEN success callback received, THEN THE Step_Functions_Workflow SHALL
   proceed to DeleteProcessedMessages
4. WHEN failure callback received, THEN THE Step_Functions_Workflow SHALL
   proceed to PrepareRetry
5. WHEN no callback received within timeout, THEN THE Step_Functions_Workflow
   SHALL fail the execution

### Requirement 9: Async Task Callback Mechanism

**User Story:** As a developer, I want async tasks to send callbacks to Step
Functions, so that workflow can resume after processing completes.

#### Acceptance Criteria

1. WHEN async task completes successfully THEN it SHALL call SendTaskSuccess
   with token
2. WHEN async task fails THEN it SHALL call SendTaskFailure with token and error
3. THE callback SHALL include user_id and message_ids for tracking
4. THE callback SHALL be sent before marking messages as failed
5. THE callback SHALL handle network errors and retry sending

### Requirement 9.5: Loop Back for Continuous Processing

**User Story:** As a system operator, I want the workflow to automatically
process new messages that arrived during processing, so that a single workflow
handles all messages until the user is idle.

#### Acceptance Criteria

1. WHEN DeleteProcessedMessages completes THEN the workflow SHALL loop back to
   GetMessages
2. WHEN GetMessages finds new messages THEN the workflow SHALL continue
   processing them
3. WHEN GetMessages finds no messages THEN the workflow SHALL proceed to
   ClearWaitingState
4. WHEN ClearWaitingState executes THEN it SHALL set waiting_state to false and
   exit
5. THE workflow SHALL continue looping until no messages remain

### Requirement 9.6: Graceful Exit When No Messages

**User Story:** As a system operator, I want the workflow to exit cleanly when
no messages remain, so that resources are freed and new messages can start a new
workflow.

#### Acceptance Criteria

1. WHEN GetMessages finds no messages THEN it SHALL transition to
   ClearWaitingState
2. WHEN ClearWaitingState executes THEN it SHALL update DynamoDB to set
   waiting_state = false
3. WHEN waiting_state is cleared THEN the workflow SHALL exit successfully
4. WHEN a new message arrives after exit THEN it SHALL start a new workflow
5. THE exit SHALL be clean with no orphaned state

### Requirement 10: Monitoring and Observability

**User Story:** As a system operator, I want visibility into async task failures
and retries, so that I can monitor system health.

#### Acceptance Criteria

1. WHEN an async task fails THEN the system SHALL log the error with context
2. WHEN a retry is triggered THEN the system SHALL log the retry attempt
3. WHEN retries are exhausted THEN the system SHALL emit a metric
4. THE logs SHALL include user_id, message_ids, and error details
5. THE logs SHALL sanitize sensitive information
