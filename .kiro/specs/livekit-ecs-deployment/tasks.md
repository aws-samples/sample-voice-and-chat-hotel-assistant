# Implementation Plan

- [x] 1. Create LiveKit ECS construct foundation
  - Create the main LiveKitECSConstruct class with proper interface
  - Set up construct parameters for VPC, MCP secret, and LiveKit secret name
  - Implement basic construct structure with proper CDK patterns
  - _Requirements: 1.1, 8.1, 8.5_

- [x] 2. Create Dockerfile for LiveKit agent
  - Create Dockerfile in hotel-assistant-livekit package following uv best
    practices
  - Use ghcr.io/astral-sh/uv:python3.13-bookworm-slim base image
  - Configure uv environment variables for bytecode compilation and link mode
  - Implement multi-layer build with dependency caching optimization
  - Set up proper virtual environment activation and CMD configuration
  - Validate Docker image builds successfully for ARM64
  - _Requirements: 7.1, 7.2_

- [x] 3. Implement Docker image asset for LiveKit agent
  - Create DockerImageAsset for hotel-assistant-livekit package
  - Configure ARM64 platform targeting for Fargate compatibility
  - Set up ECR repository integration with proper naming
  - Implement asset hash-based versioning for cache efficiency
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 4. Create ECS cluster and task definition
  - Implement ECS cluster creation for LiveKit agents
  - Configure Fargate task definition with ARM64 architecture
  - Set CPU (2048) and memory (4096 MB) resource allocation
  - Configure awsvpc network mode for private subnet deployment
  - _Requirements: 1.1, 1.2, 2.1_

- [x] 5. Configure environment variables and secrets access
  - Set up environment variables for Bedrock model ID and logging configuration
  - Configure MCP secret ARN environment variable for application access
  - Set up LiveKit secret name environment variable (not secret contents)
  - Implement proper environment variable structure for the agent
  - _Requirements: 3.1, 4.2, 9.1, 9.2, 9.3_

- [x] 6. Implement IAM roles and permissions
  - Create ECS task execution role with ECR and Secrets Manager permissions
  - Configure task execution role for LiveKit and MCP secrets access
  - Create ECS task role with Bedrock and CloudWatch permissions
  - Implement least-privilege IAM policies following existing patterns
  - _Requirements: 3.2, 4.5, 8.3_

- [x] 7. Set up ECS Fargate service configuration
  - Create Fargate service with proper deployment configuration
  - Configure service to run in existing VPC private subnets
  - Set up security groups for outbound HTTPS and HTTP access
  - Implement rolling deployment with circuit breaker for reliability
  - _Requirements: 1.3, 2.1, 2.2, 2.3, 8.2_

- [x] 8. Implement Application Auto Scaling configuration
  - Create Application Auto Scaling target for ECS service
  - Configure min capacity (1) and max capacity (5) for task scaling
  - Set up scalable dimension for ECS service desired count
  - Implement scaling target with proper resource identification
  - _Requirements: 1.4, 5.5_

- [x] 9. Configure CloudWatch metrics and scaling policy
  - Set up custom CloudWatch metric for ActiveCalls monitoring
  - Configure metric dimensions for service name and task identification
  - Create target tracking scaling policy with 20 calls per task target
  - Implement scale-out (2 min) and scale-in (10 min) cooldown periods
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4_

- [x] 10. Implement container health checks and monitoring
  - Configure container health check in task definition (not ECS service health
    check)
  - Set up health check command to validate agent process is running
  - Implement CloudWatch log group for ECS service logging
  - Configure log retention and structured logging integration
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 11. Add graceful shutdown and deployment configuration
  - Configure ECS deployment settings for rolling updates
  - Set maximum percent (200%) and minimum healthy percent (100%)
  - Implement deployment circuit breaker with automatic rollback
  - Configure stop timeout for graceful shutdown handling
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 12. Integrate construct with existing CDK stack
  - Add LiveKitECSConstruct to the backend stack
  - Wire up existing VPC and MCP secret references
  - Configure CDK context variable for LiveKit secret name
  - Implement proper construct integration following existing patterns
  - _Requirements: 8.1, 8.2, 8.4, 8.5_

- [ ] 13. Create unit tests for CDK construct
  - Write tests for construct synthesis and resource creation
  - Test IAM policy generation and permissions configuration
  - Validate environment variable and secret configuration
  - Test auto scaling and CloudWatch metric configuration
  - _Requirements: All requirements validation through testing_

- [x] 14. Implement Secrets Manager integration in LiveKit agent
  - Create secrets manager client for reading LiveKit credentials
  - Implement function to retrieve and parse LiveKit secret (URL, API key, API
    secret)
  - Update agent initialization to configure LiveKit connection with retrieved
    credentials
  - Add error handling for missing or invalid LiveKit secrets
  - _Requirements: 4.1, 4.3, 4.4_

- [x] 15. Add LiveKit auto-connection and room management
  - Implement automatic room connection logic similar to the ECS example
  - Add proper connection error handling and retry logic
  - Configure agent to handle room lifecycle events properly
  - Implement graceful shutdown handling for active connections
  - _Requirements: 11.1, 11.2, 11.3_

- [x] 16. Implement ActiveCalls metric publishing
  - Add CloudWatch client for publishing custom metrics
  - Implement metric publishing logic to track active calls per task
  - Add task ID and service name dimensions to metrics
  - Configure metric publishing frequency (every 60 seconds)
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 17. Add integration testing and validation
  - Create CDK synthesis test using the specified command
  - Test ECS service configuration and deployment settings
  - Verify IAM roles and permissions are correctly configured
  - _Requirements: 7.4, 7.5, validation of all infrastructure requirements_
