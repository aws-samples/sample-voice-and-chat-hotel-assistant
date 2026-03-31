# Requirements Document

## Introduction

This specification addresses critical architectural issues identified after the
initial deployment of the Hotel Knowledge Base system. The current
implementation incorrectly mixes Hotel PMS database concerns with Bedrock
Knowledge Base vector store requirements, leading to improper database
separation and credential management issues.

Note: "Aurora" refers to Aurora Serverless V2 PostgreSQL clusters with
instances. "Database" refers to PostgreSQL logical databases within the Aurora
cluster, following PostgreSQL's definition where multiple databases can exist
within a single cluster.

The main problems are:

1. Bedrock-specific resources are incorrectly placed in the Aurora construct
   meant for Hotel PMS
2. The same database custom resource handles both Hotel PMS and Bedrock setup,
   causing credential conflicts
3. The generative AI CDK constructs (L3) try to manage their own database setup,
   conflicting with our custom database architecture and causing authentication
   failures
4. Database separation is not properly implemented (Hotel PMS vs Bedrock KB
   PostgreSQL databases within the Aurora cluster)

## Requirements

### Requirement 1: Separate Database Architecture

**User Story:** As a system architect, I want separate PostgreSQL database
configurations for Hotel PMS and Bedrock Knowledge Base, so that each system has
proper isolation and credential management.

#### Acceptance Criteria

1. WHEN the Aurora construct is used THEN it SHALL only contain Hotel PMS
   PostgreSQL database resources and credentials
2. WHEN the Bedrock Knowledge Base construct is created THEN it SHALL manage its
   own Aurora PostgreSQL database resources separately
3. WHEN PostgreSQL database credentials are created THEN Hotel PMS and Bedrock
   SHALL use different PostgreSQL database names and user credentials
4. WHEN the system is deployed THEN the Hotel PMS SHALL use "hotel_pms"
   PostgreSQL database name
5. WHEN the system is deployed THEN the Bedrock Knowledge Base SHALL use
   "bedrock_vector_db" PostgreSQL database name

### Requirement 2: Proper Custom Resource Separation

**User Story:** As a DevOps engineer, I want separate custom resources for Hotel
PMS and Bedrock PostgreSQL database setup, so that each system can be managed
independently without conflicts.

#### Acceptance Criteria

1. WHEN the Hotel PMS custom resource runs THEN it SHALL only set up Hotel PMS
   schema and data
2. WHEN the Bedrock custom resource runs THEN it SHALL only set up Bedrock
   vector store schema and user
3. WHEN either custom resource fails THEN it SHALL not affect the other system's
   PostgreSQL database setup
4. WHEN PostgreSQL database credentials are managed THEN each custom resource
   SHALL use its own dedicated credentials
5. WHEN the Bedrock custom resource runs THEN it SHALL create the
   "bedrock_service" user with proper vector store permissions

### Requirement 3: Direct L1 Construct Usage

**User Story:** As a developer, I want the Bedrock Knowledge Base to use L1
constructs directly instead of L3 constructs, so that we have full control over
the configuration without conflicts from generative AI CDK constructs that try
to manage their own database setup.

#### Acceptance Criteria

1. WHEN the Knowledge Base is created THEN it SHALL use
   `aws_bedrock.CfnKnowledgeBase` L1 construct
2. WHEN the data source is created THEN it SHALL use `aws_bedrock.CfnDataSource`
   L1 construct
3. WHEN the Knowledge Base configuration is applied THEN it SHALL reference the
   correct PostgreSQL database name "bedrock_vector_db"
4. WHEN the Knowledge Base is configured THEN it SHALL use the correct schema
   name "bedrock_integration"
5. WHEN the Knowledge Base is configured THEN it SHALL use the correct table
   name "bedrock_kb"
6. WHEN the Knowledge Base is configured THEN it SHALL use the Bedrock service
   credentials, not the Hotel PMS credentials
7. WHEN the custom metadata field is configured THEN it SHALL be set to
   "custom_metadata" for filtering without requiring escape hatches

### Requirement 4: Proper Credential Management

**User Story:** As a security engineer, I want proper credential separation and
rotation for Hotel PMS and Bedrock systems, so that each system has secure and
independent access controls.

#### Acceptance Criteria

1. WHEN Bedrock credentials are created THEN they SHALL use `rds.DatabaseSecret`
   with proper attachment and multi-user rotation
2. WHEN the Bedrock service role is created THEN it SHALL have access only to
   Bedrock-specific secrets and Aurora cluster resources
3. WHEN credentials are rotated THEN Hotel PMS and Bedrock rotations SHALL be
   independent
4. WHEN the system is deployed THEN the Bedrock credentials SHALL specify
   "bedrock_vector_db" as the PostgreSQL database name
5. WHEN the system is deployed THEN the Hotel PMS credentials SHALL specify
   "hotel_pms" as the PostgreSQL database name

### Requirement 5: Clean Resource Organization

**User Story:** As a maintainer, I want Bedrock-specific resources moved to the
appropriate construct, so that the codebase follows proper separation of
concerns.

#### Acceptance Criteria

1. WHEN the Aurora construct is reviewed THEN it SHALL contain only Hotel PMS
   PostgreSQL database resources
2. WHEN the Bedrock Knowledge Base construct is reviewed THEN it SHALL contain
   all Bedrock-specific PostgreSQL database resources
3. WHEN Bedrock credentials are needed THEN they SHALL be created within the
   Bedrock Knowledge Base construct
4. WHEN Bedrock IAM roles are needed THEN they SHALL be created within the
   Bedrock Knowledge Base construct
5. WHEN security groups for Bedrock are needed THEN they SHALL be managed within
   the Bedrock Knowledge Base construct

### Requirement 6: Proper Vector Store Integration

**User Story:** As a Knowledge Base administrator, I want the vector store to be
properly configured with its own PostgreSQL database and credentials, so that
Bedrock Knowledge Base operations work correctly.

#### Acceptance Criteria

1. WHEN the vector store is created THEN it SHALL connect to the
   "bedrock_vector_db" PostgreSQL database
2. WHEN the vector store is configured THEN it SHALL use the Bedrock service
   credentials
3. WHEN the Knowledge Base is deployed THEN it SHALL be able to create and query
   vector embeddings
4. WHEN the custom resource runs THEN it SHALL create the pgvector extension in
   the Bedrock PostgreSQL database
5. WHEN the custom resource runs THEN it SHALL create the proper vector table
   schema with indexes
