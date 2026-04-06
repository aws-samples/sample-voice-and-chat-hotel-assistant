# Design Document

## Overview

This design document outlines the technical approach for migrating from our
custom AgentCore Runtime wrapper to the native AWS CDK L2 constructs in
`aws_cdk.aws_bedrock_agentcore_alpha`. The migration will replace our L1-based
custom wrapper with the official L2 `Runtime` construct, simplifying our
infrastructure code and reducing maintenance overhead.

## Architecture

### Current Architecture

```
BackendStack
├── AgentCoreRuntime (custom wrapper)
│   ├── _create_execution_role()
│   ├── _build_artifact_config()
│   ├── _build_network_config()
│   ├── _build_protocol_config()
│   └── CfnRuntime (L1 construct)
└── MessageProcessingConstruct
    └── Lambda (invokes runtime via ARN)
```

### Target Architecture

```
BackendStack
├── Runtime (native L2 construct)
│   ├── AgentRuntimeArtifact.from_docker_image_asset()
│   ├── RuntimeNetworkConfiguration.using_public_network()
│   ├── ProtocolType.HTTP
│   └── Automatic role creation with grant methods
└── MessageProcessingConstruct
    └── Lambda (invokes runtime via DEFAULT endpoint)
```

## Components and Interfaces

### L2 Runtime Construct Configuration

The native L2 construct will be configured as follows:

```python
from aws_cdk.aws_bedrock_agentcore_alpha import (
    Runtime,
    AgentRuntimeArtifact,
    RuntimeNetworkConfiguration,
    ProtocolType,
)

# Create runtime with L2 construct
agentcore_runtime = Runtime(
    self,
    "VirtualAssistantRuntime",
    agent_runtime_artifact=AgentRuntimeArtifact.from_docker_image_asset(
        docker_image_asset
    ),
    runtime_name="VirtualAssistantRuntime",
    protocol_configuration=ProtocolType.HTTP,
    network_configuration=RuntimeNetworkConfiguration.using_public_network(),
    environment_variables=environment_variables,
    description="Virtual Assistant AgentCore Runtime",
)
```

### Property Access Migration

| Current Custom Wrapper                 | L2 Construct Equivalent                |
| -------------------------------------- | -------------------------------------- |
| `agentcore_runtime.agent_runtime_arn`  | `agentcore_runtime.agent_runtime_arn`  |
| `agentcore_runtime.agent_runtime_id`   | `agentcore_runtime.agent_runtime_id`   |
| `agentcore_runtime.agent_runtime_name` | `agentcore_runtime.agent_runtime_name` |
| `agentcore_runtime.agent_core_role`    | `agentcore_runtime.role`               |
| `agentcore_runtime.grant_invoke()`     | `agentcore_runtime.grant_invoke()`     |

### IAM Role Configuration

The L2 construct provides automatic role creation with appropriate permissions.
For additional permissions:

```python
# Add cross-account Bedrock role assumption
if bedrock_xacct_role:
    agentcore_runtime.add_to_role_policy(
        iam.PolicyStatement(
            sid="BedrockXacctRoleAccess",
            effect=iam.Effect.ALLOW,
            actions=["sts:AssumeRole"],
            resources=[bedrock_xacct_role],
        )
    )

# Grant memory access
agentcore_memory.grant(agentcore_runtime.role)
```

## Data Models

### Environment Variables Structure

The environment variables will be passed directly to the L2 construct:

```python
environment_variables = {
    "AWS_REGION": Aws.REGION,
    "AWS_DEFAULT_REGION": Aws.REGION,
    "BEDROCK_MODEL_ID": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "MODEL_TEMPERATURE": "0.2",
    "LOG_LEVEL": "INFO",
    "AGENTCORE_MEMORY_ID": agentcore_memory.memory_id,
    # Additional environment variables as needed
}
```

### Import Structure Changes

```python
# Remove custom import
# from .stack_constructs.agentcore_runtime import AgentCoreRuntime

# Add L2 construct imports
from aws_cdk.aws_bedrock_agentcore_alpha import (
    Runtime,
    AgentRuntimeArtifact,
    RuntimeNetworkConfiguration,
    ProtocolType,
)
```

## Implementation Strategy

### Phase 1: Update Backend Stack

1. **Update imports** in `backend_stack.py`
2. **Replace AgentCoreRuntime instantiation** with L2 Runtime construct
3. **Configure L2 construct** with equivalent settings
4. **Update property references** to use L2 construct properties
5. **Test deployment** to ensure functionality is preserved

### Phase 2: Clean Up Custom Wrapper

