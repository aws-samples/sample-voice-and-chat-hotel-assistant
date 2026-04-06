# Implementation Plan

- [x] 1. Create AgentCore Identity Provider wrapper construct
  - Implement `AgentCoreIdentityProviderConstruct` with AwsCustomResource
  - Use CDK `Names.unique_resource_name()` for globally unique provider names
  - Configure OIDC with Cognito discovery URL, client ID, and client secret
  - Add IAM policy for bedrock-agent-identity API permissions
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 2. Create AgentCore Gateway construct
  - Implement `AgentCoreGatewayConstruct` with CfnGateway and CfnGatewayTarget
  - Use identity provider wrapper construct for provider ARN
  - Generate unique gateway name using CDK Names utility
  - Create CfnGateway resource (no provider ARN needed)
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 3. Configure CfnGatewayTarget with OpenAPI spec
  - Read OpenAPI specification from file
  - Generate unique target name using CDK Names utility
  - Create CfnGatewayTarget with provider ARN for authentication
  - Configure API URL and embedded OpenAPI schema
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Integrate with Hotel PMS Stack
  - Add AgentCore Gateway construct to HotelPmsStack
  - Pass API Gateway and Cognito constructs as inputs
  - Add stack outputs for gateway ARN, target ARN, and provider ARN
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 5. Validate with CDK synthesis
  - Run `pnpm exec nx run infra:synth` to generate CloudFormation template
  - Verify AwsCustomResource for identity provider creation
  - Verify CfnGateway and CfnGatewayTarget resources
  - Verify IAM policies and unique resource names
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 6. Deploy and validate integration
  - Run `pnpm exec nx deploy infra` to deploy Hotel PMS Stack
  - Verify stack outputs (gateway ARN, target ARN, provider ARN)
  - Test identity provider with
    `aws bedrock-agent-identity get-identity-provider`
  - Test gateway target with `aws bedrock-agent-core get-gateway-target`
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 7. Security and compliance validation
  - Verify least-privilege IAM roles for AwsCustomResource
  - Confirm client secrets are not logged or exposed
  - Validate proper error handling without internal details
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
