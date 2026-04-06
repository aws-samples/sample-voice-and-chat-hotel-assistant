---
inclusion: always
---

# Virtual Assistant Platform Overview

## Architecture

Industry-agnostic real-time conversational AI platform using Amazon Bedrock Nova
Sonic. Supports voice, chat, and messaging interfaces with MCP-based tool
integration. Hotel implementation serves as reference for any industry
adaptation.

### Package Structure

- **`packages/demo/`**: React + TypeScript web app with Cloudscape Design System
- **`packages/virtual-assistant/`**: Python workspace with four sub-packages:
  - `virtual-assistant-common/`: Shared utilities, MCP clients, exceptions
  - `virtual-assistant-chat/`: AgentCore chat interface with memory
  - `virtual-assistant-livekit/`: LiveKit voice agent with Nova Sonic
  - `virtual-assistant-messaging-lambda/`: Message processing for WhatsApp/SMS
- **`packages/chatbot-messaging-backend/`**: Simulated messaging backend
  (fallback)
- **`packages/hotel-pms-simulation/`**: Hotel PMS API + MCP server (reference
  implementation)
- **`packages/infra/`**: AWS CDK infrastructure (Python)

## Code Standards

### Python (3.13)

- **Package Manager**: Always use `uv` for dependency management
- **Code Quality**: Run `ruff check --fix && ruff format` after every change
- **Line Length**: 120 characters maximum
- **Async Usage**: Only when required by framework (FastAPI, LiveKit, AgentCore)
- **Error Handling**: Use structured exceptions from
  `virtual_assistant_common.exceptions`
- **Logging**: AWS Lambda Powertools with structured logging and context
- **Testing**: pytest with `@pytest.mark.integration` for AWS services
- **Imports**: Use absolute imports within packages, relative for local modules

### TypeScript/React

- **Type Safety**: Strict mode enabled, no `any` types allowed
- **Component Pattern**: Functional components with hooks only
- **UI Components**: Cloudscape Design System for all UI elements
- **Styling**: Tailwind utilities only, no custom CSS classes
- **State Management**: React hooks (useState, useEffect), no external state
  libraries
- **Testing**: Vitest + React Testing Library focusing on user behavior
- **File Naming**: PascalCase for components, camelCase for utilities

### AWS CDK Infrastructure

- **Language**: Python 3.13 with uv package management
- **Construct Organization**: Separate constructs by AWS service or logical
  grouping
- **Resource Naming**: Consistent patterns:
  `{StackName}-{Component}-{ResourceType}`
- **Security**: Least-privilege IAM, security groups, encryption at rest/transit
- **Configuration**: Environment variables and CDK context for customization
- **Reusability**: Create shared constructs in
  `packages/infra/stack/stack_constructs/`

### MCP Integration

- **Client Usage**: Use `MultiMCPClientManager` from
  `virtual_assistant_common.mcp.multi_client_manager`
- **Authentication**: Cognito tokens required for all MCP tool access
- **Error Handling**: Graceful fallbacks when MCP servers unavailable
- **Configuration**: Environment variables with `.env.example` templates
- **Tool Discovery**: Dynamic capability detection via MCP protocol

## Development Commands

### NX Monorepo

```bash
# Development servers
pnpm exec nx serve demo                    # React web app
pnpm exec nx serve hotel-pms-simulation        # Hotel PMS API

# Testing
pnpm exec nx test <package-name>           # Run tests for specific package
pnpm exec nx test demo                     # Frontend tests
pnpm exec nx run-many -t test              # All tests

# Infrastructure
pnpm exec nx deploy infra                  # Deploy to AWS
pnpm exec nx diff infra                    # Show infrastructure changes
pnpm exec nx destroy infra                 # Destroy AWS resources
pnpm exec nx bootstrap infra               # Bootstrap CDK (first time)

# Build and format
pnpm exec nx run-many -t build             # Build all packages
pnpm exec nx run-many -t lint              # Lint all packages
pnpm exec nx run-many -t format            # Format all packages
```

### Python Workspaces (uv)

```bash
# Install dependencies
cd packages/virtual-assistant && uv sync

# Run specific packages
uv run --package virtual-assistant-chat python -m virtual_assistant_chat
uv run --package virtual-assistant-livekit python -m virtual_assistant_livekit

# Add dependencies
uv add --package virtual-assistant-common boto3
uv add --package virtual-assistant-chat --group dev pytest

# Development tools
uv run ruff check --fix && uv run ruff format    # Code quality
uv run pytest                                    # Run tests
uv run pytest -m integration                     # Integration tests only
```

