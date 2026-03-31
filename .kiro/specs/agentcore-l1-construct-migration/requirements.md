# Requirements Document

## Introduction

This document outlines the requirements for migrating the Virtual Assistant
Platform from custom AgentCore constructs to the GA (Generally Available)
CloudFormation L1 constructs. Amazon Bedrock AgentCore has transitioned from
preview to GA, making official CloudFormation resources available through CDK L1
constructs. This migration will replace custom resource implementations with
native CloudFormation support, improving reliability, performance, and
maintainability.

## Requirements

### Requirement 1: Replace Custom AgentCore Memory Construct

**User Story:** As a platform developer, I want to use the GA CloudFormation L1
construct for AgentCore Memory instead of custom resources, so that I have
native CloudFormation support with better reliability and performance.

#### Acceptance Criteria

1. WHEN deploying the infrastructure THEN the system SHALL use
   `aws_cdk.aws_bedrockagentcore.CfnMemory` instead of the custom
   `AgentCoreMemory` construct
2. WHEN creating memory resources THEN the system SHALL support all current
   memory configuration options including event expiry duration, memory
   strategies, and encryption settings
3. WHEN memory strategies are configured THEN the system SHALL support semantic
   memory, summary memory, and user preference memory strategies with proper
   namespacing
4. WHEN the memory resource is created THEN the system SHALL expose the memory
   ID, ARN, and name for use by other components
5. WHEN IAM permissions are needed THEN the system SHALL provide a grant method
   compatible with the existing `IGrantable` interface pattern

### Requirement 2: Replace Custom AgentCore Gateway Construct

**User Story:** As a platform developer, I want to use the GA CloudFormation L1
construct for AgentCore Gateway instead of custom resources, so that I have
native CloudFormation support for MCP gateway functionality.

#### Acceptance Criteria

1. WHEN deploying the infrastructure THEN the system SHALL use
   `aws_cdk.aws_bedrockagentcore.CfnGateway` instead of the custom
   `AgentCoreGateway` construct
2. WHEN configuring gateway authentication THEN the system SHALL support JWT
   authorizer configuration with discovery URL, allowed audiences, and allowed
   clients
3. WHEN setting up MCP protocol THEN the system SHALL configure protocol type as
   MCP with supported versions and optional semantic search
4. WHEN gateway targets are needed THEN the system SHALL use
   `aws_cdk.aws_bedrockagentcore.CfnGatewayTarget` for Lambda integration
5. WHEN the gateway is created THEN the system SHALL expose gateway ID, ARN, and
   URL for MCP client connections
6. WHEN execution roles are configured THEN the system SHALL maintain
   compatibility with existing IAM role patterns

### Requirement 3: Replace Custom AgentCore Runtime Construct

**User Story:** As a platform developer, I want to use the GA CloudFormation L1
construct for AgentCore Runtime instead of custom resources, so that I have
native CloudFormation support for containerized agent deployment.

#### Acceptance Criteria

1. WHEN deploying the infrastructure THEN the system SHALL use
   `aws_cdk.aws_bedrockagentcore.CfnRuntime` instead of the custom
   `AgentCoreRuntime` construct
2. WHEN configuring container artifacts THEN the system SHALL support Docker
   image URIs from ECR repositories
3. WHEN setting up networking THEN the system SHALL configure network mode
   (PUBLIC/VPC) with appropriate security group and subnet configurations
4. WHEN authentication is required THEN the system SHALL support both IAM SigV4
   and custom JWT authorizer configurations
5. WHEN environment variables are needed THEN the system SHALL pass through all
   required environment variables to the runtime container
6. WHEN the runtime is created THEN the system SHALL expose runtime ID, ARN, and
   name for agent integration

### Requirement 4: Maintain Backward Compatibility in Public Interfaces

**User Story:** As a platform developer, I want the migration to maintain the
same public interface patterns, so that existing code using these constructs
continues to work without modification.

#### Acceptance Criteria

1. WHEN other constructs reference AgentCore resources THEN the system SHALL
   maintain the same property names and types (memoryId, gatewayArn, runtimeArn,
   etc.)
2. WHEN IAM permissions are granted THEN the system SHALL maintain the same
   `grant()` method signatures and behavior
3. WHEN CloudFormation outputs are generated THEN the system SHALL maintain the
   same output names and export patterns
