# Implementation Plan

- [x] 1. Create Lambda package structure and core dependencies
  - Set up new uv package in `packages/hotel-pms-lambda` following the uv
    template
  - Configure pyproject.toml with asyncpg, boto3, and AWS Lambda Powertools
    dependencies
  - Create basic package structure with handlers, models, and database modules
  - _Requirements: 7.1, 7.2_

- [x] 2. Implement database models and connection management
  - Create database connection manager using asyncpg with connection pooling
  - Implement data models for hotels, room_types, rooms, reservations,
    rate_modifiers, and housekeeping_requests
  - Add Secrets Manager integration for database credentials
  - Create database initialization utilities for schema creation
  - _Requirements: 4.1, 4.2, 7.3_

- [x] 3. Create database schema setup CloudFormation custom resource
  - Implement CloudFormation custom resource Lambda handler for database
    initialization
  - Create database setup functions that handle CREATE/UPDATE/DELETE
    CloudFormation events
  - Add seed data loading from bundled CSV files with proper transaction
    management
  - Implement proper error handling, rollback mechanisms, and CloudFormation
    response handling
  - Create separate handler for custom resource that integrates with CDK
    deployment lifecycle
  - _Requirements: 4.1, 4.3, 4.4_

- [x] 4. Implement availability and pricing business logic
  - Create availability service that queries room availability for date ranges
  - Implement pricing calculation with rate modifiers and package types
  - Add quote generation functionality with detailed pricing breakdown
  - Write unit tests for availability calculations and edge cases
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 5. Implement reservation management functionality
  - Create reservation service for creating new bookings with room assignment
  - Implement reservation retrieval and update operations
  - Add validation for guest capacity and room availability conflicts
  - Create payment status management and reservation confirmation logic
  - Write unit tests for reservation creation, updates, and validation logic
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 6. Implement guest services functionality
  - Create checkout service that updates reservation status and calculates final
    charges
  - Implement housekeeping request creation with automatic priority assignment
  - Add guest service request tracking and status management
  - Write unit tests for checkout and housekeeping workflows
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 7. Create main Lambda handler with routing
  - Implement main Lambda handler that routes requests to appropriate services
  - Add request parsing and validation using AWS Lambda Powertools
  - Implement structured logging and error handling across all endpoints
  - Create response formatting utilities for consistent API responses
  - _Requirements: 5.1, 5.2, 6.1, 6.2, 6.3_

- [x] 8. Generate OpenAPI specification for MCP integration
  - Create comprehensive OpenAPI 3.0 specification with detailed endpoint
    descriptions
  - Add AI-friendly parameter descriptions and response schemas for MCP tools
  - Include error response documentation and validation schemas
  - Generate specification file that can be used with Bedrock AgentCore Gateway
  - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [x] 9. Create CDK infrastructure stack for Aurora Serverless v2
  - Implement VPC construct with private subnets and NAT Gateway
  - Create Aurora Serverless v2 PostgreSQL cluster with proper security
    configuration
  - Add Secrets Manager for database credentials with automatic rotation
  - Configure security groups for database access from Lambda functions
  - _Requirements: 7.1, 7.3, 7.4, 8.1_

- [x] 10. Create CDK constructs for API Gateway with WAF
  - Implement API Gateway regional REST API with IAM authentication
  - Create AWS WAF v2 with managed rule sets and rate limiting
  - Configure API Gateway integration with Lambda function
  - Add CORS configuration and request validation
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [x] 11. Create Lambda deployment construct in CDK
  - Implement Lambda function construct with proper IAM permissions for main PMS
    API
  - Configure environment variables for database connection and logging
  - Add VPC configuration for Lambda to access Aurora in private subnets
  - Create separate Lambda function for database setup custom resource with
    CloudFormation permissions
  - Implement CloudFormation custom resource that triggers database
    initialization during stack deployment
  - _Requirements: 7.1, 7.2, 7.5, 8.2_

- [x] 12. Implement comprehensive error handling and logging
  - Add structured error responses with consistent format across all endpoints
  - Implement AWS Lambda Powertools for logging, tracing, and metrics
  - Create custom exception classes for different error scenarios
  - Add CloudWatch metrics for business KPIs and operational monitoring
  - _Requirements: 6.3, 8.3, 8.4_

- [x] 13. Add unit and integration tests
  - Create unit tests for all business logic functions with mocked database
  - Implement integration tests that test against real PostgreSQL database using
    synthetic data from packages/hotel-pms-lambda/hotel_pms_lambda/data/
  - Add test fixtures and factories for generating test data based on existing
    CSV files
  - Create pytest configuration with async test support and coverage reporting
  - _Requirements: 4.4, 8.5_

- [x] 14. Create NX project configuration and packaging scripts
  - Add project.json configuration for the new Lambda package
  - Create build, test, and package targets in NX configuration
  - Create Lambda packaging script that builds wheel and creates zip with
    platform targeting for aarch64-unknown-linux-gnu
  - Configure Python formatting and linting with ruff
  - Add infra package dependency on hotel-pms-lambda package target
  - _Requirements: 7.1, 7.2_

- [x] 15. Wire together CDK stack and deploy infrastructure
  - Create main CDK stack that combines VPC, Aurora, API Gateway, WAF, and
    Lambda
  - Add stack outputs for API Gateway URL and other important endpoints
  - Configure CDK deployment scripts and environment-specific parameters
  - Test end-to-end deployment and verify all components are working together
  - _Requirements: 7.4, 7.5, 8.1, 8.2_

- [x] 16. Create integration tests for deployed infrastructure
  - Set up integration tests that run against deployed AWS resources
  - Create test data management for integration test scenarios using deployed
    database
  - Test complete API workflows end-to-end with real Aurora database and API
    Gateway
  - Validate IAM authentication and API Gateway integration with actual AWS
    credentials
  - Use deployed infrastructure endpoints and connection strings from
    CloudFormation outputs
  - _Requirements: 5.1-5.5, 7.1-7.5, 8.1-8.5_

- [x] 17. Run comprehensive testing and validation
  - Execute integration tests against deployed API endpoints
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 6.1, 6.2, 6.4, 6.5_

- [x] 18. Fix async/sync mismatch in service layer tests
  - Update availability service tests to use synchronous mocks instead of
    AsyncMock
  - Remove @pytest.mark.asyncio decorators and await keywords from service tests
  - Fix reservation service tests by replacing AsyncMock with Mock for
    repository methods
  - Update guest service tests to match synchronous service architecture
  - Ensure all service layer tests properly mock synchronous repository methods
  - _Requirements: 8.5_

- [x] 19. Fix async/sync mismatch in handler and integration tests
  - Update Lambda handler tests to remove async/await since handlers are
    synchronous
  - Fix database setup tests by removing @pytest.mark.asyncio decorators
  - Update custom resource tests to use synchronous mocks
  - Fix error handling tests to match synchronous exception handling patterns
  - Ensure all handler tests properly test synchronous Lambda functions
  - _Requirements: 8.5_

- [x] 20. Fix remaining test infrastructure issues
  - Update test fixtures and factories to work with synchronous architecture
  - Fix any remaining AsyncMock usage throughout the test suite
  - Ensure test database connection mocking works with pg8000 instead of asyncpg
  - Update integration test setup to work with synchronous database operations
  - Validate that all tests pass and provide proper coverage
  - _Requirements: 8.5_
