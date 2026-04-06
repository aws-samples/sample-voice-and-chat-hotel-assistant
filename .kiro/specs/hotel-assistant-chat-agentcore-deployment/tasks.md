# Implementation Plan

Convert the feature design into a series of prompts for a code-generation LLM
that will implement each step in a test-driven manner. Prioritize best
practices, incremental progress, and early testing, ensuring no big jumps in
complexity at any stage. Make sure that each prompt builds on the previous
prompts, and ends with wiring things together. There should be no hanging or
orphaned code that isn't integrated into a previous step. Focus ONLY on tasks
that involve writing, modifying, or testing code.

- [x] 1. Create ECR Repository and Docker Image Asset
  - Create DockerImageAssetConstruct for hotel-assistant-chat package
  - Configure ARM64 platform and proper build context
  - Add lifecycle policies for image management
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 1.1, 6.1, 6.2, 6.3_

- [x] 2. Implement AgentCore Memory Resource
  - Create AgentCore Memory construct with simple short-term configuration
  - Set 7-day expiry duration without memory strategies
  - Configure proper IAM permissions for memory access
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Create AgentCore Runtime with JWT Authentication
- [x] 3.1 Implement JWT authorizer configuration
  - Reference existing Cognito user pool from HotelAssistantStack
  - Configure discovery URL and allowed clients
  - Set up HTTP server protocol for AgentCore SDK
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 3.2 Create AgentCore Runtime construct
  - Configure runtime with container image and authentication
  - Set up proper IAM role with Bedrock and memory permissions
  - Add workload identity access for JWT validation
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 1.2, 1.3, 1.4, 3.4_

- [x] 4. Configure Environment Variables and Secrets Access
  - Set up runtime environment variables for AWS region and Bedrock model
  - Configure AGENTCORE_MEMORY_ID environment variable
  - Add HOTEL_PMS_MCP_SECRET_ARN for application-level MCP integration
  - Grant read access to MCP configuration secret from Hotel PMS stack
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 5. Integrate Components into Backend Stack
  - Add AgentCore components to existing BackendStack
  - Import MCP configuration secret ARN from Hotel PMS stack
  - Reference existing Cognito user pool without creating new VPC resources
  - Ensure proper resource dependencies and ordering
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 6. Migrate to TypeScript AgentCore Constructs
  - Replace Python AgentCore Memory construct with TypeScript `AgentCoreMemory`
    from `hotel-assistant-constructs`
  - Replace Python AgentCore Runtime construct with TypeScript
    `AgentCoreRuntime` from `hotel-assistant-constructs`
  - Remove duplicate Python construct files: `agentcore_memory_construct.py`,
    `agentcore_runtime_construct.py`, `agentcore_gateway_construct.py`
  - Update backend stack imports to use TypeScript constructs via
    `hotel-assistant-constructs` package
  - Ensure all construct properties and outputs remain compatible
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 1.2, 2.1, 3.1, 3.4, 5.1_

- [ ] 7. Add Stack Outputs and CDK Nag Suppressions
  - Export AgentCore Runtime ARN as stack outputs
  - Document all exported values for integration
  - Test with `pnpm exec nx run infra:synth HotelAssistantStack`
  - _Requirements: 1.5, 3.5, 5.4, 5.5_

- [ ] 8. Test Infrastructure Deployment
  - Run CDK synthesis using `pnpm exec nx run infra:synth HotelAssistantStack`
    from workspace root
  - Verify proper resource dependencies and configurations
  - Test that all environment variables are correctly set
  - Validate IAM permissions and cross-stack references
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
