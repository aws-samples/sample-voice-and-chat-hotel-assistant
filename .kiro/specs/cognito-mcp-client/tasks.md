# Implementation Plan

- [x] 1. Set up project structure and dependencies
  - Create directory structure for cognito_mcp module
  - Update pyproject.toml with required dependencies
  - Create **init**.py files for proper module imports
  - _Requirements: 1.1, 2.1_

- [x] 2. Implement core exception classes
  - Create base exception classes in hotel_assistant_common/exceptions.py
  - Create Cognito MCP specific exceptions in cognito_mcp/exceptions.py
  - Include proper error hierarchy and documentation
  - _Requirements: 6.1, 6.3_

- [x] 3. Implement CognitoAuth class with unit tests
  - Create CognitoAuth class implementing httpx.Auth interface
  - Implement OAuth2 client credentials flow in auth_flow method
  - Add token caching and expiration tracking
  - Implement automatic token refresh logic
  - Add exponential backoff retry logic for authentication failures
  - Write focused unit tests for OAuth2 flow, token caching, and error handling
  - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3, 2.4, 6.2_

- [x] 4. Implement cognito_mcp_client function with unit tests
  - Create async context manager function that wraps streamablehttp_client
  - Integrate CognitoAuth with streamablehttp_client
  - Return same interface as streamablehttp_client (read_stream, write_stream,
    get_session_id_callback)
  - Handle authentication errors and connection failures
  - Write unit tests for client creation and error propagation
  - _Requirements: 1.2, 2.1, 2.2, 6.3_

- [x] 5. Implement hotel_pms_mcp_client function with unit tests
  - Create async context manager function for Hotel PMS specific client
  - Implement configuration loading from AWS Secrets Manager
  - Add fallback to environment variables when Secrets Manager fails
  - Validate required configuration parameters
  - Use cognito_mcp_client internally with loaded configuration
  - Write unit tests for configuration loading and validation
  - _Requirements: 3.1, 3.4, 4.1, 4.2_

- [x] 6. Create integration test for end-to-end MCP connectivity
  - Test authentication with real Cognito user pool
  - Test connection to real AgentCore Gateway deployed MCP server
  - Test tool listing functionality with real Hotel PMS tools
  - Test complete end-to-end authentication and MCP communication flow
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 7. Update package exports and documentation
  - Update hotel_assistant_common/**init**.py to export new modules
  - Add docstrings and type hints to all public functions and classes
  - Create README documentation for usage examples
  - Add logging configuration and structured logging
  - _Requirements: 6.1, 6.2, 6.4_