4. WHEN construct dependencies are established THEN the system SHALL maintain
   the same dependency relationships between resources
5. WHEN CDK Nag suppressions are applied THEN the system SHALL update
   suppression rules to match new L1 construct patterns

### Requirement 5: Preserve All Current Functionality

**User Story:** As a platform operator, I want all current AgentCore
functionality to be preserved during the migration, so that the virtual
assistant platform continues to operate without feature regression.

#### Acceptance Criteria

1. WHEN memory strategies are configured THEN the system SHALL support all
   current strategy types (SEMANTIC_MEMORY, SUMMARY_MEMORY,
   USER_PREFERENCE_MEMORY)
2. WHEN gateway targets are created THEN the system SHALL support Lambda targets
   with tool schema configuration from S3
3. WHEN runtime containers are deployed THEN the system SHALL support all
   current container configuration options including environment variables and
   network settings
4. WHEN authentication is configured THEN the system SHALL support both Cognito
   JWT and IAM-based authentication patterns
5. WHEN observability is enabled THEN the system SHALL maintain CloudWatch
   logging, X-Ray tracing, and metrics collection

### Requirement 6: Implement Proper Error Handling and Validation

**User Story:** As a platform developer, I want comprehensive error handling and
validation in the new L1 constructs, so that configuration errors are caught
early and provide clear feedback.

#### Acceptance Criteria

1. WHEN invalid configuration is provided THEN the system SHALL validate
   parameters at construct creation time and provide clear error messages
2. WHEN required properties are missing THEN the system SHALL fail fast with
   descriptive error messages indicating the missing requirements
3. WHEN ARN formats are invalid THEN the system SHALL validate ARN patterns and
   provide specific format guidance
4. WHEN resource limits are exceeded THEN the system SHALL validate against AWS
   service limits and provide actionable error messages
5. WHEN dependencies are missing THEN the system SHALL ensure proper resource
   creation order and dependency management

### Requirement 7: Support Clean Migration Path

**User Story:** As a platform operator, I want a clean migration path from
custom resources to L1 constructs, so that I can deploy the updated
infrastructure without manual intervention.

#### Acceptance Criteria

1. WHEN the migration is deployed THEN the system SHALL support destroying the
   existing stack and redeploying with L1 constructs (no in-place migration
   required)
2. WHEN new constructs are deployed THEN the system SHALL allow CDK to generate
   unique resource names based on stack name, account number, and region rather
   than maintaining identical naming patterns
3. WHEN resource properties are migrated THEN the system SHALL map all current
   configuration options to equivalent L1 construct properties
4. WHEN the deployment completes THEN the system SHALL provide the same
   CloudFormation outputs and exports for dependent systems
5. WHEN validation is performed THEN the system SHALL ensure all migrated
   resources function identically to the previous custom resource implementation

### Requirement 8: Fix Authentication Configuration Issues

**User Story:** As a platform operator, I want the AgentCore Runtime to
successfully authenticate with the AgentCore Gateway, so that the virtual
assistant can access hotel PMS tools and provide complete functionality.

#### Acceptance Criteria

1. WHEN the Cognito User Pool Client is configured THEN the system SHALL enable
   client_credentials OAuth flow for machine-to-machine authentication
2. WHEN resource servers are created THEN the system SHALL provide appropriate
   scopes for AgentCore Gateway access
3. WHEN OAuth2 token requests are made THEN the system SHALL successfully return
   valid access tokens
4. WHEN the AgentCore Runtime connects to the Gateway THEN the system SHALL
   authenticate successfully using JWT tokens
5. WHEN authentication fails THEN the system SHALL provide clear error messages
   and troubleshooting guidance

### Requirement 9: Update Documentation and Examples

**User Story:** As a platform developer, I want updated documentation and
examples for the new L1 constructs, so that I understand how to use and extend
the migrated implementation.

#### Acceptance Criteria

1. WHEN the migration is complete THEN the system SHALL provide updated code
   examples showing L1 construct usage patterns
2. WHEN configuration options are documented THEN the system SHALL include all
   available properties and their valid values
3. WHEN integration patterns are shown THEN the system SHALL demonstrate how L1
   constructs integrate with other AWS services
4. WHEN troubleshooting guidance is provided THEN the system SHALL include
   common issues and resolution steps specific to L1 constructs
5. WHEN migration notes are documented THEN the system SHALL clearly explain
   differences between custom resources and L1 constructs
