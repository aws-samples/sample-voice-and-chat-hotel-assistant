# Platform Integration Guide

This document describes the platform abstraction layer for the virtual assistant
messaging system and provides guidance for implementing new messaging platforms.

## Overview

The platform abstraction layer provides a unified interface for handling
messages across different communication channels (web, SMS, WhatsApp, etc.).
Each platform implements the `MessagingPlatform` interface and is managed
through the `PlatformRouter`.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Lambda/Agent  │───▶│  PlatformRouter  │───▶│ Platform Impls  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │  Message Event   │    │ Web │ Twilio │  │
                       │   Routing        │    │ AWS EUM │ ... │  │
                       └──────────────────┘    └─────────────────┘
```

## Platform Interface

All platforms must implement the `MessagingPlatform` abstract base class:

```python
class MessagingPlatform(ABC):
    @abstractmethod
    async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
        """Process incoming message from SNS/SQS"""

    @abstractmethod
    async def update_message_status(self, message_id: str, status: str) -> MessageResponse:
        """Update message status"""

    @abstractmethod
    async def send_response(self, conversation_id: str, content: str, sender_id: str) -> MessageResponse:
        """Send response message using conversation ID"""

    @abstractmethod
    async def send_message(self, recipient_id: str, content: str, sender_id: str, platform_metadata: dict) -> MessageResponse:
        """Send message to specific recipient"""
```

## Current Platform Status

### Web Platform (Implemented)

- **Status**: ✅ Fully implemented
- **Channels**: Web interface
- **Features**: Real-time messaging, status updates
- **Authentication**: Amazon Cognito JWT tokens
- **Integration**: Uses existing chatbot-messaging-backend API

### Twilio Platform (Stub)

- **Status**: 🚧 Stub implementation
- **Channels**: SMS, WhatsApp
- **Features**: Text messages, media messages, delivery receipts
- **Authentication**: Webhook signature validation
- **Integration**: Requires Twilio API credentials and webhook setup

### AWS End User Messaging

- **Status**: ✅ Fully implemented
- **Channels**: WhatsApp, SMS, Facebook Messenger
- **Features**: Rich messages, buttons, media
- **Authentication**: AWS IAM
- **Integration**: Requires AWS EUM service configuration

## Platform Router Usage

The `PlatformRouter` handles message routing based on the platform field:

```python
from hotel_assistant_common.platforms import platform_router

# Process incoming message
response = await platform_router.process_incoming_message(message_event)

# Send response via specific platform
response = await platform_router.send_response(
    conversation_id="user123#hotel-assistant",
    content="Hello! How can I help you?",
    platform="web"
)

# Update message status
response = await platform_router.update_message_status(
    message_id="msg-456",
    status="delivered",
    platform="twilio"
)
```

## Implementing New Platforms

### Step 1: Create Platform Class

Create a new file in the platforms directory:

```python
# platforms/my_platform.py
from .base import MessagingPlatform
from ..models.messaging import MessageEvent, MessageResponse

class MyPlatformMessaging(MessagingPlatform):
    def __init__(self):
        # Initialize platform-specific clients/config
        pass

    async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
        # Implement message processing logic
        pass

    # Implement other required methods...
```

### Step 2: Register with Router

Add your platform to the router in `router.py`:

```python
self._platforms = {
    "web": WebMessaging(),
    "twilio": TwilioMessaging(),
    "aws-eum": AWSEndUserMessaging(),
    "my-platform": MyPlatformMessaging(),  # Add here
}
```

### Step 3: Update Exports

Add your platform to `__init__.py`:

```python
from .my_platform import MyPlatformMessaging

