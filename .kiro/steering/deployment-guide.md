---
inclusion: always
---

# Deployment Guide

## Overview

The Hotel Assistant uses AWS CDK for infrastructure as code and supports
multiple deployment environments. The deployment process is automated through NX
monorepo commands and includes frontend build, Docker image creation, and AWS
resource provisioning.

## Prerequisites

### Required Tools

- **Python 3.13+**: For CDK infrastructure code
- **Node.js 18+**: For frontend build and NX
- **pnpm 8+**: Package manager
- **Docker**: For WebSocket server containerization
- **AWS CLI**: Configured with appropriate credentials
- **AWS CDK**: Installed globally or via uv

### AWS Requirements

1. **AWS Account**: With appropriate permissions
2. **AWS CLI Configuration**:

   ```bash
   aws configure --profile your-profile
   AWS Access Key ID [None]: xxxxxx
   AWS Secret Access Key [None]: yyyyyyyyyy
   Default region name [None]: us-east-1
   Default output format [None]: json
   ```

3. **Bedrock Model Access**: Enable Amazon Nova Sonic in Bedrock console
4. **CDK Bootstrap**: Bootstrap CDK in target account/region

## Deployment Process

### 1. Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd hotel-assistant

# Install all dependencies
pnpm install

# Install Python dependencies
pnpm install:python

# Bootstrap CDK (first time only)
pnpx nx bootstrap infra
```

### 2. Build Frontend

```bash
# Build frontend for local development
pnpm build

# The frontend runs locally and connects to deployed backend services
# No S3 or CloudFront deployment - use nx serve demo for development
```

### 3. Deploy Infrastructure

```bash
# Show what will be deployed
pnpm exec nx run infra deploy:diff

# Deploy all resources
pnpm exec nx run infra:deploy

# Monitor deployment progress
# Deployment typically takes 2-3 minutes total
# - HotelPmsStack: ~70 seconds
# - VirtualAssistantStack: ~50 seconds
```

### 4. Verify Deployment

```bash
# Get important stack outputs
aws cloudformation describe-stacks \
  --stack-name VirtualAssistantStack \
  --query 'Stacks[0].Outputs'
```

## Deployment Architecture

### AWS Resources Created

1. **VPC and Networking**
   - Custom VPC with public/private subnets
   - NAT Gateway for private subnet internet access
   - Security groups for different components

2. **Compute Resources**
   - ECS Fargate cluster for voice agent (when LiveKit configured)
   - Network Load Balancer for WebSocket traffic
   - Auto-scaling configuration

3. **Storage**
   - S3 bucket for configuration files (runtime-config.json)
   - ECR repository for Docker images

4. **Authentication**
   - Cognito User Pool for user management
   - Cognito Identity Pool for AWS resource access

5. **Monitoring and Logging**
   - CloudWatch logs for all services
   - CloudWatch metrics and alarms
   - X-Ray tracing (optional)

### Resource Naming Convention

Resources follow the pattern: `{StackName}-{Component}-{ResourceType}`

Example:

- `VirtualAssistantStack-WebsiteBucket-ABC123`
- `VirtualAssistantStack-UserPool-XYZ789`

## Configuration Management

### Environment Variables

The CDK automatically configures environment variables for different components:

**Frontend Configuration** (generated in `config.js`):

```javascript
window.config = {
  cognito: {
    userPoolId: 'us-east-1_xxxxxxxxx',
    userPoolClientId: 'xxxxxxxxxxxxxxxxxxxxxxxxxx',
    region: 'us-east-1',
  },
  websocket: {
    endpoint: 'wss://your-nlb-endpoint.elb.amazonaws.com',
  },
};
```

**WebSocket Server Environment**:

- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`
- `AWS_REGION`
- `BEDROCK_MODEL_ID`

### Custom Resource for Configuration

The CDK includes a custom resource that automatically updates the frontend
configuration:

```python
# Custom resource Lambda function
def update_config_js(event, context):
    """Update frontend config.js with backend endpoints"""

    config = {
        'cognito': {
            'userPoolId': event['ResourceProperties']['UserPoolId'],
            'userPoolClientId': event['ResourceProperties']['UserPoolClientId'],
            'region': event['ResourceProperties']['Region']
        },
        'websocket': {
            'endpoint': event['ResourceProperties']['WebSocketEndpoint']
        }
    }

    # Upload to S3
    s3_client.put_object(
        Bucket=bucket_name,
        Key='config.js',
        Body=f'window.config = {json.dumps(config)};',
        ContentType='application/javascript'
    )
```

