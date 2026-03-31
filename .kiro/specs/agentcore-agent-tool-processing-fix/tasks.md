# Implementation Plan

- [x] 1. Simplify event stream processing
  - Remove warnings for tool events by only processing message events
  - Update event processing loop to ignore toolUse and toolResult events
    completely
  - Test that tool events pass through without interference
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Restructure agent creation with MCP context
  - Move MCP client creation to module level
  - Wrap entire application (app creation, entrypoint, app.run) in MCP context
  - Load tools once within MCP context at module level
  - Remove complex global agent management pattern
  - Write unit tests for MCP client initialization and tool loading
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 3. Implement session/actor validation
  - Add global variables to track current session_id and actor_id
  - Create agent once per execution with proper session context
  - Add strict validation that session/actor don't change within execution
  - Raise RuntimeError if session or actor changes during execution
  - Write unit tests for session/actor validation logic
  - _Requirements: 2.4, 2.5, 4.1, 4.2_

- [x] 4. Remove async task complexity
  - Keep @app.async_task pattern but simplify the logic
  - Remove complex agent reuse logic and session context updates
  - Create agent once per execution, validate consistency
  - Process messages directly within MCP context
  - Write unit tests for simplified async task processing
  - _Requirements: 2.1, 2.2, 3.1_

- [x] 5. Add strict configuration validation
  - Replace graceful degradation with strict validation
  - Validate AGENTCORE_MEMORY_ID is configured or fail fast
  - Validate MCP client creation or fail fast
  - Provide clear error messages for missing configuration
  - Write unit tests for configuration validation scenarios
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 6. Update SessionManager creation
  - Create SessionManager per session/actor combination
  - Remove update_session_context function (not needed in isolated environment)
  - Use session_id and actor_id from invocation parameters
  - Validate SessionManager creation or fail fast
  - Write unit tests for SessionManager creation and validation
  - _Requirements: 4.3, 4.4, 4.5_

- [x] 7. Test tool functionality
  - Write unit tests for tool event processing (or lack thereof)
  - Test that tools work without warnings in integration tests
  - Verify tool invocation and results are processed correctly
  - Test multiple tool usage in single conversation
  - Validate tool events don't generate log warnings
  - _Requirements: 1.4, 1.5, 5.5_

- [x] 8. Test session persistence
  - Write unit tests for session/actor validation logic
  - Test conversation continuity across multiple messages in same session
  - Verify agent reuse works correctly within same execution
  - Test that session/actor validation catches changes correctly
  - Validate memory persistence works as expected
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 9. Remove global agent pattern files
  - Delete `global_agent.py` file completely
  - Delete tests related to global agent pattern (test_global_agent.py, etc.)
  - Remove imports of global_agent from agent.py
  - Remove complex MCPAwareAgent wrapper class
  - Update any remaining references to global agent functions
  - _Requirements: 2.1, 2.2, 3.1, 3.2_

- [x] 10. Clean up and optimize
  - Remove unused imports and functions from agent.py
  - Simplify error handling and logging
  - Write unit tests for cleaned up components
  - Update documentation and comments
  - _Requirements: 3.1, 3.2, 3.3_
