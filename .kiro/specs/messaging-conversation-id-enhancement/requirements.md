# Requirements Document

## Introduction

This feature enhances the chatbot messaging backend to support optional
conversation IDs and adds a "new session" capability to the demo frontend. The
current system generates conversation IDs deterministically using the pattern
`senderId#recipientId`, but downstream services require UUID-based conversation
IDs. Additionally, users need the ability to start fresh conversations easily
through the demo interface.

## Requirements

### Requirement 1

**User Story:** As a downstream service, I want to receive UUID-based
conversation IDs, so that I can properly integrate with systems that expect UUID
identifiers.

#### Acceptance Criteria

1. WHEN a message is sent without a conversationId THEN the system SHALL
   generate a new UUID as the conversationId
2. WHEN a message is sent with a conversationId THEN the system SHALL use the
   provided conversationId
3. WHEN a conversationId is provided THEN the system SHALL validate it is a
   valid UUID format
4. WHEN an invalid conversationId format is provided THEN the system SHALL
   return a validation error
5. WHEN storing messages THEN the system SHALL use the UUID conversationId as
   the DynamoDB partition key

### Requirement 2

**User Story:** As a user of the messaging API, I want to optionally specify a
conversation ID when sending messages, so that I can control conversation
grouping and start new conversations.

#### Acceptance Criteria

1. WHEN sending a message THEN the API SHALL accept an optional conversationId
   parameter
2. WHEN no conversationId is provided THEN the system SHALL generate a new UUID
   conversationId
3. WHEN a conversationId is provided THEN the system SHALL use it for message
   storage and SNS publishing
4. WHEN the same conversationId is used across multiple messages THEN the system
   SHALL group them in the same conversation
5. WHEN retrieving messages by conversationId THEN the system SHALL return all
   messages for that UUID-based conversation

### Requirement 3

**User Story:** As a Python client using the messaging system, I want the
messaging client to support optional conversation IDs, so that I can control
conversation flow programmatically.

#### Acceptance Criteria

1. WHEN calling send_message THEN the client SHALL accept an optional
   conversation_id parameter
2. WHEN no conversation_id is provided THEN the client SHALL let the backend
   generate a UUID
3. WHEN a conversation_id is provided THEN the client SHALL include it in the
   API request
4. WHEN the API returns a conversationId THEN the client SHALL return it to the
   caller
5. WHEN retrieving conversation messages THEN the client SHALL support
   UUID-based conversation IDs

### Requirement 4

**User Story:** As a TypeScript client using the messaging system, I want the
messaging API client to support optional conversation IDs, so that I can manage
conversations in the frontend.

#### Acceptance Criteria

1. WHEN calling sendMessage THEN the client SHALL accept an optional
   conversationId parameter
2. WHEN no conversationId is provided THEN the client SHALL let the backend
   generate a UUID
3. WHEN a conversationId is provided THEN the client SHALL include it in the API
   request
4. WHEN the API returns a conversationId THEN the client SHALL return it to the
   caller
5. WHEN generating conversation IDs client-side THEN the client SHALL use UUID
   format for consistency

### Requirement 5

**User Story:** As a demo user, I want a "New Session" button in the chat
interface, so that I can easily start fresh conversations with the hotel
assistant.

#### Acceptance Criteria

1. WHEN viewing the chat interface THEN the system SHALL display a "New Session"
   button
2. WHEN clicking "New Session" THEN the system SHALL clear the current
   conversation messages from the UI
3. WHEN starting a new session THEN the system SHALL generate a new UUID
   conversationId for subsequent messages
4. WHEN starting a new session THEN the system SHALL reset any conversation
   state in the frontend
5. WHEN starting a new session THEN the system SHALL provide visual feedback
   that a new conversation has started

### Requirement 6

**User Story:** As a system maintaining backward compatibility, I want existing
conversation ID patterns to continue working, so that current integrations are
not broken.

#### Acceptance Criteria

1. WHEN retrieving messages with legacy conversationId format THEN the system
   SHALL continue to work
2. WHEN the system encounters legacy conversationId patterns THEN the system
   SHALL handle them gracefully
3. WHEN migrating to UUID-based IDs THEN the system SHALL not break existing
   stored conversations
4. WHEN both UUID and legacy formats exist THEN the system SHALL handle both
   correctly

### Requirement 7

**User Story:** As a developer, I want clear documentation and examples of the
new conversation ID functionality, so that I can integrate it correctly.

#### Acceptance Criteria

1. WHEN using the API THEN the system SHALL provide clear documentation for the
   optional conversationId parameter
2. WHEN implementing clients THEN the system SHALL provide code examples for
   both Python and TypeScript
3. WHEN testing the functionality THEN the system SHALL include comprehensive
   test cases for UUID conversation IDs
4. WHEN debugging issues THEN the system SHALL provide clear error messages for
   conversation ID validation failures

### Requirement 8

**User Story:** As a system administrator, I want proper logging for
conversation ID operations, so that I can monitor and troubleshoot conversation
management.

#### Acceptance Criteria

1. WHEN a new conversationId is generated THEN the system SHALL log the
   generation event
2. WHEN a conversationId is provided by the client THEN the system SHALL log the
   usage
3. WHEN conversationId validation fails THEN the system SHALL log the validation
   error with details
4. WHEN retrieving messages by conversationId THEN the system SHALL log the
   query operation
5. WHEN conversation operations succeed THEN the system SHALL log success with
   relevant identifiers
