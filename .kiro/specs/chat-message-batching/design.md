# Design Document: Chat Message Batching

## Overview

This design implements message batching for chat conversations, allowing the
message processor Lambda to group multiple messages from the same sender and
process them together in a single AgentCore Runtime invocation. This improves
conversation coherence when users send rapid-fire messages and reduces
processing overhead.

The design focuses on two main components:

1. **Message Processor Lambda** - Groups messages by sender and invokes
   AgentCore once per group
2. **Chat Agent** - Accepts multiple message IDs for status tracking

## Architecture

### High-Level Flow

```
SQS Batch (up to 100 messages, 3s window)
    ↓
Message Processor Lambda
    ↓
Group by sender_id
    ↓
For each sender group:
    - Combine message content
    - Mark all as "delivered"
    - Invoke AgentCore Runtime once
    ↓
Chat Agent
    - Mark all as "read"
    - Process combined prompt
    - Send single response
```

### Message Grouping Strategy

Messages are grouped using the following logic:

1. **Extract all messages** from SQS batch
2. **Parse each message** (WhatsApp or simulated format)
3. **Group by sender identifier**:
   - WhatsApp: sanitized phone number
   - Simulated: sender_id field
4. **Sort messages within each group** by timestamp
5. **Process each group independently**

### Concurrent Invocation Handling

AgentCore Runtime automatically rejects concurrent invocations for the same
session. When this occurs:

- AgentCore returns an error indicating concurrent access
- Lambda marks the invocation as failed (SQS batch item failure)
- SQS automatically retries the message after visibility timeout
- On retry, messages are regrouped and processed again

This is AgentCore's built-in behavior - we don't need to implement additional
logic.

## Components and Interfaces

### 1. Message Grouping Module

**Purpose**: Group messages by sender within an SQS batch

**Interface**:

```python
@dataclass
class MessageGroup:
    """Group of messages from the same sender.

    This is a lightweight wrapper around a list of MessageEvent objects,
    providing convenient access to derived properties without duplicating data.
    """
    messages: list[MessageEvent]

    @property
    def sender_id(self) -> str:
        """Get sender ID from first message."""
        return self.messages[0].sender_id

    @property
    def conversation_id(self) -> str:
        """Get conversation ID from first message."""
        return self.messages[0].conversation_id

    @property
    def combined_content(self) -> str:
        """Combine message content with newlines."""
        return "\n".join(msg.content for msg in self.messages)

    @property
    def message_ids(self) -> list[str]:
        """Get all message IDs."""
        return [msg.message_id for msg in self.messages]

    @property
    def platform(self) -> str:
        """Get platform from first message."""
        return self.messages[0].platform

def group_messages_by_sender(
    records: list[dict[str, Any]]
) -> list[MessageGroup]:
    """Group SQS records by sender.

    Args:
        records: List of SQS records from batch event

    Returns:
        List of MessageGroup objects, one per unique sender
    """
```

**Implementation Details**:

- Parse each SQS record to extract MessageEvent
- Use sender_id as grouping key
- Sort messages by timestamp within each group
- MessageGroup provides computed properties (no data duplication)
- All original MessageEvent data is preserved
- Sort messages by timestamp within each group
- Combine message content with newline separators
- Preserve all message IDs for status tracking
- Maintain platform-specific metadata

### 2. Batch Processing Handler

**Purpose**: Process message groups and invoke AgentCore

**Interface**:

```python
async def process_message_groups(
    groups: list[MessageGroup]
) -> dict[str, Any]:
    """Process all message groups in batch.

    Args:
        groups: List of message groups to process

    Returns:
        SQS batch response with failed item identifiers
    """
```

**Implementation Details**:

- Iterate through each message group
- Mark all messages in group as "delivered"
- Create single AgentCore invocation request with:
  - Combined prompt (all message content)
  - List of message IDs
  - Sender's conversation_id as session identifier
