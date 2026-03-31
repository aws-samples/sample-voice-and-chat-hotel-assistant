# Implementation Plan

## Phase 1: Create MCP Infrastructure Components

- [x] 1. Create MCP configuration management module
  - Create
    `packages/virtual-assistant/virtual-assistant-common/virtual_assistant_common/mcp/`
    directory
  - Create `__init__.py` with exports
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

- [x] 1.1 Implement MCPConfigManager class
  - Create `config_manager.py` with `MCPServerConfig` dataclass
  - Implement `load_config()` method to read from SSM Parameter Store
  - Implement `_validate_server_config()` to validate standard MCP format
  - Implement `get_credentials()` to retrieve from Secrets Manager
  - Implement `find_prompt_server()` to locate server with systemPrompts
  - Handle SSM ParameterNotFound exception with clear error message
  - Handle JSON parsing errors with clear error message
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.1, 2.2_

- [x] 1.1.1 Write unit tests for MCPConfigManager
  - Create `tests/test_mcp_config_manager.py`
  - Test successful configuration loading from SSM
  - Test parameter not found error handling
  - Test invalid JSON error handling
  - Test server configuration validation
  - Test credentials retrieval from Secrets Manager
  - _Requirements: 11.1, 11.2_

- [x] 1.2 Implement MultiMCPClientManager class
  - Create `multi_client_manager.py` with `MultiMCPClientManager` class
  - Implement `initialize()` method to connect to all configured servers
  - Implement `_discover_tools()` with conflict resolution (server\_\_tool
    naming)
  - Implement `get_prompt()` to retrieve prompts from configured server
  - Implement `get_mcp_clients()` to return dict of MCP client sessions for
    LiveKit
  - Implement `get_tools_for_strands()` to return list of tool objects for
    Strands
  - Handle connection failures gracefully (add to unavailable_servers set)
  - Support optional headers from configuration
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.1, 5.2, 5.3, 5.4,
    5.5, 5.6, 5.7, 5.8_

- [x] 1.2.1 Write unit tests for MultiMCPClientManager
  - Create `tests/test_multi_mcp_client_manager.py`
  - Test initialization with multiple servers
  - Test graceful handling of server connection failures
  - Test tool discovery with conflict resolution
  - Test prompt retrieval from configured server
  - _Requirements: 11.1, 11.2_

- [x] 1.3 Implement PromptLoader class
  - Create `prompt_loader.py` with `AssistantType` enum and `PromptLoader` class
  - Implement `load_prompt()` with fallback chain logic
  - Try configured prompt name from systemPrompts first
  - Fall back to default prompt name (chat_system_prompt/voice_system_prompt)
  - Fall back to default_system_prompt
  - Use emergency fallback if all MCP attempts fail
  - Implement `_get_emergency_fallback()` with "technical difficulties" messages
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

- [x] 1.3.1 Write unit tests for PromptLoader
  - Create `tests/test_prompt_loader.py`
  - Test successful prompt loading for chat and voice
  - Test fallback chain behavior
  - Test emergency fallback messages contain "technical difficulties"
  - _Requirements: 11.1, 11.2_

## Phase 2: Update CDK Infrastructure

- [x] 2. Update HotelPmsStack to generate and export MCP configuration
  - Update `packages/infra/stack/hotel_pms_stack.py`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

- [x] 2.1 Create Secrets Manager secrets for MCP credentials
  - Implement `_create_mcp_secret()` method
  - Create secret for Hotel Assistant MCP with Cognito credentials
  - Create secret for Hotel PMS MCP with Cognito credentials
  - Include userPoolId, clientId, clientSecret, region in secrets
  - Store secrets as instance variables for export
  - _Requirements: 2.3, 2.4, 2.5, 8.2, 8.3_

