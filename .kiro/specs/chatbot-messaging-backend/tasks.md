# Implementation Plan

- [x] 1. Create Python package structure for chatbot messaging backend
  - Create new Python package directory `packages/chatbot-messaging-backend/`
  - Set up pyproject.toml with dependencies for Lambda Powertools, boto3, and
    testing
  - Create basic package structure with handlers, models, and utils modules
  - _Requirements: 7.1, 7.2_

- [ ] 2. Implement core data models and utilities
  - [x] 2.1 Create message data model with validation
    - Define Message dataclass with all required fields (messageId,
      conversationId, senderId, recipientId, content, status, timestamps)
    - Implement validation methods for message content and status values
    - Create utility functions for generating UUIDs and ISO8601 timestamps
    - _Requirements: 1.1, 2.1, 5.1_

  - [x] 2.2 Create DynamoDB repository layer
    - Implement MessageRepository class with methods for create, update, and
      query operations
    - Add method to store new messages with conversationId as partition key and
      timestamp as sort key
    - Add method to update message status by messageId using GSI
    - Add method to query messages by conversationId with timestamp filtering
    - Write unit tests for MessageRepository methods with mocked DynamoDB
    - Write integration tests for MessageRepository methods with actual DynamoDB
    - _Requirements: 1.1, 2.2, 4.1, 4.2_

  - [x] 2.3 Implement SNS publishing utilities
    - Create SNSPublisher class to handle message publishing to SNS topic
    - Format messages according to SNS message structure specification
    - Add error handling for SNS publishing failures
    - Write unit tests for SNSPublisher methods with mocked SNS topic
    - Write integration tests for SNSPublisher methods with actual SNS topic
    - _Requirements: 1.3_

- [ ] 3. Create Lambda handler with APIGatewayRestResolver
  - [x] 3.1 Set up APIGatewayRestResolver with basic structure
    - Create main lambda handler file with APIGatewayRestResolver setup
    - Configure AWS Lambda Powertools logger
    - Implement basic error handling and response formatting
    - Add environment variable configuration for table name and SNS topic ARN
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 3.2 Implement POST /messages endpoint
    - Create send_message handler function with @app.post decorator
    - Extract senderId from JWT token claims
    - Validate request body (recipientId and content)
    - Generate conversationId using senderId#recipientId pattern
    - Store message in DynamoDB with status "sent"
    - Publish message to SNS topic
    - Return message details in response
    - Write unit tests for send_message handler with various input scenarios
    - _Requirements: 1.1, 1.2, 1.3, 3.1, 3.2, 3.3, 5.1, 5.2_

  - [x] 3.3 Implement PUT /messages/{messageId}/status endpoint
    - Create update_message_status handler function with @app.put decorator
    - Validate messageId parameter and status in request body
    - Look up message by messageId using GSI
    - Update message status and updatedAt timestamp in DynamoDB
    - Return updated message status in response
    - Write unit tests for update_message_status handler with valid and invalid
      inputs
    - _Requirements: 2.1, 2.2_

  - [x] 3.3.1 Refactor business logic from Lambda handlers to service layer
    - Create `services/message_service.py` module to contain business logic
    - Extract send_message business logic from Lambda handler to
      MessageService.send_message()
    - Extract update_message_status business logic from Lambda handler to
      MessageService.update_message_status()
    - Refactor Lambda handlers to be thin wrappers that handle HTTP concerns
      (request/response parsing, JWT extraction, error handling)
    - Update existing unit tests to test service layer methods directly
    - Create new unit tests for Lambda handlers that focus on HTTP-specific
      logic
    - Ensure service layer methods are framework-agnostic and easier to test
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3_

  - [x] 3.4 Implement GET /conversations/{conversationId}/messages endpoint
    - Create get_messages handler function with @app.get decorator
    - Extract and validate conversationId parameter
    - Parse optional query parameters (since timestamp, limit)
    - Query messages from DynamoDB using conversationId and timestamp filter
    - Return paginated list of messages with hasMore indicator
    - Write unit tests for get_messages handler with different query parameters
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 3.5 Create integration tests for MessageService
    - Create test_message_service_integration.py with @pytest.mark.integration
      decorator
    - Set up real DynamoDB table and SNS topic for integration testing
    - Test complete send_message flow with real AWS services (no mocks)
    - Test update_message_status flow with real DynamoDB operations
    - Test get_messages flow with real DynamoDB queries and pagination
    - Test error scenarios with real AWS service failures
    - Verify SNS message publishing with actual SNS topic
    - Clean up test data after each test to ensure test isolation
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 4.1, 4.2, 4.3, 4.4_

