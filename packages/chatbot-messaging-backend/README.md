# Chatbot Messaging Backend

A serverless REST API that simulates messaging platform integrations like Twilio
and AWS End User Messaging Social. This backend provides a simple interface for
message handling, status management, and conversation flow simulation, enabling
realistic testing of chatbot integrations.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Authentication](#authentication)
- [API Documentation](#api-documentation)
- [Usage Examples](#usage-examples)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

The Chatbot Messaging Backend is a serverless REST API built with AWS Lambda and
Lambda Powertools that simulates messaging platform integrations. The system
provides a lightweight interface for message handling, status management, and
conversation flow simulation.

**Note**: This package provides simulated messaging for development and testing.
For production WhatsApp integration, the Virtual Assistant includes a separate
WhatsApp integration using AWS End User Messaging Social. See the
[WhatsApp Integration Guide](../../documentation/whatsapp-integration.md) for
real WhatsApp messaging setup.

### Key Components

- **AWS Lambda**: Single function (AWS Lambdalith) with APIGatewayRestResolver
- **Amazon DynamoDB**: Message storage with conversation-based organization
- **Amazon SNS**: Message publishing for downstream processing
- **Amazon Cognito**: User Pool authentication for both users and machine
  clients
- **Amazon API Gateway**: REST API with Amazon Cognito authorization

## Features

- ✅ REST API for message handling with JWT authentication
- ✅ Amazon DynamoDB storage with conversation-based organization
- ✅ SNS integration for message publishing to downstream systems
- ✅ Comprehensive status management (sent, delivered, read, failed, warning,
  deleted)
- ✅ Real-time message polling with timestamp filtering and pagination
- ✅ Dual authentication: User authentication and machine-to-machine (client
  credentials)
- ✅ Conversation management with automatic conversationId generation
- ✅ Comprehensive error handling and logging with AWS Lambda Powertools

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client App    │    │   Hotel Agent   │    │  API Gateway    │
│  (User Auth)    │    │ (Client Creds)  │    │   + Cognito     │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────┐
                    │    Lambda Function     │
                    │  (APIGatewayResolver)  │
                    └─────────────┬───────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
┌─────────▼───────┐    ┌─────────▼───────┐    ┌─────────▼───────┐
│   DynamoDB      │    │   SNS Topic     │    │  CloudWatch     │
│  Messages Table │    │ (Downstream)    │    │     Logs        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Authentication

The system supports two authentication methods:

### 1. User Authentication (JWT Tokens)

For chat users sending messages through client applications.

**Flow:**

1. User authenticates with Cognito User Pool (username/password)
2. Receives JWT access token
3. Includes token in `Authorization: Bearer <token>` header
4. `senderId` is automatically extracted from JWT `sub` claim

**Token Claims:**

```json
{
  "sub": "user-123",
  "email": "user@example.com",
  "cognito:username": "user123",
  "token_use": "access"
}
```

### 2. Machine-to-Machine Authentication (Client Credentials)

For chatbot systems that need to update message statuses and send responses.

**Flow:**

1. Chatbot authenticates with Cognito using client credentials flow
2. Receives JWT access token with custom claims
3. Includes token in `Authorization: Bearer <token>` header
4. System recognizes machine client and allows broader operations

**Client Credentials Setup:**

```bash
# Get client credentials from AWS Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id chatbot-messaging-backend/client-credentials \
  --query SecretString --output text
```

**Token Exchange:**

```bash
curl -X POST https://your-cognito-domain.auth.region.amazoncognito.com/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"
```

## API Documentation

### Base URL

```
https://your-api-gateway-id.execute-api.region.amazonaws.com/prod
```

### Common Headers

```http
Authorization: Bearer <jwt-token>
Content-Type: application/json
```

### Error Response Format

All endpoints return errors in this format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "recipientId is required"
  }
}
```

### HTTP Status Codes

- `200` - Success (GET, PUT operations)
- `201` - Created (POST operations)
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/missing JWT)
- `404` - Not Found (message/conversation not found)
- `500` - Internal Server Error (system errors)

---

### POST /messages

Send a new message from authenticated user to recipient.

**Authentication:** User JWT token required

**Request Body:**

```json
{
  "recipientId": "string",
  "content": "string"
}
```

**Response (201 Created):**

```json
{
  "messageId": "msg-123e4567-e89b-12d3-a456-426614174000",
  "conversationId": "user-123#recipient-456",
  "senderId": "user-123",
  "recipientId": "recipient-456",
  "content": "Hello, I need help with my reservation",
  "status": "sent",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "updatedAt": "2024-01-15T10:30:00.000Z"
}
```

**Example Request:**

```bash
# Replace <YOUR_TOKEN> with a valid Cognito JWT access token
curl -X POST https://api.example.com/messages \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "recipientId": "hotel-assistant",
    "content": "I need help with my reservation for tonight"
  }'
