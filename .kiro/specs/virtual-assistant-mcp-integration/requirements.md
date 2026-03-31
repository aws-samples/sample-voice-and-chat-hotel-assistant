# Requirements Document

## Introduction

This specification defines the integration of the virtual assistant chat and
voice agents with the Model Context Protocol (MCP) architecture. The integration
enables dynamic system prompt loading, knowledge base queries, and Hotel PMS API
access through a standardized MCP configuration format that supports multiple
MCP servers.

## Glossary

- **Virtual Assistant Chat**: The AgentCore-based chat interface for text-based
  hotel assistant conversations
- **Virtual Assistant Voice**: The LiveKit-based voice interface using Amazon
  Bedrock Nova Sonic for speech-to-speech interactions
- **MCP Server**: A Model Context Protocol server providing tools and prompts to
  AI agents
- **Hotel Assistant MCP**: MCP server providing knowledge base queries and
  system prompts (chat, voice, default)
- **Hotel PMS MCP**: MCP server providing Hotel PMS API operations
  (reservations, availability, housekeeping)
- **MCP Configuration**: Standard JSON format configuration defining available
  MCP servers and their authentication
- **System Prompt**: The initial instructions that define the agent's behavior
  and capabilities
- **Cognito User Pool**: AWS Cognito service managing authentication for MCP
  server access
- **Secrets Manager**: AWS service for securely storing authentication
  credentials
- **AgentCore Runtime**: AWS Bedrock service for deploying and running AI agents
- **Streamable HTTP MCP**: MCP servers accessible via HTTP with streaming
  support

## Requirements

### Requirement 1: MCP Configuration Management

**User Story:** As a system administrator, I want a standardized JSON
configuration format for MCP servers, so that I can easily add or modify MCP
server connections without code changes.

#### Acceptance Criteria

1. WHEN the system initializes, THE Virtual Assistant Chat SHALL load MCP server
   configuration from AWS Systems Manager Parameter Store
2. WHEN the system initializes, THE Virtual Assistant Voice SHALL load MCP
   server configuration from AWS Systems Manager Parameter Store
3. THE MCP Configuration JSON SHALL follow the standard MCP configuration format
   with server definitions
4. THE MCP Configuration JSON SHALL support multiple MCP server entries
5. THE MCP Configuration JSON SHALL include authentication details for each MCP
   server
6. WHERE Cognito authentication is required, THE MCP Configuration JSON SHALL
   reference Cognito User Pool ID and Client ID
7. THE HotelPmsStack CDK construct SHALL generate the MCP configuration JSON and
   store it in SSM Parameter Store during deployment
8. THE MCP Configuration JSON SHALL include both Hotel Assistant MCP and Hotel
   PMS MCP server definitions
9. THE Virtual Assistant Chat SHALL have IAM permissions to read the SSM
   Parameter containing MCP configuration
10. THE Virtual Assistant Voice SHALL have IAM permissions to read the SSM
    Parameter containing MCP configuration

### Requirement 2: Authentication Credential Management

**User Story:** As a security engineer, I want MCP server credentials stored
securely, so that sensitive authentication information is protected.

#### Acceptance Criteria

1. THE MCP Configuration JSON SHALL reference AWS Secrets Manager secret ARNs
   for sensitive credentials
2. WHEN the virtual assistant initializes, THE System SHALL retrieve credentials
   from Secrets Manager
3. THE HotelPmsStack SHALL create Secrets Manager secrets for Cognito client
   credentials
4. THE Secrets Manager secrets SHALL contain Cognito User Pool ID and Client ID
5. THE MCP Configuration JSON SHALL NOT contain plaintext credentials
6. THE Virtual Assistant Chat SHALL have IAM permissions to read required
   Secrets Manager secrets
7. THE Virtual Assistant Voice SHALL have IAM permissions to read required
   Secrets Manager secrets

### Requirement 3: Dynamic System Prompt Loading

**User Story:** As a virtual assistant developer, I want system prompts loaded
from MCP servers, so that prompt updates don't require code deployments.

#### Acceptance Criteria

1. WHEN Virtual Assistant Chat initializes, THE System SHALL request the
   "chat_system_prompt" from Hotel Assistant MCP
