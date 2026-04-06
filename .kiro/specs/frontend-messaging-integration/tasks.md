# Implementation Plan

- [x] 1. Update infrastructure configuration to include messaging backend
     properties
- [x] 1.1 Update CDK custom resource construct
  - Modify `packages/infra/stack/stack_constructs/custom_resource_construct.py`
    to pass messaging API endpoint and hotel assistant client ID
  - Add properties for `VITE_MESSAGING_API_ENDPOINT` and
    `VITE_HOTEL_ASSISTANT_CLIENT_ID` to the custom resource
  - _Requirements: 1.2, 1.3_

- [x] 1.2 Update config.js generation Lambda function
  - Modify `packages/infra/stack/lambdas/update_config_js_fn/index.py` to
    include new messaging properties in config.js output
  - Add messaging API endpoint and hotel assistant client ID to the generated
    window.APP_CONFIG object
  - _Requirements: 1.1, 1.2_

- [x] 2. Update messaging backend API to support optional model parameters
- [x] 2.1 Update SendMessageRequest model to accept modelId and temperature
  - Modify `SendMessageRequest` in
    `packages/chatbot-messaging-backend/chatbot_messaging_backend/handlers/lambda_handler.py`
  - Add optional `model_id` and `temperature` fields with proper validation
    using Pydantic
  - _Requirements: 4.2_

- [x] 2.2 Update message service to handle and pass through model parameters
  - Modify message service to accept model parameters and include them in SNS
    messages
  - Ensure parameters are passed through to downstream systems for AI model
    configuration
  - _Requirements: 4.2_

- [x] 3. Install and configure TanStack Query for state management
- [x] 3.1 Install TanStack Query dependency in frontend package
  - Run `pnpm add @tanstack/react-query` in packages/frontend directory
  - Update package.json with the new dependency for API state management
  - _Requirements: 3.1_

- [x] 3.2 Configure TanStack Query provider at application root
  - Create QueryClient instance with appropriate cache settings for messaging
    data
  - Wrap application with QueryClientProvider in main.tsx or App.tsx
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 4. Update frontend configuration management to include messaging
     properties
- [x] 4.1 Extend existing chatbot configuration with messaging backend
      properties
  - Add messaging API endpoint and hotel assistant client ID to config interface
  - Update configuration loading in `chatbot-config.ts` to include new messaging
    properties
  - _Requirements: 1.1, 1.2_

- [x] 5. Create messaging API client to replace AgentCore communication
- [x] 5.1 Implement MessagingApiClient class with authentication
  - Create new file `packages/frontend/src/lib/messaging-api-client.ts`
  - Implement sendMessage and getMessages methods with proper Bearer token
    authentication
  - Include conversation ID generation logic using lexicographic sorting
  - _Requirements: 2.1, 2.2, 4.1, 4.2, 8.1, 8.2, 8.3_

- [x] 5.2 Add Amplify authentication integration to API client
  - Use Amplify fetchAuthSession to get access tokens with
    "chatbot-messaging/write" scope
  - Include Bearer token in all API requests to messaging backend
  - Handle authentication errors gracefully using existing Amplify error
    handling
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 6. Create TanStack Query hooks for messaging operations
- [x] 6.1 Implement useSendMessage mutation hook with optimistic updates
  - Create mutation hook that calls MessagingApiClient.sendMessage
  - Include optimistic updates to immediately show sent messages in UI
  - Handle success and error states with proper user feedback
  - _Requirements: 4.1, 4.3, 4.4, 11.1_

- [x] 6.2 Implement useMessages query hook with automatic polling
  - Create query hook that calls MessagingApiClient.getMessages
  - Configure 5-second polling using TanStack Query's refetchInterval
  - Handle loading states and errors for message retrieval
  - _Requirements: 5.1, 5.2, 6.1, 6.2, 11.2_

- [x] 7. Update message data models and interfaces to match backend API
- [x] 7.1 Create TypeScript message interfaces matching backend structure
  - Define Message interface with all required fields from backend API
  - Add computed isUser field based on senderId comparison with current user
  - Include MessageStatus enum for status indicators (sent, delivered, read,
    failed)
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. Update Chatbot component to use messaging backend instead of AgentCore
- [x] 8.1 Replace AgentCoreService with MessagingApiClient and TanStack Query
      hooks
  - Remove AgentCoreService import and instantiation from Chatbot component
  - Update message sending logic to use useSendMessage hook
  - Update message retrieval to use useMessages hook with conversation ID
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 8.2 Update message state management to use TanStack Query
  - Remove local message state management in favor of TanStack Query cache
  - Update message rendering to use data from useMessages hook
  - Handle loading states from TanStack Query instead of local state
  - _Requirements: 5.1, 5.2, 11.1, 11.2, 11.3_

- [x] 8.3 Integrate conversation ID generation using user ID and assistant
      client ID
  - Generate conversation ID using user ID from Amplify and hotel assistant
    client ID
  - Use lexicographic sorting for consistent conversation ID format
  - Use conversation ID for both message retrieval and sending operations
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 9. Implement message status indicators using CloudScape components
- [x] 9.1 Create MessageStatusIcon component using CloudScape StatusIndicator
  - Implement component using CloudScape StatusIndicator with icon-only display
  - Map message statuses: sent→pending, delivered→in-progress, read→success,
    failed→error
  - Include proper accessibility labels for screen readers
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 9.2 Update ChatMessage component to display status icons for user messages
  - Add MessageStatusIcon to user messages only (not assistant messages)
  - Position status indicator appropriately in message layout
  - Ensure status updates automatically when message status changes
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Implement error handling and user feedback for API operations
- [x] 10.1 Create error display components using CloudScape Alert
  - Use CloudScape Alert component for error messages
  - Create reusable error handling for different error types (network, auth,
    API)
  - Display appropriate user-friendly messages for each error scenario
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 10.2 Integrate error handling with TanStack Query hooks
  - Configure error handling in query and mutation hooks
  - Display errors in chat interface when API calls fail
  - Allow users to retry failed operations through UI controls
  - _Requirements: 9.1, 9.4, 9.5_

- [x] 11. Add loading states and UI feedback for better user experience
- [x] 11.1 Add loading indicators for message operations using CloudScape
      components
  - Show loading indicator on send button while message is being sent
  - Display skeleton loading states while retrieving message history
  - Use CloudScape loading components for consistent UI patterns
  - _Requirements: 11.1, 11.2, 11.5_

- [x] 11.2 Implement subtle polling feedback without disrupting user experience
  - Show subtle indicator when polling for new messages in background
  - Ensure polling doesn't interfere with user typing or interaction
  - _Requirements: 11.3_

- [ ] 12. Test and validate complete integration functionality
- [ ] 12.1 Test message sending and receiving through messaging backend
  - Send messages through the new messaging backend API
  - Verify messages appear with correct status indicators
  - Test model parameter integration (modelId and temperature) from existing UI
    controls
  - _Requirements: 4.1, 4.2, 4.3, 7.1, 7.2, 7.3_

- [ ] 12.2 Test polling and real-time message updates
  - Verify that new messages appear automatically through 5-second polling
  - Test conversation history loading and display
  - Validate that assistant responses are received and displayed correctly
  - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3_

- [ ] 12.3 Test error scenarios and edge cases
  - Test behavior with network errors and connectivity issues
  - Verify authentication error handling and token refresh
  - Test with invalid or missing configuration values
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
