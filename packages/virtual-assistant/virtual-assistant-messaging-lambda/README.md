# Virtual Assistant Messaging AWS Lambda

Lambda function for processing virtual assistant messages from SQS queue and
invoking Amazon Bedrock AgentCore Runtime.

## Overview

This package provides a Lambda function that:

- Consumes messages from an SQS queue
- Parses SNS messages containing chat events
- Invokes the AgentCore Runtime for message processing
- Updates message status through the messaging API

## Architecture

The Lambda function integrates with:

- **SQS Queue**: Receives messages from SNS topic
- **AgentCore Runtime**: Processes messages using Strands agents
- **Messaging API**: Updates message status and sends responses

## Package Structure

```
hotel_assistant_messaging_lambda/
├── handlers/          # Lambda function handlers
├── services/          # Business logic and external service clients
├── models/           # Data models for SQS events and messages
└── tests/            # Unit and integration tests
```

## Development

### Install Dependencies

```bash
cd packages/virtual-assistant/virtual-assistant-messaging-lambda
uv sync
```

### Run Tests

```bash
# Unit tests
pnpm exec nx test virtual-assistant-messaging-lambda

# Integration tests
pnpm exec nx test virtual-assistant-messaging-lambda --configuration=integration

# With coverage
pnpm exec nx test virtual-assistant-messaging-lambda --configuration=coverage
```

### Code Quality

```bash
# Lint code
pnpm exec nx lint virtual-assistant-messaging-lambda

# Format code
pnpm exec nx format virtual-assistant-messaging-lambda

# Fix linting issues
pnpm exec nx lint virtual-assistant-messaging-lambda --configuration=fix
```

### Build and Package

```bash
# Build package
pnpm exec nx build virtual-assistant-messaging-lambda

# Create Lambda deployment package
pnpm exec nx package virtual-assistant-messaging-lambda
```

## Configuration

The Lambda function requires the following environment variables:

- `AGENTCORE_RUNTIME_ARN`: ARN of the AgentCore Runtime to invoke
- `MESSAGING_API_ENDPOINT`: Endpoint for the messaging API
- `LOG_LEVEL`: Logging level (default: INFO)

## Deployment

The Lambda function is deployed as part of the backend infrastructure stack. The
deployment package is created using the `package` target and includes all
dependencies for ARM64 architecture.