- [x] 2.2 Generate and store MCP configuration JSON in SSM
  - Build configuration dictionary with standard mcpServers format
  - Use "type": "streamable-http" for both servers
  - Include authentication with secretArn references
  - Add systemPrompts configuration to Hotel Assistant MCP only
  - Set chat: "chat_system_prompt" and voice: "voice_system_prompt"
  - Create SSM StringParameter at /hotel-assistant/mcp-config
  - Store as instance variable for export
  - _Requirements: 1.7, 1.8, 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 2.3 Export MCP configuration resources from HotelPmsStack
  - Add CfnOutput for mcp_config_parameter_name
  - Add CfnOutput for hotel_assistant_mcp_secret_arn
  - Add CfnOutput for hotel_pms_mcp_secret_arn
  - Store outputs as public properties for cross-stack references
  - _Requirements: 8.4, 8.5_

- [x] 2.4 Update VirtualAssistantStack to accept MCP configuration inputs
  - Create new `packages/infra/stack/virtual_assistant_stack.py` (or update
    existing)
  - Add constructor parameters: mcp_config_parameter, mcp_secrets (list)
  - Grant SSM parameter read access to chat agent role
  - Grant SSM parameter read access to voice agent role
  - Grant Secrets Manager read access to chat agent role for all provided
    secrets
  - Grant Secrets Manager read access to voice agent role for all provided
    secrets
  - Add MCP_CONFIG_PARAMETER env var to chat agent function
  - Add MCP_CONFIG_PARAMETER env var to voice agent container
  - _Requirements: 1.9, 1.10, 2.6, 2.7, 8.6, 8.7_

- [x] 2.5 Update main CDK app to wire stacks together
  - Update `packages/infra/app.py` (or equivalent)
  - Pass HotelPmsStack outputs to VirtualAssistantStack
  - Pass mcp_config_parameter from HotelPmsStack
  - Pass list of secrets [hotel_assistant_secret, hotel_pms_secret]
  - Ensure proper stack dependencies
  - _Requirements: 8.4, 8.5, 8.6, 8.7_

## Phase 3: Update Virtual Assistant Chat