## Architecture Patterns

### Messaging & Communication

- **API Structure**: RESTful endpoints with structured JSON responses
- **WebSocket Events**: Use `{type, payload}` pattern for all messages
- **Nova Sonic Streaming**: Follow strict event sequence: sessionStart →
  promptStart → content → sessionEnd
- **Error Responses**: Always include error codes and user-friendly messages
- **Message Processing**: SNS/SQS for async message handling (WhatsApp, SMS)
- **Cross-Service Communication**: Use AWS EventBridge for service decoupling

### Database & State

- **Transactions**: Always use database transactions with rollback support
- **Seed Data**: CSV-based with UPSERT operations for idempotency
- **Custom Resources**: CloudFormation custom resources for database lifecycle
- **State Management**: Keep client state minimal, server as source of truth
- **Vector Storage**: Aurora PostgreSQL with pgvector for knowledge base
- **Memory**: AgentCore Memory for conversation persistence

### AWS CDK Infrastructure

- **Stack Organization**: Separate stacks for different concerns (backend,
  hotel-pms)
- **Construct Reuse**: Shared constructs in
  `packages/infra/stack/stack_constructs/`
- **IAM Principle**: Least-privilege with specific resource ARNs
- **Configuration**: CDK context variables and environment variables
- **Resource Naming**: Consistent patterns:
  `{StackName}-{Component}-{ResourceType}`
- **Conditional Deployment**: EUM Social integration vs simulated messaging
  backend

## Implementation Requirements

### Security & Authentication

- **Authentication**: All API calls require valid Cognito JWT tokens
- **Authorization**: Role-based access through Cognito user groups
- **Input Validation**: Validate and sanitize all user inputs
- **Secrets Management**: AWS Secrets Manager for API keys, never hardcode
  credentials
- **CORS**: Proper CORS policies for frontend-backend communication
- **Network Security**: VPC, security groups, NACLs for infrastructure isolation
- **Encryption**: At rest (S3, Aurora) and in transit (TLS/SSL) encryption

### Audio Processing (Nova Sonic)

- **Input Format**: Nova Sonic supports 8kHz, 16kHz, or 24kHz, base64-encoded LPCM
- **Output Format**: Nova Sonic native output, LiveKit handles sample rate conversion
- **Asset Format**: 44.1kHz for pre-recorded audio assets (greeting.raw, un_momento.raw)
- **Streaming**: Real-time ~32ms chunks, minimize buffering
- **Browser Support**: Handle WebRTC permissions and compatibility gracefully
- **Barge-in**: Clear audio queues immediately on user interruption
- **Event Sequencing**: Strict Nova Sonic event flow for proper conversation
  handling

### Error Handling & Resilience

- **MCP Failures**: Never let MCP server failures crash the application
- **Circuit Breaker**: Implement circuit breaker pattern for external services
- **Graceful Degradation**: Provide fallbacks when services unavailable
- **User Feedback**: Always provide clear error messages to users
- **Structured Logging**: AWS Lambda Powertools with correlation IDs
- **Retry Logic**: Exponential backoff for transient failures
- **Health Checks**: ECS health checks and CloudWatch alarms

## Testing Strategy

### Test Organization

- **Unit Tests**: Mock all external dependencies (AWS, MCP servers, databases)
- **Integration Tests**: Mark with `@pytest.mark.integration` for real AWS
  resources
- **Component Tests**: React components with user interaction focus
- **End-to-End**: Complete user workflows across services
- **CDK Tests**: Infrastructure unit tests with CDK assertions

### Test Implementation

- **Python**: pytest with fixtures, async support for AgentCore/LiveKit
- **React**: Vitest + React Testing Library, test behavior not implementation
- **CDK**: aws-cdk.assertions for infrastructure testing
- **Mocking**: `moto` for AWS services, `unittest.mock` for other dependencies
- **Coverage**: High coverage for critical paths, especially conversation flows
- **Environment**: `.env.test` files for test-specific configuration

### Test Data & Fixtures

- **Pytest Fixtures**: Reusable test data and mock objects
- **Factory Patterns**: Generate test objects with realistic data
- **Database Fixtures**: Isolated test databases with seed data
- **Cleanup**: Always clean up test resources after execution
- **Test Isolation**: No dependencies between tests or external state
- **Mock Conversations**: Realistic conversation flows for voice/chat testing
