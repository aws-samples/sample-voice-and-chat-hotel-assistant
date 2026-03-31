# Requirements Document

## Introduction

This feature deploys the hotel-assistant-livekit package to AWS ECS with Fargate
on ARM64 architecture. The deployment will provide a scalable, containerized
LiveKit agent service that integrates with the existing Hotel PMS MCP server and
uses Amazon Nova Sonic for speech-to-speech interactions. The service will be
deployed in the existing VPC infrastructure with proper autoscaling, monitoring,
and secrets management.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the LiveKit agent deployed as
an ECS Fargate service, so that it can scale automatically and run reliably in a
containerized environment.

#### Acceptance Criteria

1. WHEN the infrastructure is deployed THEN it SHALL create an ECS cluster for
   the LiveKit agent
2. WHEN the service starts THEN it SHALL run on Fargate with ARM64 architecture
3. WHEN the service is deployed THEN it SHALL have a minimum task count of 1 and
   maximum of 5
4. WHEN the service scales THEN it SHALL use Application Auto Scaling to manage
   task count
5. WHEN tasks fail THEN ECS SHALL automatically replace them with healthy
   instances

### Requirement 2

**User Story:** As a system administrator, I want the ECS service to run in
private subnets with NAT Gateway access, so that the service is secure while
maintaining internet connectivity for external API calls.

#### Acceptance Criteria

1. WHEN the service is deployed THEN it SHALL run in private subnets of the
   existing VPC
2. WHEN the VPC is configured THEN it SHALL include a NAT Gateway for outbound
   internet access
3. WHEN the service needs internet access THEN it SHALL route through the NAT
   Gateway
4. WHEN inbound connectivity is evaluated THEN the ECS service SHALL have no
   public inbound access

### Requirement 3

**User Story:** As a LiveKit agent, I want to access Hotel PMS MCP configuration
from AWS Secrets Manager, so that I can connect to the MCP server securely
without hardcoded credentials.

#### Acceptance Criteria

1. WHEN the ECS task is configured THEN it SHALL have an environment variable
   with the MCP secret ARN or name
2. WHEN the ECS task execution role is created THEN it SHALL have GetSecretValue
   permissions for the MCP secret
3. WHEN the secret is not available THEN the agent SHALL fail to start and log
   an error
4. WHEN the secret is updated THEN the agent SHALL use the new configuration on
   restart

### Requirement 4

**User Story:** As a LiveKit agent, I want to access LiveKit server credentials
from AWS Secrets Manager, so that I can connect to the LiveKit server securely.

#### Acceptance Criteria

1. WHEN the ECS task starts THEN it SHALL retrieve LiveKit URL, API Key, and
   Secret from AWS Secrets Manager
2. WHEN the LiveKit secret name is provided THEN it SHALL use the CDK context
   variable or default to "hotel-assistant-livekit"
3. WHEN LiveKit credentials are missing THEN the agent SHALL fail to start and
   log appropriate error messages
4. WHEN the secret is rotated THEN the agent SHALL use new credentials on
   restart
5. WHEN accessing LiveKit secrets THEN the ECS task role SHALL have
   GetSecretValue permissions

### Requirement 5

**User Story:** As a system administrator, I want the ECS service to autoscale
based on active calls per task, so that the system can handle varying load
efficiently.

#### Acceptance Criteria

1. WHEN the service is configured THEN it SHALL target 20 active calls per task
   for autoscaling
2. WHEN active calls exceed the target THEN Application Auto Scaling SHALL add
   more tasks
3. WHEN active calls decrease THEN Application Auto Scaling SHALL remove excess
   tasks with a 10-minute cooldown period
4. WHEN scaling decisions are made THEN they SHALL be based on the custom
   CloudWatch metric
5. WHEN the maximum task count is reached THEN no additional tasks SHALL be
   created

### Requirement 6

**User Story:** As a system administrator, I want a custom CloudWatch metric for
active calls per task, so that I can monitor agent performance and enable proper
autoscaling.

#### Acceptance Criteria

1. WHEN the LiveKit agent handles calls THEN it SHALL publish active call count
   metrics to CloudWatch every minute
2. WHEN metrics are published THEN they SHALL include task-level and
   service-level dimensions
3. WHEN monitoring the service THEN the metric SHALL be named
   "ActiveCallsPerTask" or similar
4. WHEN autoscaling evaluates THEN it SHALL use CloudWatch Sum aggregation for
   total calls and Average aggregation for calls per task

### Requirement 7

**User Story:** As a developer, I want the LiveKit agent container to be built
and deployed automatically, so that code changes are reflected in the deployed
service.

#### Acceptance Criteria

1. WHEN the CDK stack is deployed THEN it SHALL build a Docker image from the
   hotel-assistant-livekit package
2. WHEN the Docker image is built THEN it SHALL target ARM64 architecture for
   Fargate compatibility
3. WHEN the image is created THEN it SHALL be pushed to an ECR repository
4. WHEN the ECS service is updated THEN it SHALL use the latest Docker image
5. WHEN the container starts THEN it SHALL run the LiveKit agent with proper
   configuration

### Requirement 8

**User Story:** As a system administrator, I want the ECS service integrated
with the existing CDK infrastructure, so that it reuses existing VPC, security
groups, and IAM patterns.

#### Acceptance Criteria

1. WHEN the service is deployed THEN it SHALL use the existing VPC from the
   backend stack
2. WHEN networking is configured THEN it SHALL reuse existing private subnets
3. WHEN IAM roles are created THEN they SHALL follow existing naming and
   permission patterns
4. WHEN security groups are configured THEN they SHALL integrate with existing
   security group rules
5. WHEN the stack is deployed THEN it SHALL be part of the existing CDK
   application structure

### Requirement 9

**User Story:** As a LiveKit agent, I want proper environment variable
configuration, so that I can connect to AWS services and external APIs
correctly.

#### Acceptance Criteria

1. WHEN Bedrock is accessed THEN the agent SHALL use the configured model ID
   (Amazon Nova Sonic)
2. WHEN logging is configured THEN it SHALL use structured logging with
   appropriate log levels
3. WHEN the agent connects to services THEN it SHALL use environment-specific
   configuration
4. WHEN debugging is needed THEN log levels SHALL be configurable via
   environment variables

### Requirement 10

**User Story:** As a system administrator, I want comprehensive monitoring and
logging, so that I can troubleshoot issues and monitor service health.

#### Acceptance Criteria

1. WHEN the service runs THEN it SHALL send logs to CloudWatch Logs
2. WHEN errors occur THEN they SHALL be logged with appropriate severity levels
3. WHEN the service health is checked THEN it SHALL expose health check
   endpoints
4. WHEN monitoring is configured THEN it SHALL include ECS service metrics and
   custom application metrics
5. WHEN alerts are needed THEN CloudWatch alarms SHALL be configured for
   critical metrics

### Requirement 11

**User Story:** As a system administrator, I want the ECS service to handle
graceful shutdowns, so that active calls are not interrupted during deployments
or scaling events.

#### Acceptance Criteria

1. WHEN a task is being stopped THEN it SHALL receive a SIGTERM signal for
   graceful shutdown
2. WHEN graceful shutdown starts THEN the agent SHALL stop accepting new calls
3. WHEN active calls are in progress THEN the task SHALL wait for them to
   complete before terminating
4. WHEN the grace period expires THEN the task SHALL be forcefully terminated
5. WHEN deployments occur THEN they SHALL use rolling updates to maintain
   service availability