- Invoke AgentCore Runtime
- Handle success/failure for entire group
- Return failed message IDs to SQS if needed

### 3. Chat Agent Message Tracking

**Purpose**: Track multiple message IDs during processing

**Interface**:

```python
@app.async_task
async def process_user_message(
    user_message: str,
    actor_id: str,
    message_ids: list[str],  # Changed from single message_id
    conversation_id: str,
    model_id: str,
    temperature: float,
    session_id: str,
):
    """Process user message(s) with agent.

    Args:
        user_message: Combined message content
        actor_id: Sender identifier
        message_ids: List of message IDs in this group
        conversation_id: Conversation identifier
        model_id: Bedrock model identifier
        temperature: Model temperature
        session_id: Session identifier
    """
```

**Implementation Details**:

- Accept list of message IDs instead of single ID
- Mark all message IDs as "read" when processing starts
- Process combined message as single conversation turn
- Send single response for entire group
- On error, mark all message IDs as "failed"

### 4. AgentCore Invocation Request Model

**Purpose**: Updated request model to support multiple messages

**Interface**:

```python
class AgentCoreInvocationRequest(BaseModel):
    """Request model for AgentCore Runtime invocation."""
    prompt: str
    actorId: str
    messageIds: list[str]  # Changed from messageId
    conversationId: str
    modelId: Optional[str] = None
    temperature: Optional[float] = None
```

## Data Models

### MessageGroup

```python
@dataclass
class MessageGroup:
    """Lightweight wrapper for grouping messages from the same sender.

    Provides computed properties to avoid data duplication from MessageEvent.
    Location: virtual_assistant_common.models.messaging
    """
    messages: list[MessageEvent]

    @property
    def sender_id(self) -> str:
        return self.messages[0].sender_id

    @property
    def conversation_id(self) -> str:
        return self.messages[0].conversation_id

    @property
    def combined_content(self) -> str:
        return "\n".join(msg.content for msg in self.messages)

    @property
    def message_ids(self) -> list[str]:
        return [msg.message_id for msg in self.messages]

    @property
    def platform(self) -> str:
        return self.messages[0].platform
```

### Updated MessageEvent

No changes needed - existing MessageEvent model in
`virtual_assistant_common.models.messaging` supports all required fields.

### Updated AgentCoreInvocationRequest

