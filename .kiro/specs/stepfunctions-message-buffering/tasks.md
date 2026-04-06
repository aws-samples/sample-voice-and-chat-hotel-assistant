# Implementation Plan: Step Functions Message Buffering

## Overview

This implementation adds Step Functions-based message buffering to replace the
inconsistent SQS batching approach. Messages are buffered in DynamoDB with a
2-second window, and Step Functions orchestrates the batching logic using
JSONata transformations and a processing flag for retry safety.

## Tasks

- [x] 1. Implement Message Handler Lambda
  - [x] 1.1 Create message handler function
    - Parse SNS message to extract MessageEvent (reuse existing parsing)
    - Write message to DynamoDB buffer with `processing = false`
    - Store full MessageEvent object using model_dump()
    - Set session_id, last_update_time, and ttl
    - _Requirements: 1.2_

  - [x] 1.2 Implement atomic workflow initiation
    - Check waiting_state in DynamoDB
    - Use conditional update to set waiting_state = true
    - Start Step Functions workflow with user_id if condition succeeds
    - Return success if workflow already running
    - _Requirements: 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4_

  - [x] 1.3 Write property tests for message handler
    - **Property 1: Message Buffer Write** - All messages written to buffer
    - **Property 2: Waiting State Check** - Check happens before workflow start
    - **Property 3: Conditional Workflow Start** - Workflow starts when not
      waiting
    - **Property 4: No Duplicate Workflows** - No workflow when already waiting
    - **Property 5: Waiting State Atomicity** - Only one Lambda sets waiting
      state
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4_

- [x] 2. Implement Mark Messages As Processing Lambda
  - Get all messages from buffer
  - Filter to non-processing messages
  - Update each message to set `processing = true` in DynamoDB
  - Return the messages that were marked
  - _Requirements: 4.1_

- [x] 2.1 Write property tests for marking messages
  - **Property 11: Messages Marked as Processing** - Non-processing messages
    marked
  - _Requirements: 4.1_

- [x] 3. Implement Delete Processed Messages Lambda
  - Get current buffer from DynamoDB
  - Filter out messages where `processing = true`
  - If remaining messages exist, update buffer
  - If no remaining messages, delete buffer entry
  - _Requirements: 4.5_

- [x] 3.1 Write property tests for deleting messages
  - **Property 12: Delete Only After Success** - Only processing messages
    deleted
  - **Property 13: Messages Retained on Failure** - Processing messages stay on
    failure
  - _Requirements: 4.5_

- [x] 4. Implement Invoke AgentCore Lambda
  - [x] 4.1 Create invoke function
    - Mark all messages as "delivered" using platform router
    - Create AgentCoreInvocationRequest (reuse existing model)
    - Invoke AgentCore using AgentCoreClient (reuse existing client)
    - Raise AgentCoreSessionBusyError if session busy
    - Return success response
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1_

  - [x] 4.2 Write property tests for AgentCore invocation
    - **Property 16: Combined Content Passed to AgentCore** - Content passed
      correctly
    - **Property 17: Message IDs Passed to AgentCore** - All IDs passed
    - **Property 18: Session ID Used** - Session ID used correctly
    - **Property 19: Workflow Completes on Success** - Success path works
    - **Property 20: Retry on Failure** - Retries happen without deleting
      messages
    - **Property 21: Delivered Status** - Messages marked delivered
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 8.1_

- [x] 5. Implement Handle Failure Lambda
  - Mark all processing messages as "failed" using platform router
  - Log error details with all message IDs
  - Leave messages in buffer for manual cleanup (TTL will clean up)
  - _Requirements: 7.5_