2. WHEN Virtual Assistant Voice initializes, THE System SHALL request the
   "voice_system_prompt" from Hotel Assistant MCP
3. THE MCP Configuration JSON MAY specify which MCP server provides system
   prompts
4. THE MCP Configuration JSON MAY specify the prompt name for each virtual
   assistant type
5. WHERE no prompt name is specified, THE System SHALL default to
   "chat_system_prompt" for chat and "voice_system_prompt" for voice
6. IF the specified prompt is not found, THEN THE System SHALL fall back to
   "default_system_prompt"
7. IF all prompt requests fail, THEN THE System SHALL use a hardcoded fallback
   prompt
8. THE Virtual Assistant Chat SHALL NOT use hardcoded system prompts as the
   primary prompt source
9. THE Virtual Assistant Voice SHALL NOT use hardcoded system prompts as the
   primary prompt source
10. THE MCP Server SHALL provide dynamic context (current date, hotel list) in
    the prompt response

### Requirement 4: Multi-MCP Server Support

**User Story:** As a virtual assistant, I want to access tools from multiple MCP
servers, so that I can provide comprehensive hotel assistance.

#### Acceptance Criteria

1. THE Virtual Assistant Chat SHALL connect to all MCP servers defined in the
   configuration
2. THE Virtual Assistant Voice SHALL connect to all MCP servers defined in the
   configuration
3. WHEN a tool is invoked, THE System SHALL route the request to the correct MCP
   server
4. THE System SHALL discover available tools from all connected MCP servers
5. THE System SHALL handle tool name conflicts across MCP servers
6. IF one MCP server is unavailable, THEN THE System SHALL continue operating
   with remaining servers
7. THE System SHALL log connection status for each MCP server
8. THE System SHALL provide graceful degradation when MCP servers are
   unavailable

### Requirement 5: Streamable HTTP MCP Protocol Support

**User Story:** As a system architect, I want to use streamable HTTP MCP
servers, so that the solution works with AgentCore Runtime deployment.

#### Acceptance Criteria

1. THE MCP Configuration JSON SHALL only define streamable HTTP MCP servers
2. THE Virtual Assistant Chat SHALL use HTTP transport for all MCP server
   connections
3. THE Virtual Assistant Voice SHALL use HTTP transport for all MCP server
   connections
4. THE System SHALL support streaming responses from MCP servers
5. THE System SHALL include proper HTTP headers for MCP protocol communication
6. THE System SHALL handle HTTP connection timeouts gracefully
7. THE System SHALL retry failed HTTP requests with exponential backoff
8. THE System SHALL validate MCP server responses according to protocol
   specification

### Requirement 6: Virtual Assistant Chat Integration

**User Story:** As a hotel guest, I want to use the chat interface with full MCP
capabilities, so that I can get accurate information and make reservations.

#### Acceptance Criteria

1. THE Virtual Assistant Chat SHALL load the "chat_system_prompt" from Hotel
   Assistant MCP
2. THE Virtual Assistant Chat SHALL access the query_hotel_knowledge tool from
   Hotel Assistant MCP
3. THE Virtual Assistant Chat SHALL access Hotel PMS API tools through Hotel PMS
   MCP
4. WHEN a user asks about hotel information, THE Virtual Assistant Chat SHALL
   query the knowledge base via MCP
5. WHEN a user requests reservation operations, THE Virtual Assistant Chat SHALL
   call Hotel PMS API via MCP
6. THE Virtual Assistant Chat SHALL maintain conversation context across MCP
   tool calls
7. THE Virtual Assistant Chat SHALL use AgentCore Memory for conversation
   persistence
8. THE Virtual Assistant Chat SHALL handle MCP tool errors gracefully with
   user-friendly messages

### Requirement 7: Virtual Assistant Voice Integration

**User Story:** As a hotel guest, I want to use the voice interface with full
MCP capabilities, so that I can have natural spoken conversations about hotel
services.

#### Acceptance Criteria

1. THE Virtual Assistant Voice SHALL load the "voice_system_prompt" from Hotel
   Assistant MCP
2. THE Virtual Assistant Voice SHALL access the query_hotel_knowledge tool from
   Hotel Assistant MCP