- [ ] 4. Create CDK infrastructure stack
  - [x] 4.1 Create new CDK stack file for messaging backend
    - Create `packages/infra/stack/messaging_stack.py`
    - Define MessagingStack class extending Stack
    - Set up basic stack structure with imports and initialization
    - _Requirements: 7.1_

  - [x] 4.2 Implement Cognito User Pool for authentication
    - Create Cognito User Pool with support for username/password authentication
    - Configure User Pool Client for user authentication
    - Add App Client for machine-to-machine authentication (client credentials)
    - Configure JWT token settings and claims
    - Create Secrets Manager secret to store chatbot client credentials
    - _Requirements: 6.1, 6.2_

  - [x] 4.3 Create DynamoDB table and GSI
    - Define DynamoDB table with conversationId as partition key and timestamp
      as sort key
    - Create Global Secondary Index (MessageIdIndex) with messageId as partition
      key
    - Configure auto-scaling for read and write capacity
    - Set up on demand billing mode
    - _Requirements: 1.1, 2.2_

  - [x] 4.4 Set up SNS topic and Lambda function
    - Create SNS topic for message publishing
    - Define Lambda function with appropriate runtime, memory, and timeout
      settings
    - Configure environment variables for DynamoDB table name and SNS topic ARN
    - Set up IAM permissions for DynamoDB read/write and SNS publish
    - _Requirements: 1.3, 6.1_

  - [x] 4.5 Create API Gateway with Cognito authorization
    - Set up REST API Gateway with Cognito User Pool authorizer
    - Configure API Gateway to integrate with Lambda function
    - Set up proper CORS configuration for web clients
    - Define API Gateway deployment and stage
    - _Requirements: 7.1, 7.2_

- [ ] 5. Write comprehensive tests
  - [ ] 5.1 Create unit tests for data models and utilities
    - Test Message dataclass validation and serialization
    - Test MessageRepository methods with mocked DynamoDB
    - Test SNSPublisher with mocked SNS service
    - Test utility functions for UUID generation and timestamp formatting
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

  - [ ] 5.2 Create unit tests for Lambda handlers
    - Test send_message handler with various input scenarios
    - Test update_message_status handler with valid and invalid inputs
    - Test get_messages handler with different query parameters
    - Mock JWT token extraction and validation
    - Test error handling for all endpoints
    - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 6.2, 6.3_

  - [ ] 5.3 Create integration tests for API endpoints
    - Test complete API flow with real DynamoDB and SNS (using moto)
    - Test authentication with mock Cognito JWT tokens
    - Test conversation flow from message creation to status updates
    - Test message polling with timestamp filtering
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 4.1, 4.2, 4.3, 4.4_

- [ ] 6. Update project configuration and documentation
  - [x] 6.1 Add NX project configuration
    - Create `packages/chatbot-messaging-backend/project.json` with package and
      test targets
    - Configure NX to include the new package in workspace operations
    - Set up proper dependencies between messaging backend and other packages
    - _Requirements: 7.4_

  - [x] 6.2 Create package documentation
    - Write README.md with API documentation and usage examples
    - Document authentication flow for both user and machine clients
    - Provide example requests and responses for all endpoints
    - Document deployment and configuration steps
    - _Requirements: 7.3_

  - [x] 6.3 Update main CDK app to include messaging stack
    - Modify `packages/infra/app.py` to instantiate MessagingStack
    - Configure stack dependencies so Hotel Assistant stack can use SNS topic
    - Export SNS topic ARN as stack output for cross-stack reference
    - Export Secrets Manager secret ARN for chatbot client credentials access
    - _Requirements: 7.1_

- [x] 7. Create end-to-end tests using deployed ChatbotMessagingStack resources
  - Create test_end_to_end.py with @pytest.mark.e2e decorator for deployed stack
    testing
  - Create fixtures to retrieve CloudFormation stack outputs (DynamoDB table,
    API endpoint, SNS topic, Cognito details)
  - Create fixture to get machine-to-machine credentials from Secrets Manager
  - Create fixture to create test user in Cognito User Pool with
    cryptographically secure password
  - Create SQS queue fixture that subscribes to the SNS topic for message
    verification
  - Implement complete conversation flow test:
    1. User and hotel assistant authenticate with Cognito (both user credentials
       and client credentials flows)
    2. User sends message to hotel assistant via POST /messages endpoint
    3. Hotel assistant receives message notification via SQS (subscribed to SNS
       topic)
    4. Hotel assistant marks message as "delivered" via PUT
       /messages/{messageId}/status endpoint 4a. User polls for latest messages
       via GET /conversations/{conversationId}/messages and verifies "delivered"
       status
    5. Hotel assistant marks message as "read" via PUT
       /messages/{messageId}/status endpoint 5a. User polls for latest messages
       and verifies "read" status
    6. Hotel assistant sends reply message to user via POST /messages endpoint
       6a. User polls for latest messages and sees the reply message
    7. User sends another message to hotel assistant
    8. Verify all messages share the same conversationId pattern
       (senderId#recipientId)
  - Clean up test data and resources after each test run
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4,
    6.1, 6.2_
