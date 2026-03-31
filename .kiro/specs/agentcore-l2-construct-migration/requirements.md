# Requirements Document

## Introduction

This document outlines the requirements for migrating the Virtual Assistant
Platform from our custom AgentCore Runtime wrapper construct to the new native
AWS CDK L2 constructs available in `aws_cdk.aws_bedrock_agentcore_alpha`. The
AWS CDK team has now released official L2 constructs (`Runtime` and
`RuntimeEndpoint`) that provide a higher-level, more developer-friendly
interface compared to our current L1-based wrapper. This migration will simplify
our infrastructure code and reduce maintenance burden for this prototype
solution.

## Glossary

- **L1 Construct**: Low-level CloudFormation resource wrapper (CfnRuntime)
- **L2 Construct**: Higher-level construct with sensible defaults and helper
  methods (Runtime)
- **AgentCore_Runtime**: Our current custom wrapper around CfnRuntime
- **Runtime**: New native L2 construct from aws_cdk.aws_bedrock_agentcore_alpha
- **RuntimeEndpoint**: New native L2 construct for runtime endpoints
- **Backend_Stack**: The main CDK stack that deploys AgentCore infrastructure

## Requirements

### Requirement 1: Replace Custom AgentCore Runtime Wrapper with Native L2 Construct

**User Story:** As a platform developer, I want to use the official AWS CDK L2
construct for AgentCore Runtime instead of our custom wrapper, so that I have
AWS-supported constructs with simpler code and reduced maintenance.

#### Acceptance Criteria

1. WHEN deploying the infrastructure, THE Backend_Stack SHALL use
   `aws_cdk.aws_bedrock_agentcore_alpha.Runtime` instead of the custom
   `AgentCoreRuntime` construct
2. WHEN configuring the runtime, THE Backend_Stack SHALL use the L2 construct's
   `AgentRuntimeArtifact.from_docker_image_asset()` method for container
   configuration
3. WHEN setting environment variables, THE Backend_Stack SHALL pass environment
   variables directly to the Runtime constructor
4. WHEN configuring networking, THE Backend_Stack SHALL use
   `RuntimeNetworkConfiguration.using_public_network()` for public network mode
5. WHEN the runtime is created, THE Backend_Stack SHALL access properties using
   `agent_runtime_arn`, `agent_runtime_id`, and `agent_runtime_name`

### Requirement 2: Maintain Current Runtime Configuration

**User Story:** As a platform operator, I want all current AgentCore Runtime
configuration to work with the L2 construct, so that the virtual assistant
platform continues to operate with the same functionality.

#### Acceptance Criteria

1. WHEN the Docker container is configured, THE Runtime SHALL use the same
   virtual assistant Docker image asset via
   `AgentRuntimeArtifact.from_docker_image_asset()`
2. WHEN the server protocol is set, THE Runtime SHALL use `ProtocolType.HTTP`
   for AgentCore SDK compatibility
3. WHEN environment variables are configured, THE Runtime SHALL pass through all
   current environment variables including AWS region, model ID, memory ID, and
   API endpoints
4. WHEN IAM permissions are configured, THE Runtime SHALL use the L2 construct's
   automatic role creation or accept a custom execution role
5. WHEN networking is configured, THE Runtime SHALL use public network mode with
   `RuntimeNetworkConfiguration.using_public_network()`

### Requirement 3: Remove Custom Wrapper Implementation

**User Story:** As a platform developer, I want to remove the custom AgentCore
Runtime wrapper code, so that we reduce maintenance burden and code complexity.

#### Acceptance Criteria

1. WHEN the migration is complete, THE system SHALL delete the
   `agentcore_runtime.py` file from the stack constructs directory
2. WHEN imports are updated, THE Backend_Stack SHALL import `Runtime` and
   `AgentRuntimeArtifact` from `aws_cdk.aws_bedrock_agentcore_alpha`
3. WHEN the construct is removed, THE system SHALL update the `__init__.py` file
   to remove the AgentCoreRuntime export
4. WHEN dependencies are cleaned up, THE system SHALL remove any unused imports
   or helper methods specific to the custom wrapper
5. WHEN the removal is complete, THE system SHALL ensure no references to the
   custom AgentCoreRuntime remain in the codebase

### Requirement 4: Use L2 Construct Simplified Configuration

**User Story:** As a platform developer, I want to use the L2 construct's
simplified configuration options, so that the infrastructure code is cleaner and
easier to understand.

#### Acceptance Criteria

1. WHEN configuring the runtime artifact, THE Runtime SHALL use
   `AgentRuntimeArtifact.from_docker_image_asset(container_asset)` instead of
   manual dictionary construction
2. WHEN setting up networking, THE Runtime SHALL use
   `RuntimeNetworkConfiguration.using_public_network()` instead of manual
   network config dictionaries
3. WHEN configuring protocol, THE Runtime SHALL use `ProtocolType.HTTP` instead
   of string literals
4. WHEN creating the runtime, THE Runtime SHALL use the simplified constructor
   with named parameters instead of props objects
5. WHEN accessing runtime properties, THE Runtime SHALL use the L2 construct's
   property accessors directly

### Requirement 5: Maintain IAM Permissions and Security

**User Story:** As a platform operator, I want the same security posture and IAM
permissions to be maintained during the migration, so that the virtual assistant
continues to operate securely.

#### Acceptance Criteria

1. WHEN the execution role is created, THE Runtime SHALL either use the L2
   construct's automatic role creation or accept a custom role with the same
   permissions
2. WHEN cross-account roles are configured, THE Runtime SHALL preserve the
   ability to assume cross-account roles for Bedrock access via
   `add_to_role_policy()`
3. WHEN AgentCore permissions are set, THE Runtime SHALL maintain access to
   AgentCore workload identity and service operations
4. WHEN container access is granted, THE Runtime SHALL ensure the execution role
   can pull the Docker image from ECR
5. WHEN runtime invocation is needed, THE Runtime SHALL provide `grant_invoke()`
   method for IAM permissions

### Requirement 6: Use Default Runtime Endpoint

**User Story:** As a platform developer, I want to use the automatically created
DEFAULT endpoint for runtime invocation, so that I avoid unnecessary complexity
while maintaining stable runtime access.

#### Acceptance Criteria

1. WHEN the Runtime is created, THE system SHALL rely on the automatically
   created "DEFAULT" endpoint that points to the latest runtime version
2. WHEN runtime invocation is needed, THE system SHALL use the default endpoint
   without creating additional RuntimeEndpoint constructs
3. WHEN the runtime ARN is referenced, THE system SHALL use the runtime ARN
   directly for invocation permissions
4. WHEN the implementation is complete, THE system SHALL verify that the message
   processing Lambda can successfully invoke the runtime using the default
   endpoint
5. WHEN the migration is validated, THE system SHALL confirm that the virtual
   assistant functionality works identically to the previous implementation
