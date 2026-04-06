# Implementation Plan

- [x] 1. Update backend API to accept optional conversationId
  - Modify SendMessageRequest model to include optional conversationId field
    with UUID validation
  - Update message creation logic to use provided conversationId or generate
    UUID if none provided
  - Update message service send_message method to pass through conversationId
    parameter
  - Write and run tests for backend API with and without conversationId
    parameter
  - Test UUID validation in SendMessageRequest model
  - _Requirements: 1.1, 1.3, 1.4, 2.1, 2.2, 2.3_

- [x] 2. Update Python messaging client
  - Add optional conversation_id parameter to send_message method
  - Include conversationId in request payload when provided
  - Return conversationId from API response to caller
  - Write and run tests for Python client with optional conversation_id
    parameter
  - Test error handling when conversationId is invalid
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Update TypeScript messaging client
  - Add optional conversationId parameter to sendMessage method
  - Include conversationId in request payload when provided
  - Add generateNewConversationId utility method using crypto.randomUUID()
  - Write and run tests for TypeScript client with optional conversationId
    parameter
  - Test generateNewConversationId utility method
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Add New Session button to demo frontend
  - Create simple NewSessionButton component with refresh icon
  - Add button to chat interface header or input area
  - Implement handleNewSession function to clear messages and generate new
    conversationId
  - Show success flash message when new session starts
  - Write and run tests for New Session button functionality
  - Test component rendering and click behavior
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 5. Update conversation state management in frontend
  - Add currentConversationId state to chat component
  - Pass conversationId to sendMessage calls when available
  - Update conversationId state from API response for first message
  - Clear conversationId when starting new session
  - Write and run tests for conversation state management
  - Test state updates and message flow with conversationId
  - _Requirements: 5.2, 5.3, 5.4_
