# Implementation Plan

- [x] 1. Enhance DynamoDB construct with quotes table
  - Add quotes table to `HotelPMSDynamoDBConstruct` with TTL configuration
  - Update environment variables and grant methods for quotes table access
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Update availability service for DynamoDB quote storage
  - Modify `SimplifiedAvailabilityService` to store quotes in DynamoDB
  - Implement quote generation with unique IDs and TTL expiration
  - Add quote retrieval method for reservation creation validation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 3. Create Lambda handler with Powertools in
     packages/hotel-pms-lambda/hotel_pms_lambda/handlers/api_gateway_handler.py
  - Implement APIGatewayRestResolver with route handlers for all hotel PMS
    operations
  - Add structured logging, tracing, and error handling with Lambda Powertools
  - Update quote generation handler to use DynamoDB persistence
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Set up API Gateway and Cognito with CDK
  - Create Cognito User Pool using existing `AgentCoreCognitoUserPool` construct
  - Set up API Gateway REST API with Lambda proxy integration
  - Configure Cognito authorizer and expose JWT configuration for AgentCore
    Gateway
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 5. Create OpenAPI specification file
  - Generate complete OpenAPI spec with all endpoints and operationId fields
  - Include request/response schemas and AI-friendly descriptions for AgentCore
    Gateway
  - Validate spec meets AgentCore Gateway requirements (no auth in spec, simple
    parameters)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 6. Implement CDK RestAPI construct
  - Create `HotelPmsApiConstruct` using `AgentCoreCognitoUserPool` for
    authentication
  - Set up API Gateway resources and methods with proper authorizer
    configuration
  - Add construct properties for API endpoint URL and Cognito configuration
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 7. Add comprehensive error handling and IAM permissions
  - Implement consistent error responses with proper HTTP status codes
  - Add IAM permissions for DynamoDB access (including new quotes table)
  - Configure Lambda environment variables for all DynamoDB tables
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 8. Integration testing and validation
  - Test complete workflow: availability -> quote (with DynamoDB) -> reservation
  - Verify Cognito authentication and JWT token validation
  - Validate OpenAPI spec compatibility with AgentCore Gateway
  - Test quote expiration and TTL functionality
  - **Test Results**: See `tests/post_deploy/INTEGRATION_TEST_RESULTS.md`
  - **Finding**: Quote-based reservation flow needs implementation
    (create_reservation should accept quote_id)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 9. Implement quote-based reservation flow
  - Update `create_reservation()` in `simplified_tools.py` to accept `quote_id`
    parameter
  - Add DynamoDB quote retrieval method to availability service
  - Implement quote expiration validation (check expires_at timestamp)
  - Extract booking details (hotel_id, room_type_id, dates, guests) from quote
  - Update reservation service to create reservation using quote data
  - Handle error cases: quote not found, quote expired, invalid quote data
  - Update unit tests to cover quote-based reservation flow
  - Re-run integration tests to verify complete workflow
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.4_
