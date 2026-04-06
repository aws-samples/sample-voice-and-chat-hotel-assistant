# Troubleshooting Guide

This document provides troubleshooting guidance for common issues with the
Virtual Assistant, including WhatsApp integration, voice processing, and general
deployment problems.

## Table of Contents

- [WhatsApp Integration Issues](#whatsapp-integration-issues)
- [Voice Assistant Issues](#voice-assistant-issues)
- [Chat Assistant Issues](#chat-assistant-issues)
- [Deployment Issues](#deployment-issues)
- [Performance Issues](#performance-issues)
- [Authentication Issues](#authentication-issues)

## WhatsApp Integration Issues

### Messages Not Being Received

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
   - Check EUM Social webhook configuration in AWS console
   - Confirm WhatsApp Business Account is properly connected

3. **Verify SNS Topic Policy**:

   ```bash
   # Check if topic policy allows social-messaging service to publish
   aws sns get-topic-attributes --topic-arn YOUR-TOPIC-ARN --query "Attributes.Policy"

   # Update topic policy if needed
   aws sns set-topic-attributes \
     --topic-arn YOUR-TOPIC-ARN \
     --attribute-name Policy \
     --attribute-value '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Principal": {"Service": "social-messaging.amazonaws.com"},
           "Action": "sns:Publish",
           "Resource": "YOUR-TOPIC-ARN"
         }
       ]
     }'
   ```

4. **Monitor SQS Queue**:
   ```bash
   aws sqs get-queue-attributes \
     --queue-url YOUR-QUEUE-URL \
     --attribute-names ApproximateNumberOfMessages
   ```

### Messages Blocked by Allow List

**Symptoms:**

- Messages appear in logs but are not processed
- DEBUG log entries showing blocked phone numbers

**Solutions:**

1. **Check Allow List Configuration**:

   ```bash
   aws ssm get-parameter \
     --name "/virtual-assistant/whatsapp/allow-list" \
     --query "Parameter.Value" \
     --output text
   ```

2. **Verify Phone Number Format**:
   - Ensure phone numbers include country code and `+` prefix
   - Example: `+1234567890` (correct) vs `1234567890` (incorrect)

3. **Test with Wildcard** (for debugging):
   ```bash
   aws ssm put-parameter \
     --name "/virtual-assistant/whatsapp/allow-list" \
     --value "*" \
     --overwrite
   ```

### EUM Social API Failures

**Symptoms:**

- Messages processed but responses not sent
- ERROR logs showing EUM Social API failures

**Solutions:**

1. **Check IAM Permissions**:

   ```bash
   # Verify Lambda role has EUM Social permissions
   aws iam simulate-principal-policy \
     --policy-source-arn YOUR-LAMBDA-ROLE-ARN \
     --action-names socialmessaging:SendWhatsAppMessage \
     --resource-arns "*"
   ```

2. **Verify Phone Number ID**:
   - Check that `eumSocialPhoneNumberId` context variable is correct
   - Verify phone number is active in EUM Social console

### Cross-Account Authentication Issues

**Symptoms:**

- Authentication errors in CloudWatch logs
- `sts:AssumeRole` failures

**Solutions:**

1. **Test Role Assumption**:

   ```bash
   aws sts assume-role \
     --role-arn YOUR-CROSS-ACCOUNT-ROLE \
     --role-session-name test-session
   ```

2. **Check Trust Relationship**:
   ```bash
   aws iam get-role \
     --role-name WhatsAppCrossAccountRole \
     --query "Role.AssumeRolePolicyDocument"
   ```

## Voice Assistant Issues

### Audio Quality Problems

**Symptoms:**

- Choppy or distorted audio
- Audio cutting out during conversation
- Poor speech recognition

**Solutions:**

1. **Check Network Connection**:
   - Ensure stable internet connection
   - Test with different network (WiFi vs cellular)
   - Check for network congestion

2. **Browser Compatibility**:
   - Use supported browsers (Chrome, Firefox, Safari)
   - Enable microphone permissions
   - Check browser audio settings

3. **LiveKit Configuration**:
   ```bash
   # Verify LiveKit credentials
   aws secretsmanager get-secret-value \
     --secret-id virtual-assistant-livekit
   ```

### Voice Agent Not Responding

**Symptoms:**

- Voice agent connects but doesn't respond to speech
- No audio output from agent

**Solutions:**

1. **Check Amazon Bedrock Model Access**:
   - Verify Amazon Nova Sonic is enabled in Bedrock console
   - Check model access permissions in target region

2. **Monitor ECS Logs**:

   ```bash
   # Check LiveKit agent logs
   aws logs tail /ecs/virtual-assistant-livekit --follow
   ```

3. **Verify Amazon Bedrock AgentCore Integration**:
   ```bash
   # Check AgentCore runtime status
   aws bedrock-agent-runtime list-agent-runtimes
   ```

### Microphone Permission Issues

**Symptoms:**

- Browser prompts for microphone access repeatedly
- "Microphone not available" errors

**Solutions:**

1. **Browser Settings**:
   - Check site permissions in browser settings
   - Clear browser cache and cookies
   - Try incognito/private browsing mode

2. **HTTPS Requirement**:
   - Ensure accessing site via HTTPS
   - Microphone access requires secure context

## Chat Assistant Issues

### Chat Not Loading

**Symptoms:**

- Chat interface shows loading spinner indefinitely
- Authentication errors in browser console

**Solutions:**

1. **Check Amazon Cognito Configuration**:

   ```bash
   # Verify user pool exists
   aws cognito-idp describe-user-pool --user-pool-id YOUR-USER-POOL-ID
   ```

2. **Check Browser Console**:
   - Open browser developer tools
   - Look for JavaScript errors in console
   - Check network tab for failed requests

### Messages Not Sending

**Symptoms:**

- Chat interface loads but messages don't send
- Error messages in chat interface

**Solutions:**

1. **Check User Authentication**:
   - Verify user is properly logged in
   - Check JWT token validity
   - Try logging out and back in

2. **Amazon API Gateway Issues**:

   ```bash
   # Check API Gateway logs
   aws logs tail /aws/apigateway/YOUR-API-ID --follow
   ```

3. **AgentCore Runtime**:
   ```bash
   # Check AgentCore runtime health
   aws bedrock-agent-runtime invoke-agent \
     --agent-id YOUR-AGENT-ID \
     --agent-alias-id TSTALIASID \
     --session-id test-session \
     --input-text "Hello"
   ```

## Deployment Issues

### CDK Deployment Failures

**Symptoms:**

- CDK deploy command fails with errors
- AWS CloudFormation stack in failed state

**Common Solutions:**

1. **Bootstrap CDK** (if not done):

   ```bash
   pnpm exec nx bootstrap infra
   ```

2. **Check AWS Credentials**:

   ```bash
   aws sts get-caller-identity
   ```

3. **Verify Permissions**:
   - Ensure AWS credentials have necessary permissions
   - Check for service quotas and limits

4. **Clean Failed Stack**:
   ```bash
   # If stack is in failed state
   pnpm exec nx destroy infra
   pnpm exec nx deploy infra
   ```

### Resource Limit Errors

**Symptoms:**

- Deployment fails with quota exceeded errors
- VPC limit errors

**Solutions:**

1. **Check Service Quotas**:

   ```bash
   aws service-quotas list-service-quotas --service-code ec2
   ```

2. **Request Quota Increases**:
   - Use AWS Service Quotas console
   - Request increases for needed resources

3. **Clean Up Unused Resources**:
   ```bash
   # List unused VPCs
   aws ec2 describe-vpcs --filters "Name=is-default,Values=false"
   ```

### Docker Build Issues

**Symptoms:**

- Docker image build failures during deployment
- ECR push errors

**Solutions:**

1. **Check Docker Daemon**:

   ```bash
   docker info
   ```

2. **Clean Docker Cache**:

   ```bash
   docker system prune -a
   ```

3. **ECR Authentication**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR-ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
   ```

## Performance Issues

### Slow Response Times

**Symptoms:**

- Long delays in chat responses
- Voice agent takes too long to respond

**Solutions:**

1. **Check AWS Lambda Performance**:

   ```bash
   # Monitor Lambda duration metrics
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Duration \
     --dimensions Name=FunctionName,Value=YOUR-FUNCTION-NAME \
     --start-time 2024-01-01T00:00:00Z \
     --end-time 2024-01-01T23:59:59Z \
     --period 3600 \
     --statistics Average
   ```

2. **Bedrock Model Performance**:
   - Check if using appropriate model for use case
   - Consider using Cross-Region Inference for higher throughput
   - Monitor token usage and optimize prompts

3. **Database Performance**:
   ```bash
   # Check Aurora cluster metrics
   aws rds describe-db-clusters --db-cluster-identifier YOUR-CLUSTER-ID
   ```

### High Costs

**Symptoms:**

- AWS bill higher than expected
- Unexpected resource usage

**Solutions:**

1. **Cost Analysis**:

   ```bash
   # Check cost by service
   aws ce get-cost-and-usage \
     --time-period Start=2024-01-01,End=2024-01-31 \
     --granularity MONTHLY \
     --metrics BlendedCost \
     --group-by Type=DIMENSION,Key=SERVICE
   ```

2. **Resource Optimization**:
   - Review CloudWatch metrics for unused resources
   - Consider using Spot instances for non-critical workloads
   - Implement auto-scaling policies

3. **Set Up Budgets**:
   ```bash
   aws budgets create-budget \
     --account-id YOUR-ACCOUNT-ID \
     --budget file://budget.json
   ```

## Authentication Issues

### Cognito Authentication Failures

**Symptoms:**

- Users cannot log in
- JWT token validation errors

**Solutions:**

1. **Check User Pool Configuration**:

   ```bash
   aws cognito-idp describe-user-pool --user-pool-id YOUR-USER-POOL-ID
   ```

2. **Verify User Status**:

   ```bash
   aws cognito-idp admin-get-user \
     --user-pool-id YOUR-USER-POOL-ID \
     --username YOUR-USERNAME
   ```

3. **Reset User Password**:
   ```bash
   aws cognito-idp admin-set-user-password \
     --user-pool-id YOUR-USER-POOL-ID \
     --username YOUR-USERNAME \
     --password NEW-PASSWORD \
     --permanent
   ```

### Cross-Service Authentication

**Symptoms:**

- Services cannot communicate with each other
- IAM permission errors

**Solutions:**

1. **Check IAM Roles**:

   ```bash
   aws iam get-role --role-name YOUR-ROLE-NAME
   ```

2. **Test Permissions**:

   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn YOUR-ROLE-ARN \
     --action-names YOUR-ACTION \
     --resource-arns YOUR-RESOURCE-ARN
   ```

3. **Review CloudTrail Logs**:
   ```bash
   aws logs filter-log-events \
     --log-group-name CloudTrail/YOUR-TRAIL \
     --filter-pattern "{ $.errorCode = * }"
   ```

## General Debugging Commands

### CloudWatch Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/YOUR-FUNCTION --follow

# Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/YOUR-FUNCTION \
  --filter-pattern "ERROR"

# Search for specific text
aws logs filter-log-events \
  --log-group-name /aws/lambda/YOUR-FUNCTION \
  --filter-pattern "WhatsApp"
```

### Resource Status Checks

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name YOUR-STACK-NAME \
  --query "Stacks[0].StackStatus"

# List stack resources
aws cloudformation list-stack-resources \
  --stack-name YOUR-STACK-NAME

# Check Lambda function status
aws lambda get-function \
  --function-name YOUR-FUNCTION-NAME
```

### Network Diagnostics

```bash
# Test connectivity to API Gateway
curl -I https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod/health

# Check DNS resolution
nslookup YOUR-CLOUDFRONT-DOMAIN

# Test WebSocket connection
wscat -c wss://YOUR-WEBSOCKET-ENDPOINT
```

## Getting Help

### AWS Support Resources

- [AWS Support Center](https://console.aws.amazon.com/support/)
- [AWS Documentation](https://docs.aws.amazon.com/)
- [AWS Forums](https://forums.aws.amazon.com/)

### Monitoring and Alerting

Set up CloudWatch alarms for:

- Lambda error rates
- API Gateway 5xx errors
- Database connection failures
- High cost alerts

### Log Analysis

Use CloudWatch Insights for advanced log analysis:

```sql
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20
```

---

For WhatsApp-specific troubleshooting, see the detailed
[WhatsApp Integration Guide](#whatsapp-integration-with-aws-end-user-messaging-social).
