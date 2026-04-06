# Implementation Plan

- [x] 1. Set up base application structure and configuration
  - Create new package.json with minimal dependencies for Hotel Assistant
    messaging
  - Update vite.config.ts for Hotel Assistant branding and build configuration
  - Configure TypeScript settings for messaging functionality
  - _Requirements: 8.1, 8.3, 8.4_

- [x] 2. Update CDK infrastructure for S3 configuration deployment
  - Remove CloudFront distribution from messaging_stack.py
  - Create S3 bucket for storing runtime-config.json (private bucket)
  - Implement CDK custom resource to generate and upload runtime-config.json to
    S3
  - Update stack outputs to include S3 bucket name for configuration access
  - _Requirements: 6.1, 6.2_
- [x] 3. Update NX project configuration
  - Update project.json with correct build and serve targets for Hotel Assistant
  - Add load:runtime-config target to download configuration from S3 bucket
  - Configure development and production build settings
  - Update vite.config.ts with Hotel Assistant branding and auth vendor chunk
  - _Requirements: 6.1, 6.2_

- [x] 4. Configure authentication and runtime configuration
  - Update CognitoAuth component to use Hotel Assistant Cognito settings
  - Modify RuntimeConfig component to support Hotel Assistant configuration
    schema
  - Update main.tsx to use Hotel Assistant configuration instead of prescription
    reader config
  - _Requirements: 1.1, 1.2, 6.3, 6.5_

- [x] 5. Update application branding and navigation
  - Update application name to "Hotel Assistant" in configuration and components
  - Remove Smart Prescription Reader navigation items from navitems.ts
  - Add Hotel Assistant Chat navigation items
  - Update page titles and branding throughout the application
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 6. Remove prescription reader functionality
  - Delete prescription reader pages and components
  - Remove prescription reader routes from routing configuration
  - Clean up unused imports and dependencies related to prescription
    functionality
  - Update routing to default to Hotel Assistant chat interface
  - Fix TypeScript compilation errors by removing prescription reader code
  - Test NX targets for building and serving the application after cleanup
  - _Requirements: 1.3, 1.4_

- [x] 7. Migrate messaging API client with new authentication
  - Copy MessagingApiClient from
    packages/frontend/src/lib/messaging-api-client.ts
  - Update getAuthToken method to use react-oidc-context instead of AWS Amplify
  - Update getUserId method to use react-oidc-context user information
  - Test API client with new authentication system
  - _Requirements: 3.1, 3.2, 3.5_

- [x] 7.1. Fix unit tests
  - Run unit tests with `nx test @hotel-assistant/demo`
  - Identify which tests are useful
  - Remove useless tests
  - Fix remaining tests

- [x] 8. Migrate messaging hooks and state management
  - Copy messaging hooks from packages/frontend/src/lib/messaging-hooks.ts
  - Update hooks to use new MessagingApiClient with react-oidc-context
  - Integrate error handling with GlobalUIContext flash notifications
  - Test messaging hooks with React Query and new authentication
  - _Requirements: 3.3, 3.4, 5.1, 5.4_

- [x] 9. Migrate chatbot configuration and types
  - Copy chatbot configuration from packages/frontend/src/lib/chatbot-config.ts
  - Copy type definitions from packages/frontend/src/types/index.ts
  - Update configuration to work with new runtime config system
  - Ensure all messaging types are properly defined
  - _Requirements: 6.4, 8.4_

- [x] 10. Create main chatbot page component
  - Create new HotelAssistantChat page component
  - Implement page layout using Cloudscape Design System
  - Integrate with AppLayout structure from demo
  - Set up routing to chatbot page as default route
  - _Requirements: 2.1, 4.5, 1.4_

- [x] 11. Migrate and integrate Chatbot component
  - Copy Chatbot component from
    packages/frontend/src/components/chatbot/Chatbot.tsx
  - Update error handling to use GlobalUIContext flash notifications instead of
    inline alerts
  - Integrate with new messaging hooks and authentication system
  - Test chatbot functionality with new infrastructure
  - _Requirements: 4.1, 4.5, 5.1, 5.2_

- [x] 12. Migrate ChatMessage component
  - Copy ChatMessage component from
    packages/frontend/src/components/chatbot/ChatMessage.tsx
  - Ensure compatibility with Cloudscape Design System styling
  - Test message display with user/assistant differentiation
  - Verify timestamp and status indicator functionality
  - _Requirements: 4.2_

- [x] 13. Migrate ChatInput component
  - Copy ChatInput component from
    packages/frontend/src/components/chatbot/ChatInput.tsx
  - Ensure model selection and temperature controls work properly
  - Integrate input validation and submission handling
  - Test chat input functionality with new messaging system
  - _Requirements: 4.3_

- [x] 14. Migrate loading and status components
  - Copy MessageSkeleton component for loading states
  - Copy PollingIndicator component for background polling indication
  - Ensure components integrate properly with Cloudscape Design System
  - Test loading states and polling indicators
  - _Requirements: 4.4_

- [x] 15. Implement flash notification error handling
  - Replace all inline error alerts with GlobalUIContext flash notifications
  - Update messaging error handling to use addFlashItem function
  - Implement retry functionality through flash notification actions
  - Test error scenarios with flash notifications
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 16. Test infrastructure changes
  - Deploy updated CDK stack without CloudFront
  - Verify S3 bucket creation and runtime-config.json upload
  - Test load:runtime-config NX target with new S3 bucket
  - Verify configuration download works with AWS credentials
  - _Requirements: 6.1, 6.2_

- [ ] 17. Test complete messaging functionality
  - Test user authentication flow with Cognito
  - Test sending and receiving messages through chat interface
  - Test error handling and flash notifications
  - Test configuration loading from both runtime-config.json and environment
    variables
  - _Requirements: 2.2, 2.3, 2.4, 2.5_

- [ ] 18. Clean up and optimize dependencies
  - Remove unused dependencies from package.json
  - Verify all required dependencies are included
  - Test application build and bundle size
  - Ensure no AWS Amplify dependencies remain
  - _Requirements: 8.1, 8.2, 8.5_

- [ ] 19. Final integration testing and cleanup
  - Test complete user flow from login to messaging
  - Verify all Hotel Assistant branding is applied correctly
  - Test both development and production configurations
  - Clean up any remaining prescription reader references
  - _Requirements: 1.5, 7.4, 6.1, 6.2_
