# Design Document

## Overview

This design outlines the technical approach for transforming the Smart
Prescription Reader demo into a Hotel Assistant messaging application. We will
leverage the demo's proven authentication infrastructure, UI framework, and
architectural patterns while completely replacing the prescription functionality
with messaging capabilities.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Hotel Assistant App                      │
├─────────────────────────────────────────────────────────────┤
│  Authentication Layer (react-oidc-context)                 │
│  ├─ CognitoAuth Component                                   │
│  ├─ Runtime Config Provider                                 │
│  └─ Authentication State Management                         │
├─────────────────────────────────────────────────────────────┤
│  UI Layer (Cloudscape Design System)                       │
│  ├─ AppLayout with Navigation                               │
│  ├─ GlobalUIContext (Flash Notifications)                  │
│  └─ Responsive Layout Components                            │
├─────────────────────────────────────────────────────────────┤
│  Messaging Layer                                            │
│  ├─ Chatbot Component                                       │
│  ├─ Message Components (ChatMessage, ChatInput)            │
│  ├─ Messaging Hooks (React Query)                          │
│  └─ MessagingApiClient                                      │
├─────────────────────────────────────────────────────────────┤
│  Configuration Layer                                        │
│  ├─ Runtime Config (deployment)                            │
│  ├─ Environment Variables (development)                     │
│  └─ Chatbot Configuration                                   │
└─────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
App
├── RuntimeConfigProvider
    ├── CognitoAuth
        ├── QueryClientProvider
            ├── GlobalUIContextProvider
                ├── AppLayout
                    ├── TopNavigation
                    ├── SideNavigation
                    ├── Breadcrumbs
                    ├── Flashbar (notifications)
                    └── Content Area
                        └── ChatbotPage
                            ├── Chatbot
                            │   ├── ChatMessage (multiple)
                            │   ├── MessageSkeleton (loading)
                            │   ├── PollingIndicator
                            │   └── ChatInput
                            └── ErrorAlert (flash notifications)
```

## Components and Interfaces

### Authentication Components (Reused from Demo)

#### CognitoAuth

- **Purpose**: Handles OIDC authentication flow
- **Configuration**: Uses runtime-config.json or environment variables
- **Scopes**: 'aws.cognito.signin.user.admin', 'openid', 'profile',
  'chatbot-messaging/write'
- **Integration**: Provides authentication context to messaging components

#### RuntimeConfigProvider

- **Purpose**: Manages configuration loading
- **Sources**: runtime-config.json (deployment) or import.meta.env (development)
- **Pattern**: Same as demo but with Hotel Assistant configuration

### UI Framework Components (Reused from Demo)

#### AppLayout

- **Purpose**: Main application layout with navigation
- **Modifications**: Update navigation items and branding
- **Components**: TopNavigation, SideNavigation, Breadcrumbs

#### GlobalUIContextProvider

- **Purpose**: Manages flash notifications and UI state
- **Usage**: Replace error alerts with flash notifications
- **Integration**: Used by messaging components for error display

### Messaging Components (Migrated from Frontend)

#### Chatbot

- **Purpose**: Main chat interface container
- **Dependencies**: Messaging hooks, error handling, configuration
- **Features**: Message display, loading states, error handling
- **Integration**: Uses GlobalUIContext for flash notifications

#### ChatMessage

- **Purpose**: Individual message display component
- **Features**: User/assistant differentiation, timestamps, status indicators
- **Styling**: Cloudscape Design System components

#### ChatInput

- **Purpose**: Message input with model configuration
- **Features**: Text input, model selection, temperature control
- **Validation**: Input validation and submission handling

#### MessageSkeleton

- **Purpose**: Loading state placeholder
- **Usage**: Displayed during message loading

#### PollingIndicator

- **Purpose**: Subtle indicator for background polling
- **Integration**: Shows when fetching new messages

### API and State Management

#### MessagingApiClient

- **Purpose**: HTTP client for messaging API
- **Authentication**: Uses react-oidc-context tokens instead of Amplify
- **Methods**: sendMessage, getMessages, getMessagesSince,
  generateConversationId
- **Error Handling**: Integrates with flash notification system

#### Messaging Hooks

- **useSendMessage**: Mutation for sending messages
- **useMessages**: Query for retrieving messages with polling
- **useConversationId**: Query for generating conversation IDs
- **useMessagesSince**: Optimized polling for new messages
- **Integration**: Uses React Query with flash notifications for errors

## Data Models

### Configuration Interfaces

```typescript
interface RuntimeConfig {
  cognitoProps: {
    userPoolId: string;
    userPoolWebClientId: string;
    region: string;
  };
  messagingApiEndpoint: string;
  hotelAssistantClientId: string;
  applicationName: string;
  logo?: string;
}

