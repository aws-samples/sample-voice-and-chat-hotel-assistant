# Requirements Document

## Introduction

This feature refactors the Hotel PMS MCP (Model Context Protocol) integration
with the LiveKit agent to use a simpler, more robust approach. Instead of
complex global client management and caching, this refactor creates a custom
MCPServer subclass that uses the existing `hotel_pms_mcp_client()` from the
common package and creates fresh MCP connections per session.

This is a prototype solution focused on core functionality with minimal
complexity and maximum reliability.

## Requirements

### Requirement 1

**User Story:** As a LiveKit agent, I want to use a custom MCPServer subclass
that integrates with the hotel_pms_mcp_client, so that I can access hotel
management tools with proper session isolation.

#### Acceptance Criteria

1. WHEN the LiveKit agent creates an MCPServer THEN it SHALL use a custom
   subclass that implements client_streams() using hotel_pms_mcp_client()
2. WHEN the MCP connection is established THEN LiveKit SHALL automatically load
   available tools from the server
3. IF the MCP connection fails THEN the agent SHALL start without MCP tools and
   log a warning
4. WHEN each session ends THEN the MCP connection SHALL be properly cleaned up

### Requirement 2

**User Story:** As a LiveKit agent, I want to use Hotel PMS tools through MCP,
so that I can help guests with hotel-related requests via voice.

#### Acceptance Criteria

1. WHEN the agent receives a voice request for room availability THEN it SHALL
   call the appropriate MCP tool and provide a spoken response
2. WHEN the agent receives a voice request for hotel amenities THEN it SHALL
   call the appropriate MCP tool and provide a spoken response
3. WHEN the agent receives a voice request for housekeeping THEN it SHALL call
   the appropriate MCP tool and provide a spoken response
4. WHEN an MCP tool call fails THEN the agent SHALL provide a helpful error
   message to the user
5. WHEN MCP tools are not available THEN the agent SHALL inform the user that
   hotel services are temporarily unavailable

### Requirement 3

**User Story:** As a LiveKit agent, I want to create fresh MCP connections per
session in the prewarm function, so that I can get hotel data for dynamic
prompts without complex caching.

#### Acceptance Criteria

1. WHEN the agent prewarm function runs THEN it SHALL create a new
   hotel_pms_mcp_client connection for that session
2. WHEN the MCP client is created THEN it SHALL use the client to fetch hotel
   data for dynamic prompt generation
3. WHEN hotel data is fetched THEN it SHALL be used to generate hotel-specific
   instructions similar to the chat agent pattern
4. WHEN the session ends THEN the MCP connection SHALL be properly closed

### Requirement 4

**User Story:** As a developer, I want to reuse the existing
hotel_pms_mcp_client from the common package, so that I can leverage proven
authentication and configuration logic without duplication.

#### Acceptance Criteria

1. WHEN the custom MCPServer needs MCP streams THEN it SHALL use
   hotel_pms_mcp_client() from hotel_assistant_common
2. WHEN hotel_pms_mcp_client() is called THEN it SHALL handle all
   authentication, configuration loading, and error handling automatically
3. WHEN authentication fails THEN the hotel_pms_mcp_client SHALL raise
   appropriate exceptions that are handled gracefully
4. WHEN the MCP client is created THEN it SHALL provide the streams needed by
   LiveKit's MCPServer interface
