# Implementation Plan

- [x] 1. Remove existing complex MCP configuration
  - Delete hotel_assistant_livekit/mcp/ directory and all contents
  - Remove complex configuration loading and caching logic from agent.py
  - Clean up unused imports and dependencies
  - _Requirements: 4.1, 4.2_

- [x] 2. Update pyproject.toml dependencies
  - Add hotel-assistant-common dependency
  - Remove unused dependencies (httpx, boto3 if not used elsewhere)
  - Ensure livekit-agents[mcp] dependency exists
  - _Requirements: 4.1, 4.2_

- [x] 3. Create custom HotelPmsMCPServer class
  - Create hotel_assistant_livekit/hotel_pms_mcp_server.py
  - Implement HotelPmsMCPServer subclass of MCPServer
  - Implement client_streams() method using hotel_pms_mcp_client()
  - Add proper error handling and logging
  - _Requirements: 1.1, 1.2, 4.1, 4.3_

- [x] 4. Refactor agent.py for per-session MCP connections
  - Import hotel_pms_mcp_client and get_hotels from common package
  - Update prewarm function to create MCP client and fetch hotel data
  - Use hotel data to generate dynamic instructions with
    generate_dynamic_hotel_instructions
  - Replace MCPServerHTTP with HotelPmsMCPServer in agent session creation
  - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 3.4_

- [ ] 5. Implement comprehensive error handling
  - Add try-catch blocks around hotel data fetching in prewarm
  - Add fallback to generic instructions if hotel data fetch fails
  - Add graceful handling for MCP server creation failures
  - Add appropriate logging for all error scenarios
  - _Requirements: 1.3, 2.4, 2.5, 3.4_

- [ ] 6. Write unit tests for HotelPmsMCPServer
  - Test HotelPmsMCPServer creation and client_streams() method
  - Mock hotel_pms_mcp_client to test error handling
  - Test integration with LiveKit's MCPServer interface
  - _Requirements: 1.1, 1.2, 4.3, 4.4_

- [x] 7. Write integration tests for refactored agent
  - Test agent prewarm function with real MCP server
  - Test hotel data fetching and dynamic prompt generation
  - Test agent session creation with HotelPmsMCPServer
  - Test tool execution through the new MCP integration
  - Tests must fail if external resources are unavailable
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_
