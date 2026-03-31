# Implementation Plan

- [x] 1. Update dependencies and imports
  - Add bedrock-agentcore memory imports to agent.py
  - Import Strands hooks (AgentInitializedEvent, MessageAddedEvent,
    HookProvider, HookRegistry)
  - Add logging for memory operations
  - _Requirements: 2.1, 3.1_

- [x] 2. Create MemoryHookProvider class
  - Create new file hotel_assistant_chat/memory_hooks.py
  - Implement MemoryHookProvider with **init** method taking memory_client,
    memory_id, actor_id, session_id
  - Implement on_agent_initialized method to load last 30 conversation turns
    using get_last_k_turns (configurable via AGENTCORE_MEMORY_MAX_TURNS
    environment variable)
  - Implement on_message_added method to store messages using create_event
  - Add \_format_conversation_history helper method to format turns for agent
    context
  - Add error handling with try/except blocks and warning logs
  - Implement register_hooks method to register callbacks with HookRegistry
  - _Requirements: 2.2, 2.3, 3.1, 3.2, 6.1, 6.2, 7.1, 7.2_

- [x] 3. Enhance agent creation with memory support
  - Modify create_agent function to create_agent_with_memory with actor_id and
    session_id parameters
  - Add memory client initialization using MemoryClient with AWS region
  - Get memory_id from AGENTCORE_MEMORY_ID environment variable
  - Create MemoryHookProvider instance if memory_id is available
  - Add memory hooks to agent configuration alongside existing MCP tools
  - Implement graceful fallback to empty hooks list if memory initialization
    fails
  - Preserve all existing MCP tool and prompt functionality
  - _Requirements: 3.3, 4.1, 7.3, 8.1, 8.2, 8.3_

- [x] 4. Update FastAPI request/response models
  - Modify InvocationRequest class to include optional session_id and actor_id
    fields
  - Update InvocationResponse class to include session_id and actor_id in output
  - Add default values for session_id ("default_session") and actor_id
    ("default_user")
  - _Requirements: 1.1, 1.4, 5.1, 5.4_

- [x] 5. Update FastAPI endpoint handler
  - Modify invoke_agent endpoint to extract session_id and actor_id from request
  - Call create_agent_with_memory instead of create_agent with session
    parameters
  - Include session_id and actor_id in response output
  - Ensure existing error handling continues to work
  - _Requirements: 1.2, 5.2, 5.3_

- [x] 6. Add environment variable configuration
  - Update .env.example with AGENTCORE_MEMORY_ID and AGENTCORE_MEMORY_MAX_TURNS
    configuration
  - Add documentation comment explaining the memory ID should be set by
    infrastructure
  - _Requirements: 4.2, 4.4_

- [x] 7. Create unit tests for memory functionality
  - Create tests/test_memory_hooks.py file
  - Test MemoryHookProvider initialization and hook registration
  - Test on_agent_initialized loads conversation history correctly
  - Test on_message_added stores messages in memory
  - Test error handling when memory operations fail
  - Mock MemoryClient for isolated testing
  - _Requirements: 9.1_

- [x] 8. Create integration tests for conversation continuity
  - Add test_conversation_continuity to tests/test_integration.py
  - Test that messages persist across multiple agent invocations with same
    session
  - Test that different sessions have isolated memory spaces
  - Test agent continues working when AGENTCORE_MEMORY_ID is not set
  - _Requirements: 9.2, 9.3_

- [x] 9. Update documentation
  - Update README.md with memory functionality description
  - Document new environment variables and session parameters
  - Add example usage showing session management
  - _Requirements: 4.3_
