# Implementation Plan

## Documentation References

During implementation, consult the following documentation:

### AWS CDK BedrockAgentCore L1 Constructs

- **CfnMemory**:
  https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_bedrockagentcore.CfnMemory.html
- **CfnGateway**:
  https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_bedrockagentcore.CfnGateway.html
- **CfnGatewayTarget**:
  https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_bedrockagentcore.CfnGatewayTarget.html
- **CfnRuntime**:
  https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_bedrockagentcore.CfnRuntime.html

### AgentCore Service Documentation

- **Gateway Configuration**:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building.html
- **Memory Strategies**:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html
- **Runtime Deployment**:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- **Outbound Authentication**:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-outbound-auth.html

### Current Implementation References

- **Existing TypeScript Constructs**: `packages/common/constructs/src/` (for
  interface compatibility)
- **Current Usage Patterns**:
  `packages/infra/stack/stack_constructs/agentcore_gateway_construct.py`
- **Stack Integration**: `packages/infra/stack/backend_stack.py` and
  `packages/infra/stack/hotel_pms_stack.py`

### Python CDK Patterns

- **AWS CDK Python Documentation**:
  https://docs.aws.amazon.com/cdk/api/v2/python/
- **Construct Development**:
  https://docs.aws.amazon.com/cdk/v2/guide/constructs.html
- **IAM Grant Patterns**:
  https://docs.aws.amazon.com/cdk/v2/guide/permissions.html

- [x] 1. Create Python wrapper constructs for AgentCore L1 constructs
  - Create new Python construct files that wrap the L1 constructs with the same
    interface as the TypeScript custom constructs
  - Implement property validation and mapping to L1 construct format
  - _Requirements: 1.1, 2.1, 3.1, 4.1_

- [x] 1.1 Create AgentCore Memory wrapper construct
  - Create `packages/infra/stack/stack_constructs/agentcore_memory.py` with
    `AgentCoreMemory` class
  - Implement property mapping from wrapper props to `CfnMemory` L1 construct
  - Add validation for event expiry duration (7-365 days), memory name format,
    and ARN formats
  - Map memory strategy configurations to L1 construct format (semantic,
    summary, user preference)
  - Implement `grant()` method for IAM permissions compatible with `IGrantable`
    interface
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 1.2 Create AgentCore Gateway wrapper construct
  - Create `packages/infra/stack/stack_constructs/agentcore_gateway.py` with
    `AgentCoreGateway` class
  - Implement JWT authorizer configuration mapping to L1 construct format
  - Add MCP protocol configuration with semantic search and instructions support
  - Map execution role, exception level, and KMS encryption settings
  - Expose gateway ID, ARN, and URL properties for MCP client connections
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 1.3 Create AgentCore Gateway Target wrapper construct
  - Create `AgentCoreGatewayTarget` class in the same file as `AgentCoreGateway`
  - Implement target configuration mapping for Lambda targets with tool schema
    from S3
  - Add credential provider configuration support (IAM role, API key, OAuth2)
  - Map target name, description, and gateway reference
  - Expose target ID and gateway ARN properties
  - _Requirements: 2.1, 2.4, 2.5_

- [x] 1.4 Create AgentCore Runtime wrapper construct
  - Create `packages/infra/stack/stack_constructs/agentcore_runtime.py` with
    `AgentCoreRuntime` class
  - Implement container artifact configuration from Docker image assets
  - Add network configuration support (PUBLIC/VPC modes with security groups and
    subnets)
  - Map authorization configuration (IAM SigV4 and custom JWT)
  - Create execution role with appropriate permissions for ECR, CloudWatch, and
    Bedrock
  - Expose runtime ID, ARN, and name properties
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 1.5 Create AgentCore Cognito construct
  - Create `packages/infra/stack/stack_constructs/agentcore_cognito.py` with
    `AgentCoreCognitoUserPool` class
  - Implement Cognito User Pool configuration for AgentCore Gateway
    authentication
  - Add JWT authorizer configuration generation method
  - Map token validity settings and self sign-up configuration
  - Maintain compatibility with existing Cognito integration patterns
  - _Requirements: 2.2, 4.1_

- [x] 2. Update infrastructure code to use Python wrapper constructs
  - Replace TypeScript construct imports with Python wrapper imports in
    infrastructure stacks
  - Update construct instantiation calls to use Python classes
  - Verify all properties are correctly mapped and maintain same functionality
  - _Requirements: 4.1, 4.2, 4.3, 7.3_

- [x] 2.1 Update hotel PMS stack to use Python constructs
  - Update `packages/infra/stack/hotel_pms_stack.py` to import Python AgentCore
    constructs
  - Replace `AgentCoreGatewayConstruct` usage with new Python wrapper constructs
  - Update construct instantiation with proper property mapping
  - Verify gateway and target configuration maintains same functionality
  - _Requirements: 2.1, 2.2, 2.4, 4.1, 4.3_

- [x] 2.2 Update backend stack to use Python constructs
  - Update `packages/infra/stack/backend_stack.py` to import Python AgentCore
    constructs
  - Replace `AgentCoreMemory` and `AgentCoreRuntime` imports with Python
    versions
  - Update construct instantiation calls with proper property mapping
  - Verify memory and runtime configuration maintains same functionality
  - _Requirements: 1.1, 3.1, 4.1, 4.3_

- [x] 2.3 Update construct files to use Python wrappers
  - Update
    `packages/infra/stack/stack_constructs/agentcore_gateway_construct.py` to
    use Python wrappers
  - Replace TypeScript construct imports with Python wrapper imports
  - Update construct instantiation and property mapping
  - Maintain same public interface and property exposure
  - _Requirements: 2.1, 4.1, 4.2_

