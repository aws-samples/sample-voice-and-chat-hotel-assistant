# Implementation Plan

**Note**: Use the AWS Documentation MCP server to look up EUM Social service
details, API specifications, and configuration requirements during
implementation.

- [x] 1. Enhance message processor to detect EUM Social WhatsApp messages
  - Extend existing `process_message_record` function to detect WhatsApp vs
    simulated messages
  - Add `is_eum_whatsapp_message` function to identify EUM Social webhook format
  - Add `parse_whatsapp_message` function to convert WhatsApp webhook to
    MessageEvent
  - Write unit tests for message detection and parsing logic
  - _Requirements: 1.1, 3.3, 3.4_

- [x] 2. Implement phone number allow list validation
  - Add SSM parameter client for retrieving allow list configuration
  - Implement `get_allow_list` function with caching (5-minute TTL)
  - Add `is_phone_allowed` function supporting wildcard (\*) and comma-separated
    numbers
  - Write unit tests for allow list validation including wildcard and specific
    numbers
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6_

- [x] 3. Create wrapper functions for multi-backend message handling
  - Implement `update_message_status_wrapper` to handle WhatsApp vs simulated
    status updates
  - Implement `send_response_wrapper` to route responses to appropriate backend
  - Modify `_process_message_async` to use wrapper functions instead of direct
    messaging client calls
  - Write unit tests for wrapper function routing logic
  - _Requirements: 4.1, 4.3, 5.1, 5.2, 5.3_

- [x] 4. Implement EUM Social WhatsApp API client
  - Add `get_eum_social_client` function with session caching similar to bedrock
    sessions
  - Implement cross-account role assumption with credential caching
  - Add `send_whatsapp_response` function using EUM Social SendWhatsAppMessage
    API
  - Write unit tests for client creation and message sending
  - _Requirements: 4.1, 4.3, 6.2, 6.3_

- [x] 5. Add CDK context configuration and environment variables
  - Enhance backend stack to detect EUM Social context variables
    (eumSocialTopicArn, eumSocialPhoneNumberId)
  - Add subscription to user-provided SNS topic when EUM Social is configured
  - Set WhatsApp-specific environment variables on message processor Lambda
  - Add conditional deployment logic to skip messaging stack when EUM Social is
    configured
  - _Requirements: 1.1, 1.2, 1.5, 6.1, 6.2, 6.4, 6.5_

- [x] 6. Grant IAM permissions for WhatsApp operations
  - Add SSM parameter read permissions for allow list access
  - Add EUM Social SendWhatsAppMessage API permissions
  - Add STS AssumeRole permissions for cross-account scenarios
  - Verify CDK synth works with new permissions
  - _Requirements: 6.3, 7.3_

- [x] 7. Add error handling and logging for WhatsApp operations
  - Enhance existing error handling to support WhatsApp-specific errors
  - Add DEBUG-level logging for phone numbers and message content
  - Add ERROR-level logging for API failures and authentication errors
  - Ensure existing retry and batch processing logic works with WhatsApp
    messages
  - _Requirements: 7.1, 7.2, 7.4, 8.1, 8.2_

- [x] 8. Write integration tests for end-to-end WhatsApp flow
  - Create test for complete WhatsApp message processing (SNS → SQS → Lambda →
    AgentCore → EUM Social)
  - Test allow list validation with blocked and allowed phone numbers
  - Test cross-account role assumption and EUM Social API calls
  - Test error scenarios and fallback behavior
  - _Requirements: 3.5, 5.3, 7.3, 7.5_

- [x] 9. Update documentation and deployment instructions
  - Document CDK context variables for EUM Social configuration
  - Add README section explaining SNS topic setup requirements
  - Document allow list parameter format and wildcard usage
  - Add troubleshooting guide for common WhatsApp integration issues
  - _Requirements: 1.4, 2.5, 6.5_

- [x] 10. Fix environment variable validation for conditional messaging backends
  - Modify `_validate_environment` function to conditionally require environment
    variables based on configuration
  - When EUM Social is configured (EUM_SOCIAL_PHONE_NUMBER_ID present), only
    require EUM Social and AgentCore variables
  - When messaging backend is configured, only require messaging backend and
    AgentCore variables
  - Update wrapper functions to handle missing messaging client gracefully when
    using EUM Social
  - Write unit tests for conditional environment validation scenarios
  - _Requirements: 1.1, 1.2, 9.1_
