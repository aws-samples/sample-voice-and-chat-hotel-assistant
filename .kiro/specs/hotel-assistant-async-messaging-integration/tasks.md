# Implementation Plan

- [x] 1. Create hotel-assistant-messaging-lambda package structure
  - Create package directory at
    `packages/hotel-assistant/hotel-assistant-messaging-lambda`
  - Set up pyproject.toml with dependencies (boto3, aws-lambda-powertools,
    httpx)
  - Create NX project.json with same targets as chatbot-messaging-backend
  - Set up basic package structure with handlers, services, models, and tests
    directories
  - _Requirements: 2.1, 2.2_

- [x] 2. Add shared message models to hotel-assistant-common
  - Create `hotel_assistant_common/models/messaging.py` with MessageEvent and
    related models
  - Add platform interfaces in `hotel_assistant_common/platforms/` with base,
    web, twilio, and aws_eum modules
  - Create messaging client in
    `hotel_assistant_common/clients/messaging_client.py`
  - Update hotel-assistant-common pyproject.toml with new dependencies (httpx,
    pydantic)
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Create platform abstraction stubs
  - Implement web platform messaging in
    `hotel_assistant_common/platforms/web.py`
  - Create Twilio platform stub with process_incoming_message,
    update_message_status, and send_response methods
  - Create AWS EUM platform stub with same interface methods
  - Add platform routing logic to handle different message sources
    (implementation stubs only)
  - Document platform integration points for future implementation
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 4. Implement message processor Lambda handler
  - Create `hotel_assistant_messaging_lambda/handlers/message_processor.py` with
    SQS batch processing
  - Implement SNS message parsing from SQS records using
    chatbot-messaging-backend Message format
  - Add boto3 AgentCore Runtime client integration with IAM authentication
  - Implement message status updates using shared messaging client
  - Add proper error handling and logging with AWS Lambda Powertools
  - _Requirements: 2.3, 2.4, 4.1, 4.2, 4.3_

- [x] 5. Update AgentCore Runtime for async processing
  - Modify `hotel_assistant_chat/agent.py` to use `@app.async_task` decorator
  - Implement immediate message status update to "read" when agent starts
    processing
  - Add Strands async streaming with `agent.stream_async()` for non-blocking
    operations
  - Integrate shared messaging client for sending responses
  - Add error handling that sends generic error messages to users
  - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6. Create SQS queue and Lambda integration in backend stack
  - Add SQS queue creation in backend stack that subscribes to existing SNS
    topic
  - Configure dead letter queue with 3 retry attempts for failed message
    processing
  - Create Lambda function deployment with proper IAM permissions for SQS and
    AgentCore Runtime
  - Add SQS event source to Lambda function with batch processing configuration
  - Set environment variables for AgentCore Runtime ARN and messaging API
    endpoint
  - **COMPLETED**: Implemented SNS message filtering to only process messages
    intended for hotel assistant (recipientId filter)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 9.1, 9.2, 9.3, 9.4_

- [x] 7. Implement Lambda packaging and deployment
  - Add package target to hotel-assistant-messaging-lambda project.json
  - Create Lambda deployment package with ARM64 architecture for performance
  - Update backend stack to deploy Lambda function from packaged zip file
  - Configure Lambda timeout (30 seconds) and memory (128MB) for lightweight
    queue processing
  - Test Lambda deployment and basic SQS message consumption
  - _Requirements: 2.2, 9.5_

- [ ] 8. Test end-to-end message flow
  - Test web interface message sending through existing
    chatbot-messaging-backend(packages/chatbot-messaging-backend/tests/test_end_to_end.py)
  - Verify SNS message publishing and SQS queue message delivery
  - Test Lambda function invocation and AgentCore Runtime integration
  - Verify message status updates (sent → delivered → read) through the pipeline
  - Test agent response sending back through messaging API
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ] 9. Implement error handling and retry logic
  - Test Lambda function error scenarios with SQS default retry behavior
  - Configure and test dead letter queue for permanently failed messages
  - Test AgentCore Runtime error handling with generic error message sending
  - Verify proper logging and monitoring through CloudWatch
  - Test message processing failure scenarios and recovery
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 9. Add comprehensive testing
  - Write unit tests for message processor Lambda handler with mocked
    dependencies
  - Create integration tests for SQS message processing and AgentCore Runtime
    invocation
  - Test shared messaging client functionality in different contexts
  - Add tests for platform interface stubs and message routing
  - Test error scenarios and dead letter queue functionality
  - _Requirements: 2.5, 10.4_

- [ ] 10. Update IAM policies and security
  - Configure Lambda IAM role with least-privilege permissions for SQS and
    specific AgentCore Runtime
  - Set up SigV4 authentication for AgentCore Runtime API calls
  - Ensure proper encryption for SQS messages and Lambda environment variables
  - Test IAM authentication and verify access restrictions
  - Document security configuration and access patterns
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 11. Performance optimization and monitoring
  - Configure SQS batch processing (10 messages per batch) for efficient Lambda
    invocation
  - Set appropriate Lambda memory allocation and timeout based on agent
    processing requirements
  - Add CloudWatch metrics and alarms for message processing pipeline
  - Test performance with multiple concurrent messages and agent processing
  - Optimize cold start performance with ARM64 architecture and minimal
    dependencies
  - _Requirements: 9.5_

- [ ] 12. Documentation and deployment guide
  - Document the async messaging architecture and message flow
  - Create deployment instructions for the new Lambda function and SQS queue
  - Document platform integration patterns for future Twilio and AWS EUM
    implementation
  - Add troubleshooting guide for common message processing issues
  - Update system architecture documentation with async processing capabilities
  - _Requirements: 8.5_