```

---

### PUT /messages/{messageId}/status

Update the status of an existing message.

**Authentication:** User JWT token or Client credentials

**Path Parameters:**

- `messageId` (string, required) - The message ID to update

**Request Body:**

```json
{
  "status": "delivered|read|failed|warning|deleted"
}
```

**Response (200 OK):**

```json
{
  "messageId": "msg-123e4567-e89b-12d3-a456-426614174000",
  "status": "read",
  "updatedAt": "2024-01-15T10:35:00.000Z"
}
```

**Example Request:**

```bash
# Replace <YOUR_TOKEN> with a valid Cognito JWT access token
curl -X PUT https://api.example.com/messages/msg-123e4567-e89b-12d3-a456-426614174000/status \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "read"
  }'
```

---

### GET /conversations/{conversationId}/messages

Retrieve messages from a conversation with optional filtering and pagination.

**Authentication:** User JWT token required

**Path Parameters:**

- `conversationId` (string, required) - The conversation ID (format:
  `senderId#recipientId`)

**Query Parameters:**

- `since` (string, optional) - ISO8601 timestamp to get messages after this time
- `limit` (number, optional) - Maximum number of messages to return (default:
  50, max: 100)

**Response (200 OK):**

```json
{
  "messages": [
    {
      "messageId": "msg-123e4567-e89b-12d3-a456-426614174000",
      "conversationId": "user-123#hotel-assistant",
      "senderId": "user-123",
      "recipientId": "hotel-assistant",
      "content": "I need help with my reservation",
      "status": "read",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "createdAt": "2024-01-15T10:30:00.000Z",
      "updatedAt": "2024-01-15T10:35:00.000Z"
    },
    {
      "messageId": "msg-456e7890-e89b-12d3-a456-426614174001",
      "conversationId": "user-123#hotel-assistant",
      "senderId": "hotel-assistant",
      "recipientId": "user-123",
      "content": "I'd be happy to help! Can you provide your confirmation number?",
      "status": "delivered",
      "timestamp": "2024-01-15T10:32:00.000Z",
      "createdAt": "2024-01-15T10:32:00.000Z",
      "updatedAt": "2024-01-15T10:32:00.000Z"
    }
  ],
  "hasMore": false,
  "nextTimestamp": null
}
```

**Example Request:**

```bash
# Get all messages in conversation
# Replace <YOUR_TOKEN> with a valid Cognito JWT access token
curl -X GET "https://api.example.com/conversations/user-123%23hotel-assistant/messages" \
  -H "Authorization: Bearer <YOUR_TOKEN>"

# Get messages since specific timestamp with limit
curl -X GET "https://api.example.com/conversations/user-123%23hotel-assistant/messages?since=2024-01-15T10:30:00.000Z&limit=10" \
  -H "Authorization: Bearer <YOUR_TOKEN>"
```

## Usage Examples

### Complete Conversation Flow

Here's a complete example showing a conversation between a user and hotel
assistant:

#### 1. User Authentication

```javascript
// Frontend: Authenticate user with Cognito
import {
  CognitoUserPool,
  AuthenticationDetails,
  CognitoUser,
} from 'amazon-cognito-identity-js';

const userPool = new CognitoUserPool({
  UserPoolId: 'us-east-1_xxxxxxxxx',
  ClientId: 'xxxxxxxxxxxxxxxxxxxxxxxxxx',
});

const authenticationDetails = new AuthenticationDetails({
  Username: 'user123',
  Password: 'password123',
});

const cognitoUser = new CognitoUser({
  Username: 'user123',
  Pool: userPool,
});

cognitoUser.authenticateUser(authenticationDetails, {
  onSuccess: result => {
    const accessToken = result.getAccessToken().getJwtToken();
    // Use accessToken for API calls
  },
});
```

#### 2. Send Initial Message

```javascript
// User sends message to virtual assistant
const response = await fetch('https://api.example.com/messages', {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    recipientId: 'hotel-assistant',
    content: 'I need help with my reservation for tonight',
  }),
});

const message = await response.json();
console.log('Message sent:', message);
// Output: { messageId: "msg-123...", conversationId: "user-123#hotel-assistant", ... }
```

#### 3. Virtual Assistant Processes Message (via SNS)

