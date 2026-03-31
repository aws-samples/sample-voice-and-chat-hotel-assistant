# Implementation Plan

- [x] 1. Set up AgentCore Gateway MCP client infrastructure
  - Create AgentCoreGatewayMcpClient module using official MCP Python client
  - Implement OAuth2 client credentials flow for Cognito authentication
  - Add HTTP streaming transport with ClientSession management
  - Implement connection management with retry logic and exponential backoff
  - Add configuration loading from environment variables with
    environment-specific support
  - Write unit tests for authentication flow and connection management
  - _Requirements: 2.1, 2.2, 2.4, 7.1, 7.2, 7.4, 7.5, 8.2, 8.5_

- [x] 2. Create hotel tools manager with auto-discovery
  - Implement HotelToolsManager class with cursor-based tool discovery
    pagination
  - Add tool schema caching with TTL-based invalidation
  - Create generic tool execution interface with error handling
  - Implement tool categorization for hotel service workflows
  - Add tool refresh functionality for dynamic updates
  - Write unit tests for tool discovery, caching, and execution
  - _Requirements: 2.1, 2.3, 3.1, 4.1, 5.1, 6.1_

- [x] 3. Create MCP tool wrapper for BaseTool integration
  - Implement McpToolWrapper class that extends BaseTool
  - Add proper name and display_name properties
  - Implement execute method that delegates to HotelToolsManager
  - Handle error translation and logging consistently
  - Write unit tests for tool wrapper functionality
  - _Requirements: 2.1, 8.1, 8.4_

- [x] 4. Refactor frontend to secure architecture
  - Remove Nova Sonic protocol events from frontend (sessionStart, promptStart,
    etc.)
  - Simplify WebSocketEventManager to handle only audio I/O and UI display
  - Implement simplified message protocol (authorization, audio_chunk,
    start_recording, etc.)
  - Update frontend to receive and display backend-generated transcripts and
    status
  - Remove tool configuration and system prompt logic from frontend
  - Write unit tests for simplified frontend message handling
  - _Requirements: 7.1, 7.2, 8.1_

- [x] 4. Implement missing promptStart event with tool configuration
  - Create promptStart event generation in S2sEvent class
  - Implement tool schema conversion from MCP format to Bedrock toolSpec format
  - Add dynamic tool configuration building that combines existing and MCP tools
  - Update WebSocketHandler to send promptStart event during stream
    initialization
  - Ensure promptStart is sent after sessionStart but before any content events
  - Write unit tests for promptStart event generation and tool schema conversion
  - _Requirements: 2.1, 2.3, 3.1, 4.1, 5.1, 6.1_

- [x] 5. Implement Nova Sonic protocol manager in backend
  - Create NovaSonicProtocolManager class to handle all protocol events
  - Implement sessionStart, promptStart, contentStart, textInput event
    generation
  - Add tool schema conversion from MCP format to Bedrock toolSpec format
  - Use WebSocketHandler tool registry as single source of truth for tools
  - Generate promptStart toolConfiguration dynamically from tool registry
  - Eliminate case-variation tool duplicates, implement case-insensitive lookup
  - Add async context manager support to MCP client for proper cleanup
  - Ensure proper event sequence: sessionStart -> promptStart ->
    contentStart(SYSTEM) -> textInput
  - Write unit tests for protocol event generation and tool schema conversion
  - _Requirements: 2.1, 2.3, 3.1, 4.1, 5.1, 6.1_

- [x] 6. Create Spanish system prompt management
  - Write system_prompt.txt with Spanish hotel receptionist prompt
  - Include agent introduction, service acknowledgment, and general hotel
    service guidance
  - Create SystemPromptManager class for file-based prompt loading
  - Remove dynamic tool list insertion (tools defined in promptStart
    toolConfiguration)
  - Implement backend-controlled prompt injection into Bedrock conversation
    context
  - Write unit tests for prompt loading and injection
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 7. Integrate MCP client into WebSocketHandler
  - Add MCP client initialization to WebSocketHandler
  - Implement simplified message handling for frontend (authorization,
    audio_chunk, etc.)
  - Add Nova Sonic protocol event generation using NovaSonicProtocolManager
  - Update cleanup methods to properly close MCP connections
  - _Requirements: 2.1, 2.2, 2.4, 8.1_

- [x] 8. Enhance backend message processing
  - Update WebSocketHandler to handle simplified frontend messages
  - Implement audio chunk processing and forwarding to Bedrock
  - Add backend-controlled session management and conversation flow
  - Update tool execution to work with backend-generated protocol events
  - _Requirements: 3.1, 4.1, 5.1, 6.1_

- [ ] 9. Implement comprehensive error handling with Spanish responses
  - Add MCP connection error handling with specific Spanish error messages
  - Implement retry logic with exponential backoff for network issues
  - Add graceful degradation when MCP services are unavailable
  - Create error categorization for authentication, timeout, and malformed
    response failures
  - Implement hotel service workflow error handling for reservations, checkout,
    housekeeping, and info requests
  - Add circuit breaker pattern for repeated failures
  - Write unit tests for all error scenarios and recovery mechanisms
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 10. Add MCP configuration to CDK deployment
  - Update FargateNLBConstruct to include MCP environment variables
  - Add AgentCore Gateway URL and Cognito credentials to container
  - Update Docker image to include system_prompt.txt file
  - Configure proper IAM permissions for MCP access
  - _Requirements: 7.1, 7.2, 7.3_

- [ ] 11. Write comprehensive tests
  - Create unit tests for AgentCoreGatewayMcpClient authentication and tool
    calls
  - Add integration tests for WebSocket tool use workflows
  - Test error handling scenarios and recovery mechanisms
  - Verify system prompt loading and injection
  - _Requirements: 2.1, 2.2, 8.1, 8.2, 8.3_

- [ ] 12. Add monitoring and logging
  - Implement structured logging for MCP operations
  - Add CloudWatch metrics for tool usage and errors
  - Create health check endpoints for MCP connection status
  - Add performance monitoring for tool execution times
  - _Requirements: 2.5, 8.1, 8.4_

- [ ] 13. Update project dependencies and deployment
  - Add MCP client library (mcp>=1.0.0) to pyproject.toml
  - Add requests library for OAuth2 token management
  - Update Docker image build to include new dependencies and system_prompt.txt
  - Add required dependencies for HTTP streaming transport
  - Update uv.lock file with new dependencies
  - Test dependency installation and import functionality
  - _Requirements: 2.1, 7.1_
