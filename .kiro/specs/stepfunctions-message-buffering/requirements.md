# Requirements Document: Step Functions Message Buffering

## Introduction

This feature implements a robust message buffering system using AWS Step
Functions to orchestrate message collection from the same sender before
processing them together in a single AgentCore Runtime invocation. Step
Functions manages the buffering window and retry logic, providing deterministic
batching with configurable timing.

## Glossary

- **Message_Handler_Lambda**: Lambda function triggered by SNS that adds
  messages to Step Functions workflow
- **Batcher_Step_Function**: Step Functions workflow that manages message
  buffering and batching
- **Message_Buffer**: DynamoDB table storing messages temporarily per user
- **AgentCore_Runtime**: Amazon Bedrock AgentCore service that executes the chat
  agent
- **Sender**: User sending messages (identified by user_id/phone number)
- **Message_Group**: Collection of messages from the same sender buffered
  together
- **Buffering_Window**: Time window (2 seconds) for collecting additional
  messages
- **Waiting_State**: Step Functions state indicating an active buffering window
  for a user
- **Chat_Agent**: AgentCore application that processes user messages
- **SNS_Topic**: Topic receiving WhatsApp messages from AWS EUM Social

## Requirements

### Requirement 1: Message Reception and Workflow Initiation

**User Story:** As a chat user, I want my messages to be received immediately,
so that the system can start processing them.

#### Acceptance Criteria

1. WHEN a message arrives via SNS THEN the Message_Handler_Lambda SHALL be
   invoked
2. WHEN the Lambda receives a message THEN it SHALL write the message to the
   Message_Buffer
3. WHEN writing to the buffer THEN the Lambda SHALL check if a workflow is
   already waiting for this user
4. WHEN no workflow is waiting THEN the Lambda SHALL start a new
   Batcher_Step_Function execution
5. WHEN a workflow is already waiting THEN the Lambda SHALL return success
   without starting a new workflow

### Requirement 2: Step Functions Buffering Workflow

**User Story:** As a system operator, I want Step Functions to manage the
buffering window, so that message collection is deterministic and reliable.

#### Acceptance Criteria

1. WHEN the workflow starts THEN it SHALL set the waiting state for the user
2. AFTER setting waiting state THEN the workflow SHALL wait for the configured
   buffering window (2 seconds)
3. AFTER the wait period THEN the workflow SHALL check if more messages arrived
4. WHEN more messages arrived THEN the workflow SHALL check the age of the
   latest message
5. WHEN the latest message is within the window THEN the workflow SHALL wait
   again

### Requirement 3: Message Age and Window Management

**User Story:** As a system operator, I want the buffering window to extend when
new messages arrive, so that rapid-fire messages are collected together.

#### Acceptance Criteria

1. WHEN checking message age THEN the workflow SHALL get the timestamp of the
   latest message
2. WHEN the latest message age is less than the buffering window THEN the
   workflow SHALL continue waiting
3. WHEN the latest message age exceeds the buffering window THEN the workflow
   SHALL proceed to invoke AgentCore
4. THE workflow SHALL set the user's state to "not waiting" before invoking
   AgentCore
5. THE buffering window SHALL be configurable via environment variable

### Requirement 4: Message Batch Retrieval and Processing

**User Story:** As a system operator, I want to retrieve all buffered messages
safely, so that no messages are lost during retries.

#### Acceptance Criteria

1. WHEN ready to process THEN the workflow SHALL mark messages as "processing"
   in the buffer
2. WHEN messages are marked as processing THEN new messages SHALL be added with
   "processing" = false
3. WHEN messages are marked as processing THEN the workflow SHALL combine their
   content with newline separators
4. WHEN messages are marked as processing THEN the workflow SHALL collect all
   message IDs for status tracking
5. WHEN AgentCore invocation succeeds THEN the workflow SHALL delete the
   processed messages from the buffer

### Requirement 5: AgentCore Runtime Invocation