- [x] 6. Create CDK infrastructure for message buffering
  - [x] 6.1 Create DynamoDB message buffer table
    - Define table with user_id partition key
    - Enable TTL on ttl attribute
    - Configure on-demand billing mode
    - Enable point-in-time recovery
    - _Requirements: 9.1, 9.3, 9.4, 9.5_

  - [x] 6.2 Define Step Functions state machine (state-machine.json)
    - SetWaitingState: Update DynamoDB to set waiting_state = true
    - WaitForMessages: Wait 2 seconds
    - GetMessages: Get item from DynamoDB (non-destructive)
    - CheckMessageAge: Use JSONata to check age of non-processing messages
    - DecideNextAction: Choice state based on should_wait
    - ClearWaitingState: Update DynamoDB to set waiting_state = false
    - MarkMessagesAsProcessing: Call Lambda to mark messages
    - PrepareAgentCoreInvocation: Use JSONata to combine processing messages
    - InvokeAgentCore: Invoke Lambda with retry policy
    - DeleteProcessedMessages: Call Lambda to delete processed messages
    - HandleFailure: Handle errors and mark messages as failed
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 4.1, 4.3, 4.4,
      5.5_

  - [x] 6.3 Add JSONata expressions in state machine
    - Message age calculation in CheckMessageAge state (filter non-processing,
      calculate age)
    - Message content combination in PrepareAgentCoreInvocation state (filter
      processing, join with newlines)
    - Message ID extraction in PrepareAgentCoreInvocation state (filter
      processing, extract IDs)
    - _Requirements: 3.1, 3.2, 3.3, 4.3, 4.4_

  - [x] 6.4 Configure retry policy for AgentCore invocation
    - ErrorEquals: ["AgentCoreSessionBusyError"]
    - IntervalSeconds: 15
    - MaxAttempts: 3
    - BackoffRate: 2.0 (gives 15s, 30s, 60s)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 6.5 Configure workflow timeout and DLQ
    - Set workflow timeout to 5 minutes
    - Configure dead letter queue for failed executions
    - _Requirements: 6.5_

  - [x] 6.6 Create MessageBufferingConstruct
    - Create DynamoDB table (from 6.1)
    - Create Message Handler Lambda
    - Create Mark Messages As Processing Lambda
    - Create Delete Processed Messages Lambda
    - Create Invoke AgentCore Lambda (reuse existing logic)
    - Create Handle Failure Lambda
    - Create Step Functions state machine from state-machine.json (from 6.2)
    - Grant necessary IAM permissions
    - Subscribe Message Handler Lambda to SNS topic
    - Remove SQS queue subscription
    - Configure Lambda async invocation settings (2 retries)
    - Configure dead letter queue for Lambda
    - _Requirements: All infrastructure, 1.1_

  - [x] 6.7 Update VirtualAssistantStack
    - Replace MessageProcessingConstruct with MessageBufferingConstruct
    - Remove SQS queue and related resources
    - Update environment variables
    - _Requirements: All infrastructure_

  - [ ]\* 6.8 Write property tests for workflow and JSONata
    - **Property 6: Workflow Sets Waiting State** - Waiting state set at start
    - **Property 7: Message Age Check** - Age checked correctly with JSONata
    - **Property 8: Conditional Wait Loop** - Loops when messages arriving
    - **Property 9: Processing Decision** - Proceeds when window expired
    - **Property 10: Waiting State Cleared Before Processing** - State cleared
      before marking
    - **Property 14: Message Content Combination with JSONata** - Content
      combined correctly
    - **Property 15: Message ID Collection with JSONata** - IDs extracted
      correctly
    - **Property 22: TTL Set on Buffer Entries** - TTL set to 10 minutes
    - **Property 25: Waiting State Cleared on Completion** - State cleared on
      completion
    - _Requirements: 2.1, 2.3, 2.5, 3.1, 3.2, 3.3, 3.4, 4.3, 4.4, 7.5, 9.1_

