# Requirements Document

## Introduction

This feature integrates the hotel-assistant-chat with the
chatbot-messaging-backend to enable asynchronous message processing using Amazon
Bedrock AgentCore Runtime and Strands agents. The system will support multiple
messaging platforms including the current web interface, with stubs for future
AWS End User Messaging Social and Twilio integration. The architecture uses
SNS/SQS for reliable message delivery and implements async task processing for
improved user experience.

## Requirements

### Requirement 1

**User Story:** As a system architect, I want to integrate hotel-assistant-chat
with the chatbot-messaging-backend, so that messages flow through a reliable
SNS/SQS architecture with proper message status tracking.

#### Acceptance Criteria

1. WHEN a user sends a message through the web interface THEN it SHALL be
   processed by the chatbot-messaging-backend API
2. WHEN the backend receives a message THEN it SHALL publish to an SNS topic for
   agent processing
3. WHEN an SQS queue receives a message THEN it SHALL trigger a Lambda function
   to invoke the AgentCore Runtime
4. WHEN the agent processes a message THEN it SHALL update message status to
   "read" and send responses back through the messaging API
5. WHEN message status changes THEN it SHALL be tracked through the entire
   pipeline (sent → delivered → read)

### Requirement 2

**User Story:** As a developer, I want to create a new Lambda package for
auxiliary messaging functions, so that message processing is handled by
dedicated serverless functions with proper error handling.

#### Acceptance Criteria

1. WHEN creating the auxiliary package THEN it SHALL be located at
   `packages/hotel-assistant/hotel-assistant-messaging-lambda`
2. WHEN the package is configured THEN it SHALL have the same NX targets as
   `packages/chatbot-messaging-backend/project.json`
3. WHEN the Lambda function is deployed THEN it SHALL consume messages from the
   SQS queue
4. WHEN processing messages THEN it SHALL invoke the AgentCore Runtime using IAM
   authentication (SigV4)
5. WHEN errors occur THEN it SHALL implement proper retry logic and dead letter
   queue handling

### Requirement 3

**User Story:** As a developer, I want to add message types and models to
hotel-assistant-common, so that all messaging components share consistent data
structures.

#### Acceptance Criteria

1. WHEN message models are defined THEN they SHALL be located in
   `packages/hotel-assistant/hotel-assistant-common`
2. WHEN message types are created THEN they SHALL support the messaging
   backend's message format
3. WHEN SNS message formats are defined THEN they SHALL include all necessary
   metadata for agent processing
4. WHEN message status enums are created THEN they SHALL match the
   chatbot-messaging-backend status values
5. WHEN conversation context is modeled THEN it SHALL support both web and
   future messaging platform contexts

### Requirement 4

**User Story:** As a developer, I want to update the AgentCore Runtime to use
IAM authentication, so that it integrates securely with AWS services without
OAuth complexity.

#### Acceptance Criteria

1. WHEN the AgentCore Runtime is configured THEN it SHALL use IAM roles instead
   of OAuth for authentication
2. WHEN the Lambda function invokes AgentCore THEN it SHALL use SigV4 signing
   for API requests
3. WHEN IAM policies are created THEN they SHALL follow least-privilege
   principles
4. WHEN the runtime is accessed THEN it SHALL validate IAM credentials properly
5. WHEN authentication fails THEN it SHALL return appropriate error responses

### Requirement 5

**User Story:** As a user, I want the agent to provide immediate feedback during
long operations, so that I know the system is processing my request.

#### Acceptance Criteria

1. WHEN the agent starts processing a message THEN it SHALL immediately mark the
   message as "read"
2. WHEN the agent will perform time-consuming operations THEN it SHALL send an
   intermediate message like "Please give me a moment"
3. WHEN the agent invokes tools or external services THEN it SHALL use Strands
   async mode for non-blocking processing
4. WHEN the agent determines it needs to send additional messages THEN it SHALL
   use the messaging API to communicate with the user
5. WHEN processing completes THEN it SHALL send the final response through the
   messaging API

### Requirement 6

**User Story:** As a developer, I want to implement Strands async processing, so
that the agent can handle long-running operations without blocking the response
pipeline.

#### Acceptance Criteria

1. WHEN the agent is initialized THEN it SHALL use the `@app.async_task`
   decorator for background operations
2. WHEN tool invocations are made THEN they SHALL run asynchronously using
   `asyncio.create_task()`
3. WHEN the agent starts background work THEN it SHALL return an immediate
   acknowledgment to the user
4. WHEN async tasks complete THEN they SHALL send results through the messaging
   API
5. WHEN the AgentCore Runtime reports status THEN it SHALL use "HealthyBusy"
   during background processing

### Requirement 7

**User Story:** As a developer, I want to create infrastructure for SNS/SQS
message flow, so that the messaging backend integrates with the agent processing
pipeline.

#### Acceptance Criteria

1. WHEN the messaging backend publishes to SNS THEN it SHALL use the existing
   SNS topic from the messaging stack
2. WHEN the SQS queue is created THEN it SHALL subscribe to the SNS topic with
   proper filtering
3. WHEN the Lambda function is deployed THEN it SHALL have appropriate IAM
   permissions for SQS and AgentCore
4. WHEN dead letter queues are configured THEN they SHALL handle failed message
   processing

### Requirement 8

**User Story:** As a developer, I want to prepare stubs for future messaging
platforms, so that Twilio and AWS End User Messaging Social can be integrated
later without architectural changes.

#### Acceptance Criteria

1. WHEN messaging platform interfaces are defined THEN they SHALL support
   multiple channel types (web, SMS, WhatsApp, etc.)
2. WHEN message routing is implemented THEN it SHALL handle different
   platform-specific message formats
3. WHEN Twilio stubs are created THEN they SHALL include webhook handling and
   response formatting
4. WHEN AWS End User Messaging Social stubs are created THEN they SHALL include
   proper event handling
5. WHEN platform abstraction is implemented THEN it SHALL allow easy addition of
   new messaging channels

### Requirement 9

**User Story:** As a developer, I want to update the infrastructure stack to
support the new messaging architecture, so that all components are properly
deployed and configured.

#### Acceptance Criteria

1. WHEN the backend stack is updated THEN it SHALL include SQS queue and Lambda
   function resources (SNS topic already exists)
2. WHEN IAM roles are created THEN they SHALL provide appropriate permissions
   for AgentCore Runtime access
3. WHEN environment variables are configured THEN they SHALL include all
   necessary endpoints and identifiers
4. WHEN the stack is deployed THEN it SHALL integrate with the existing
   chatbot-messaging-backend
5. WHEN monitoring is configured THEN it SHALL provide visibility into the
   entire message processing pipeline

### Requirement 10

**User Story:** As a developer, I want to implement proper error handling and
retry logic, so that message processing is reliable and failures are handled
gracefully.

#### Acceptance Criteria

1. WHEN Lambda function errors occur THEN they SHALL follow the default SQS
   retry behavior with Lambda
2. WHEN AgentCore Runtime is unavailable THEN messages SHALL be queued for retry
3. WHEN message processing fails permanently THEN messages SHALL be sent to dead
   letter queue
4. WHEN errors are logged THEN they SHALL include sufficient context for
   debugging
5. WHEN users experience errors THEN they SHALL receive appropriate feedback
   through the messaging interface
