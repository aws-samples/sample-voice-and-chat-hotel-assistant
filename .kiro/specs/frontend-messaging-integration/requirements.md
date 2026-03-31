# Requirements Document

## Introduction

This feature updates the frontend chat interface to integrate with the new
chatbot messaging backend instead of directly communicating with AgentCore
runtime. The frontend will authenticate users through Cognito, send messages via
REST API, and implement real-time message polling with status indicators. The
system will support conversation history, message status tracking, and
configurable AI model parameters.

## Requirements

### Requirement 1: Configuration Integration

**User Story:** As a developer, I want the frontend to load messaging backend
configuration from config.js or environment variables, so that the application
can connect to the correct endpoints.

#### Acceptance Criteria

1. WHEN the frontend loads THEN it SHALL read configuration from
   window.APP_CONFIG (production) or import.meta.env (development)
2. WHEN configuration is loaded THEN it SHALL include messaging API endpoint,
   messaging Cognito User Pool details, and hotel assistant client ID
3. WHEN the custom resource updates config.js THEN it SHALL include the new
   messaging backend configuration properties
4. WHEN configuration properties are missing THEN the system SHALL display clear
   error messages indicating missing configuration

### Requirement 2: Authentication Token Management

**User Story:** As a user, I want the system to automatically manage
authentication tokens with the messaging backend, so that I can securely send
and receive messages.

#### Acceptance Criteria

1. WHEN making API calls THEN the system SHALL obtain an access token with
   "chatbot-messaging/write" scope
2. WHEN making API calls THEN the system SHALL include the Bearer token in
   Authorization headers
3. WHEN tokens expire THEN the system SHALL automatically refresh them using
   existing Amplify authentication
4. WHEN authentication is invalid THEN the system SHALL handle errors gracefully
   using existing Amplify error handling

### Requirement 3: TanStack Query Integration

**User Story:** As a developer, I want to use TanStack Query for API state
management, so that the application has efficient caching, loading states, and
error handling.

#### Acceptance Criteria

1. WHEN the application initializes THEN it SHALL configure TanStack Query with
   appropriate cache settings
2. WHEN API calls are made THEN the system SHALL use TanStack Query mutations
   for POST requests and queries for GET requests
3. WHEN data is cached THEN the system SHALL implement appropriate stale time
   and cache invalidation strategies
4. WHEN errors occur THEN TanStack Query SHALL provide structured error handling
   and retry mechanisms

### Requirement 4: Message Sending

**User Story:** As a user, I want to send messages to the hotel assistant using
the messaging backend API, so that I can have conversations with the AI
assistant.

#### Acceptance Criteria

1. WHEN a user submits a message THEN the system SHALL call POST /messages with
   recipientId set to hotel assistant client ID
2. WHEN sending a message THEN the system SHALL include modelId and temperature
   parameters from existing UI controls
3. WHEN a message is sent successfully THEN it SHALL be immediately added to the
   local message list with "sent" status
4. WHEN message sending fails THEN the system SHALL display error messages and
   allow retry
5. WHEN a message is sent THEN the system SHALL generate a conversation ID using
   user's Cognito username and hotel assistant client ID in lexicographical
   order

### Requirement 5: Message Retrieval and History

**User Story:** As a user, I want to view my conversation history with the hotel
assistant, so that I can reference previous interactions.

#### Acceptance Criteria

1. WHEN a conversation loads THEN the system SHALL call GET
   /conversations/{conversationId}/messages with timestamp from past 24 hours
2. WHEN messages are retrieved THEN they SHALL be displayed in chronological
   order with newest at bottom
3. WHEN there are older messages THEN the system SHALL display a "Load older
   messages" button at the top
4. WHEN "Load older messages" is clicked THEN the system SHALL retrieve the most
   recent 100 messages since unix epoch sorted newest to oldest
5. WHEN loading older messages THEN the system SHALL maintain scroll position
   and prepend messages to the list