```python
class AgentCoreInvocationRequest(BaseModel):
    """Request for AgentCore Runtime invocation.

    Location: virtual_assistant_common.models.messaging
    """
    prompt: str                 # Combined message content
    actorId: str               # Sender identifier
    messageIds: list[str]      # List of message IDs (was messageId)
    conversationId: str        # Session identifier
    modelId: Optional[str] = None
    temperature: Optional[float] = None
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all
valid executions of a system-essentially, a formal statement about what the
system should do. Properties serve as the bridge between human-readable
specifications and machine-verifiable correctness guarantees._

### Property 1: Message Grouping by Sender

_For any_ SQS batch containing messages, all messages with the same sender_id
should be grouped together into a single MessageGroup, and no messages from
different senders should appear in the same group.

**Validates: Requirements 1.1, 1.5**

### Property 2: Message Order Preservation

_For any_ MessageGroup, the messages within the group should be ordered by
timestamp in ascending order (earliest first).

**Validates: Requirements 1.2**

### Property 3: Message Content Combination

_For any_ MessageGroup with multiple messages, the combined_content should equal
the message contents joined with newline separators, preserving the order.

**Validates: Requirements 1.3**

### Property 4: Message ID Tracking

_For any_ MessageGroup, the message_ids list should contain exactly the message
IDs from all messages in the group, with no duplicates or omissions.

**Validates: Requirements 1.4**

### Property 5: Single Invocation Per Sender

_For any_ batch processing operation, each unique sender_id should result in
exactly one AgentCore Runtime invocation.

**Validates: Requirements 2.1**

### Property 6: Session Identifier Consistency

_For any_ AgentCore invocation, the session identifier passed to AgentCore
should equal the conversation_id from the message group.

**Validates: Requirements 2.2**

### Property 7: Combined Prompt Format

_For any_ message group with multiple messages, the prompt sent to AgentCore
should be the combined_content from the MessageGroup.

**Validates: Requirements 2.3**

### Property 8: Delivered Status for All Messages

_For any_ MessageGroup that begins processing, all message IDs in the group
should be marked with "delivered" status before AgentCore invocation.

**Validates: Requirements 3.1**

### Property 9: Read Status for All Messages

_For any_ message group processed by the Chat Agent, all message IDs should be
marked with "read" status when processing begins.

**Validates: Requirements 3.2**

### Property 10: Success Status Preservation

_For any_ message group that completes processing successfully, all message IDs
should maintain "read" status.

**Validates: Requirements 3.3**

### Property 11: Failed Status for All Messages

_For any_ message group that fails processing, all message IDs in the group
should be marked with "failed" status.

**Validates: Requirements 3.4**

### Property 12: Failed Items Reporting

_For any_ message group that fails processing, all message IDs from the group
should appear in the SQS batch response's batchItemFailures list.

**Validates: Requirements 4.1**

### Property 13: Grouping Idempotency

_For any_ message that is retried by SQS, it should be grouped with the same
sender's messages using the same grouping logic as the initial attempt.

**Validates: Requirements 4.2**

### Property 14: Message ID Logging

_For any_ message group being processed, the logs should contain all message IDs
from the group.

**Validates: Requirements 4.4**

### Property 15: Error Context Logging

_For any_ error during message group processing, the error log should include
context for all affected message IDs.

**Validates: Requirements 4.5**

### Property 16: Single Conversation Turn

_For any_ combined prompt sent to the Chat Agent, it should be processed as a
single conversation turn (one agent.stream_async call).

**Validates: Requirements 5.1**

### Property 17: Message ID List Acceptance

_For any_ list of message IDs (of any length > 0), the Chat Agent's
process_user_message function should accept it without error.

**Validates: Requirements 5.2**

### Property 18: Single Response Per Group

_For any_ message group processed by the Chat Agent, exactly one response should
be sent via platform_router.send_response.

**Validates: Requirements 5.3**

### Property 19: Error Propagation to All Messages

_For any_ error encountered by the Chat Agent during processing, all message IDs
in the group should be marked as "failed".

**Validates: Requirements 5.4**

### Property 20: Batch Size Support

_For any_ SQS batch with up to 100 messages, the Message Processor should
successfully process all messages without errors related to batch size.

**Validates: Requirements 6.1**

### Property 21: Complete Batch Processing

_For any_ SQS batch, all messages in the batch should be processed (either
successfully or marked as failed).

**Validates: Requirements 6.3**

### Property 22: Batch Metrics Logging

_For any_ batch processing operation, the logs should contain metrics including
the number of groups and message distribution across groups.

**Validates: Requirements 6.5**

### Property 23: WhatsApp Grouping by Phone

_For any_ batch containing WhatsApp messages, messages should be grouped by
sanitized phone number (sender_id with special characters removed).

**Validates: Requirements 7.1**

### Property 24: Simulated Message Grouping

_For any_ batch containing simulated messages, messages should be grouped by the
sender_id field.

**Validates: Requirements 7.2**

### Property 25: Message Data Preservation

_For any_ message group, all original MessageEvent objects should be preserved
in the messages list without modification.

**Validates: Requirements 7.3**

### Property 26: Platform Router for Responses

_For any_ response sent by the Chat Agent, it should be sent using
platform_router.send_response.

**Validates: Requirements 7.4**

### Property 27: Platform Router for Status Updates

_For any_ message status update, it should be performed using
platform_router.update_message_status for both WhatsApp and simulated platforms.

**Validates: Requirements 7.5**

## Error Handling

### Message Parsing Errors

- **Scenario**: Invalid JSON or malformed message in SQS record
- **Handling**:
  - Log error with record details
  - Mark record as failed in batch response
  - SQS will retry based on retry policy

### AgentCore Invocation Errors

- **Scenario**: AgentCore Runtime returns error (including concurrent access)
- **Handling**:
  - Log error with all message IDs in group
  - Mark all messages in group as "failed"
  - Return all message IDs as failed items in batch response
  - SQS will retry the messages

### Platform Router Errors

- **Scenario**: Failed to send response or update status
- **Handling**:
  - Log error with context
  - Continue processing (don't fail entire batch)
  - Status updates are best-effort

### Partial Batch Failures

- **Scenario**: Some message groups succeed, others fail
- **Handling**:
  - Process all groups independently
  - Return only failed message IDs in batch response
  - SQS will retry only the failed messages

## Testing Strategy

### Unit Tests

1. **Message Grouping**:
   - Test grouping with single sender
   - Test grouping with multiple senders
   - Test empty batch handling
   - Test message ordering within groups

2. **Content Combination**:
   - Test single message (no combination needed)
   - Test multiple messages with newlines
   - Test empty message content handling

3. **Status Updates**:
   - Test marking multiple messages as delivered
   - Test marking multiple messages as read
   - Test marking multiple messages as failed

4. **Error Handling**:
   - Test parsing errors
   - Test AgentCore errors
   - Test platform router errors

### Property-Based Tests

Each correctness property should be implemented as a property-based test with
minimum 100 iterations. Tests should:

- Generate random batches with varying numbers of messages
- Generate random sender IDs and message content
- Verify properties hold across all generated inputs
- Use appropriate generators for timestamps, IDs, and content

### Integration Tests

1. **End-to-End Batch Processing**:
   - Send batch with multiple senders to Lambda
   - Verify correct grouping and invocations
   - Verify status updates for all messages

2. **AgentCore Integration**:
   - Test actual AgentCore invocations with combined prompts
   - Verify conversation history is maintained
   - Test concurrent invocation handling

3. **Platform Integration**:
   - Test with WhatsApp messages
   - Test with simulated messages
   - Verify platform router integration

## Performance Considerations

### Batch Size Impact

- Larger batches (up to 100 messages) reduce Lambda invocations
- More messages per sender = fewer AgentCore invocations
- Trade-off: Larger batches increase processing time per Lambda invocation

### Memory Usage

- Each MessageGroup holds full message content in memory
- 100 messages × ~1KB average = ~100KB per batch
- Well within Lambda memory limits

### Latency

- Batching window (3 seconds) adds latency for first message
- Subsequent messages in window have reduced latency
- Overall: Better throughput, slightly higher latency for first message

## Deployment Considerations

### CDK Configuration Updates

Update `message_processing_construct.py`:

```python
# Update SQS event source configuration
self.lambda_function.add_event_source(
    lambda_event_sources.SqsEventSource(
        self.processing_queue,
        batch_size=100,  # Increased from 10
        max_batching_window=Duration.seconds(3),  # Increased from 5
        report_batch_item_failures=True,
    )
)
```

### Environment Variables

No new environment variables required - existing configuration supports
batching.

## Migration Strategy

### Phase 1: Add Grouping Logic

- Implement message grouping module
- Update Lambda handler to group messages
- Keep single-message processing for now
- Deploy and monitor

### Phase 2: Update Chat Agent

- Update Chat Agent to accept message ID lists
- Update status tracking for multiple IDs
- Deploy and test with single-message groups

### Phase 3: Enable Multi-Message Processing

- Update Lambda to invoke AgentCore with combined prompts
- Update batch size and window configuration
- Deploy and monitor metrics

### Phase 4: Optimize

- Tune batch size and window based on observed behavior
- Optimize grouping algorithm if needed
