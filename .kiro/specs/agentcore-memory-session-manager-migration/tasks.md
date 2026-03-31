# Implementation Plan

- [x] 1. Update dependencies and imports
  - Update bedrock-agentcore dependency to include strands-agents extra with
    minimum version 0.1.3
  - Add imports for AgentCore Memory components (MemoryClient,
    AgentCoreMemoryConfig, AgentCoreMemorySessionManager)
  - Remove imports for custom memory hook components
  - _Requirements: 1.4_

- [x] 2. Implement global agent pattern with lazy initialization
  - Write unit tests for get_or_create_agent lazy initialization logic (first
    call, reuse, recreation scenarios)
  - Add global variables for agent, session_id, and actor_id at module level
  - Create get_or_create_agent function that implements lazy initialization
    pattern
  - Implement logic to detect when agent needs to be recreated (session/actor
    changes)
  - Add thread safety considerations for global agent access
  - _Requirements: 1.3, 1.5, 6.1, 6.5_

- [x] 3. Implement memory client initialization
  - Write unit tests for initialize_memory_client function (success, failure,
    missing config scenarios)
  - Create initialize_memory_client function with error handling
  - Read AGENTCORE_MEMORY_ID and AWS_REGION from environment variables
  - Add proper logging for successful initialization and failure cases
  - Return None gracefully when memory is not configured
  - _Requirements: 2.1, 2.2, 4.1, 4.2_

- [x] 4. Implement session manager factory
  - Write unit tests for create_session_manager function (valid params, invalid
    config, error scenarios)
  - Create create_session_manager function that takes session_id and actor_id
  - Configure AgentCoreMemoryConfig with provided parameters
  - Create AgentCoreMemorySessionManager with proper error handling
  - Add logging for session manager creation success and failures
  - _Requirements: 2.3, 4.3, 4.4_

- [x] 5. Refactor agent creation logic
  - Update agent instantiation to use SessionManager instead of custom hooks
  - Remove MemoryHookProvider usage and related hook registration
  - Remove greeting functionality from agent creation
  - Ensure agent uses existing model, system_prompt, and tools configuration
  - _Requirements: 1.1, 1.2, 3.2_

- [x] 6. Update async message processing function
  - Modify process_user_message to use get_or_create_agent function
  - Remove custom memory hook initialization code
  - Remove greeting-related logic and variables
  - Update agent usage to work with global agent pattern
  - _Requirements: 1.1, 1.2, 3.1, 3.4_

- [x] 7. Update entrypoint function
  - Ensure session_id and actor_id are properly extracted and passed to
    get_or_create_agent
  - Remove any custom memory hook related parameter passing
  - Maintain existing error handling and response patterns
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Remove custom memory hook files
  - Delete memory_hooks.py file
  - Remove any other custom memory implementation files
  - Clean up any remaining imports or references to removed files
  - _Requirements: 6.1_

- [x] 9. Remove obsolete tests
  - Remove tests for MemoryHookProvider functionality
  - Remove tests for greeting functionality
  - Remove tests specific to custom memory hook implementation
  - Update any remaining tests to work with new SessionManager approach
  - _Requirements: 6.1_

- [x] 10. Update error handling and logging
  - Ensure all memory-related errors are handled gracefully without affecting
    core functionality
  - Add appropriate logging levels for different scenarios (info for success,
    warning for failures)
  - Ensure error messages don't expose sensitive information to users
  - Test that agent continues to function when memory is unavailable
  - _Requirements: 2.2, 2.4, 4.1, 4.2, 4.3, 4.4_

- [x] 11. Validate session persistence and memory functionality
  - Write integration tests for agent functionality with SessionManager
  - Write tests for error handling scenarios (memory unavailable, invalid
    config)
  - Test that conversation history is maintained within sessions
  - Verify that AgentCore Runtime routes same-session messages to same agent
    instance
  - Test agent recreation when session parameters change
  - Validate that short-term memory works as expected with SessionManager
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 6.2, 6.3, 6.4_

- [x] 12. Investigate and fix agent_default actor issue in memory
  - Add comprehensive logging to track actor_id flow from WhatsApp message
    processing through AgentCore invocation
  - Investigate why AgentCore Memory creates events with "agent_default" instead
    of phone number actor_id
  - Verify that AgentCoreInvocationRequest properly passes actor_id to the agent
  - Test that memory events are created with correct actor_id (phone number) for
    WhatsApp users
  - Ensure each WhatsApp user gets isolated memory context instead of sharing
    agent_default
  - Add validation to prevent actor_id from being defaulted or sanitized
    incorrectly
  - _Requirements: 2.1, 3.1, 3.2, 6.1_