## Docker Deployment

### WebSocket Server Container

The WebSocket server is containerized using a multi-stage Docker build:

```dockerfile
FROM python:3.12-slim as builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

FROM python:3.12-slim

# Copy virtual environment from builder
COPY --from=builder /.venv /.venv

# Copy application code
COPY . .

# Set environment variables
ENV PATH="/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

EXPOSE 8080

CMD ["python", "websocket_server.py"]
```

### Local Docker Testing

```bash
# Build Docker image
pnpm docker:build

# Run container locally
pnpm docker:run

# Test WebSocket connection
wscat -c ws://localhost:8080/ws
```

## Monitoring and Logging

### CloudWatch Logs

All services automatically send logs to CloudWatch:

- **Voice Agent**: Application logs from Fargate
- **CDK Custom Resources**: Lambda function logs

### Viewing Logs

```bash
# Voice agent logs
aws logs describe-log-groups --log-group-name-prefix "/ecs/livekit"

# Tail logs in real-time
aws logs tail /ecs/livekit-task --follow

# Custom resource logs
aws logs tail /aws/lambda/config-updater --follow
```

### Metrics and Alarms

Key metrics to monitor:

- **WebSocket Connections**: Active connection count
- **Message Throughput**: Messages per second
- **Error Rates**: 4xx/5xx error percentages
- **Latency**: Response time percentiles
- **Resource Utilization**: CPU/Memory usage

## Troubleshooting

### Common Deployment Issues

1. **CDK Bootstrap Required**:

   ```bash
   pnpx nx bootstrap infra
   ```

2. **Insufficient Permissions**:
   - Verify AWS credentials have necessary permissions
   - Check IAM policies for CDK execution role

3. **Resource Conflicts**:
   - Ensure unique stack names for different environments
   - Check for existing resources with same names

4. **Frontend Build Failures**:

   ```bash
   # Clean and rebuild
   pnpm clean
   pnpm install
   pnpm build
   ```

5. **Docker Build Issues**:

   ```bash
   # Clean Docker cache
   docker system prune -a

   # Rebuild image
   pnpm docker:build
   ```

### Debugging Deployment

```bash
# Enable CDK debug logging
pnpm deploy --debug

# Show CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name VirtualAssistantStack

# Check stack status
aws cloudformation describe-stacks \
  --stack-name VirtualAssistantStack \
  --query 'Stacks[0].StackStatus'
```

### Rolling Back Deployments

```bash
# Destroy current stack
pnpm deploy:destroy

# Deploy previous version
git checkout previous-commit
pnpm deploy
```

## Cleanup

### Complete Cleanup

```bash
# Destroy all AWS resources
pnpm deploy:destroy

# Clean local artifacts
pnpm clean

# Remove Docker images
docker rmi websocket-server
```

### Partial Cleanup

```bash
# Empty S3 buckets before deletion
aws s3 rm s3://your-bucket-name --recursive

# Delete specific resources
aws cloudformation delete-stack --stack-name VirtualAssistantStack
```

## Security Considerations

### Deployment Security

1. **IAM Roles**: Use least-privilege IAM roles
2. **Secrets Management**: Store sensitive data in AWS Secrets Manager
3. **Network Security**: Use security groups and NACLs appropriately
4. **Encryption**: Enable encryption at rest and in transit

### Access Control

1. **AWS Profiles**: Use separate AWS profiles for different environments
2. **MFA**: Enable MFA for AWS accounts
3. **Temporary Credentials**: Use temporary credentials when possible
4. **Audit Logging**: Enable CloudTrail for audit logging

## Performance Optimization

### CDK Deployment Performance

1. **Parallel Deployments**: Deploy independent stacks in parallel
2. **Incremental Updates**: Use `cdk diff` to minimize changes
3. **Asset Optimization**: Optimize Docker images and Lambda packages

### Runtime Performance

1. **Auto Scaling**: Configure appropriate auto-scaling policies
2. **Load Balancing**: Use Network Load Balancer for WebSocket traffic
3. **Connection Pooling**: Implement connection pooling in WebSocket server

## Cost Optimization

### Resource Sizing

1. **Right-sizing**: Choose appropriate instance sizes
2. **Reserved Instances**: Use reserved instances for predictable workloads
3. **Spot Instances**: Consider spot instances for non-critical workloads

### Monitoring Costs

1. **Cost Explorer**: Monitor costs with AWS Cost Explorer
2. **Budgets**: Set up AWS Budgets for cost alerts
3. **Resource Tagging**: Tag resources for cost allocation