```python
# Virtual Assistant receives SNS notification and processes message
import json
import boto3

def lambda_handler(event, context):
    # Parse SNS message
    for record in event['Records']:
        sns_message = json.loads(record['Sns']['Message'])

        # Process user message
        user_message = sns_message['content']
        conversation_id = sns_message['conversationId']

        # Generate response (simplified)
        response_content = "I'd be happy to help! Can you provide your confirmation number?"

        # Send response message using client credentials
        send_response_message(conversation_id, response_content)

def send_response_message(conversation_id, content):
    # Get client credentials token
    token = get_client_credentials_token()

    # Extract recipient from conversation_id
    sender_id, recipient_id = conversation_id.split('#')

    # Send response message
    response = requests.post('https://api.example.com/messages',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        },
        json={
            'recipientId': sender_id,  # Send back to original sender
            'content': content
        }
    )
```

#### 4. Poll for New Messages

```javascript
// Frontend: Poll for new messages
let lastTimestamp = null;

async function pollMessages(conversationId) {
  const url = new URL(
    `https://api.example.com/conversations/${encodeURIComponent(conversationId)}/messages`
  );
  if (lastTimestamp) {
    url.searchParams.set('since', lastTimestamp);
  }

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  const data = await response.json();

  if (data.messages.length > 0) {
    // Display new messages
    data.messages.forEach(message => {
      displayMessage(message);
    });

    // Update last timestamp
    lastTimestamp = data.messages[data.messages.length - 1].timestamp;
  }

  // Continue polling
  setTimeout(() => pollMessages(conversationId), 2000);
}

// Start polling
pollMessages('user-123#hotel-assistant');
```

#### 5. Mark Messages as Read

```javascript
// Mark message as read when user views it
async function markAsRead(messageId) {
  const response = await fetch(
    `https://api.example.com/messages/${messageId}/status`,
    {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        status: 'read',
      }),
    }
  );

  const result = await response.json();
  console.log('Message marked as read:', result);
}
```

### Python Client Example

```python
import requests
import json
from datetime import datetime, timezone

class ChatbotMessagingClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

    def send_message(self, recipient_id, content):
        """Send a message to recipient"""
        response = requests.post(
            f'{self.base_url}/messages',
            headers=self.headers,
            json={
                'recipientId': recipient_id,
                'content': content
            }
        )
        response.raise_for_status()
        return response.json()

    def update_message_status(self, message_id, status):
        """Update message status"""
        response = requests.put(
            f'{self.base_url}/messages/{message_id}/status',
            headers=self.headers,
            json={'status': status}
        )
        response.raise_for_status()
        return response.json()

    def get_messages(self, conversation_id, since=None, limit=50):
        """Get messages from conversation"""
        params = {'limit': limit}
        if since:
            params['since'] = since.isoformat()

        response = requests.get(
            f'{self.base_url}/conversations/{conversation_id}/messages',
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

# Usage example
client = ChatbotMessagingClient(
    base_url='https://api.example.com',
    access_token='your-jwt-token'
)

# Send message
message = client.send_message('hotel-assistant', 'Hello, I need help')
print(f"Sent message: {message['messageId']}")

# Get conversation messages
messages = client.get_messages('user-123#hotel-assistant')
print(f"Found {len(messages['messages'])} messages")

# Mark as read
client.update_message_status(message['messageId'], 'read')
```

## Development

This package uses `uv` for dependency management and follows the monorepo Python
standards.

### Setup

```bash
# Navigate to package directory
cd packages/chatbot-messaging-backend

# Install dependencies
uv sync

# Activate virtual environment (optional, uv run handles this automatically)
source .venv/bin/activate
```

### Code Quality

```bash
# Format and lint code
uv run ruff check --fix && uv run ruff format

# Type checking (if mypy is configured)
uv run mypy chatbot_messaging_backend/
```

### Project Structure

```
packages/chatbot-messaging-backend/
├── chatbot_messaging_backend/           # Main package
│   ├── __init__.py
│   ├── handlers/                        # Lambda handlers
│   │   ├── __init__.py
│   │   └── lambda_handler.py           # APIGatewayRestResolver handler
│   ├── models/                         # Data models
│   │   ├── __init__.py
│   │   └── message.py                  # Message dataclass
│   ├── services/                       # Business logic
│   │   ├── __init__.py
│   │   └── message_service.py          # Message operations
│   └── utils/                          # Utilities
│       ├── __init__.py
│       ├── repository.py               # DynamoDB operations
│       └── sns_publisher.py            # SNS publishing
├── tests/                              # Test suite
│   ├── __init__.py
│   ├── test_lambda_handler.py          # Handler tests
│   ├── test_message_model.py           # Model tests
│   ├── test_message_service.py         # Service tests
│   ├── test_repository.py              # Repository tests
│   ├── test_sns_publisher.py           # SNS tests
│   └── test_*_integration.py           # Integration tests
├── project.json                        # NX configuration
├── pyproject.toml                      # Python project config
├── README.md                           # This file
└── uv.lock                            # Dependency lock file
```

## Testing

The package includes comprehensive unit and integration tests.

### Running Tests

```bash
# Run all unit tests (default)
uv run pytest

# Run integration tests (requires AWS resources)
uv run pytest -m integration

# Run end-to-end tests (requires deployed ChatbotMessagingStack)
uv run pytest -m e2e

# Run specific test file
uv run pytest tests/test_message_service.py

# Run with coverage
uv run pytest --cov=chatbot_messaging_backend

# Run with verbose output
uv run pytest -v
```

### Test Categories

- **Unit Tests**: Mock external dependencies (DynamoDB, SNS, Cognito)
- **Integration Tests**: Use real AWS services (marked with
  `@pytest.mark.integration`)
- **End-to-End Tests**: Test complete workflows against deployed infrastructure
  (marked with `@pytest.mark.e2e`)
- **Handler Tests**: Test Lambda function entry points
- **Service Tests**: Test business logic
- **Model Tests**: Test data validation and serialization

### End-to-End Testing

End-to-end tests require a deployed ChatbotMessagingStack and test the complete
conversation flow:

**Prerequisites:**

- AWS credentials configured (`aws configure` or environment variables)
- ChatbotMessagingStack deployed in your AWS account
- All dependencies installed (`uv sync`)

**Running E2E Tests:**

```bash
# Run against default stack name (ChatbotMessagingStack)
uv run pytest -m e2e

# Run against custom stack name
CHATBOT_MESSAGING_STACK_NAME=MyCustomStack uv run pytest -m e2e

# Run with verbose output to see detailed test flow
uv run pytest -m e2e -v -s
```

**What E2E Tests Cover:**

- User and machine authentication flows
- Complete message sending and status update workflow
- SNS message publishing and SQS verification
- Message polling with timestamp filtering
- Conversation isolation and management
- Error handling scenarios

### Test Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests",
]
testpaths = ["tests"]
addopts = "-m 'not integration'"  # Skip integration tests by default
```

### Integration Test Setup

Integration tests require AWS resources. Set up test environment:

```bash
# Set AWS credentials
export AWS_PROFILE=your-test-profile

# Set test environment variables
export DYNAMODB_TABLE_NAME=test-chatbot-messages
export SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:test-topic
export COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
```

## Deployment

The messaging backend is deployed as a separate CDK stack that other stacks can
depend on.

### Prerequisites

- AWS CLI configured with appropriate permissions
- CDK bootstrapped in target account/region
- Python 3.12+ and uv installed

### CDK Stack

The messaging backend is defined in `packages/infra/stack/messaging_stack.py`:

```python
from aws_cdk import Stack
from constructs import Construct

class MessagingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Creates:
        # - Cognito User Pool with client credentials support
        # - DynamoDB table with GSI
        # - SNS topic for message publishing
        # - Lambda function with APIGatewayRestResolver
        # - API Gateway with Cognito authorization
        # - IAM roles and policies
```

### Deployment Commands

```bash
# From project root
cd packages/infra

# Install CDK dependencies
uv sync

# Deploy messaging stack
uv run cdk deploy MessagingStack

# Show what will be deployed
uv run cdk diff MessagingStack

# Destroy stack (preserves DynamoDB data by default)
uv run cdk destroy MessagingStack
```

### Stack Outputs

After deployment, the stack provides these outputs:

- `ApiGatewayUrl` - Base URL for API endpoints
- `UserPoolId` - Cognito User Pool ID for authentication
- `UserPoolClientId` - Client ID for user authentication
- `SnsTopicArn` - SNS topic ARN for downstream integration
- `ClientCredentialsSecretArn` - Secret ARN for machine-to-machine auth

### Cross-Stack Integration

Other stacks can reference the messaging backend:

```python
# In hotel-assistant stack
from aws_cdk import Fn

class VirtualAssistantStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Import SNS topic from messaging stack
        messaging_topic_arn = Fn.import_value("MessagingStack-SnsTopicArn")

        # Subscribe virtual assistant to messaging events
        messaging_topic = sns.Topic.from_topic_arn(
            self, "MessagingTopic", messaging_topic_arn
        )

        messaging_topic.add_subscription(
            sns_subscriptions.LambdaSubscription(hotel_assistant_lambda)
        )
```

## Configuration

### Environment Variables

The Lambda function uses these environment variables:

- `DYNAMODB_TABLE_NAME` - DynamoDB table name for message storage
- `SNS_TOPIC_ARN` - SNS topic ARN for message publishing
- `COGNITO_USER_POOL_ID` - Cognito User Pool ID for JWT validation
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `AWS_REGION` - AWS region (automatically set by Lambda)

### DynamoDB Configuration

**Table Schema:**

- **Table Name**: `chatbot-messages`
- **Partition Key**: `conversationId` (String)
- **Sort Key**: `timestamp` (String)
- **GSI**: `MessageIdIndex` with `messageId` as partition key
- **Billing Mode**: On-demand
- **Point-in-time Recovery**: Enabled

### SNS Configuration

**Topic Configuration:**

- **Topic Name**: `chatbot-messaging-events`
- **Message Format**: JSON with message details
- **Delivery Policy**: Standard retry policy
- **Encryption**: Server-side encryption enabled

### Cognito Configuration

**User Pool Settings:**

- **Authentication**: Username/password and client credentials
- **Token Expiration**: Access tokens expire in 1 hour
- **App Clients**:
  - User client (public, no secret)
  - Machine client (confidential, with secret)

## Troubleshooting

### Common Issues

#### 1. Authentication Errors (401 Unauthorized)

**Symptoms:**

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing authorization token"
  }
}
```

**Solutions:**

- Verify JWT token is included in `Authorization: Bearer <token>` header
- Check token expiration (tokens expire after 1 hour)
- Ensure token is from correct Cognito User Pool
- For client credentials, verify client ID and secret are correct

#### 2. Message Not Found (404)

**Symptoms:**

```json
{
  "error": {
    "code": "MESSAGE_NOT_FOUND",
    "message": "Message with ID msg-123 not found"
  }
}
```

**Solutions:**

- Verify messageId is correct and exists
- Check if message belongs to authenticated user's conversations
- Ensure GSI is properly configured for messageId lookups

#### 3. Validation Errors (400)

**Symptoms:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "recipientId is required"
  }
}
```

