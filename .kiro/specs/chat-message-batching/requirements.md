# Requirements Document: Chat Message Batching

## Introduction

This feature enables the message processor Lambda to handle multiple messages
from the same sender in a single batch, combining them into a single AgentCore
Runtime invocation. This improves conversation coherence and reduces processing
overhead when users send multiple messages in quick succession.

## Glossary

- **Message_Processor**: Lambda function that processes messages from SQS queue
- **AgentCore_Runtime**: Amazon Bedrock AgentCore service that executes the chat
  agent
- **Sender**: User sending messages (identified by sender_id/phone number)
- **Batch**: Collection of SQS records processed together (up to 100 messages,
  3-second window)
- **Message_Group**: Subset of batch containing messages from the same sender
- **Conversation_ID**: Unique identifier for a conversation session (maps to
  AgentCore session_id)
- **Chat_Agent**: AgentCore application that processes user messages and
  maintains conversation state

## Requirements

### Requirement 1: Message Grouping

**User Story:** As a chat user, I want my rapid-fire messages to be processed
together, so that the assistant understands the complete context of what I'm
saying.

#### Acceptance Criteria

1. WHEN the Message_Processor receives a batch of messages THEN the system SHALL
   group messages by sender_id
2. WHEN messages are grouped by sender THEN the system SHALL preserve message
   order based on timestamp
3. WHEN a message group contains multiple messages THEN the system SHALL combine
   message content with newline separators
4. WHEN combining messages THEN the system SHALL track all individual
   message_ids for status updates
5. WHEN a batch contains messages from different senders THEN the system SHALL
   process each sender's messages as separate groups

### Requirement 2: AgentCore Runtime Invocation

**User Story:** As a system operator, I want to minimize AgentCore Runtime
invocations, so that we reduce costs and improve response coherence.

#### Acceptance Criteria

1. WHEN a message group is ready for processing THEN the system SHALL invoke
   AgentCore_Runtime once per sender
2. WHEN invoking AgentCore_Runtime THEN the system SHALL use the sender's
   conversation_id as the session identifier
3. WHEN multiple messages are combined THEN the system SHALL send them as a
   single prompt to AgentCore_Runtime
4. WHEN AgentCore_Runtime is processing a session THEN the system SHALL reject
   concurrent invocations for the same session
5. WHEN a concurrent invocation is rejected THEN the system SHALL return the
   message to the SQS queue for retry

### Requirement 3: Message Status Management

**User Story:** As a chat user, I want to see accurate delivery status for each
of my messages, so that I know they were received and processed.

#### Acceptance Criteria

1. WHEN a message group starts processing THEN the system SHALL mark all
   messages in the group as "delivered"
2. WHEN AgentCore_Runtime begins processing THEN the Chat_Agent SHALL mark all
   messages in the group as "read"
3. WHEN processing completes successfully THEN the system SHALL maintain "read"
   status for all messages
4. WHEN processing fails THEN the system SHALL mark all messages in the group as
   "failed"
5. WHEN a message is returned to queue due to concurrent invocation THEN the
   system SHALL not update its status

### Requirement 4: Error Handling and Retry

**User Story:** As a system operator, I want robust error handling for batched
messages, so that transient failures don't lose user messages.

#### Acceptance Criteria

1. WHEN a message group fails processing THEN the system SHALL report all
   message_ids in the group as failed items
2. WHEN SQS retries a message THEN the system SHALL reprocess it with the same
   grouping logic
3. WHEN a message exceeds retry limit THEN the system SHALL move it to the dead
   letter queue
4. WHEN processing a message group THEN the system SHALL log all message_ids for
   debugging
5. WHEN an error occurs during processing THEN the system SHALL log the error
   with context for all affected messages

### Requirement 5: Chat Agent Multi-Message Support

**User Story:** As a chat agent, I want to process multiple messages from a user
at once, so that I can provide coherent responses to their complete thought.

#### Acceptance Criteria

1. WHEN the Chat_Agent receives a combined prompt THEN the system SHALL process
   it as a single conversation turn
2. WHEN marking messages as read THEN the Chat_Agent SHALL accept a list of
   message_ids
3. WHEN the Chat_Agent sends a response THEN the system SHALL send it once for
   the entire message group
4. WHEN the Chat_Agent encounters an error THEN the system SHALL propagate it to
   mark all messages as failed
5. WHEN processing completes THEN the Chat_Agent SHALL maintain conversation
   history for the session

### Requirement 6: Batch Processing Configuration

**User Story:** As a system operator, I want to configure batch processing
parameters, so that I can optimize for message latency and throughput.

#### Acceptance Criteria

1. THE Message_Processor SHALL support SQS batch size up to 100 messages
2. THE Message_Processor SHALL support SQS batching window up to 5 seconds
3. WHEN batch size is configured THEN the system SHALL process all messages in
   the batch together
4. WHEN batching window expires THEN the system SHALL process available messages
   immediately
5. THE system SHALL log batch processing metrics including group count and
   message distribution

### Requirement 7: Platform Compatibility

**User Story:** As a system integrator, I want message batching to work with
both WhatsApp and simulated messaging backends, so that the feature works across
all platforms.

#### Acceptance Criteria

1. WHEN processing WhatsApp messages THEN the system SHALL group by sanitized
   phone number
2. WHEN processing simulated messages THEN the system SHALL group by sender_id
3. WHEN combining messages THEN the system SHALL preserve platform-specific
   metadata
4. WHEN sending responses THEN the system SHALL use the platform router for
   delivery
5. WHEN updating message status THEN the system SHALL use the platform router
   for both platforms