**User Story:** As a system operator, I want to minimize AgentCore Runtime
invocations, so that we reduce costs and improve response coherence.

#### Acceptance Criteria

1. WHEN invoking AgentCore THEN the workflow SHALL pass the combined message
   content
2. WHEN invoking AgentCore THEN the workflow SHALL pass all message IDs for
   status tracking
3. WHEN invoking AgentCore THEN the workflow SHALL use the user's session_id
4. WHEN AgentCore invocation succeeds THEN the workflow SHALL complete
   successfully
5. WHEN AgentCore invocation fails THEN the workflow SHALL retry according to
   retry policy

### Requirement 6: Error Handling and Retry

**User Story:** As a system operator, I want robust error handling with
configurable retries, so that transient failures don't lose user messages.

#### Acceptance Criteria

1. WHEN AgentCore invocation fails THEN Step Functions SHALL retry with
   exponential backoff
2. THE first retry SHALL wait 15 seconds
3. THE second retry SHALL wait 30 seconds
4. THE third retry SHALL wait 60 seconds
5. WHEN all retries are exhausted THEN the workflow SHALL send the event to a
   dead letter queue

### Requirement 7: Concurrent Workflow Prevention

**User Story:** As a system operator, I want to prevent multiple workflows for
the same user, so that messages are not processed out of order.

#### Acceptance Criteria

1. WHEN a message arrives THEN the Lambda SHALL check the user's waiting state
   in DynamoDB
2. WHEN the user has a waiting workflow THEN the Lambda SHALL not start a new
   workflow
3. WHEN the user has no waiting workflow THEN the Lambda SHALL set the waiting
   state and start a workflow
4. THE waiting state check and set SHALL be atomic
5. WHEN a workflow completes THEN it SHALL clear the user's waiting state

### Requirement 8: Message Status Management

**User Story:** As a chat user, I want to see accurate delivery status for each
of my messages, so that I know they were received and processed.

#### Acceptance Criteria

1. WHEN messages are buffered THEN the system SHALL mark them as "delivered"
2. WHEN AgentCore begins processing THEN the Chat_Agent SHALL mark all messages
   as "read"
3. WHEN processing completes successfully THEN all messages SHALL maintain
   "read" status
4. WHEN processing fails THEN all messages in the group SHALL be marked as
   "failed"
5. THE status updates SHALL use the platform router for both WhatsApp and
   simulated platforms

### Requirement 9: DynamoDB Buffer Management

**User Story:** As a system operator, I want efficient buffer management, so
that the system scales and cleans up automatically.

#### Acceptance Criteria

1. WHEN creating buffer entries THEN the system SHALL set TTL to 10 minutes from
   creation
2. WHEN TTL expires THEN DynamoDB SHALL automatically delete the entry
3. THE buffer table SHALL use on-demand billing mode
4. THE buffer table SHALL have point-in-time recovery enabled
5. THE buffer table SHALL be partitioned by user_id

### Requirement 10: Step Functions Workflow Observability

**User Story:** As a system operator, I want visibility into workflow execution,
so that I can monitor and debug the system.

#### Acceptance Criteria

1. WHEN a workflow executes THEN Step Functions SHALL log all state transitions
2. WHEN a workflow fails THEN Step Functions SHALL log the error details
3. THE workflow SHALL emit CloudWatch metrics for execution count and duration
4. THE workflow SHALL support X-Ray tracing for distributed tracing
5. THE workflow execution history SHALL be retained for debugging

### Requirement 11: Scalability and Concurrency

**User Story:** As a system operator, I want the system to handle multiple
concurrent users efficiently, so that it scales with demand.

#### Acceptance Criteria

1. WHEN multiple users send messages simultaneously THEN each user SHALL have an
   independent workflow
2. WHEN a single user sends multiple messages THEN only one workflow SHALL be
   active per user
3. THE Lambda SHALL have no reserved concurrency (auto-scaling)
4. THE DynamoDB table SHALL scale automatically with on-demand mode
5. THE Step Functions SHALL handle concurrent executions for different users