- [x] 3. Integrate MCP configuration in chat agent
  - Update
    `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 3.1 Replace single MCP client with multi-client manager
  - Import MCPConfigManager, MultiMCPClientManager, PromptLoader, AssistantType
  - Remove `MCPClient(hotel_pms_mcp_client)` pattern
  - Initialize MCPConfigManager at module level
  - Initialize MultiMCPClientManager at module level
  - Initialize PromptLoader at module level
  - _Requirements: 6.1, 6.2_

- [x] 3.2 Load system prompt from MCP server
  - Create async `initialize_mcp()` function
  - Call `client_manager.initialize()` to connect to all servers
  - Call `prompt_loader.load_prompt(AssistantType.CHAT)` to get prompt
  - Run initialization synchronously at module level with asyncio.run()
  - Remove `generate_dynamic_hotel_instructions()` call
  - _Requirements: 3.1, 3.8, 3.9, 6.1_

- [x] 3.3 Update agent creation to use MCP tools
  - Get tools from `client_manager.get_tools_for_strands()`
  - Pass loaded prompt as system_prompt to Agent
  - Pass tools list to Agent constructor
  - Keep existing agent creation pattern (once per execution)
  - Keep existing session manager and model configuration
  - _Requirements: 6.2, 6.3, 6.6_

- [x] 3.4 Write integration tests for chat agent
  - Create `tests/integration/test_chat_agent_mcp_integration.py`
  - Test chat agent loads configuration from SSM
  - Test chat agent loads prompt from MCP (not emergency fallback)
  - Test chat agent has tools from both MCP servers
  - Mark tests with @pytest.mark.integration
  - _Requirements: 11.3, 11.4, 11.5_

## Phase 4: Update Virtual Assistant Voice

- [x] 4. Integrate MCP configuration in voice agent
  - Update
    `packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/agent.py`
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

- [x] 4.1 Update prewarm function to use multi-client manager
  - Import MCPConfigManager, MultiMCPClientManager, PromptLoader, AssistantType
  - Remove `hotel_pms_mcp_client()` call
  - Create async `_initialize_mcp()` function in prewarm
  - Initialize MCPConfigManager, MultiMCPClientManager, PromptLoader
  - Call `client_manager.initialize()` to connect to all servers
  - Call `prompt_loader.load_prompt(AssistantType.VOICE)` to get prompt
  - Store instructions and client_manager in proc.userdata
  - _Requirements: 7.1, 7.2_

- [x] 4.2 Update entrypoint to use MCP clients for LiveKit
  - Retrieve instructions and client_manager from ctx.proc.userdata
  - Get MCP client sessions from `client_manager.get_mcp_clients()`
  - Create list of HotelPmsMCPServer wrappers for each client
  - Pass mcp_servers list to AgentSession
  - Remove old single MCP server connection code
  - _Requirements: 7.3, 7.4, 7.5, 7.6_

- [x] 4.3 Write integration tests for voice agent
  - Create `tests/integration/test_voice_agent_mcp_integration.py`
  - Test voice agent prewarm loads MCP configuration
  - Test voice agent prompt is concise (< 1000 chars)
  - Test voice agent prompt not emergency fallback
  - Mark tests with @pytest.mark.integration
  - _Requirements: 11.3, 11.4, 11.5_

## Phase 5: Integration Testing and Validation

- [x] 5. End-to-end integration testing
  - _Requirements: 11.5, 11.6, 11.7_

- [x] 5.1 Test multi-MCP server integration
  - Use cloudformation stack outputs to get real AWS resource ids
  - Create `tests/integration/test_multi_mcp_servers.py`
  - Test both Hotel Assistant and Hotel PMS MCP servers accessible
  - Test tools discovered from both servers
  - Test prompts loaded from Hotel Assistant MCP only
  - Verify no unavailable servers
  - _Requirements: 11.7_

- [ ]\* 5.2 Test error scenarios
  - Test handling of missing SSM parameter
  - Test handling of invalid JSON configuration
  - Test handling of MCP server connection failures
  - Test handling of Secrets Manager access denied
  - Test emergency fallback prompt usage
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 11.6_

- [x] 5.3 Verify hardcoded prompts removed
  - Verify chat agent no longer uses assets/system-prompt-\*.md files
  - Verify voice agent no longer uses assets/voice_prompt.txt file
  - Verify generate_dynamic_hotel_instructions() no longer called
  - Verify emergency fallback prompts indicate service unavailability
  - _Requirements: 3.8, 3.9, 11.8_

## Phase 6: Documentation and Cleanup

- [x] 6. Create configuration documentation
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

- [x] 6.1 Document MCP configuration format
  - Update README.md in virtual_assistant_common/
  - Document standard mcpServers format with examples
  - Explain extension fields (url, authentication, systemPrompts)
  - Document headers support for custom HTTP headers
  - Provide examples of adding new MCP servers
  - Document how to deploy VirtualAssistantStack with custom MCP servers
  - _Requirements: 10.1, 10.2, 10.5_

- [x] 6.2 Document configuration and deployment
  - Document SSM Parameter Store location
  - Explain authentication credential flow via Secrets Manager
  - Document environment variable requirements
  - Document IAM permissions needed
  - Provide troubleshooting steps for common issues
  - Document prompt name fallback behavior
  - Document cross-stack reference pattern for MCP configuration
  - _Requirements: 10.3, 10.4, 10.6, 10.7, 10.8_

- [x] 6.3 Optional: Remove old prompt files
  - Remove assets/system-prompt-es-mx.md from chat agent
  - Remove assets/system-prompt-en.md from chat agent
  - Remove assets/voice_prompt.txt from voice agent
  - Keep emergency fallback prompts in code
  - Update .gitignore if needed
  - _Note: This is optional cleanup, not required for functionality_
