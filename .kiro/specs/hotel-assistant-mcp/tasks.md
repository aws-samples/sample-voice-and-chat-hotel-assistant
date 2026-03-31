# Implementation Plan

- [x] 1. Copy prompt templates from virtual-assistant packages
  - Copy chat prompt from
    `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/assets`
    to
    `packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/chat_prompt.txt`
  - Copy voice prompt from
    `packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/assets`
    to
    `packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/voice_prompt.txt`
  - Add placeholders `{current_date}` and `{hotel_list}` to both templates for
    dynamic context injection
  - _Requirements: 3.2, 3.3_

- [x] 2. Implement FastMCP server with knowledge query tool
  - [x] 2.1 Implement query_hotel_knowledge tool
    - Create `packages/hotel-pms-simulation/hotel_pms_simulation/mcp/server.py`
    - Initialize FastMCP server with name "Hotel Assistant"
    - Implement `query_hotel_knowledge` tool with `@mcp.tool()` decorator
    - Tool accepts query (string), hotel_ids (optional list), max_results (int,
      default 5)
    - Query Bedrock knowledge base using boto3 bedrock-agent-runtime client
    - Apply hotel_ids filter when provided using vectorSearchConfiguration
      filter
    - Return formatted results with content, score, metadata, and source
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_
  - [x] 2.2 Write unit tests for knowledge query tool
    - Test query with hotel_ids filter applied correctly
    - Test query with max_results parameter
    - Test query response formatting (content, score, metadata, source)
    - Mock boto3 bedrock-agent-runtime client
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 3. Implement MCP prompt functions with dynamic context
  - [x] 3.1 Implement prompt functions and helpers
    - Implement `chat_system_prompt` function with
      `@mcp.prompt(name='chat_system_prompt')` decorator
    - Implement `voice_system_prompt` function with
      `@mcp.prompt(name='voice_system_prompt')` decorator
    - Implement `default_system_prompt` function that returns chat prompt
    - Create `load_prompt_with_context` helper function to load templates and
      inject context
    - Create `generate_hotel_context` helper function to get current date and
      hotel list from DynamoDB
    - Use existing HotelService.get_hotels() to retrieve hotel data
    - Format hotel list as "- {name} (ID: {id})" for each hotel
    - _Requirements: 1.4, 3.1, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_
  - [x] 3.2 Write unit tests for prompt functions
    - Test load_prompt_with_context injects current_date correctly
    - Test load_prompt_with_context injects hotel_list correctly
    - Test generate_hotel_context formats hotel list properly
    - Test default_system_prompt returns chat prompt
    - Mock HotelService.get_hotels()
    - _Requirements: 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [x] 4. Create Dockerfile for AgentCore Runtime deployment
  - Create `packages/hotel-pms-simulation/Dockerfile-mcp`
  - Use `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` as base image
  - Install curl for healthchecks
  - Create non-root user (appuser:appgroup with uid/gid 1001)
  - Copy pyproject.toml and install dependencies with uv
  - Copy hotel_pms_simulation code
  - Set PATH to include .venv/bin and PYTHONPATH to /app
  - Expose port 8080 and add healthcheck
  - Set entrypoint to `python -m hotel_pms_simulation.mcp.server`
  - _Requirements: 4.1, 4.3_

- [x] 5. Create CDK construct for MCP server deployment
  - Create
    `packages/infra/stack/stack_constructs/hotel_assistant_mcp_construct.py`
  - Implement HotelAssistantMCPConstruct class
  - Build Docker image using DockerImageAsset with Dockerfile-mcp
  - Create IAM role for MCP server with bedrock:Retrieve and dynamodb:Scan
    permissions
  - Deploy using agentcore.Runtime with CUSTOM_JWT authorizer
  - Configure authorizer with cognito_discovery_url and cognito_allowed_clients
  - Set environment variables: KNOWLEDGE_BASE_ID, AWS_REGION, HOTELS_TABLE_NAME,
    LOG_LEVEL
  - Add CDK Nag suppressions for IAM permissions
  - _Requirements: 4.1, 4.2, 4.5_

- [x] 6. Integrate MCP server with HotelPMSStack and verify with CDK synth
  - Update `packages/infra/stack/hotel_pms_stack.py` to import
    HotelAssistantMCPConstruct
  - Instantiate MCP server construct after knowledge base and DynamoDB
    constructs
  - Pass knowledge_base_id, knowledge_base_arn, hotels_table_name,
    hotels_table_arn
  - Pass cognito_discovery_url and cognito_allowed_clients from
    jwt_authorizer_config
  - Add CfnOutput for MCPServerRuntimeArn and MCPServerRuntimeUrl
  - Run `uv run cdk synth` to verify infrastructure synthesizes correctly
  - _Requirements: 4.5_

- [ ]\* 7. Write integration tests for MCP server
  - Create
    `packages/hotel-pms-simulation/tests/mcp/integration/test_mcp_integration.py`
  - Test end-to-end knowledge query against real knowledge base
  - Test prompt generation with real DynamoDB hotel data
  - Test MCP server handler function
  - Mark tests with `@pytest.mark.integration`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
