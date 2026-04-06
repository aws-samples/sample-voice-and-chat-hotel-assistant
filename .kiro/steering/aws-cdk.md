---
inclusion: fileMatch
fileMatchPattern: 'packages/infra/**/*.py'
---

# AWS CDK Development Guide

## Architecture Patterns

### Construct Organization

- **Reusable Constructs**: Create focused constructs for multi-resource patterns
  (e.g., `MessageProcessingConstruct`, `MessagingBackendConstruct`)
- **Direct Imports**: Use direct imports like
  `from .stack_constructs.message_processing_construct import MessageProcessingConstruct`
- **Property Exposure**: Expose resources as simple properties
  (`self.processing_queue`, `self.lambda_function`) without `@property`
  decorators
- **Conditional Deployment**: Use constructs for conditional infrastructure (EUM
  Social vs simulated messaging backend)

### Resource Patterns

- **Grant Methods**: Follow CDK `IGrantable` patterns for permissions (e.g.,
  `grant_whatsapp_permissions(grantee: iam.IGrantable)`)
- **Environment Variables**: Pass configuration through constructor parameters
  and environment variables
- **Resource Naming**: Use consistent pattern:
  `f"{stack_name}-{component}-{resource_type}"`

## Project Structure

```
packages/infra/
├── app.py                    # CDK app entry point
├── pyproject.toml           # Python dependencies and configuration
├── uv.lock                  # Dependency lockfile
├── cdk.json                 # CDK configuration
├── cdk.context.json         # CDK context values
├── cdk.out/                 # CDK synthesis output (generated)
└── stack/
    ├── __init__.py
    ├── backend_stack.py     # Main backend infrastructure
    └── stack_constructs/    # Reusable CDK constructs
        ├── message_processing_construct.py
        ├── messaging_backend_construct.py
        ├── whatsapp_grant_utils.py
        ├── cognito_constructs.py
        ├── custom_resource_construct.py
        ├── docker_constructs.py
        ├── livekit_ecs_construct.py
        ├── s3_constructs.py
        └── vpc_construct.py
```

## Key CDK Commands

### Development Commands

```bash
# Install Python dependencies
uv sync         # Runs uv sync in infra directory

# Direct CDK commands (from packages/infra/)
uv run cdk deploy             # Deploy stack
uv run cdk diff               # Show changes
uv run cdk synth              # Synthesize CloudFormation
uv run cdk destroy            # Destroy stack
uv run cdk bootstrap          # Bootstrap CDK in account/region

# NX commands (from workspace root)
pnpm exec nx deploy infra     # Deploy via NX
pnpm exec nx diff infra       # Show changes via NX
```

## Infrastructure Components

### Backend Stack (`BackendStack`)

The main backend stack includes:

1. **AgentCore Runtime** - Virtual assistant chat runtime with JWT
   authentication
2. **Message Processing** (`MessageProcessingConstruct`) - SQS queue, DLQ, and
   Lambda for async messaging
3. **Conditional Messaging Integration**:
   - **EUM Social**: WhatsApp integration via external SNS topic
   - **Messaging Backend** (`MessagingBackendConstruct`): Complete simulated
     messaging platform
4. **LiveKit ECS** (`LiveKitECSConstruct`) - Voice agent infrastructure
   (optional)
5. **Docker Assets** - ECR repositories and container images

### Messaging Backend Construct

When EUM Social is unavailable, deploys complete messaging infrastructure:

- **DynamoDB Table**: Message storage with GSI for message ID lookups
- **SNS Topic**: Message publishing with SSL enforcement
- **Lambda Function**: API handler with APIGatewayRestResolver
- **API Gateway**: REST API with Cognito authorization and WAF protection
- **Cognito User Pool**: Authentication with OAuth2 client credentials flow
- **WAF Web ACL**: Security protection with AWS managed rule groups
- **Secrets Manager**: Machine client credentials storage

## CDK Best Practices

### Construct Design Patterns

```python
# Reusable construct with simple interface
class MessageProcessingConstruct(Construct):
    def __init__(self, scope, construct_id, agentcore_runtime_arn, environment_variables=None):
        super().__init__(scope, construct_id)

        # Expose resources as simple properties (no @property decorators)
        self.processing_queue = sqs.Queue(...)
        self.dead_letter_queue = sqs.Queue(...)
        self.lambda_function = _lambda.Function(...)

# Grant pattern following CDK conventions
def grant_whatsapp_permissions(grantee: iam.IGrantable, cross_account_role: str = None) -> iam.Grant:
    """Grant WhatsApp permissions following CDK IGrantable pattern."""
    return grantee.grant(...)
```

### Resource Naming & Configuration

```python
# Consistent naming pattern
stack_name = Stack.of(self).stack_name
resource_name = f"{stack_name}-{component}-{resource_type}"

# Environment variables through constructor
environment_vars = {
    "AGENTCORE_RUNTIME_ARN": agentcore_runtime_arn,
    "LOG_LEVEL": "INFO",
}
if additional_vars:
    environment_vars.update(additional_vars)
```

### CDK Nag Suppressions

```python
# Specific suppressions with detailed justifications
NagSuppressions.add_resource_suppressions(
    lambda_function,
    [
        NagPackSuppression(
            id="AwsSolutions-IAM5",
            reason="Lambda requires wildcard permissions for: 1) CloudWatch Logs "
            "(arn:aws:logs:*:*:*) for runtime logging, 2) AgentCore Runtime ARN "
            "wildcard (*) for dynamic resource access. Scoped to service namespaces.",
            applies_to=[
                "Action::bedrock-agentcore:*",
                "Resource::arn:aws:logs:*:*:*",
                "Resource::*",
            ],
        ),
    ],
    apply_to_children=True,
)
```

