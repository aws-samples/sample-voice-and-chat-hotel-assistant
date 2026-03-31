# Implementation Plan

- [x] 1. Update WebSocket Server MCP Client for Secrets Manager Support
  - Modify the McpConfig class to support loading configuration from AWS Secrets
    Manager instead of SSM Parameter Store
  - Add \_from_secrets_manager method to handle secret retrieval and JSON
    parsing
  - Update from_environment method to prioritize Secrets Manager over
    environment variables
  - _Requirements: 2.3, 2.4_

- [x] 2. Add Secrets Manager Configuration Tests
  - Create unit tests for Secrets Manager configuration loading with mocked
    boto3 responses
  - _Requirements: 2.3, 2.4_

- [x] 3. Create Secrets Manager Secret in CDK Infrastructure
  - Add Secrets Manager secret construct to the CDK stack
  - Configure secret with MCP configuration JSON object containing url,
    client_id, client_secret, user_pool_id, and region
  - Source configuration values from existing CDK constructs (Cognito client,
    user pool, etc.)
  - _Requirements: 1.1, 1.2, 3.1, 3.2_

- [x] 4. Update ECS Service Configuration
  - Add HOTEL_PMS_MCP_SECRET_ARN environment variable to ECS container
    definition
  - Grant Secrets Manager read permissions to ECS task role for the specific
    secret
  - Ensure IAM permissions follow principle of least privilege
  - _Requirements: 2.1, 2.2, 4.1, 4.2_

- [ ] 5. Test Infrastructure Deployment and Configuration Loading
  - Deploy updated CDK stack and verify secret is created correctly
  - Verify ECS service has correct environment variable and IAM permissions
  - Test WebSocket server startup with Secrets Manager configuration
  - Validate fallback to environment variables when secret is not available
  - _Requirements: 1.1, 2.1, 2.3, 2.4, 3.1, 3.2_
