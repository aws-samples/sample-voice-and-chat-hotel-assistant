# AWS Payload Formats Used in Integration Tests

This document describes the accurate AWS payload formats used in the WhatsApp
integration tests, based on official AWS documentation.

## AWS End User Messaging Social Event Format

Based on:
[AWS End User Messaging Social - Message and event format](https://docs.aws.amazon.com/social-messaging/latest/userguide/managing-event-destination-dlrs.html)

### EUM Social Event Structure

```json
{
  "context": {
    "MetaWabaIds": [
      {
        "wabaId": "1234567890abcde",
        "arn": "arn:aws:social-messaging:us-east-1:123456789012:waba/fb2594b8a7974770b128a409e2example"
      }
    ],
    "MetaPhoneNumberIds": [
      {
        "metaPhoneNumberId": "46271669example",
        "arn": "arn:aws:social-messaging:us-east-1:123456789012:phone-number-id/976c72a700aac43eaf573ae050example"
      }
    ]
  },
  "whatsAppWebhookEntry": "{\"...JSON STRING...}",
  "aws_account_id": "123456789012",
  "message_timestamp": "2025-01-08T23:30:43.271279391Z",
  "messageId": "6d69f07a-c317-4278-9d5c-6a84078419ec"
}
```

### WhatsApp Webhook Entry (JSON String)

The `whatsAppWebhookEntry` contains a JSON string that follows the WhatsApp
Business Platform Cloud API format:

```json
{
  "id": "503131219501234",
  "changes": [
    {
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "+1234567890",
          "phone_number_id": "46271669example"
        },
        "contacts": [
          {
            "profile": {
              "name": "Test User"
            },
            "wa_id": "1987654321"
          }
        ],
        "messages": [
          {
            "id": "wamid.HBgL1987654321123456VAgARGBJExample",
            "from": "+1987654321",
            "timestamp": "1736379042",
            "type": "text",
            "text": {
              "body": "Hello, I need help with my reservation"
            }
          }
        ]
      }
    }
  ]
}
```

## SNS Notification Format

Based on:
[SNS HTTP/HTTPS notification JSON format](https://docs.aws.amazon.com/sns/latest/dg/http-notification-json.html)

```json
{
  "Type": "Notification",
  "MessageId": "22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324",
  "TopicArn": "arn:aws:sns:us-east-1:123456789012:whatsapp-messages",
  "Subject": "WhatsApp Message",
  "Message": "{...EUM Social Event JSON...}",
  "Timestamp": "2025-01-08T23:30:43.271Z",
  "SignatureVersion": "1",
  "Signature": "EXAMPLEw6JRNwXuzaQVSPiUliseQF5clo...",
  "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-f3ecfb7224c7233fe7bb5f59f96de52f.pem",
  "UnsubscribeURL": "https://sns.us-east-1.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=..."
}
```

## SQS Event Record Format

Based on:
[AWS Lambda with Amazon SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)

```json
{
  "messageId": "059f36b4-87a3-44ab-83d2-661975830a7d",
  "receiptHandle": "AQEBwJnKyrHigUMZj6rYigCgxlaS3SLy0a...",
  "body": "{...SNS Notification JSON...}",
  "attributes": {
    "ApproximateReceiveCount": "1",
    "SentTimestamp": "1736379043271",
    "SenderId": "AIDACKCEVSQ6C2EXAMPLE",
    "ApproximateFirstReceiveTimestamp": "1736379043273"
  },
  "messageAttributes": {},
  "md5OfBody": "e4e68fb7bd0e697a0ae8f1bb342846b3",
  "eventSource": "aws:sqs",
  "eventSourceARN": "arn:aws:sqs:us-east-1:123456789012:whatsapp-queue",
  "awsRegion": "us-east-1"
}
```

## EUM Social SendWhatsAppMessage API

Based on:
[SendWhatsAppMessage API](https://docs.aws.amazon.com/social-messaging/latest/APIReference/API_SendWhatsAppMessage.html)

### Request Format

```json
{
  "originationPhoneNumberId": "phone-number-id-976c72a700aac43eaf573ae050example",
  "destinationPhoneNumber": "+1987654321",
  "message": {
    "text": {
      "body": "Thank you for your message! How can I help you with your reservation?"
    }
  }
}
```

### Response Format

```json
{
  "messageId": "eum-msg-456"
}
```

## Key Differences from Previous Format

1. **EUM Social Event Wrapper**: The WhatsApp webhook data is now wrapped in an
   AWS EUM Social event structure with context information.

2. **Phone Number ID Format**: Uses the actual AWS format
   `phone-number-id-{hash}` instead of a simple string.

3. **Message ID Format**: WhatsApp message IDs follow the format
   `wamid.{encoded_data}` as used by Meta.

4. **Timestamp Format**: Uses Unix timestamps for WhatsApp data and ISO 8601 for
   AWS events.

5. **Complete SQS Record**: Includes all standard SQS attributes like
   `ApproximateReceiveCount`, `SentTimestamp`, etc.

6. **Proper SNS Structure**: Follows the exact SNS notification format with
   signature fields.

## Test Coverage

The integration tests verify:

- ✅ Correct parsing of EUM Social event structure
- ✅ Proper extraction of WhatsApp webhook data from JSON string
- ✅ Phone number validation against allow lists
- ✅ Amazon Bedrock AgentCore invocation with correct parameters
- ✅ EUM Social API calls with proper request format
- ✅ Error handling for malformed payloads
- ✅ Cross-account role assumption for EUM Social access
- ✅ SQS batch processing with mixed message types

These formats ensure the tests accurately reflect real AWS service behavior and
payload structures.
