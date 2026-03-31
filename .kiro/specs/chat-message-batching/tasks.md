# Implementation Plan: Chat Message Batching

## Overview

This implementation adds message batching support to the chat messaging system,
allowing multiple messages from the same sender to be grouped and processed
together in a single AgentCore Runtime invocation.

## Tasks

- [x] 1. Update shared models in virtual-assistant-common
  - Add MessageGroup dataclass to virtual_assistant_common.models.messaging
  - Update AgentCoreInvocationRequest to use messageIds (list) instead of
    messageId
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 1.1 Write property tests for MessageGroup
  - **Property 2: Message Order Preservation** - Messages within group ordered
    by timestamp
  - **Property 3: Message Content Combination** - Combined content equals
    messages joined with newlines
  - **Property 4: Message ID Tracking** - All message IDs present with no
    duplicates
  - **Property 25: Message Data Preservation** - Original MessageEvent objects
    preserved
  - _Requirements: 1.2, 1.3, 1.4, 7.3_

- [x] 2. Implement message grouping and batch processing in message processor
     Lambda
  - [x] 2.1 Create group_messages_by_sender function
    - Parse SQS records to extract MessageEvent objects
    - Group messages by sender_id
    - Sort messages within each group by timestamp
    - Return list of MessageGroup objects
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 2.2 Modify lambda_handler to use message grouping
    - Call group_messages_by_sender on batch records
    - Iterate through message groups instead of individual records
    - Track failed message IDs per group
    - Return batch item failures for SQS
    - _Requirements: 2.1, 4.1, 6.3_

  - [x] 2.3 Update \_process_message_async to handle message groups
    - Accept MessageGroup instead of single MessageEvent
    - Mark all messages in group as "delivered"
    - Create AgentCore invocation with combined content and all message IDs
    - Handle success/failure for entire group
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.3, 3.4_

  - [x] 2.4 Write property tests for message grouping and batch processing
    - **Property 1: Message Grouping by Sender** - Same sender_id grouped
      together
    - **Property 5: Single Invocation Per Sender** - One invocation per unique
      sender
    - **Property 8: Delivered Status for All Messages** - All messages marked
      delivered
    - **Property 11: Failed Status for All Messages** - All messages marked
      failed on error
    - **Property 12: Failed Items Reporting** - All message IDs in
      batchItemFailures
    - **Property 13: Grouping Idempotency** - Retried messages grouped
      consistently
    - **Property 21: Complete Batch Processing** - All messages processed or
      failed
    - **Property 23: WhatsApp Grouping by Phone** - WhatsApp messages grouped by
      sanitized phone
    - **Property 24: Simulated Message Grouping** - Simulated messages grouped
      by sender_id
    - _Requirements: 1.1, 1.2, 1.5, 2.1, 3.1, 3.4, 4.1, 4.2, 6.3, 7.1, 7.2_

- [x] 3. Verify platform router supports multiple message IDs
  - Test update_message_status with multiple message IDs
  - Ensure both WhatsApp and simulated platforms work
  - Add any needed updates to platform router
  - _Requirements: 7.5_

- [x] 3.1 Write property tests for platform integration
  - **Property 26: Platform Router for Responses** - Responses use
    platform_router
  - **Property 27: Platform Router for Status Updates** - Status updates use
    platform_router
  - _Requirements: 7.4, 7.5_

- [x] 4. Update Chat Agent to support multiple message IDs
  - [x] 4.1 Modify process_user_message signature
    - Change message_id parameter to message_ids (list)
    - Update all references to use message_ids list
    - _Requirements: 5.2_

  - [x] 4.2 Update message status tracking
    - Mark all message IDs as "read" when processing starts
    - Use platform_router.update_message_status for each ID
    - Handle errors by marking all IDs as "failed"
    - _Requirements: 3.2, 3.4, 5.4_

  - [x] 4.3 Update invoke entrypoint
    - Parse messageIds from payload (list instead of single ID)
    - Pass message_ids list to process_user_message
    - _Requirements: 5.2_

  - [x] 4.4 Write property tests for multi-message processing
    - **Property 9: Read Status for All Messages** - All messages marked read
    - **Property 16: Single Conversation Turn** - Combined prompt processed as
      one turn
    - **Property 17: Message ID List Acceptance** - Function accepts any list
      length > 0
    - **Property 18: Single Response Per Group** - One response sent per group
    - **Property 19: Error Propagation to All Messages** - All messages marked
      failed on error
    - _Requirements: 3.2, 5.1, 5.2, 5.3, 5.4_

- [x] 5. Update CDK infrastructure configuration
  - Update message_processing_construct.py SQS event source
  - Change batch_size from 10 to 100
  - Change max_batching_window from 5 seconds to 3 seconds
  - _Requirements: 6.1, 6.3_

- [x] 6. Add logging for message groups
  - [x] 6.1 Log message group details
    - Log number of groups in batch
    - Log message IDs for each group
    - Log sender_id for each group (sanitized)
    - _Requirements: 4.4, 6.5_

  - [x] 6.2 Log error context for groups
    - Include all message IDs when logging errors
    - Include group context in error messages
    - _Requirements: 4.5_

  - [x] 6.3 Write property tests for logging
    - **Property 14: Message ID Logging** - Logs contain all message IDs
    - **Property 15: Error Context Logging** - Error logs include all affected
      IDs
    - **Property 22: Batch Metrics Logging** - Logs contain group count and
      distribution
    - _Requirements: 4.4, 4.5, 6.5_

- [ ] 7. Integration testing
  - [ ] 7.1 Test end-to-end batch processing
    - Send batch with multiple senders
    - Verify correct grouping and invocations
    - Verify status updates for all messages
    - _Requirements: All_

  - [ ] 7.2 Test error scenarios
    - Test AgentCore invocation failures
    - Test platform router failures
    - Test partial batch failures
    - _Requirements: 4.1, 4.2, 4.5_

  - [ ] 7.3 Test platform compatibility
    - Test with WhatsApp messages
    - Test with simulated messages
    - Test mixed batches
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests
- Each property test should run minimum 100 iterations
- Integration tests require deployed infrastructure
- Task 2 combines message grouping and batch processing for cohesive
  implementation
- Task 3 (platform router verification) moved earlier to ensure compatibility
  before chat agent updates
- Message grouping is the core functionality - implement and test thoroughly
  before moving to other tasks
- Chat agent changes are independent and can be developed in parallel with
  Lambda changes