1. **Remove `agentcore_runtime.py`** file
2. **Update `__init__.py`** to remove AgentCoreRuntime export
3. **Verify no remaining references** to custom wrapper
4. **Update any documentation** or comments

### Phase 3: Validation

1. **Deploy updated stack** and verify successful deployment
2. **Test runtime invocation** from message processing Lambda
3. **Validate virtual assistant functionality** end-to-end
4. **Monitor CloudWatch logs** for any issues

## Error Handling

### L2 Construct Validation

The L2 construct provides built-in validation for:

- Runtime name format (alphanumeric + underscore, max 48 chars)
- Environment variable format (string key-value pairs)
- Container image URI format
- IAM role permissions

### Migration Error Scenarios

1. **Import errors**: Ensure CDK version supports `aws_bedrock_agentcore_alpha`
2. **Property access errors**: Update all references to use L2 construct
   properties
3. **Permission errors**: Verify L2 construct creates appropriate IAM
   permissions
4. **Runtime invocation errors**: Ensure message processing Lambda can invoke
   the runtime

### Rollback Strategy

Since this is a prototype solution:

1. **Destroy existing stack** before migration
2. **Deploy with L2 constructs**
3. **If issues occur**, revert to previous commit and redeploy

## Testing Strategy

### Unit Testing

- **CDK synthesis tests**: Verify L2 construct generates expected CloudFormation
- **Property access tests**: Ensure all properties are accessible
- **IAM permission tests**: Verify grant methods work correctly

### Integration Testing

- **Stack deployment**: Deploy to test environment
- **Runtime invocation**: Test Lambda can invoke runtime
- **End-to-end functionality**: Verify virtual assistant works correctly

### Validation Checklist

- [ ] Stack deploys successfully with L2 construct
- [ ] Runtime ARN is accessible and correctly formatted
- [ ] Message processing Lambda can invoke runtime
- [ ] Virtual assistant responds to messages correctly
- [ ] CloudWatch logs show no errors
- [ ] All environment variables are passed correctly
- [ ] IAM permissions are equivalent to previous implementation

## Performance Considerations

### L2 Construct Benefits

- **Reduced code complexity**: Eliminates custom validation and configuration
  logic
- **Better error messages**: L2 constructs provide clearer validation errors
- **Automatic best practices**: L2 constructs include AWS recommended
  configurations
- **Simplified maintenance**: No need to maintain custom wrapper code

### Runtime Performance

- **No performance impact**: L2 constructs generate the same underlying
  CloudFormation resources
- **Same runtime behavior**: Virtual assistant functionality remains identical
- **Equivalent IAM permissions**: Security posture is maintained

## Security Considerations

### IAM Role Management

The L2 construct will either:

1. **Create automatic role** with appropriate permissions for AgentCore Runtime
2. **Accept custom role** if additional permissions are needed

### Permission Equivalence

Ensure the L2 construct provides equivalent permissions to our custom wrapper:

- ECR access for container image pulls
- CloudWatch Logs for runtime logging
- Bedrock access for model invocation
- AgentCore service permissions
- Cross-account role assumption (if configured)

### Network Security

- **Public network mode**: Maintains current configuration
- **No VPC changes**: Runtime continues to operate in public network mode
- **Same security groups**: No changes to network security posture

## Deployment Considerations

### CDK Version Requirements

- Ensure CDK version supports `aws_bedrock_agentcore_alpha` module
- Update `pyproject.toml` if necessary to include alpha module dependencies

### Stack Deployment Process

1. **Destroy existing stack**: `cdk destroy`
2. **Deploy with L2 constructs**: `cdk deploy`
3. **Verify functionality**: Test virtual assistant end-to-end
4. **Monitor for issues**: Check CloudWatch logs and metrics

### Resource Naming

- **Let CDK generate names**: L2 construct will generate appropriate resource
  names
- **No naming conflicts**: New deployment will create fresh resources
- **Update outputs**: Ensure CloudFormation outputs remain consistent for
  dependent systems

## Monitoring and Observability

### CloudWatch Integration

The L2 construct provides built-in CloudWatch metrics:

- `metric_invocations()`: Total runtime invocations
- `metric_latency()`: Runtime response latency
- `metric_system_errors()`: System error count
- `metric_user_errors()`: User error count

### Logging

- **Same log groups**: Runtime logs continue to go to CloudWatch
- **Same log format**: No changes to log structure
- **Same retention**: Log retention policies remain unchanged

### Alerting

- **Existing alarms**: Should continue to work with same metric names
- **New metrics available**: L2 construct provides additional metrics if needed
- **Error monitoring**: Same error patterns and alerting capabilities
