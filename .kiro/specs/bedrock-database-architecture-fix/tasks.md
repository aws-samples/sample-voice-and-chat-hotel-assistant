# Implementation Plan

## Task 1: Clean Aurora Construct

**Priority**: High  
**Dependencies**: None

#### Subtasks:

- [x] **1.1**: Remove Bedrock-specific resources from Aurora construct
  - Modify `packages/infra/stack/stack_constructs/aurora_construct.py`
  - Remove `bedrock_credentials` creation and attachment
  - Remove `bedrock_service_role` creation
  - Remove `bedrock_security_group` creation
  - Keep only Hotel PMS database resources and Lambda security group
  - Update properties to remove Bedrock-related exports

- [x] **1.2**: Update Aurora construct interface
  - Remove Bedrock-related property methods (`bedrock_secret_arn`,
    `bedrock_role_arn`, etc.)
  - Keep only Hotel PMS and cluster-level properties
  - Ensure RDS Data API remains enabled for Bedrock access
  - Update CDK Nag suppressions to remove Bedrock-related suppressions

**Acceptance Criteria**:

- Aurora construct contains only Hotel PMS database resources
- Bedrock-specific credentials, roles, and security groups are removed
- RDS Data API remains enabled for Bedrock Knowledge Base access
- CDK synth validates without errors: `uv run cdk synth HotelPmsApiStack`

---

## Task 2: Create Bedrock Database Custom Resource

**Priority**: High  
**Dependencies**: Task 1

#### Subtasks:

- [x] **2.1**: Create Bedrock database setup handler
  - Create
    `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/bedrock_db_custom_resource.py`
  - Implement CloudFormation custom resource handler using Lambda Powertools
  - Handle CREATE/UPDATE/DELETE events for Bedrock database setup
  - Use `@event_source(data_class=CloudFormationCustomResourceEvent)` decorator

- [x] **2.2**: Implement Bedrock database setup functions
  - Create
    `packages/hotel-pms-lambda/hotel_pms_lambda/database/bedrock_db_setup.py`
  - Implement `setup_bedrock_database()` function for "bedrock_vector_db"
    database
  - Create bedrock_integration schema and bedrock_kb table
  - Enable pgvector extension in bedrock_vector_db database
  - Create bedrock_service user with proper permissions
  - Use Bedrock database credentials exclusively

**Acceptance Criteria**:

- Bedrock custom resource handler is implemented with proper CloudFormation
  integration
- Database setup functions create "bedrock_vector_db" database and schema
- pgvector extension is enabled in the correct database
- bedrock_service user is created with vector store permissions
- Custom resource uses Bedrock-specific database credentials

---

## Task 3: Enhance Bedrock Knowledge Base Construct

**Priority**: High  
**Dependencies**: Task 1, Task 2

#### Subtasks:

- [x] **3.1**: Add Bedrock database resources to construct
  - Modify
    `packages/infra/stack/stack_constructs/bedrock_knowledge_base_construct.py`
  - Create Bedrock database credentials using `rds.DatabaseSecret`
  - Set database name to "bedrock_vector_db" in credentials
  - Create Bedrock service IAM role with RDS Data API permissions
  - Add multi-user credential rotation for Bedrock credentials

- [x] **3.2**: Update vector store configuration
  - Use `AmazonAuroraVectorStore.from_existing_aurora_vector_store()` method
  - Configure with correct database name "bedrock_vector_db"
  - Use Bedrock-specific credentials instead of Hotel PMS credentials
  - Set metadata_field to "metadata" as required by L3 construct
  - Apply escape hatch for CustomMetadataField after Knowledge Base creation

- [x] **3.3**: Add Bedrock custom resource integration
  - Create Bedrock database custom resource in the construct
  - Pass Bedrock credentials to the custom resource
  - Ensure custom resource runs before Knowledge Base creation
  - Add proper dependency management between resources

**Acceptance Criteria**:

- Bedrock construct creates its own database credentials with
  "bedrock_vector_db" database name
