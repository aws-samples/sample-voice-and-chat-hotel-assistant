# Implementation Plan

Convert the AgentCore Runtime migration from custom wrapper to native L2
constructs into a series of focused implementation steps. Each task builds
incrementally toward a working L2 construct implementation while maintaining the
same virtual assistant functionality.

## Tasks

- [ ] 1. Migrate Backend Stack to L2 Runtime Construct
- [x] 1.1 Update imports and Runtime instantiation
  - Replace custom AgentCoreRuntime import with
    aws_cdk.aws_bedrock_agentcore_alpha imports
  - Update Runtime instantiation to use L2 construct with
    AgentRuntimeArtifact.from_docker_image_asset()
  - Configure networking with RuntimeNetworkConfiguration.using_public_network()
  - Set protocol to ProtocolType.HTTP for AgentCore SDK compatibility
  - Pass environment variables directly to Runtime constructor
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.5, 4.1, 4.2, 4.3,
    4.4_

- [x] 1.2 Configure IAM permissions and role
  - Use L2 construct's automatic role creation or configure custom execution
    role
  - Add cross-account Bedrock role assumption using add_to_role_policy() method
  - Grant AgentCore Memory access using the L2 construct's role property
  - Ensure message processing Lambda can invoke runtime using grant_invoke()
    method
  - _Requirements: 2.4, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 1.3 Update property references and outputs
  - Update all references to use L2 construct properties (agent_runtime_arn,
    agent_runtime_id, agent_runtime_name)
  - Update CloudFormation outputs to use L2 construct property accessors
  - Ensure message processing construct can access runtime ARN correctly
  - _Requirements: 1.5, 4.5_

- [x] 2. Remove Custom Wrapper Implementation
  - Delete agentcore_runtime.py file from stack_constructs directory
  - Update **init**.py to remove AgentCoreRuntime export
  - Remove any unused imports or helper methods specific to custom wrapper
  - Verify no remaining references to custom AgentCoreRuntime in codebase
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Deploy and Validate Migration
  - Deploy updated stack with L2 constructs (destroy and redeploy approach)
  - Verify runtime can be successfully invoked by message processing Lambda
  - Test virtual assistant functionality end-to-end to ensure identical behavior
  - Monitor CloudWatch logs for any issues or errors
  - Confirm all environment variables are passed correctly to runtime
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
