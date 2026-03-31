# Requirements Document

## Introduction

The Hotel Assistant MCP Server provides an MCP (Model Context Protocol) server
that integrates the S3 Vectors Knowledge Base with system prompt capabilities.
This server enables AI agents to query hotel documentation using MCP tools and
retrieve context-appropriate system prompts using the MCP prompt primitive.

The MCP server will be implemented in `packages/hotel-pms-simulation` and
deployed on AgentCore Runtime. It will include prompt templates copied from the
virtual assistant packages and enhanced with dynamic hotel context.

## Glossary

- **MCP_Server**: Model Context Protocol server providing tools and prompts to
  AI agents
- **Knowledge_Query_Tool**: MCP tool for searching hotel documentation in the
  knowledge base
- **MCP_Prompt_Primitive**: MCP protocol feature for providing system prompts to
  agents
- **AgentCore_Runtime**: AWS service for deploying and running MCP servers
- **S3_Vectors_KB**: Bedrock Knowledge Base using S3 vectors for hotel
  documentation
- **Chat_Prompt**: System prompt optimized for text interactions
- **Voice_Prompt**: System prompt optimized for speech interactions
- **Default_Prompt**: General-purpose system prompt for any interaction type
- **Hotel_Context**: Dynamic information including current date and list of
  hotels with IDs

## Requirements

### Requirement 1: MCP Server Implementation

**User Story:** As a virtual assistant developer, I want an MCP server that
provides hotel knowledge tools and prompts, so that I can build AI agents with
consistent access to hotel information.

#### Acceptance Criteria

1. THE MCP_Server SHALL implement the Model Context Protocol specification
2. THE MCP_Server SHALL be located in `packages/hotel-pms-simulation` directory
3. THE MCP_Server SHALL provide knowledge query tools for searching hotel
   documentation
4. THE MCP_Server SHALL provide prompts using the MCP_Prompt_Primitive
5. THE MCP_Server SHALL integrate with the S3_Vectors_KB for document retrieval
6. THE MCP_Server SHALL handle authentication using AgentCore identity tokens
7. THE MCP_Server SHALL return structured responses in JSON format

### Requirement 2: Knowledge Query Tool

**User Story:** As an AI agent, I want to query hotel documentation through an
MCP tool, so that I can answer guest questions with accurate information.

#### Acceptance Criteria

1. WHEN an agent requests hotel information, THE Knowledge_Query_Tool SHALL
   search the S3_Vectors_KB
2. THE Knowledge_Query_Tool SHALL accept a query string parameter
3. THE Knowledge_Query_Tool SHALL accept an optional hotel_ids list parameter
   for filtering by hotel
4. WHEN hotel_ids is provided, THE Knowledge_Query_Tool SHALL filter results to
   only those hotels
5. WHEN hotel_ids is empty or not provided, THE Knowledge_Query_Tool SHALL query
   all hotels without filtering
6. THE Knowledge_Query_Tool SHALL accept an optional max_results parameter with
   a default value of 5
7. THE Knowledge_Query_Tool SHALL return relevant document excerpts with
   metadata
8. THE Knowledge_Query_Tool SHALL include source attribution in responses

### Requirement 3: System Prompts with Dynamic Context

**User Story:** As a virtual assistant developer, I want to retrieve
context-appropriate system prompts with dynamic hotel information, so that my
agents have current data for conversations.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide three prompt types using MCP_Prompt_Primitive:
   chat, voice, and default
2. THE MCP_Server SHALL store Chat_Prompt template copied from
   `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/assets`
3. THE MCP_Server SHALL store Voice_Prompt template copied from
   `packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/assets`
4. WHEN a chat agent requests a prompt, THE MCP_Server SHALL return the
   Chat_Prompt with Hotel_Context
5. WHEN a voice agent requests a prompt, THE MCP_Server SHALL return the
   Voice_Prompt with Hotel_Context
6. WHEN no type is specified, THE MCP_Server SHALL return the Default_Prompt
   with Hotel_Context
7. THE Hotel_Context SHALL include the current date
8. THE Hotel_Context SHALL include the list of hotels with their IDs
9. THE MCP_Server SHALL dynamically inject Hotel_Context into prompt templates

### Requirement 4: AgentCore Runtime Deployment

**User Story:** As a DevOps engineer, I want to deploy the MCP server on
AgentCore Runtime, so that it is scalable and managed by AWS.

#### Acceptance Criteria

1. THE MCP_Server SHALL be packaged as a Python application compatible with
   AgentCore Runtime
2. THE MCP_Server SHALL use environment variables for configuration (knowledge
   base ID, region)
3. THE MCP_Server SHALL implement health check endpoints for AgentCore
   monitoring
4. THE MCP_Server SHALL log all requests using AWS Lambda Powertools structured
   logging
5. THE MCP_Server SHALL be deployed using CDK infrastructure code

### Requirement 5: Error Handling and Resilience

**User Story:** As a system administrator, I want the MCP server to handle
errors gracefully, so that temporary failures don't break virtual assistant
functionality.

#### Acceptance Criteria

1. WHEN the S3_Vectors_KB is unavailable, THE MCP_Server SHALL return a clear
   error message
2. WHEN authentication fails, THE MCP_Server SHALL return a 401 Unauthorized
   response
3. WHEN invalid parameters are provided, THE MCP_Server SHALL return a 400 Bad
   Request with details
4. THE MCP_Server SHALL implement retry logic with exponential backoff for
   transient failures
5. THE MCP_Server SHALL never expose internal error details to clients