- Vector store uses `from_existing_aurora_vector_store` with correct parameters
- CustomMetadataField escape hatch is properly applied to Knowledge Base
- Bedrock custom resource is integrated and runs before Knowledge Base creation
- CDK synth validates the enhanced construct:
  `uv run cdk synth HotelPmsApiStack`

---

## Task 4: Restore Hotel PMS Custom Resource

**Priority**: Medium  
**Dependencies**: Task 2 (to avoid conflicts)

#### Subtasks:

- [x] **4.1**: Restore Hotel PMS custom resource files
  - Use `git checkout` to restore the following files:
    - `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/db_custom_resource.py`
    - `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/db_setup.py`
    - `packages/hotel-pms-lambda/tests/test_db_custom_resource_integration.py`
    - `packages/hotel-pms-lambda/tests/test_db_setup.py`

- [x] **4.2**: Clean Hotel PMS custom resource to use Hotel PMS credentials
      exclusively
  - In `db_setup.py`: Remove `setup_bedrock_integration()` function call from
    `setup_database()`
  - In `db_setup.py`: Remove `from ..database.bedrock_integration import` import
    statements
  - In `db_custom_resource.py`: Remove any Bedrock-related response data from
    CloudFormation responses
  - In `db_custom_resource.py`: Ensure custom resource only connects to
    "hotel_pms" database
  - Update environment variable usage to use Hotel PMS database secret ARN only
  - Remove any references to `BEDROCK_SERVICE_SECRET_ARN` environment variable
  - Verify all database operations use Hotel PMS credentials and connect to
    "hotel_pms" database

**Acceptance Criteria**:

- Hotel PMS custom resource files are restored from git
- All Bedrock-related code is removed from Hotel PMS custom resource
- Hotel PMS custom resource only manages "hotel_pms" database and schema
- No conflicts exist between Hotel PMS and Bedrock custom resources

---

## Task 5: Update Stack Integration

**Priority**: High  
**Dependencies**: Task 1, Task 3

#### Subtasks:

- [x] **5.1**: Update HotelPmsApiStack
  - Modify `packages/infra/stack/hotel_pms_stack.py`
  - Update Aurora construct instantiation to remove Bedrock parameters
  - Update Bedrock Knowledge Base construct to be self-contained
  - Remove passing of Bedrock resources from Aurora to Knowledge Base construct
  - Ensure proper dependency ordering between constructs

- [x] **5.2**: Validate stack configuration
  - Run `uv run cdk synth HotelPmsApiStack` to validate stack
  - Verify both Aurora and Bedrock constructs are properly integrated
  - Check that no circular dependencies exist
  - Ensure all required resources are created in correct order

**Acceptance Criteria**:

- HotelPmsApiStack properly integrates both constructs without parameter passing
- Aurora construct is independent and only handles Hotel PMS resources
- Bedrock Knowledge Base construct is self-contained with all required resources
- CDK synth validates the complete stack without errors

---

## Task 6: Deploy and Test

**Priority**: High  
**Dependencies**: Task 1, Task 2, Task 3, Task 4, Task 5

#### Subtasks:

- [x] **6.1**: Deploy infrastructure
  - Use `pnpm exec nx run infra:deploy:hotel-pms --no-rollback` for fast
    deployment
  - Monitor deployment for both custom resources
  - Verify Aurora cluster is created with both databases
  - Confirm Knowledge Base is created and accessible

- [x] **6.2**: Create Bedrock database custom resource integration test
  - Create
    `packages/hotel-pms-lambda/tests/test_bedrock_db_custom_resource_integration.py`
  - Model after existing `test_db_custom_resource_integration.py`
  - Test CREATE, UPDATE, DELETE events for Bedrock database setup
  - Focus on isolating the PostgreSQL transaction issue with CREATE DATABASE
  - Verify pgvector extension setup and bedrock_integration schema creation
  - Test bedrock_service user creation and permissions
  - Use shared pytest fixtures for database connectivity
  - _Requirements: 2.1, 2.2, 3.1_

