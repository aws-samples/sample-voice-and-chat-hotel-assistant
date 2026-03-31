# Requirements Document

## Introduction

The current CDK infrastructure code in `packages/infra/` contains several
functions that should be refactored into proper CDK constructs to improve
reusability, testability, and maintainability. The most egregious example is the
message processing infrastructure in `backend_stack.py` which creates multiple
related AWS resources (SQS queues, Lambda functions, IAM permissions) within
private methods rather than encapsulated constructs.

This refactoring will align the codebase with CDK best practices and AWS
Well-Architected principles by creating reusable, composable infrastructure
components.

## Requirements

### Requirement 1

**User Story:** As a CDK developer, I want message processing infrastructure to
be encapsulated in a reusable construct, so that I can easily deploy consistent
message processing patterns across different stacks.

#### Acceptance Criteria

1. WHEN I need to create message processing infrastructure THEN I SHALL use a
   `MessageProcessingConstruct` that encapsulates SQS queue, DLQ, and Lambda
   function creation
2. WHEN I instantiate the `MessageProcessingConstruct` THEN it SHALL accept
   AgentCore runtime ARN and environment variables as configuration parameters
3. WHEN the construct is created THEN it SHALL automatically configure proper
   IAM permissions between the Lambda function and SQS queues
4. WHEN the construct is created THEN it SHALL include CDK Nag suppressions with
   proper justifications
5. WHEN I need to grant external services permission to publish messages THEN I
   SHALL access the construct's queue property and use its existing grant
   methods

### Requirement 2

**User Story:** As a CDK developer, I want the entire messaging backend to be
encapsulated in a construct, so that I can conditionally deploy messaging
infrastructure based on whether EUM Social is available.

#### Acceptance Criteria

1. WHEN EUM Social is not available THEN I SHALL deploy a
   `MessagingBackendConstruct` that provides simulated messaging capabilities
2. WHEN the messaging backend construct is created THEN it SHALL include
   DynamoDB table, SNS topic, Lambda function, API Gateway, Cognito, and WAF
3. WHEN the messaging backend construct is created THEN it SHALL expose
   necessary outputs (topic, client secret, API endpoint) for integration with
   other stacks
4. WHEN EUM Social is available THEN the messaging backend construct SHALL NOT
   be deployed
5. WHEN the backend stack needs messaging integration THEN it SHALL use either
   EUM Social configuration or messaging backend construct outputs

### Requirement 3

**User Story:** As a CDK developer, I want WhatsApp permissions to follow CDK
grant patterns, so that I can consistently manage permissions across different
constructs.

#### Acceptance Criteria

1. WHEN I need to grant WhatsApp permissions THEN I SHALL use a
   `grant_whatsapp_permissions()` method that accepts an `IGrantable`
2. WHEN the method is called THEN it SHALL grant SSM parameter access for allow
   lists
3. WHEN the method is called THEN it SHALL grant EUM Social API permissions
4. WHEN cross-account role is specified THEN it SHALL grant STS assume role
   permissions
5. WHEN the method is used THEN it SHALL follow the same pattern as other CDK
   grant methods

### Requirement 4

**User Story:** As a CDK developer, I want to distinguish between constructs and
utility functions, so that I can organize code appropriately and maintain clear
separation of concerns.

#### Acceptance Criteria

1. WHEN creating multiple related AWS resources THEN I SHALL use a construct
2. WHEN implementing reusable infrastructure patterns THEN I SHALL use a
   construct
3. WHEN creating simple utility functions THEN I SHALL use private methods
4. WHEN granting permissions to existing resources THEN I SHALL use utility
   functions or grant methods
5. WHEN the logic has no resource creation THEN I SHALL use utility functions

### Requirement 5

**User Story:** As a CDK developer, I want existing stack code to be refactored
to use the new constructs, so that the codebase follows consistent patterns and
is easier to maintain.

#### Acceptance Criteria

1. WHEN `backend_stack.py` is refactored THEN it SHALL use
   `MessageProcessingConstruct` instead of
   `_create_message_processing_infrastructure()`
2. WHEN `backend_stack.py` is refactored THEN it SHALL use
   `MessageProcessingConstruct` for message processing and conditionally
   integrate with either EUM Social or `MessagingBackendConstruct`
3. WHEN `messaging_stack.py` is refactored THEN it SHALL become a
   `MessagingBackendConstruct` that can be used by other stacks
4. WHEN refactoring is complete THEN all stack files SHALL have reduced
   complexity and improved readability