**Solutions:**

- Check request body format matches API documentation
- Ensure all required fields are provided
- Verify field types (strings, numbers) match expectations
- Check status values are from allowed list

#### 4. SNS Publishing Failures

**Symptoms:**

- Messages stored in DynamoDB but downstream systems not notified
- CloudWatch logs show SNS publish errors

**Solutions:**

- Verify SNS topic ARN is correct in environment variables
- Check IAM permissions for Lambda to publish to SNS
- Ensure SNS topic exists and is in same region
- Check SNS topic subscription configuration

### Debugging

#### Enable Debug Logging

```bash
# Set LOG_LEVEL environment variable
export LOG_LEVEL=DEBUG

# Or update Lambda function configuration
aws lambda update-function-configuration \
  --function-name chatbot-messaging-backend \
  --environment Variables='{LOG_LEVEL=DEBUG}'
```

#### CloudWatch Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/chatbot-messaging-backend --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/chatbot-messaging-backend \
  --filter-pattern "ERROR"

# View specific request
aws logs filter-log-events \
  --log-group-name /aws/lambda/chatbot-messaging-backend \
  --filter-pattern "requestId-123"
```

#### DynamoDB Debugging

```bash
# Check table status
aws dynamodb describe-table --table-name chatbot-messages

# Query messages for conversation
aws dynamodb query \
  --table-name chatbot-messages \
  --key-condition-expression "conversationId = :cid" \
  --expression-attribute-values '{":cid":{"S":"user-123#hotel-assistant"}}'

# Check GSI
aws dynamodb query \
  --table-name chatbot-messages \
  --index-name MessageIdIndex \
  --key-condition-expression "messageId = :mid" \
  --expression-attribute-values '{":mid":{"S":"msg-123"}}'
```

### Performance Monitoring

#### Key Metrics

- **Amazon API Gateway**: Request count, latency, error rate
- **Lambda**: Duration, memory usage, error count
- **DynamoDB**: Read/write capacity, throttling
- **SNS**: Message count, delivery failures

#### CloudWatch Alarms

Set up alarms for:

- Lambda error rate > 1%
- API Gateway 5xx errors > 0.1%
- DynamoDB throttling events
- SNS delivery failures

### Support

For additional support:

1. Check CloudWatch logs for detailed error messages
2. Review AWS service health dashboard
3. Verify IAM permissions and resource configurations
4. Test with minimal examples to isolate issues
5. Check AWS service quotas and limits

---

## License

This project is licensed under the MIT License. See the LICENSE file for
details.