- [x] **6.3**: Replace L3 constructs with L1 constructs for Knowledge Base
  - Replace `AmazonAuroraVectorStore.from_existing_aurora_vector_store()` with
    direct L1 construct usage
  - Use `aws_bedrock.CfnKnowledgeBase` instead of the generative AI CDK
    construct
  - Use `aws_bedrock.CfnDataSource` for data source configuration
  - Configure RDS storage configuration directly in CfnKnowledgeBase
  - Set custom_metadata_field to "hotel_id" for hotel filtering
  - _Requirements: 3.2, 3.3_

- [ ] **6.4**: Validate database separation
  - Verify "hotel_pms" database contains Hotel PMS tables
  - Verify "bedrock_vector_db" database contains vector store schema
  - Test Hotel PMS API functionality with hotel_pms database
  - Test Knowledge Base operations with bedrock_vector_db database

**Acceptance Criteria**:

- Deployment succeeds using nx command without AuroraVectorStore conflicts
- Both PostgreSQL databases are created in Aurora cluster
- Hotel PMS custom resource sets up hotel_pms database correctly
- Bedrock custom resource sets up bedrock_vector_db database correctly
- Knowledge Base uses L1 constructs and connects to vector store using Bedrock
  credentials
- Hotel PMS API functions correctly with separated database
- CustomMetadataField (hotel_id) works for hotel filtering

---

## Task 7: Integration Testing

**Priority**: Medium  
**Dependencies**: Task 6 (requires deployed resources)

#### Subtasks:

- [ ] **7.1**: Test Hotel PMS functionality
  - Verify Hotel PMS API endpoints work with hotel_pms database
  - Test database operations (CRUD) through API
  - Confirm Hotel PMS custom resource operations are isolated

- [ ] **7.2**: Test Knowledge Base functionality
  - Verify Knowledge Base can query vector store
  - Test vector embeddings are stored in bedrock_vector_db database
  - Confirm CustomMetadataField works for hotel filtering
  - Test that Knowledge Base operations don't affect Hotel PMS database

**Acceptance Criteria**:

- Hotel PMS API functions correctly with separated database
- Knowledge Base queries work with vector store in bedrock_vector_db
- Hotel filtering works through CustomMetadataField
- Both systems operate independently without interference
- Integration tests pass with deployed resources (no mocking)

---

## Success Metrics

### Functional Success

- [ ] Aurora construct contains only Hotel PMS resources
- [ ] Bedrock Knowledge Base construct is self-contained with all required
      resources
- [ ] Two separate PostgreSQL databases exist in Aurora cluster
- [ ] Hotel PMS API works with hotel_pms database
- [ ] Knowledge Base works with bedrock_vector_db database

### Technical Success

- [ ] CDK synth validates both constructs: `uv run cdk synth HotelPmsApiStack`
- [ ] Deployment succeeds:
      `pnpm exec nx run infra:deploy:hotel-pms --no-rollback`
- [ ] Knowledge Base uses L1 constructs (CfnKnowledgeBase, CfnDataSource)
      correctly
- [ ] CustomMetadataField (hotel_id) enables hotel filtering without escape
      hatches
- [ ] Database credentials are properly separated and managed
- [ ] No conflicts with generative AI CDK constructs

### Quality Success

- [ ] Integration tests pass with deployed resources
- [ ] No conflicts between Hotel PMS and Bedrock systems
- [ ] Clean separation of concerns in codebase
- [ ] Proper error handling in both custom resources

---

## Deliverables

### Code Deliverables

- [ ] Cleaned Aurora construct with only Hotel PMS resources
- [ ] Enhanced Bedrock Knowledge Base construct with database resources
- [ ] New Bedrock database custom resource
- [ ] Restored and cleaned Hotel PMS custom resource
- [ ] Updated stack integration

### Infrastructure Deliverables

- [ ] Aurora cluster with two separate PostgreSQL databases
- [ ] Proper credential separation and management
- [ ] Working Knowledge Base with vector store
- [ ] Functional Hotel PMS API

### Validation Deliverables

- [ ] CDK synth validation
- [ ] Successful deployment
- [ ] Integration tests with deployed resources
- [ ] Functional verification of both systems