__all__ = [
    # ... existing exports
    "MyPlatformMessaging",
]
```

## Message Flow Integration

### SNS/SQS Integration

Messages flow through the system as follows:

1. **Incoming Message**: Platform receives message (webhook, API, etc.)
2. **SNS Publishing**: Message published to SNS topic with platform metadata
3. **SQS Processing**: AWS Lambda processes message from SQS queue
4. **Platform Routing**: Router determines correct platform handler
5. **Agent Processing**: Amazon Bedrock AgentCore processes message and generates response
6. **Response Delivery**: Platform sends response back to user

### Message Event Structure

```json
{
  "message_id": "msg-123",
  "conversation_id": "user456#hotel-assistant",
  "sender_id": "user456",
  "recipient_id": "hotel-assistant",
  "content": "Hello, I need help with my reservation",
  "timestamp": "2024-01-01T12:00:00Z",
  "platform": "twilio",
  "platform_metadata": {
    "phone_number": "+1234567890",
    "channel": "sms",
    "twilio_message_sid": "SM123..."
  }
}
```

## Platform-Specific Implementation Guides

### Twilio Implementation

When implementing Twilio integration:

1. **Webhook Setup**:

   ```python
   # Validate Twilio webhook signature
   def validate_twilio_signature(request_data, signature, auth_token):
       # Implement Twilio signature validation
       pass
   ```

2. **Message Processing**:

   ```python
   async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
       # Extract Twilio-specific data
       phone_number = message_event.platform_metadata.get("phone_number")
       message_sid = message_event.platform_metadata.get("twilio_message_sid")

       # Process message content
       # Return appropriate response
   ```

3. **Response Sending**:
   ```python
   async def send_response(self, conversation_id: str, content: str, sender_id: str) -> MessageResponse:
       # Extract phone number from conversation_id or metadata
       # Use Twilio API to send SMS/WhatsApp message
       # Handle rate limiting and delivery status
   ```

### AWS End User Messaging Implementation

When implementing AWS EUM integration:

1. **Event Processing**:

   ```python
   async def process_incoming_message(self, message_event: MessageEvent) -> MessageResponse:
       # Parse AWS EUM event structure
       channel = message_event.platform_metadata.get("channel")  # whatsapp, sms, etc.
       sender_info = message_event.platform_metadata.get("sender")

       # Handle different channel types
       # Process rich content if applicable
   ```

2. **Response Formatting**:
   ```python
   async def send_response(self, conversation_id: str, content: str, sender_id: str) -> MessageResponse:
       # Format response for specific channel capabilities
       # Use AWS EUM API for message delivery
       # Handle rich message features (buttons, media, etc.)
   ```

## Error Handling Patterns

### Graceful Degradation

Platforms should handle errors gracefully:

```python
async def send_message(self, recipient_id: str, content: str, **kwargs) -> MessageResponse:
    try:
        # Attempt to send message
        result = await self.platform_api.send_message(recipient_id, content)
        return MessageResponse(success=True, message_id=result.id, data=result.dict())
    except PlatformAPIError as e:
        logger.error(f"Platform API error: {e}")
        return MessageResponse(success=False, error=f"Platform API error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return MessageResponse(success=False, error=f"Unexpected error: {e}")
```

### Retry Logic

Implement appropriate retry logic for transient failures:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def send_with_retry(self, message_data):
    # Implement message sending with automatic retries
    pass
```

## Testing Platforms

### Unit Testing

Test each platform method independently:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_platform_send_message():
    platform = MyPlatformMessaging()

    with patch.object(platform, 'platform_api') as mock_api:
        mock_api.send_message.return_value = {"id": "msg-123"}

        response = await platform.send_message("user123", "Hello")

        assert response.success is True
        assert response.message_id == "msg-123"
```

### Integration Testing

Test platform integration with real APIs (when available):

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_platform_integration():
    # Test with real platform API (requires credentials)
    platform = MyPlatformMessaging()

    response = await platform.send_message("test_recipient", "Test message")

    # Verify response structure and cleanup test data
```

## Configuration Management

### Environment Variables

Each platform should use environment variables for configuration:

```python
import os

class TwilioMessaging(MessagingPlatform):
    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.phone_number = os.environ.get("TWILIO_PHONE_NUMBER")

        if not all([self.account_sid, self.auth_token, self.phone_number]):
            raise ValueError("Missing required Twilio configuration")
```

### AWS Secrets Manager

For production deployments, use AWS Secrets Manager:

```python
import boto3
import json

class PlatformWithSecrets(MessagingPlatform):
    def __init__(self):
        secrets_client = boto3.client('secretsmanager')
        secret_value = secrets_client.get_secret_value(SecretId='platform-credentials')
        credentials = json.loads(secret_value['SecretString'])

        self.api_key = credentials['api_key']
        self.api_secret = credentials['api_secret']
```

## Monitoring and Observability

### Logging

Use structured logging for platform operations:

```python
import logging

logger = logging.getLogger(__name__)

async def send_message(self, recipient_id: str, content: str, **kwargs) -> MessageResponse:
    logger.info(
        "Sending message",
        extra={
            "platform": self.__class__.__name__,
            "recipient_id": recipient_id,
            "content_length": len(content),
            "metadata": kwargs.get("platform_metadata", {})
        }
    )

    # Implementation...

    logger.info(
        "Message sent successfully",
        extra={
            "platform": self.__class__.__name__,
            "message_id": response.message_id,
            "delivery_status": "sent"
        }
    )
```

### Metrics

Track platform-specific metrics:

```python
from aws_lambda_powertools import Metrics
from aws_lambda_powertools.metrics import MetricUnit

metrics = Metrics()

@metrics.log_metrics
async def send_message(self, recipient_id: str, content: str, **kwargs) -> MessageResponse:
    metrics.add_metric(name="MessagesSent", unit=MetricUnit.Count, value=1)
    metrics.add_metadata(key="platform", value=self.__class__.__name__)

    # Implementation...

    if response.success:
        metrics.add_metric(name="MessagesSuccessful", unit=MetricUnit.Count, value=1)
    else:
        metrics.add_metric(name="MessagesFailed", unit=MetricUnit.Count, value=1)
```

## Security Considerations

### Input Validation

Always validate and sanitize inputs:

```python
from pydantic import BaseModel, validator

class MessageInput(BaseModel):
    content: str
    recipient_id: str

    @validator('content')
    def validate_content(cls, v):
        if len(v) > 4000:  # Platform-specific limit
            raise ValueError('Message content too long')
        return v.strip()
```

### Authentication

Implement proper authentication for each platform:

```python
async def authenticate_webhook(self, request_data: dict, signature: str) -> bool:
    """Validate webhook signature for security."""
    expected_signature = self.calculate_signature(request_data)
    return hmac.compare_digest(signature, expected_signature)
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from asyncio import Semaphore

class RateLimitedPlatform(MessagingPlatform):
    def __init__(self):
        self.rate_limiter = Semaphore(10)  # Max 10 concurrent requests

    async def send_message(self, *args, **kwargs):
        async with self.rate_limiter:
            return await super().send_message(*args, **kwargs)
```

## Future Enhancements

### Planned Features

1. **Message Templates**: Support for platform-specific message templates
2. **Rich Media**: Enhanced support for images, videos, and interactive content
3. **Analytics**: Built-in analytics and reporting for message delivery
4. **A/B Testing**: Framework for testing different message formats
5. **Localization**: Multi-language support with platform-specific formatting

### Extension Points

The platform system is designed to be extensible:

- **Custom Middleware**: Add middleware for message processing
- **Plugin System**: Support for third-party platform plugins
- **Event Hooks**: Hooks for custom processing at different stages
- **Custom Routing**: Advanced routing logic based on user preferences

## Support and Troubleshooting

### Common Issues

1. **Platform Not Found**: Ensure platform is registered in router
2. **Authentication Failures**: Check environment variables and credentials
3. **Message Delivery Failures**: Verify platform API status and rate limits
4. **Webhook Validation**: Ensure webhook signatures are properly validated

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging
logging.getLogger('hotel_assistant_common.platforms').setLevel(logging.DEBUG)
```

### Health Checks

Implement health checks for platform availability:

```python
async def health_check(self) -> dict:
    """Check platform health and connectivity."""
    try:
        # Test platform API connectivity
        await self.platform_api.ping()
        return {"status": "healthy", "platform": self.__class__.__name__}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "platform": self.__class__.__name__}
```