3. THE Virtual Assistant Voice SHALL access Hotel PMS API tools through Hotel
   PMS MCP
4. WHEN a user speaks about hotel information, THE Virtual Assistant Voice SHALL
   query the knowledge base via MCP
5. WHEN a user requests reservation operations, THE Virtual Assistant Voice
   SHALL call Hotel PMS API via MCP
6. THE Virtual Assistant Voice SHALL maintain conversation context across MCP
   tool calls
7. THE Virtual Assistant Voice SHALL provide spoken responses based on MCP tool
   results
8. THE Virtual Assistant Voice SHALL handle MCP tool errors gracefully with
   spoken error messages

### Requirement 8: Configuration Deployment and Updates

**User Story:** As a DevOps engineer, I want MCP configuration deployed
automatically, so that infrastructure updates include proper MCP setup.

#### Acceptance Criteria

1. THE HotelPmsStack SHALL generate MCP configuration JSON during CDK deployment
2. THE MCP Configuration JSON SHALL include Hotel Assistant MCP server URL and
   authentication
3. THE MCP Configuration JSON SHALL include Hotel PMS MCP server URL and
   authentication
4. THE MCP Configuration JSON SHALL be stored in SSM Parameter Store accessible
   to both virtual assistants
5. WHEN the CDK stack is updated, THE MCP Configuration JSON SHALL be
   regenerated
6. THE Virtual Assistant Chat deployment SHALL include environment variable
   specifying the SSM Parameter name for MCP configuration
7. THE Virtual Assistant Voice deployment SHALL include environment variable
   specifying the SSM Parameter name for MCP configuration
8. THE System SHALL validate MCP configuration JSON format during deployment

### Requirement 9: Error Handling and Resilience

**User Story:** As a system operator, I want robust error handling for MCP
operations, so that temporary failures don't crash the virtual assistants.

#### Acceptance Criteria

1. IF an MCP server is unreachable, THEN THE System SHALL log the error and
   continue with available servers
2. IF a prompt loading fails, THEN THE System SHALL use a fallback default
   prompt
3. IF a tool call fails, THEN THE System SHALL return a user-friendly error
   message
4. IF authentication fails, THEN THE System SHALL retry with fresh credentials
   from Secrets Manager
5. THE System SHALL implement circuit breaker pattern for failing MCP servers
6. THE System SHALL provide health check endpoints indicating MCP server
   connectivity status
7. THE System SHALL emit CloudWatch metrics for MCP operation success/failure
   rates
8. THE System SHALL include correlation IDs in all MCP-related log entries

### Requirement 10: Configuration Documentation

**User Story:** As a developer, I want clear documentation on how to configure
virtual assistants with MCP servers, so that I can understand and modify the
configuration.

#### Acceptance Criteria

1. THE System SHALL include documentation describing the MCP configuration JSON
   format
2. THE Documentation SHALL include examples of MCP server configuration entries
3. THE Documentation SHALL explain how to specify prompt names for each virtual
   assistant type
4. THE Documentation SHALL describe the SSM Parameter Store location for MCP
   configuration
5. THE Documentation SHALL explain how to add new MCP servers to the
   configuration
6. THE Documentation SHALL describe the authentication credential flow using
   Secrets Manager
7. THE Documentation SHALL include troubleshooting steps for common MCP
   configuration issues
8. THE Documentation SHALL explain the prompt name fallback behavior
   (chat_system_prompt → default_system_prompt)

### Requirement 11: Testing and Validation

**User Story:** As a quality assurance engineer, I want comprehensive tests for
MCP integration, so that I can verify correct functionality.

#### Acceptance Criteria

1. THE System SHALL include unit tests for MCP configuration parsing
2. THE System SHALL include unit tests for MCP client initialization
3. THE System SHALL include integration tests for prompt loading from MCP
   servers
4. THE System SHALL include integration tests for tool invocation through MCP
   servers
5. THE System SHALL include end-to-end tests for complete conversation flows
   using MCP
6. THE System SHALL include tests for error scenarios (server unavailable,
   authentication failure)
7. THE System SHALL include tests for multi-MCP server scenarios
8. THE System SHALL validate that hardcoded prompts are removed from both
   virtual assistants
