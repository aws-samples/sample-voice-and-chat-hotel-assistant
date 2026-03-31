# Infrastructure (CDK)

This package contains the AWS CDK infrastructure code for the Virtual Assistant,
written in Python using AWS CDK v2.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [CDK Context Variables](#cdk-context-variables)
- [Deployment](#deployment)
- [WhatsApp Integration Setup](#whatsapp-integration-setup)
- [Troubleshooting](#troubleshooting)

## Overview

The infrastructure is defined using AWS CDK (Cloud Development Kit) with Python
and includes:

- **VPC and Networking**: Custom VPC with public/private subnets (when LiveKit
  configured)
- **Authentication**: Amazon Cognito User Pool and Identity Pool
- **Compute**: Amazon ECS with AWS Fargate for LiveKit voice agents (optional)
- **Storage**: Amazon DynamoDB for hotel data + S3 Vectors for knowledge base
- **Messaging**: Optional WhatsApp integration via EUM Social
- **Monitoring**: CloudWatch logs and metrics

## Prerequisites

- Python 3.13+
- uv package manager
- AWS CLI configured with appropriate permissions
- Docker (for container builds)
- CDK bootstrapped in target account/region

## Configuration

### CDK Context Variables

The infrastructure supports various configuration options through CDK context
variables. These can be set in `cdk.context.json` or passed via command line.

#### Core Configuration

```json
{
  "bedrock_xacct_role": "arn:aws:iam::123456789012:role/BedrockCrossAccountRole"
}
```

#### WhatsApp Integration (Optional)

For real WhatsApp messaging through AWS End User Messaging Social:

```json
{
  "eumSocialTopicArn": "arn:aws:sns:us-east-1:123456789012:whatsapp-messages",
  "eumSocialPhoneNumberId": "phone-number-id-01234567890123456789012345678901",
  "eumSocialCrossAccountRole": "arn:aws:iam::123456789012:role/WhatsAppCrossAccountRole",
  "whatsappAllowListParameter": "/virtual-assistant/whatsapp/allow-list"
}
```

### Context Variable Details

#### `bedrock_xacct_role` (Optional)

- **Description**: Cross-account IAM role for Amazon Bedrock access
- **Format**: `arn:aws:iam::account-id:role/role-name`
- **Use Case**: When Bedrock models are in a different AWS account
- **Example**: `arn:aws:iam::123456789012:role/BedrockCrossAccountRole`

#### `eumSocialTopicArn` (Optional)

- **Description**: SNS topic ARN for WhatsApp webhook events from EUM Social
- **Format**: `arn:aws:sns:region:account-id:topic-name`
- **Required For**: WhatsApp integration
- **Example**: `arn:aws:sns:us-east-1:123456789012:whatsapp-messages`
- **Note**: You must create and manage this SNS topic

#### `eumSocialPhoneNumberId` (Optional)

- **Description**: EUM Social phone number ID for sending WhatsApp messages
- **Format**: 36-character alphanumeric string
- **Required For**: WhatsApp integration
- **Example**: `phone-number-id-01234567890123456789012345678901`
- **Location**: Found in EUM Social console

#### `eumSocialCrossAccountRole` (Optional)

- **Description**: Cross-account role for EUM Social API access
- **Format**: `arn:aws:iam::account-id:role/role-name`
- **Use Case**: When EUM Social is in different AWS account
- **Example**: `arn:aws:iam::123456789012:role/WhatsAppCrossAccountRole`

#### `whatsappAllowListParameter` (Optional)

- **Description**: SSM parameter name for phone number allow list
- **Format**: SSM parameter path
- **Default**: `/virtual-assistant/whatsapp/allow-list`
- **Example**: `/virtual-assistant/whatsapp/allow-list`

## Deployment

### Standard Deployment (Simulated Messaging)

```bash
# From project root
pnpm install
pnpm exec nx bootstrap infra  # First time only
pnpm exec nx deploy infra
```

### WhatsApp Integration Deployment

#### Method 1: Using cdk.context.json

1. **Create `cdk.context.json`**:

   ```json
   {
     "eumSocialTopicArn": "arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages",
     "eumSocialPhoneNumberId": "your-phone-number-id",
     "eumSocialCrossAccountRole": "arn:aws:iam::EUM-ACCOUNT:role/WhatsAppRole",
     "whatsappAllowListParameter": "/virtual-assistant/whatsapp/allow-list"
   }
   ```

2. **Deploy**:
   ```bash
   pnpm exec nx deploy infra
   ```

#### Method 2: Command Line Context

```bash
pnpm exec nx deploy infra \
  --context eumSocialTopicArn=arn:aws:sns:us-east-1:123456789012:whatsapp-messages \
  --context eumSocialPhoneNumberId=phone-number-id-01234567890123456789012345678901 \
  --context eumSocialCrossAccountRole=arn:aws:iam::123456789012:role/WhatsAppCrossAccountRole
```

### Deployment Behavior

- **With EUM Social Context**: Deploys WhatsApp integration, skips simulated
  messaging
- **Without EUM Social Context**: Deploys simulated messaging backend (default)
- **Partial EUM Social Context**: Deployment fails with validation error

## WhatsApp Integration Setup

### Prerequisites

1. **AWS End User Messaging Social**: Set up in your AWS account
2. **WhatsApp Business Account**: Connected to EUM Social
3. **SNS Topic**: For receiving webhook events
4. **Phone Number Allow List**: SSM parameter for security

### Step-by-Step Setup

#### 1. Create SNS Topic

```bash
# Create SNS topic
aws sns create-topic --name whatsapp-messages --region us-east-1

# Set topic policy to allow EUM Social service to publish
aws sns set-topic-attributes \
  --topic-arn arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages \
  --attribute-name Policy \
  --attribute-value '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {"Service": "social-messaging.amazonaws.com"},
        "Action": "sns:Publish",
        "Resource": "arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages"
      }
    ]
  }'
```

#### 2. Create Phone Number Allow List

```bash
# Allow specific phone numbers (recommended for production)
aws ssm put-parameter \
  --name "/virtual-assistant/whatsapp/allow-list" \
  --value "+1234567890,+0987654321" \
  --type "String" \
  --description "Comma-separated list of allowed WhatsApp phone numbers"

# Allow all numbers (for development/testing)
aws ssm put-parameter \
  --name "/virtual-assistant/whatsapp/allow-list" \
  --value "*" \
  --type "String" \
  --description "Allow all WhatsApp phone numbers"
```

#### 3. Set Up Cross-Account Role (if needed)

```bash
# In EUM Social account
aws iam create-role \
  --role-name WhatsAppCrossAccountRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {"AWS": "arn:aws:iam::VIRTUAL-ASSISTANT-ACCOUNT:root"},
        "Action": "sts:AssumeRole"
      }
    ]
  }'

# Attach EUM Social permissions
aws iam attach-role-policy \
  --role-name WhatsAppCrossAccountRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSocialMessagingFullAccess
```

#### 4. Configure EUM Social

In the EUM Social console:

1. Configure your WhatsApp integration
2. Set webhook URL to publish to your SNS topic
3. Note the phone number ID for CDK configuration

#### 5. Deploy with WhatsApp Integration

```bash
# Update cdk.context.json with your values
{
  "eumSocialTopicArn": "arn:aws:sns:us-east-1:YOUR-ACCOUNT:whatsapp-messages",
  "eumSocialPhoneNumberId": "your-actual-phone-number-id"
}

# Deploy
pnpm exec nx deploy infra
```

### Phone Number Allow List Formats

#### Specific Phone Numbers

```
1234567890,0987654321,1122334455
```

#### Wildcard (Allow All)

```
*
```

#### Mixed Format

```
1234567890,*,0987654321
```

**Phone Number Format Requirements:**

- Include country code WITH `+` prefix
- Use international format (e.g., `+1234567890`)
- No spaces, dashes, or other formatting

### Updating Allow List

```bash
# Update existing parameter
aws ssm put-parameter \
  --name "/virtual-assistant/whatsapp/allow-list" \
  --value "1234567890,5521987654321" \
  --type "String" \
  --overwrite

# View current allow list
aws ssm get-parameter \
  --name "/virtual-assistant/whatsapp/allow-list" \
  --query "Parameter.Value" \
  --output text
```

## Troubleshooting

### Common Issues

#### 1. CDK Bootstrap Required

**Error**: `Need to perform AWS CDK bootstrap`

**Solution**:

```bash
pnpm exec nx bootstrap infra
```

#### 2. Missing EUM Social Configuration

**Error**: `eumSocialTopicArn provided but eumSocialPhoneNumberId is missing`

**Solution**: Provide both required context variables:

```bash
pnpm exec nx deploy infra \
  --context eumSocialTopicArn=arn:aws:sns:us-east-1:123456789012:whatsapp-messages \
  --context eumSocialPhoneNumberId=phone-number-id-01234567890123456789012345678901
```

#### 3. Cross-Account Role Issues

**Error**: `Unable to assume cross-account role`

**Solutions**:

1. Verify trust relationship in cross-account role
2. Check role permissions
3. Test manual role assumption:
   ```bash
   aws sts assume-role \
     --role-arn arn:aws:iam::EUM-ACCOUNT:role/WhatsAppCrossAccountRole \
     --role-session-name test-session
   ```

#### 4. SNS Topic Access Issues

**Error**: `Access denied to SNS topic`

**Solutions**:

1. Verify topic exists and is in correct region
2. Check topic policy allows subscription
3. Ensure account has SNS permissions

### Debugging Commands

```bash
# Show what will be deployed
pnpm exec nx diff infra

# Deploy with debug output
pnpm exec nx deploy infra --debug

# Check stack status
aws cloudformation describe-stacks \
  --stack-name VirtualAssistantStack \
  --query "Stacks[0].StackStatus"

# View stack outputs
aws cloudformation describe-stacks \
  --stack-name VirtualAssistantStack \
  --query "Stacks[0].Outputs"
```

### Stack Outputs

After successful deployment, key outputs include:

- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Cognito Client ID
- `ConfigBucketName`: S3 bucket for runtime-config.json
- `EUMSocialTopicArn`: SNS topic ARN (if WhatsApp integration enabled)
- `MessageProcessingQueueUrl`: SQS queue URL (if WhatsApp integration enabled)

### Monitoring

Monitor deployment and runtime through:

- **CloudWatch Logs**: AWS Lambda function logs
- **CloudWatch Metrics**: Resource utilization
- **AWS CloudFormation Events**: Deployment progress
- **ECS Console**: Fargate service health

For detailed WhatsApp integration troubleshooting, see the WhatsApp Integration
Guide (`../../documentation/whatsapp-integration.md`).

## Development

### Local Development

```bash
# Install dependencies
cd packages/infra
uv sync

# Synthesize CloudFormation template
uv run cdk synth

# Show differences
uv run cdk diff

# Deploy changes
uv run cdk deploy --no-rollback
```

### Code Quality

```bash
# Format and lint
uv run ruff check --fix && uv run ruff format

# Type checking (if configured)
uv run mypy stack/
```

### Testing

```bash
# Run CDK unit tests (if configured)
uv run pytest

# Validate CloudFormation template
uv run cdk synth > template.yaml
aws cloudformation validate-template --template-body file://template.yaml
```

## Security Considerations

- **Least Privilege**: IAM roles have minimal required permissions
- **Encryption**: All data encrypted at rest and in transit
- **Network Security**: Security groups restrict access to necessary ports
- **Secrets Management**: Sensitive data stored in AWS Secrets Manager
- **Cross-Account Access**: Properly configured trust relationships

## Cost Optimization

- **Auto Scaling**: Amazon ECS with AWS Fargate scales based on demand
- **Serverless**: Aurora Serverless v2 scales with usage
- **Efficient Compute**: ARM64 instances for better price/performance
- **Resource Tagging**: All resources tagged for cost allocation

---

For complete WhatsApp integration setup and troubleshooting, see the WhatsApp
Integration Guide (`../../documentation/whatsapp-integration.md`).
