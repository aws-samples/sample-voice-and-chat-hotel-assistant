# WhatsApp Integration with AWS End User Messaging Social

This document provides comprehensive guidance for integrating the Virtual
Assistant with real WhatsApp messaging through AWS End User Messaging Social
(EUM Social).

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [SNS Topic Setup](#sns-topic-setup)
- [Phone Number Allow List](#phone-number-allow-list)
- [Deployment](#deployment)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Overview

The WhatsApp integration extends the existing Virtual Assistant messaging system
to support real WhatsApp conversations through AWS End User Messaging Social.
When configured, the system automatically detects and processes WhatsApp
messages alongside the existing simulated messaging backend.

### Key Features

- **Automatic Message Detection**: Distinguishes between WhatsApp and simulated
  messages based on message structure
- **Phone Number Allow List**: Security through SSM-based phone number
  validation with wildcard support
- **Cross-Account Support**: Supports both same-account and cross-account EUM
  Social deployments
- **Seamless Integration**: Reuses existing Amazon Bedrock AgentCore flow and conversation
  management
- **Fallback Support**: Maintains existing simulation-based messaging when EUM
  Social is not configured

### Architecture

![WhatsApp EUM Social Integration](./diagrams/whatsapp-eum-social.png)

```
WhatsApp User → EUM Social → SNS Topic → SQS Queue → Enhanced Message Processor → AgentCore → EUM Social API → WhatsApp User
```

The integration enhances the existing `virtual-assistant-messaging-lambda` to
automatically detect WhatsApp messages and route them through the appropriate
backend (EUM Social or simulated messaging).

## Prerequisites

### AWS Services

1. **AWS End User Messaging Social**: Set up and configured in your AWS account
2. **WhatsApp Business Account**: Registered with Meta and connected to EUM
   Social
3. **SNS Topic**: For receiving WhatsApp webhook events from EUM Social
4. **Parameter Store**: For managing phone number allow lists

### Permissions

- EUM Social permissions for sending WhatsApp messages
- SNS topic subscription permissions
- SSM parameter read permissions
- Cross-account role assumption (if using cross-account setup)

## Configuration

The WhatsApp integration is configured through CDK context variables. Add these
to your `cdk.context.json` or pass them via command line.

### Required Context Variables

```json
{
  "eumSocialTopicArn": "arn:aws:sns:us-east-1:123456789012:whatsapp-messages",
  "eumSocialPhoneNumberId": "phone-number-id-01234567890123456789012345678901"
}
```

### Optional Context Variables

```json
{
  "eumSocialCrossAccountRole": "arn:aws:iam::123456789012:role/WhatsAppCrossAccountRole",
  "whatsappAllowListParameter": "/virtual-assistant/whatsapp/allow-list"
}
```

### Context Variable Details

#### `eumSocialTopicArn` (Required)

- **Description**: ARN of the SNS topic that receives WhatsApp webhook events
  from EUM Social
- **Format**: `arn:aws:sns:region:account-id:topic-name`
- **Example**: `arn:aws:sns:us-east-1:123456789012:whatsapp-messages`
- **Note**: This topic must be created and managed by you (see
  [SNS Topic Setup](#sns-topic-setup))

#### `eumSocialPhoneNumberId` (Required)

- **Description**: EUM Social phone number ID for sending WhatsApp messages
- **Format**: 36-character alphanumeric string
- **Example**: `phone-number-id-01234567890123456789012345678901`
- **Location**: Found in EUM Social console under your WhatsApp phone number
  configuration

#### `eumSocialCrossAccountRole` (Optional)

- **Description**: IAM role ARN for cross-account EUM Social access
- **Format**: `arn:aws:iam::account-id:role/role-name`
- **Example**: `arn:aws:iam::123456789012:role/WhatsAppCrossAccountRole`
- **Use Case**: When EUM Social is deployed in a different AWS account than the
  Virtual Assistant

#### `whatsappAllowListParameter` (Optional)

- **Description**: SSM parameter name for phone number allow list
- **Default**: `/virtual-assistant/whatsapp/allow-list`
- **Format**: SSM parameter path
- **Example**: `/virtual-assistant/whatsapp/allow-list`

## SNS Topic Setup

The SNS topic is a critical component that receives WhatsApp webhook events from
EUM Social. You are responsible for creating and managing this topic with the
correct permissions.

### Standard Setup

1. **Create SNS Topic**:

   ```bash
   aws sns create-topic --name whatsapp-messages --region us-east-1
   ```

2. **Set Topic Policy for EUM Social Service**:

   ```bash
   # Allow social-messaging.amazonaws.com service to publish to the topic
   aws sns set-topic-attributes \
     --topic-arn arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages \
     --attribute-name Policy \
     --attribute-value '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Principal": {
             "Service": "social-messaging.amazonaws.com"
           },
           "Action": "sns:Publish",
           "Resource": "arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages"
         }
       ]
     }'
   ```

3. **Configure EUM Social**: In the EUM Social console, configure your WhatsApp
   integration to publish events to this SNS topic.

4. **Update CDK Context**:
   ```json
   {
     "eumSocialTopicArn": "arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages"
   }
   ```

### Cross-Account Setup

When EUM Social is in a different AWS account than the Virtual Assistant
deployment:

1. **Create SNS Topic for WhatsApp in EUM Social Account**:

   ```bash
   # In EUM Social account - use phone number in topic name for multiple numbers
   aws sns create-topic --name whatsapp-messages-PHONE_NUMBER --region us-east-1
   # Example: whatsapp-messages-18555729598
   ```

2. **Configure WhatsApp Business Account Event Destination**:

   ```bash
   # In EUM Social account - configure WABA to send events to SNS topic
   aws socialmessaging put-whatsapp-business-account-event-destinations \
     --id "waba-YOUR-WABA-ID" \
     --event-destinations eventDestinationArn=arn:aws:sns:us-east-1:EUM-SOCIAL-ACCOUNT:whatsapp-messages-PHONE_NUMBER
   ```

3. **Set SNS Topic Policy for EUM Social Service and Cross-Account Access**:

   ```bash
   # In EUM Social account - allow social-messaging service to publish and deployment account to subscribe
   aws sns set-topic-attributes \
     --topic-arn arn:aws:sns:us-east-1:EUM-SOCIAL-ACCOUNT:whatsapp-messages-PHONE_NUMBER \
     --attribute-name Policy \
     --attribute-value '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Principal": {
             "Service": "social-messaging.amazonaws.com"
           },
           "Action": "sns:Publish",
           "Resource": "arn:aws:sns:us-east-1:EUM-SOCIAL-ACCOUNT:whatsapp-messages-PHONE_NUMBER"
         },
         {
           "Effect": "Allow",
           "Principal": {
             "AWS": "arn:aws:iam::DEPLOYMENT-ACCOUNT:root"
           },
           "Action": "sns:Subscribe",
           "Resource": "arn:aws:sns:us-east-1:EUM-SOCIAL-ACCOUNT:whatsapp-messages-PHONE_NUMBER"
         }
       ]
     }'
   ```

4. **Create Cross-Account Role in EUM Social Account**:

   ```bash
   # In EUM Social account - create role for deployment account to assume
   aws iam create-role \
     --role-name VirtualAssistantEUMSocialRole \
     --assume-role-policy-document '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Principal": {
             "AWS": "arn:aws:iam::DEPLOYMENT-ACCOUNT:root"
           },
           "Action": "sts:AssumeRole"
         }
       ]
     }'

   # Attach EUM Social permissions
   aws iam put-role-policy \
     --role-name VirtualAssistantEUMSocialRole \
     --policy-name EUMSocialOperations \
     --policy-document '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "social-messaging:SendWhatsAppMessage",
             "social-messaging:UpdateWhatsAppMessageStatus"
           ],
           "Resource": "*"
         }
       ]
     }'
   ```

5. **Update CDK Context in Deployment Account**:

   ```json
   {
     "eumSocialTopicArn": "arn:aws:sns:us-east-1:EUM-SOCIAL-ACCOUNT:whatsapp-messages-PHONE_NUMBER",
     "eumSocialPhoneNumberId": "phone-number-id-YOUR-PHONE-NUMBER-ID",
     "eumSocialCrossAccountRole": "arn:aws:iam::EUM-SOCIAL-ACCOUNT:role/VirtualAssistantEUMSocialRole"
   }
   ```

6. **Create Phone Number Allow List in Deployment Account**:
   ```bash
   # In deployment account - create SSM parameter for allowed phone numbers
   aws ssm put-parameter \
     --name "/virtual-assistant/whatsapp/allow-list" \
     --value "+1234567890,+0987654321" \
     --type "String"
   ```

### Important Notes for Cross-Account Setup

- **SNS Topic Location**: The SNS topic must be in the EUM Social account where
  WhatsApp events are generated
- **SQS Queue Location**: The SQS queue will be created in the deployment
  account by CDK
- **Cross-Account Subscription**: CDK automatically subscribes the deployment
  account's SQS queue to the EUM Social account's SNS topic
- **Phone Number Naming**: Use phone number in topic name (without + or spaces)
  to support multiple WhatsApp numbers
- **Permissions**: The deployment account needs `sns:Subscribe` permission on
  the EUM Social topic, and `sts:AssumeRole` permission for the cross-account
  role

### Topic Subscription

The Virtual Assistant automatically subscribes its SQS queue to your SNS topic
during deployment. No manual subscription is required.

## Phone Number Allow List

The phone number allow list provides security by restricting which WhatsApp
numbers can interact with the Virtual Assistant.

### Creating the Allow List

1. **Create SSM Parameter**:
   ```bash
   aws ssm put-parameter \
     --name "/virtual-assistant/whatsapp/allow-list" \
     --value "+1234567890,+0987654321" \
     --type "String" \
     --description "Comma-separated list of allowed WhatsApp phone numbers"
   ```

### Allow List Formats

#### Specific Phone Numbers

```
+1234567890,+0987654321,+1122334455
```

#### Wildcard (Allow All)

```
*
```

#### Mixed Format

```
+1234567890,*,+0987654321
```

### Phone Number Format

- **Include country code**: Always use international format with `+` and country code
- **Include + prefix**: Phone numbers in allow list MUST include `+` prefix
- **No spaces or dashes**: Use only `+` and digits
- **Examples**:
  - ✅ `+1234567890` (correct format)
  - ✅ `+521234567890` (correct format with country code)
  - ❌ `1234567890` (missing + prefix)
  - ❌ `+1-234-567-890` (contains dashes)
  - ❌ `+1 234 567 890` (contains spaces)

### Updating the Allow List

```bash
# Update existing parameter
aws ssm put-parameter \
  --name "/virtual-assistant/whatsapp/allow-list" \
  --value "+1234567890,+5521987654321" \
  --type "String" \
  --overwrite

# View current allow list
aws ssm get-parameter \
  --name "/virtual-assistant/whatsapp/allow-list" \
  --query "Parameter.Value" \
  --output text
```

### Allow List Behavior

- **Allowed Numbers**: Messages are processed normally and forwarded to
  AgentCore
- **Blocked Numbers**: Messages are logged at DEBUG level and discarded
- **Missing Parameter**: All messages are blocked for security (fail-safe)
- **Wildcard (`*`)**: All phone numbers are allowed (useful for
  development/testing)
- **Cache**: Allow list is cached for 5 minutes to reduce SSM API calls

## Deployment

### Standard Deployment

When EUM Social context variables are provided, the system automatically
configures WhatsApp integration:

```bash
# Set context variables in cdk.context.json or via command line
pnpm exec nx deploy infra --context eumSocialTopicArn=arn:aws:sns:us-east-1:123456789012:whatsapp-messages --context eumSocialPhoneNumberId=phone-number-id-01234567890123456789012345678901
```

### Deployment Behavior

- **With EUM Social Config**: Deploys WhatsApp integration, skips simulated
  messaging stack
- **Without EUM Social Config**: Deploys simulated messaging backend (existing
  behavior)
- **Partial Config**: Deployment fails with clear error message if required
  variables are missing

### Environment Variables Set

The deployment automatically configures these environment variables for the
message processor AWS Lambda:

- `EUM_SOCIAL_PHONE_NUMBER_ID`: Phone number ID for sending messages
- `WHATSAPP_ALLOW_LIST_PARAMETER`: SSM parameter path for allow list
- `EUM_SOCIAL_CROSS_ACCOUNT_ROLE`: Cross-account role ARN (if provided)

### IAM Permissions Granted

- **SSM Parameter Access**: Read access to `/virtual-assistant/whatsapp/*`
  parameters
- **EUM Social API**: `socialmessaging:SendWhatsAppMessage` permission
- **Cross-Account Role**: `sts:AssumeRole` permission (if cross-account role
  provided)

## Simulated Messaging Backend

![Simulated Messaging Backend](./diagrams/simulated-messaging-backend.png)

The simulated messaging backend is deployed by default when EUM Social configuration is not provided. It replicates WhatsApp's webhook-driven architecture without requiring a WhatsApp Business account.

### Architecture

The simulated backend provides:

- **Amazon API Gateway**: Webhook-compatible REST API that simulates WhatsApp's message delivery model
- **Amazon Cognito**: User authentication for demo users
- **Amazon DynamoDB**: Message history storage for demo conversations
- **SNS/SQS Integration**: Same message processing flow as WhatsApp integration

### Use Cases

- Test and validate your virtual assistant before connecting to WhatsApp
- Demonstrate the platform to stakeholders
- Iterate on conversation flows
- Validate industry-specific customizations

The simulated backend is automatically deployed when `eumSocialTopicArn` and `eumSocialPhoneNumberId` context variables are not provided, and is used by the demo frontend.

## Testing

### Unit Testing

The integration includes comprehensive unit tests:

```bash
cd packages/virtual-assistant/virtual-assistant-messaging-lambda
uv run pytest tests/test_whatsapp_*.py -v
```

### Integration Testing

Test with real AWS resources:

```bash
# Requires deployed infrastructure and valid AWS credentials
uv run pytest tests/test_whatsapp_integration.py -m integration -v
```

### Manual Testing

1. **Send Test Message**: Send a WhatsApp message from an allowed phone number
2. **Check Logs**: Monitor CloudWatch logs for message processing
3. **Verify Response**: Confirm the assistant responds via WhatsApp

### Test Message Flow

```bash
# Monitor Lambda logs
aws logs tail /aws/lambda/YOUR-STACK-message-processor --follow

# Check SQS queue for messages
aws sqs get-queue-attributes \
  --queue-url YOUR-QUEUE-URL \
  --attribute-names ApproximateNumberOfMessages

# View SSM parameter
aws ssm get-parameter \
  --name "/virtual-assistant/whatsapp/allow-list"
```

## Troubleshooting

### Common Issues

#### 1. Messages Not Being Received

**Symptoms:**

- WhatsApp messages sent but no processing in CloudWatch logs
- SQS queue remains empty

**Troubleshooting Steps:**

1. **Verify SNS Topic Configuration**:

   ```bash
   # Check if topic exists
   aws sns get-topic-attributes --topic-arn YOUR-TOPIC-ARN

   # List topic subscriptions
   aws sns list-subscriptions-by-topic --topic-arn YOUR-TOPIC-ARN
   ```

2. **Check EUM Social Configuration**:
   - Verify EUM Social is publishing to the correct SNS topic
   - Check EUM Social webhook configuration
   - Confirm WhatsApp Business Account is properly connected

3. **Verify SQS Subscription**:
   ```bash
   # Check if SQS queue is subscribed to SNS topic
   aws sqs get-queue-attributes \
     --queue-url YOUR-QUEUE-URL \
     --attribute-names Policy
   ```

#### 2. Messages Blocked by Allow List

**Symptoms:**

- Messages appear in logs but are not processed
- DEBUG log entries showing blocked phone numbers

**Troubleshooting Steps:**

1. **Check Allow List Configuration**:

   ```bash
   aws ssm get-parameter \
     --name "/virtual-assistant/whatsapp/allow-list" \
     --query "Parameter.Value" \
     --output text
   ```

2. **Verify Phone Number Format**:
   - Ensure phone numbers include country code but NO `+` prefix in allow list
   - Check for spaces, dashes, or other formatting issues
   - Compare logged phone number with allow list entries (both are sanitized without `+`)

3. **Test with Wildcard**:
   ```bash
   # Temporarily allow all numbers for testing
   aws ssm put-parameter \
     --name "/virtual-assistant/whatsapp/allow-list" \
     --value "*" \
     --overwrite
   ```

#### 3. EUM Social API Failures

**Symptoms:**

- Messages processed but responses not sent
- ERROR logs showing EUM Social API failures

**Troubleshooting Steps:**

1. **Check IAM Permissions**:

   ```bash
   # Verify Lambda role has EUM Social permissions
   aws iam get-role-policy \
     --role-name YOUR-LAMBDA-ROLE \
     --policy-name EUMSocialAPIAccess
   ```

2. **Test Cross-Account Role** (if applicable):

   ```bash
   # Test role assumption
   aws sts assume-role \
     --role-arn YOUR-CROSS-ACCOUNT-ROLE \
     --role-session-name test-session
   ```

3. **Verify Phone Number ID**:
   - Check that `eumSocialPhoneNumberId` is correct
   - Verify phone number is active in EUM Social console

#### 4. Cross-Account Authentication Issues

**Symptoms:**

- Authentication errors in CloudWatch logs
- `sts:AssumeRole` failures

**Troubleshooting Steps:**

1. **Verify Trust Relationship**:

   ```bash
   # Check cross-account role trust policy
   aws iam get-role \
     --role-name WhatsAppCrossAccountRole \
     --query "Role.AssumeRolePolicyDocument"
   ```

2. **Check Role Permissions**:

   ```bash
   # Verify role has EUM Social permissions
   aws iam list-attached-role-policies \
     --role-name WhatsAppCrossAccountRole
   ```

3. **Test Manual Role Assumption**:
   ```bash
   aws sts assume-role \
     --role-arn arn:aws:iam::EUM-SOCIAL-ACCOUNT:role/WhatsAppCrossAccountRole \
     --role-session-name manual-test
   ```

### Debugging Commands

#### CloudWatch Logs

```bash
# View recent Lambda logs
aws logs tail /aws/lambda/YOUR-STACK-message-processor --since 1h

# Filter for WhatsApp-specific logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/YOUR-STACK-message-processor \
  --filter-pattern "WhatsApp"

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/YOUR-STACK-message-processor \
  --filter-pattern "ERROR"
```

#### SQS Queue Monitoring

```bash
# Check queue depth
aws sqs get-queue-attributes \
  --queue-url YOUR-QUEUE-URL \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible

# Receive messages manually (for debugging)
aws sqs receive-message \
  --queue-url YOUR-QUEUE-URL \
  --max-number-of-messages 1
```

#### SSM Parameter Debugging

```bash
# List all WhatsApp parameters
aws ssm get-parameters-by-path \
  --path "/virtual-assistant/whatsapp" \
  --recursive

# Check parameter history
aws ssm get-parameter-history \
  --name "/virtual-assistant/whatsapp/allow-list"
```

### Performance Monitoring

#### Key Metrics to Monitor

- **Lambda Duration**: Message processing time
- **Lambda Errors**: Error rate and types
- **SQS Queue Depth**: Backlog of unprocessed messages
- **EUM Social API Latency**: Response time for sending messages

#### CloudWatch Alarms

Set up alarms for:

```bash
# Lambda error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "WhatsApp-Lambda-Errors" \
  --alarm-description "WhatsApp message processor errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold

# SQS queue depth
aws cloudwatch put-metric-alarm \
  --alarm-name "WhatsApp-Queue-Depth" \
  --alarm-description "WhatsApp SQS queue backlog" \
  --metric-name ApproximateNumberOfVisibleMessages \
  --namespace AWS/SQS \
  --statistic Average \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

## Security Considerations

### Phone Number Allow List Security

- **Default Deny**: System blocks all messages when allow list parameter is
  missing
- **Audit Logging**: All blocked attempts are logged at DEBUG level
- **Parameter Encryption**: Consider using SecureString type for sensitive allow
  lists
- **Regular Review**: Periodically review and update allowed phone numbers

### Cross-Account Security

- **Least Privilege**: Cross-account roles should have minimal required
  permissions
- **Trust Boundaries**: Clearly define which accounts can assume cross-account
  roles
- **Session Names**: Use descriptive session names for audit trails
- **Temporary Credentials**: All cross-account access uses temporary credentials

### Message Content Security

- **Debug Logging Only**: Phone numbers and message content logged only at DEBUG
  level
- **No Persistent Storage**: WhatsApp messages not stored beyond AgentCore
  memory retention
- **Encryption in Transit**: All API calls use HTTPS/TLS encryption
- **Data Residency**: Consider data residency requirements for WhatsApp messages

### API Security

- **Authentication**: All EUM Social API calls use AWS IAM authentication
- **Rate Limiting**: Implement appropriate rate limiting for WhatsApp API calls
- **Error Handling**: Avoid exposing sensitive information in error messages
- **Monitoring**: Monitor for unusual API usage patterns

### Best Practices

1. **Use Specific Phone Numbers**: Avoid wildcard (`*`) in production
   environments
2. **Regular Rotation**: Rotate cross-account role credentials regularly
3. **Monitor Access**: Set up CloudTrail logging for all WhatsApp-related API
   calls
4. **Test Security**: Regularly test with blocked phone numbers to verify
   security
5. **Document Access**: Maintain documentation of who has access to WhatsApp
   integration

### Compliance Considerations

- **Data Protection**: Ensure compliance with local data protection regulations
- **Message Retention**: Understand WhatsApp message retention policies
- **Audit Requirements**: Maintain audit logs for compliance purposes
- **Privacy Policies**: Update privacy policies to reflect WhatsApp integration

---

## Support and Resources

### AWS Documentation

- [AWS End User Messaging Social](https://docs.aws.amazon.com/social-messaging/)
- [Amazon SNS](https://docs.aws.amazon.com/sns/)
- [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [AWS STS AssumeRole](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html)

### WhatsApp Business

- [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp)
- [WhatsApp Business Platform](https://business.whatsapp.com/)

### Troubleshooting Resources

- [AWS CloudWatch Logs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
- [Amazon SQS Troubleshooting](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-troubleshooting.html)
- [AWS IAM Troubleshooting](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot.html)