- [x] 2.4 Update CDK Nag suppressions for L1 constructs
  - Remove custom resource specific CDK Nag suppressions
  - Add L1 construct specific suppressions as needed for security findings
  - Update suppression reasons to reflect L1 construct patterns
  - Ensure all security findings are properly addressed
  - _Requirements: 4.4, 6.1, 6.2_

- [ ] 3. Implement comprehensive testing for migrated constructs
  - Create unit tests for all Python wrapper constructs
  - Add integration tests for stack deployment with L1 constructs
  - Verify functional equivalence with previous custom resource implementation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.5_

- [ ] 3.1 Create unit tests for Python wrapper constructs
  - Create test files for each wrapper construct in appropriate test directories
  - Test property validation and mapping from wrapper props to L1 constructs
  - Test error handling for invalid configurations (ARN formats, duration
    limits, etc.)
  - Test unique name generation and resource property exposure
  - Verify grant method functionality for memory construct
  - _Requirements: 6.1, 6.2, 6.3_

- [ ]\* 3.2 Create integration tests for stack deployment
  - Create test stack configurations using Python wrapper constructs
  - Test deployment of memory, gateway, and runtime resources
  - Verify resources are created with correct properties and configurations
  - Test resource lifecycle operations (create, update, delete)
  - _Requirements: 6.4, 7.5_

- [ ]\* 3.3 Create functional tests for AgentCore integration
  - Test memory integration with virtual assistant chat functionality
  - Verify gateway MCP connectivity with hotel PMS Lambda targets
  - Test runtime container deployment and scaling behavior
  - Validate end-to-end functionality matches previous implementation
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.5_

- [ ] 4. Deploy and validate migration in development environment
  - Deploy new stack with L1 wrapper constructs (previous deployment already
    destroyed)
  - Verify all resources are created correctly and function as expected
  - _Requirements: 7.2, 7.4, 7.5_

- [x] 4.1 Deploy new stack with L1 constructs
  - Run `pnpm exec nx deploy infra` with updated Python wrapper constructs
  - Monitor deployment progress and verify successful resource creation
  - Verify all CloudFormation outputs and exports are generated correctly
  - _Requirements: 7.2, 7.4_

- [x] 4.1.1 Fix JWT authorizer pattern validation issue
  - Resolve BedrockAgentCore service API validation error for
    CustomJWTAuthorizer DiscoveryUrl
  - Error occurs during resource creation (not CloudFormation template
    validation), indicating the BedrockAgentCore service is rejecting the
    resolved discovery URL
  - Pattern expects: `^.+/\.well-known/openid-configuration$` but service
    rejects the resolved URL for unknown reasons
  - Investigate CloudTrail events to see the exact API call and parameters being
    sent to BedrockAgentCore service
  - Compare the resolved discovery URL format with working examples from
    TypeScript constructs
  - Research BedrockAgentCore service documentation for discovery URL
    requirements
  - Test with different URL formats or investigate if there are additional
    required fields
  - Current workaround uses NO_AUTHORIZER - need to restore proper JWT
    authentication
  - _Requirements: 2.2, 4.1, 7.2_

- [x] 4.2 Fix critical Cognito authentication configuration issue
  - The current Cognito User Pool Client is missing client credentials OAuth
    flow configuration
  - AgentCore Runtime authentication is failing because the client doesn't
    support machine-to-machine authentication
  - Update AgentCoreCognitoUserPool construct to enable client_credentials OAuth
    flow only
  - Create resource server with identifier "gateway-resource-server" and scopes:
    - `cognito.ResourceServerScope(scope_name="read", scope_description="Read access")`
    - `cognito.ResourceServerScope(scope_name="write", scope_description="Write access")`
  - Configure User Pool Client with resource server scopes using
    `cognito.OAuthScope.resource_server()`
  - Remove callback URLs, authorization code grant, and implicit grant flows
    (M2M only)
  - Set `generate_secret=True` and disable user-based auth flows (user_password,
    user_srp, admin_user_password)
  - _Requirements: 2.2, 4.1, 5.4, 8.1, 8.2, 8.3, 8.4_

- [ ] 4.3 Validate migrated functionality after authentication fix
  - Test virtual assistant chat functionality with new memory resource
  - Verify MCP gateway connectivity and tool schema access with proper
    authentication
  - Test container runtime deployment and environment variable configuration
  - Confirm all functionality works as expected with L1 constructs and proper
    authentication
  - _Requirements: 5.1, 5.2, 5.3, 7.4, 7.5_

- [ ] 5. Clean up and finalize migration
  - Remove TypeScript construct package and dependencies
  - Update imports to use new Python constructs
  - Finalize implementation
  - _Requirements: 9.1, 9.2_

- [x] 5.1 Remove packages/common/constructs package
  - Delete entire `packages/common/constructs` directory with TypeScript
    constructs
  - Remove package references from workspace configuration
  - Update any remaining imports to use new Python constructs
  - Clean up build scripts and dependencies related to TypeScript constructs
  - _Requirements: 9.1, 9.2_

- [x] 5.2 Finalize Python construct implementation
  - Ensure all Python constructs are properly implemented and tested
  - Verify all imports and dependencies are correctly configured
  - Add comprehensive docstrings and type hints to public interfaces
  - Confirm all requirements are met and functionality is preserved
  - _Requirements: 4.1, 4.2, 5.1, 5.2, 5.3, 5.4, 5.5, 7.5, 8.1, 8.2, 8.3, 8.4,
    8.5_
