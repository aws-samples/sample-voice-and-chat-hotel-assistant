# Implementation Plan

- [x] 1. Create TypeScript interfaces and types for AgentCore Memory construct
  - Define MemoryStrategyConfig interface with type, description, and namespaces
    properties
  - Define AgentCoreMemoryProps interface with all required and optional
    properties
  - Add proper JSDoc documentation for all interfaces
  - _Requirements: 1.3, 5.4_

- [x] 2. Implement core AgentCoreMemory construct class
  - Create class extending Construct and implementing IGrantable interface
  - Add constructor with props validation
  - Implement private validation methods for eventExpiryDuration, memoryName,
    and ARN formats
  - Set up public readonly properties for memoryId, memoryArn, and
    grantPrincipal
  - _Requirements: 1.1, 1.2, 5.1, 6.2_

- [x] 3. Implement AWS Custom Resource for CREATE operations
  - Create AwsCustomResource with onCreate configuration
  - Implement buildCreateParameters method to map props to CreateMemory API
    parameters
  - Handle memory strategies array transformation for API format
  - Set physicalResourceId from response memory.id
  - _Requirements: 1.1, 1.4, 4.1, 4.2_

- [x] 4. Implement AWS Custom Resource for UPDATE operations
  - Add onUpdate configuration to existing AwsCustomResource
  - Implement buildUpdateParameters method for UpdateMemory API
  - Handle memory strategies updates using addMemoryStrategies approach
  - Use PhysicalResourceIdReference for memoryId parameter
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 5. Implement AWS Custom Resource for DELETE operations
  - Add onDelete configuration to existing AwsCustomResource
  - Configure DeleteMemory API call with memoryId from
    PhysicalResourceIdReference
  - Ensure deletion doesn't fail CloudFormation stack on errors
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Create IAM policy for custom resource permissions
  - Implement createCustomResourcePolicy method
  - Add bedrock-agentcore:CreateMemory, UpdateMemory, DeleteMemory, GetMemory
    permissions
  - Set resource to "\*" for bedrock-agentcore actions
  - Enable installLatestAwsSdk for custom resource
  - _Requirements: 1.4, 2.2, 3.3_

- [x] 7. Implement grant method for IAM permissions
  - Create grant method accepting IGrantable and optional actions
  - Define default actions for memory operations (GetMemory, PutMemoryEvent,
    GetMemoryEvents, DeleteMemoryEvents)
  - Use iam.Grant.addToPrincipal with memoryArn as resource
  - Return Grant object for chaining
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 8. Add construct to package exports
  - Update packages/common/constructs/src/index.ts to export AgentCoreMemory
    class
  - Export all related interfaces (AgentCoreMemoryProps, MemoryStrategyConfig)
  - Ensure proper TypeScript module structure
  - _Requirements: 5.3_

- [x] 9. Create comprehensive unit tests
  - Test construct creation with minimal required props
  - Test construct creation with all optional props including strategies
  - Test props validation for eventExpiryDuration range (7-365)
  - Test props validation for memoryName format
  - Test buildCreateParameters method output
  - Test buildUpdateParameters method output
  - Test grant method with default and custom actions
  - _Requirements: 5.4_

- [ ] 10. Add CloudFormation outputs for key properties
  - Add CfnOutput for memoryId with descriptive name
  - Add CfnOutput for memoryArn with descriptive name
  - Include proper descriptions for each output
  - _Requirements: 1.2_