### Security & Permissions

```python
# Least privilege with specific resource ARNs
lambda_function.add_to_role_policy(
    iam.PolicyStatement(
        sid="AgentCoreRuntimeInvoke",
        effect=iam.Effect.ALLOW,
        actions=["bedrock-agentcore:InvokeAgentRuntime"],
        resources=[f"{agentcore_runtime_arn}*"],
    )
)

# SSL enforcement for queues and topics
queue = sqs.Queue(self, "Queue", enforce_ssl=True)
```

## Development Workflow

### Local Development

1. **Setup Environment**:

   ```bash
   cd packages/infra
   uv sync  # Install dependencies
   ```

2. **Configure AWS**:

   ```bash
   aws configure --profile your-profile
   export AWS_PROFILE=your-profile
   ```

3. **Bootstrap CDK** (first time only):

   ```bash
   uv run cdk bootstrap
   ```

4. **Development Cycle**:
   ```bash
   # Make changes to CDK code
   uv run cdk diff      # Review changes
   uv run cdk deploy --no-rollback   # Deploy changes
   ```

### Conditional Deployment Patterns

```python
# EUM Social vs Messaging Backend
eum_social_topic_arn = self.node.try_get_context("eumSocialTopicArn")
eum_social_phone_id = self.node.try_get_context("eumSocialPhoneNumberId")

if eum_social_topic_arn and eum_social_phone_id:
    # Use EUM Social integration
    self._create_messaging_integration(
        agentcore_runtime,
        eum_social_topic_arn=eum_social_topic_arn,
        eum_social_phone_id=eum_social_phone_id,
    )
elif messaging_topic is None:
    # Deploy MessagingBackendConstruct
    messaging_backend = MessagingBackendConstruct(self, "MessagingBackend")
    self._create_messaging_integration(
        agentcore_runtime,
        messaging_topic=messaging_backend.messaging_topic,
    )
```

### Testing & Validation

```bash
# Synthesize to check for errors
uv run cdk synth

# Show what will change
uv run cdk diff

# Deploy with NX (preferred)
pnpm exec nx deploy infra

# Check for CDK Nag violations
uv run cdk synth 2>&1 | grep -i "nag"
```

## Configuration

### CDK Context Variables

```bash
# EUM Social WhatsApp integration
cdk deploy --context eumSocialTopicArn=arn:aws:sns:... \
           --context eumSocialPhoneNumberId=... \
           --context eumSocialCrossAccountRole=arn:aws:iam::...

# Cross-account Bedrock access
cdk deploy --context bedrock_xacct_role=arn:aws:iam::... \
           --context bedrock_xacct_region=us-west-2

# LiveKit voice agent
cdk deploy --context livekit_secret_name=livekit-credentials
```

### Python Dependencies (`pyproject.toml`)

Key dependencies:

- `aws-cdk-lib==2.194.0` - Main CDK library
- `constructs>=10.0.0` - CDK constructs framework
- `cdk_nag` - Security and best practices validation
- `virtual-assistant-constructs` - AgentCore Memory and Runtime constructs

### Lambda Package Paths

```python
# Consistent Lambda package structure
lambda_package_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "virtual-assistant",
    "virtual-assistant-messaging-lambda",
    "dist",
    "lambda",
    "message-processor",
    "lambda.zip",
)
```

## Common Patterns

### Messaging Integration Patterns

```python
# Unified messaging integration method
def _create_messaging_integration(
    self,
    agentcore_runtime,
    # EUM Social parameters (optional)
    eum_social_topic_arn: str = None,
    eum_social_phone_id: str = None,
    # Simulated messaging parameters (optional)
    messaging_topic: sns.ITopic = None,
    messaging_client_secret: secretsmanager.ISecret = None,
) -> None:
    # Create MessageProcessingConstruct for both integration types
    message_processing = MessageProcessingConstruct(
        self, "MessageProcessing",
        agentcore_runtime_arn=agentcore_runtime.agent_runtime_arn,
        environment_variables=environment_vars,
    )

    # Configure based on integration type
    if eum_social_topic_arn:
        # EUM Social integration
        grant_whatsapp_permissions(grantee=message_processing.lambda_function)
    elif messaging_topic:
        # Simulated messaging integration
        messaging_topic.add_subscription(
            sns_subscriptions.SqsSubscription(message_processing.processing_queue)
        )
```

### CDK Nag Path Suppressions

```python
# Dynamic stack name for robust path suppressions
stack_name = Stack.of(self).stack_name

NagSuppressions.add_resource_suppressions_by_path(
    self,
    f"/{stack_name}/Custom::CDKBucketDeployment.../ServiceRole/Resource",
    [
        NagPackSuppression(
            id="AwsSolutions-IAM4",
            reason="CDK BucketDeployment uses AWS managed policies for S3 operations",
        )
    ],
)
```

## Troubleshooting

### Common Issues

1. **CDK Nag Violations**: Check suppressions have correct `applies_to` values
2. **Lambda Package Paths**: Verify relative paths to `dist/lambda/*/lambda.zip`
3. **Context Variables**: Use `self.node.try_get_context()` for optional
   configuration
4. **Resource Dependencies**: Ensure proper dependency ordering with
   `node.add_dependency()`

### Stack Outputs

Key outputs for integration:

- `AgentCoreRuntimeArn` - Runtime ARN for message processing
- `MessageProcessingQueueArn` - SQS queue for async messaging
- `EUMSocialTopicArn` - External SNS topic (if EUM Social)
- `MessagingAPIEndpoint` - API Gateway URL (if messaging backend)