interface ChatbotConfig {
  awsRegion: string;
  messagingApiEndpoint: string;
  hotelAssistantClientId: string;
}
```

### Message Interfaces (Reused)

```typescript
interface Message {
  messageId: string;
  conversationId: string;
  senderId: string;
  recipientId: string;
  content: string;
  status: MessageStatus;
  timestamp: string;
  createdAt: string;
  updatedAt: string;
  isUser: boolean;
}

enum MessageStatus {
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed',
}
```

### API Response Interfaces (Reused)

```typescript
interface SendMessageResponse {
  message: MessageApiResponse;
  success: boolean;
  error?: string;
}

interface GetMessagesResponse {
  messages: Message[];
  success: boolean;
  error?: string;
  nextToken?: string;
}
```

## Error Handling

### Flash Notification Integration

Replace inline error alerts with GlobalUIContext flash notifications:

```typescript
// Instead of inline ErrorAlert components
<ErrorAlert error={error} onRetry={retry} />

// Use flash notifications
const { addFlashItem } = useGlobalUIContext();

addFlashItem({
  type: 'error',
  content: 'Failed to send message',
  dismissible: true,
  action: {
    text: 'Retry',
    onClick: handleRetry
  }
});
```

### Error Categories

1. **Authentication Errors**: Handled by CognitoAuth component
2. **Network Errors**: Flash notifications with retry options
3. **API Errors**: Flash notifications with specific error messages
4. **Validation Errors**: Inline form validation with flash backup

## Testing Strategy

### Manual Testing

- **Authentication Flow**: Manually test login and token usage
- **Messaging Components**: Manual testing of chat interface
- **Error Handling**: Manual testing of flash notifications
- **Configuration**: Manual testing of runtime config loading

### Integration Testing

- **API Integration**: Test messaging API client with new auth
- **Authentication Integration**: Test token usage in API calls
- **UI Integration**: Test flash notifications with messaging errors

### End-to-End Testing

- **Complete User Flow**: Login → Chat → Send Message → Receive Response
- **Error Scenarios**: Network failures, authentication errors
- **Configuration Scenarios**: Runtime config vs environment variables

## Migration Strategy

### Phase 1: Base Setup

1. Update package.json with minimal dependencies
2. Configure authentication for Hotel Assistant
3. Update branding and navigation
4. Remove prescription reader functionality

### Phase 2: Messaging Integration

1. Migrate messaging API client
2. Update authentication token usage
3. Integrate messaging hooks
4. Add chatbot components

### Phase 3: Error Handling

1. Replace error alerts with flash notifications
2. Integrate error handling with GlobalUIContext
3. Test error scenarios

### Phase 4: Testing and Optimization

1. Comprehensive testing
2. Performance optimization
3. Bundle size optimization
4. Documentation updates

## File Structure

```
packages/demo/
├── src/
│   ├── components/
│   │   ├── AppLayout/           # Reused from demo
│   │   ├── CognitoAuth/         # Reused from demo
│   │   ├── RuntimeConfig/       # Reused from demo
│   │   ├── GlobalUIContextProvider.tsx  # Reused from demo
│   │   ├── chatbot/             # Migrated from frontend
│   │   │   ├── Chatbot.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── MessageSkeleton.tsx
│   │   │   └── PollingIndicator.tsx
│   │   └── common/              # Updated for flash notifications
│   ├── lib/                     # Migrated from frontend
│   │   ├── messaging-api-client.ts
│   │   ├── messaging-hooks.ts
│   │   ├── chatbot-config.ts
│   │   └── error-handling.ts
│   ├── types/                   # Migrated from frontend
│   │   └── index.ts
│   ├── pages/
│   │   └── HotelAssistantChat.tsx  # New main page
│   ├── routes/
│   │   ├── __root.tsx           # Updated for Hotel Assistant
│   │   └── index.tsx            # Route to chat page
│   └── main.tsx                 # Updated configuration
├── package.json                 # New minimal dependencies
└── vite.config.ts              # Updated for Hotel Assistant
```

## Dependencies

### Core Dependencies

- `react` & `react-dom`: UI framework
- `react-oidc-context`: Authentication
- `@cloudscape-design/components`: UI components
- `@tanstack/react-query`: State management
- `@tanstack/react-router`: Routing

### Development Dependencies

- `typescript`: Type checking
- `vite`: Build tool
- `@vitejs/plugin-react-swc`: React support

### Removed Dependencies

- All AWS Amplify packages
- Prescription reader specific packages
- Unused UI libraries
- Development tools not needed for messaging

## Configuration Management

### Runtime Configuration (Deployment)

```json
{
  "cognitoProps": {
    "userPoolId": "us-east-1_ZJphzcwtW",
    "userPoolWebClientId": "3t00m6161d4jmf19t92gddf969",
    "region": "us-east-1"
  },
  "messagingApiEndpoint": "https://api.example.com/prod",
  "hotelAssistantClientId": "5chn36kl3hkjesit9cgokb8vc",
  "applicationName": "Hotel Assistant"
}
```

### Environment Variables (Development)

```bash
VITE_COGNITO_USER_POOL_ID=us-east-1_ZJphzcwtW
VITE_COGNITO_USER_POOL_CLIENT_ID=3t00m6161d4jmf19t92gddf969
VITE_AWS_REGION=us-east-1
VITE_MESSAGING_API_ENDPOINT=https://api.example.com/prod
VITE_HOTEL_ASSISTANT_CLIENT_ID=5chn36kl3hkjesit9cgokb8vc
VITE_APP_NAME="Hotel Assistant"
```

## Infrastructure Updates

### CDK Stack Changes

The infrastructure needs to be updated to support the new deployment pattern:

#### S3 Bucket for Configuration Only

- **Purpose**: Store only runtime-config.json (not static files)
- **Security**: Private S3 bucket with no public read access
- **Access**: Developers use AWS credentials with `aws s3 cp` to download
  configuration
- **Generation**: CDK custom resource generates and uploads runtime-config.json
  to private bucket

#### Static File Deployment

- **Method**: Static files deployed through existing CDK/build process (not S3
  hosting)
- **Runtime Config**: Application loads runtime-config.json from local public/
  directory after download

#### Stack Outputs

- **Update**: Ensure correct stack outputs for S3 bucket name and configuration
- **Integration**: Update load:runtime-config nx target to use correct stack and
  outputs

### NX Target Updates

#### load:runtime-config Target

```json
{
  "executor": "nx:run-commands",
  "options": {
    "command": "aws s3 cp s3://`aws cloudformation describe-stacks --query \"Stacks[?StackName=='ChatbotMessagingStack'][].Outputs[?contains(OutputKey, 'ConfigurationBucket')].OutputValue\" --output text`/runtime-config.json ./packages/demo/public/runtime-config.json"
  }
}
```

## Performance Considerations

### Bundle Optimization

- Remove unused Cloudscape components
- Tree-shake unused dependencies
- Optimize React Query cache settings
- Minimize authentication bundle size

### Runtime Performance

- Efficient message polling
- Optimistic UI updates
- Proper React Query caching
- Minimal re-renders

### Memory Management

- Proper cleanup of polling intervals
- React Query garbage collection
- Component unmounting cleanup
- Authentication token management