- [x] 7. Refactor state machine to use CDK constructs
  - [x] 7.1 Read CDK Step Functions documentation
    - Review
      https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_stepfunctions/README.html
    - Review
      https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_stepfunctions_tasks/README.html
    - Review
      https://docs.aws.amazon.com/step-functions/latest/dg/transforming-data.html
      (JSONata in Step Functions)
    - Understand JSONata support in CDK (Pass.jsonata(), Choice.jsonata(), etc.)
    - Understand how to build state machines using CDK constructs
    - _Requirements: All infrastructure_

  - [x] 7.2 Refactor MessageBufferingConstruct to use CDK state machine
        constructs
    - Remove JSON file loading and string replacement approach
    - Use sfn.Pass.jsonata() for CheckMessageAge and PrepareAgentCoreInvocation
      states
    - Use sfn.Choice.jsonata() for DecideNextAction state
    - Use tasks.DynamoUpdateItem for SetWaitingState and ClearWaitingState
    - Use tasks.DynamoGetItem for GetMessages
    - Use tasks.LambdaInvoke for all Lambda function calls
    - Use sfn.Wait for WaitForMessages
    - Set queryLanguage=sfn.QueryLanguage.JSONATA at state machine level
    - Build state machine using .next() chaining pattern
    - Use sfn.DefinitionBody.from_chainable() to create definition
    - _Requirements: All infrastructure_

  - [x] 7.3 Test refactored state machine
    - Run CDK synth to verify no errors
    - Run CDK diff to verify changes as expected
    - Deploy and verify state machine works correctly
    - Fixed JSONata expression errors:
      - Changed from ternary operator to direct `and` expression
      - Used `$toMillis()` for timestamp conversion
      - Ensured proper boolean evaluation for should_wait
    - _Requirements: All infrastructure_

  - [x] 7.4 Add retry preparation logic
    - Create PrepareRetry Lambda to unmark messages and reset waiting state
    - Add CheckRetryLimit choice state to check retry count < 3
    - Add CalculateRetryWait pass state to calculate exponential backoff (15s,
      30s, 60s)
    - Add WaitBeforeRetry wait state with dynamic wait time
    - Update InvokeAgentCore catch to route session busy errors to PrepareRetry
    - Route other errors directly to HandleFailure
    - Retry from ClearWaitingState after PrepareRetry to re-evaluate buffering
      window
    - _Requirements: 5.5, 6.1, 6.2, 6.3, 6.4_

- [ ] 8. Integration testing
  - [ ] 8.1 Test single message flow
    - Send single message
    - Verify workflow starts and completes
    - Verify AgentCore invocation
    - Verify message deleted after success
    - _Requirements: All_

  - [ ] 8.2 Test rapid-fire messages
    - Send 4 messages in quick succession
    - Verify single workflow processes all messages
    - Verify messages combined correctly
    - Verify all messages deleted after success
    - _Requirements: 1.1, 1.2, 1.3, 2.3, 2.4, 2.5, 4.5_

  - [ ] 8.3 Test messages during retry
    - Send 2 messages
    - Simulate AgentCore session busy (triggers retry)
    - Send 2 more messages during retry wait
    - Verify original 2 messages stay in buffer with processing=true
    - Verify new 2 messages added with processing=false
    - Verify retry processes original 2 messages
    - Verify new 2 messages processed in next batch
    - _Requirements: 4.1, 4.5, 5.5, 6.1, 6.2, 6.3, 6.4_

  - [ ] 8.4 Test concurrent users
    - Send messages from multiple users simultaneously
    - Verify independent workflows
    - Verify no cross-user interference
    - _Requirements: 11.1, 11.2_

  - [ ] 8.5 Test error scenarios
    - Test invalid message formats
    - Test DynamoDB errors
    - Test workflow timeouts
    - Test all retries exhausted
    - _Requirements: 6.5, 7.5_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests
- Each property test should run minimum 100 iterations
- Integration tests require deployed infrastructure
- Reuse existing models and clients from chat-message-batching spec:
  - MessageEvent
  - MessageGroup
  - AgentCoreInvocationRequest
  - AgentCoreClient
- JSONata expressions in Step Functions eliminate need for separate
  transformation Lambdas
- Processing flag ensures no message loss during retries
- Step Functions handles all orchestration with configurable retry timing
- Task 6 groups all CDK infrastructure work (DynamoDB, Step Functions, Lambdas,
  SNS subscription)
