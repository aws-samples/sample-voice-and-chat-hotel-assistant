# Requirements Document

## Introduction

This specification defines the integration between the Hotel PMS API Gateway and
AWS AgentCore Gateway service. AgentCore Gateway enables AI agents to securely
access REST APIs through a managed service that handles authentication,
authorization, and API discovery.

The integration requires custom CloudFormation resources to create identity
provider configurations and manage API credentials, as AgentCore Gateway
currently lacks native CDK L2 constructs for these operations.

**Architectural Context:**

- This integration is part of the **Hotel PMS Stack** (customer-replaceable
  reference implementation)
- Demonstrates how customers can expose their own APIs as agent tools via
  AgentCore Gateway
- The Virtual Assistant (spec #6) will be configured to work with any MCP
  servers, including this hotel PMS implementation or customer alternatives
- Customers can replace the entire Hotel PMS Stack with their own APIs/MCP
  servers while keeping the core Virtual Assistant infrastructure

## Glossary

- **AgentCore_Gateway**: AWS managed service for exposing REST APIs to AI agents
- **AgentCore_Identity**: AWS service for creating identity provider
  configurations
- **Identity_Provider**: Configuration that links Cognito authentication to
  AgentCore Gateway (created by AgentCore Identity service)
- **Provider_ARN**: Unique identifier for the identity provider used by
  CfnGateway and CfnGatewayTarget
- **AwsCustomResource**: CDK construct for calling AWS APIs without custom
  Lambda functions
- **CfnGateway**: L1 CloudFormation construct for AgentCore Gateway
- **CfnGatewayTarget**: L1 CloudFormation construct for AgentCore Gateway API
  targets
- **OpenAPI_Spec**: API specification file used by AgentCore Gateway for tool
  discovery

## Requirements

### Requirement 1: Identity Provider Configuration

**User Story:** As a system administrator, I want to configure AgentCore
Identity with the Hotel PMS Cognito identity provider, so that AgentCore Gateway
can authenticate API requests using OAuth2 client credentials flow.

#### Acceptance Criteria

1. THE System SHALL create an identity provider using AwsCustomResource to call
   AgentCore Identity APIs
2. THE Identity_Provider SHALL reference the Cognito User Pool discovery URL
3. THE Identity_Provider SHALL specify OAuth2 client credentials as the
   authentication type
4. THE Identity_Provider SHALL return a unique provider ARN for use with
   CfnGateway and CfnGatewayTarget
5. THE System SHALL handle identity provider creation, update, and deletion
   lifecycle events

### Requirement 2: AgentCore Gateway Configuration

**User Story:** As a system administrator, I want to configure AgentCore Gateway
with the Hotel PMS API, so that AI agents can discover and use hotel management
tools.

#### Acceptance Criteria

1. THE System SHALL create a CfnGateway resource with the provider ARN from
   AgentCore Identity
2. THE System SHALL create a CfnGatewayTarget resource linking the API Gateway
   endpoint
3. THE CfnGatewayTarget SHALL reference the OpenAPI specification for tool
   discovery
4. THE CfnGatewayTarget SHALL include Cognito client credentials for
   authentication
5. THE System SHALL expose the gateway ARN and target ARN as stack outputs

### Requirement 3: OpenAPI Specification Integration

**User Story:** As a developer, I want the Hotel PMS OpenAPI specification
properly integrated with AgentCore Gateway, so that AI agents can discover and
use all available hotel management tools.

#### Acceptance Criteria

1. THE System SHALL provide the OpenAPI specification to CfnGatewayTarget
2. THE OpenAPI_Spec SHALL include all hotel PMS operations with operationId
   fields
3. THE OpenAPI_Spec SHALL meet AgentCore Gateway requirements (no auth in spec,
   simple parameters)
4. THE System SHALL validate the OpenAPI spec format before deployment
5. THE System SHALL enable AI agents to discover all hotel PMS operations
   through the gateway

### Requirement 4: AwsCustomResource Implementation

**User Story:** As a DevOps engineer, I want reliable AWS API calls for
AgentCore Identity integration, so that infrastructure deployments are
repeatable and maintainable.

#### Acceptance Criteria

1. THE AwsCustomResource SHALL call AgentCore Identity APIs for provider
   creation
2. THE AwsCustomResource SHALL implement CREATE, UPDATE, and DELETE operations
3. THE AwsCustomResource SHALL handle errors gracefully with proper
   CloudFormation responses
4. THE AwsCustomResource SHALL use appropriate IAM permissions for AgentCore
   Identity API calls
5. THE AwsCustomResource SHALL include retry logic for transient failures

### Requirement 5: CDK Construct Integration

**User Story:** As a developer, I want a reusable CDK construct for AgentCore
Gateway integration, so that I can easily deploy the Hotel PMS API with gateway
configuration.

#### Acceptance Criteria

1. THE CDK_Construct SHALL encapsulate AwsCustomResource, CfnGateway, and
   CfnGatewayTarget
2. THE CDK_Construct SHALL accept the API Gateway construct and Cognito
   construct as inputs
3. THE CDK_Construct SHALL expose the gateway ARN and target ARN as outputs
4. THE CDK_Construct SHALL manage IAM permissions for AwsCustomResource API
   calls
5. THE CDK_Construct SHALL support stack updates without resource replacement

### Requirement 6: Deployment Validation

**User Story:** As a QA engineer, I want automated validation of the AgentCore
Gateway integration, so that I can verify the API is accessible to AI agents
after deployment.

#### Acceptance Criteria

1. THE System SHALL validate identity provider creation after deployment
2. THE System SHALL verify CfnGateway and CfnGatewayTarget resources are created
   successfully
3. THE System SHALL confirm OpenAPI spec is accessible through AgentCore Gateway
4. THE System SHALL test AI agent access to at least one hotel PMS operation
5. THE System SHALL provide clear error messages for integration failures

### Requirement 7: Security and Compliance

**User Story:** As a security engineer, I want the AgentCore Gateway integration
to follow AWS security best practices, so that the system maintains a strong
security posture.

#### Acceptance Criteria

1. THE System SHALL use least-privilege IAM roles for AwsCustomResource API
   calls
2. THE System SHALL store Cognito client secrets securely in CfnGatewayTarget
   configuration
3. THE System SHALL not log sensitive information (client secrets, tokens)
4. THE System SHALL use VPC endpoints for AgentCore Identity API calls WHERE
   available
5. THE System SHALL implement proper error handling without exposing internal
   details