### Requirement 6: Real-time Message Polling

**User Story:** As a user, I want to receive assistant responses in real-time,
so that the conversation feels natural and responsive.

#### Acceptance Criteria

1. WHEN a message is sent successfully THEN the system SHALL start polling for
   new messages every 5 seconds
2. WHEN polling for messages THEN the system SHALL use the timestamp of the sent
   message as the "since" parameter
3. WHEN new messages are received THEN they SHALL replace any local placeholder
   messages with matching IDs
4. WHEN no new messages are found THEN the system SHALL continue polling until a
   response is received or timeout occurs
5. WHEN polling encounters errors THEN the system SHALL implement exponential
   backoff and retry logic

### Requirement 7: Message Status Indicators

**User Story:** As a user, I want to see the delivery status of my messages, so
that I know when they have been sent, delivered, and read.

#### Acceptance Criteria

1. WHEN a message has "sent" status THEN it SHALL display a single grey
   checkmark icon
2. WHEN a message has "delivered" status THEN it SHALL display two grey
   checkmark icons
3. WHEN a message has "read" status THEN it SHALL display two green checkmark
   icons
4. WHEN a message has "failed" status THEN it SHALL display an error icon with
   red color
5. WHEN message status updates are received THEN the icons SHALL update
   automatically without page refresh

### Requirement 8: Conversation ID Generation

**User Story:** As a system, I want to generate consistent conversation IDs, so
that messages are properly grouped and retrieved.

#### Acceptance Criteria

1. WHEN generating a conversation ID THEN it SHALL use the format
   "userId#assistantId" where userId is the Cognito username
2. WHEN the user ID and assistant ID are provided THEN they SHALL be sorted
   lexicographically and separated by "#"
3. WHEN the conversation ID is used in API calls THEN it SHALL be URL-encoded
   for safe transmission
4. WHEN retrieving messages THEN the same conversation ID generation logic SHALL
   be used consistently

### Requirement 9: Error Handling and User Experience

**User Story:** As a user, I want clear error messages and graceful degradation
when issues occur, so that I understand what went wrong and can take appropriate
action.

#### Acceptance Criteria

1. WHEN API calls fail THEN the system SHALL display user-friendly error
   messages
2. WHEN network connectivity is lost THEN the system SHALL indicate offline
   status and queue messages for retry
3. WHEN the messaging backend is unavailable THEN the system SHALL display
   maintenance messages
4. WHEN rate limits are exceeded THEN the system SHALL display appropriate wait
   time messages
5. WHEN validation errors occur THEN the system SHALL display specific
   field-level error messages

### Requirement 10: Message Timestamp Filtering

**User Story:** As a system, I want to efficiently retrieve messages using
timestamp filtering, so that API calls are optimized and pagination works
correctly.

#### Acceptance Criteria

1. WHEN retrieving recent messages THEN the system SHALL use "since" parameter
   with timestamp from 24 hours ago
2. WHEN loading older messages THEN the system SHALL use "since" parameter with
   unix epoch timestamp
3. WHEN the API supports "until" parameter THEN the system SHALL use it for
   bounded time range queries
4. WHEN timestamp filtering is applied THEN the system SHALL handle timezone
   conversions correctly
5. WHEN no timestamp is provided THEN the API SHALL return the most recent
   messages by default

### Requirement 11: Loading States and UI Feedback

**User Story:** As a user, I want visual feedback during loading operations, so
that I understand when the system is processing my requests.

#### Acceptance Criteria

1. WHEN sending a message THEN the system SHALL show a loading indicator on the
   send button
2. WHEN loading conversation history THEN the system SHALL display skeleton
   loading states for messages
3. WHEN polling for new messages THEN the system SHALL show a subtle indicator
   of background activity
4. WHEN loading older messages THEN the system SHALL show a loading spinner on
   the "Load older" button
5. WHEN operations complete THEN all loading indicators SHALL be removed and
   content SHALL be displayed
