# Hotel Knowledge Base Implementation Tasks

## Task 1: Update Aurora Construct for Bedrock Integration

**Priority**: High  
**Dependencies**: Existing Aurora construct

#### Subtasks:

- [x] **1.1**: Update Aurora construct configuration
  - Modify `packages/infra/stack/stack_constructs/aurora_construct.py`
  - Ensure RDS Data API is enabled
  - Add IAM permissions for Bedrock service access
  - Update security groups for Bedrock access

- [x] **1.2**: Update database custom resource for Bedrock schema setup
  - Extend
    `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/db_custom_resource.py`
  - Add `setup_bedrock_integration()` function (will run automatically on
    deployment)
  - Create `bedrock_integration` schema
  - Create `bedrock_kb` table with proper structure and GIN index on JSONB
  - Create Bedrock service user with credentials stored in Secrets Manager

**Acceptance Criteria**:

- Aurora construct is updated with RDS Data API enabled
- IAM permissions are configured for Bedrock service access
- Security groups allow Bedrock access
- Custom resource code is updated to set up Bedrock schema automatically on
  deployment

---

## Task 2: Create Knowledge Base Construct

**Priority**: High  
**Dependencies**: Task 1, L3 constructs package (already installed)

#### Subtasks:

- [x] **2.1**: Create Knowledge Base construct
  - Create `packages/common/constructs/bedrock_knowledge_base_construct.py`
  - Implement `HotelKnowledgeBaseConstruct` class using L3 constructs
  - Configure `AmazonAuroraVectorStore` with existing Aurora cluster
  - Set up single `VectorKnowledgeBase` with Titan embeddings
  - Configure single S3 data source for all hotels

- [x] **2.2**: Integrate with existing HotelPmsApiStack
  - Modify `packages/infra/stack/hotel_pms_api_stack.py`
  - Add Knowledge Base construct to existing stack
  - Configure S3 bucket for hotel documents
  - Set up proper IAM roles and permissions

**Acceptance Criteria**:

- `HotelKnowledgeBaseConstruct` is implemented using L3 constructs
- Single Knowledge Base resource is created with Aurora backend
- Single S3 data source includes all hotel directories
- Knowledge Base integrates with existing HotelPmsApiStack
- IAM roles have correct permissions for Bedrock and Aurora access

---

## Task 3: Create Local Metadata Generation Script

**Priority**: High  
**Dependencies**: None

#### Subtasks:

- [x] **3.1**: Create metadata generation script
  - Create `scripts/generate_metadata.py`
  - Implement hotel ID mapping for all 4 hotels
  - Generate `.metadata.json` files for each document
  - Include hotel_id, document_type, language, and category metadata
  - Run script once locally to generate all metadata files

**Acceptance Criteria**:

- All 28 hotel documents have corresponding metadata files
- Metadata follows defined schema with hotel_id for filtering
- Script runs successfully and generates all required metadata files

---

## Task 4: Implement Simplified Query Handler

**Priority**: High  
**Dependencies**: Task 2

#### Subtasks:

- [x] **4.1**: Create Knowledge Base query handler
  - Create
    `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/kb_query_handler.py`
  - Implement `KnowledgeBaseQueryHandler` class
  - Use `bedrock_agent.retrieve()` method (not retrieve_and_generate)
  - Return all results for client to handle

- [x] **4.2**: Implement query methods
  - `query_hotel_specific(query, hotel_id)` - filter by specific hotel
  - `query_multi_hotel(query, hotel_ids=None)` - query all hotels if hotel_ids
    is None/empty
  - Use metadata filtering with JSONB custom_metadata column
  - Add basic error handling and logging with Python's builtin logging

**Acceptance Criteria**:

- Query handler only retrieves results, doesn't generate responses
- Hotel-specific filtering works correctly using metadata
- Multi-hotel queries work when hotel_ids is None or empty
- Error handling prevents crashes and logs issues appropriately

---

## Task 5: Integrate with AgentCore Gateway

**Priority**: High  
**Dependencies**: Task 4, existing AgentCore infrastructure

#### Subtasks:

- [x] **5.1**: Add Knowledge Base tool to AgentCore handler
  - Extend
    `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/agentcore_handler.py`
  - Add Knowledge Base query tool definition
  - Implement tool parameter validation for hotel filtering
  - Use Lambda Powertools logging within handler

- [x] **5.2**: Update AgentCore tools schema
  - Update `packages/hotel-pms-lambda/agentcore_tools_schema.json`
  - Add Knowledge Base query tool with proper parameters
  - Define hotel_id filtering parameters
  - Update schema validation

**Acceptance Criteria**:

- Knowledge Base queries work through AgentCore Gateway
- Hotel filtering parameters are properly handled
- Tool schema is updated and validated
- Integration tests pass successfully

---

## Task 6: Deploy Infrastructure

**Priority**: High  
**Dependencies**: Tasks 1, 2, 4, 5

#### Subtasks:

- [ ] **6.1**: Deploy using existing nx commands
  - Use `pnpm exec nx run infra:deploy:hotel-pms --no-rollback` for development
  - Validate deployment success
  - Verify Knowledge Base and Aurora integration are working
  - Test basic connectivity to deployed resources

**Acceptance Criteria**:

- Deployment succeeds using existing nx commands
- Knowledge Base is created and accessible
- Aurora vector table is set up correctly (via custom resource)
- `bedrock_integration.bedrock_kb` table exists with proper schema
- GIN index on `custom_metadata` JSONB column is created
- Bedrock service user is created with credentials in Secrets Manager
- S3 bucket for documents is created and accessible

---

## Task 7: Upload Documents and Configure Data Ingestion

**Priority**: Medium  
**Dependencies**: Task 3, Task 6 (requires deployed infrastructure with Bedrock
schema)

#### Subtasks:

- [x] **7.1**: Create combined upload and ingestion script
  - Create `scripts/upload_and_ingest_documents.py`
  - Upload all documents and metadata files to S3
  - Organize by hotel directory structure
  - Trigger Knowledge Base sync after upload
  - Monitor ingestion progress and validate completion

- [ ] **7.2**: Validate data source configuration
  - Verify single S3 data source processes all hotel documents
  - Confirm semantic chunking produces coherent chunks for Spanish content
  - Validate default parsing strategy works with Markdown documents
  - Test that all hotel directories are included

**Acceptance Criteria**:

- All documents and metadata are uploaded to S3 with correct structure
- Knowledge Base ingestion completes successfully for all documents
- Vector embeddings are generated and stored in Aurora
- Single data source processes all hotel documents correctly

---

## Task 8: Fix AgentCore Schema Validation Issues

**Priority**: High  
**Dependencies**: Task 5 (AgentCore integration)

#### Subtasks:

- [x] **8.1**: Fix JSON schema validation errors
  - Analyze the schema validation failure in CreateGatewayTarget
  - Fix missing `required` arrays in outputSchema sections
  - Simplify complex nested object structures if needed
  - Ensure all tools follow the exact schema specification format

- [ ] **8.2**: Validate schema compliance
  - Test schema against AgentCore validation requirements
  - Verify all existing tools still work after schema fixes
  - Test knowledge base tools work through AgentCore gateway
  - Ensure no regression in existing functionality

**Acceptance Criteria**:

- CreateGatewayTarget succeeds without "unexpected error"
- All tools in schema pass validation
- Knowledge base queries work through AgentCore
- Existing hotel PMS tools continue to function
- Schema follows exact specification format

---

## Task 9: Testing and Documentation

**Priority**: High  
**Dependencies**: Task 7 (requires deployed infrastructure and ingested data)

#### Subtasks:

- [ ] **9.1**: Create unit tests
  - Test Knowledge Base query handler methods
  - Test metadata generation script
  - Test hotel filtering logic
  - Test error handling scenarios

- [x] **9.2**: Create integration tests
  - Test end-to-end query flow through AgentCore

- [ ] **9.3**: Create documentation
  - Document Knowledge Base architecture and design
  - Create deployment and operations guide
  - Document query API and usage examples
  - Create troubleshooting guide

**Acceptance Criteria**:

- Unit tests pass with good code coverage
- Integration tests validate complete workflows using deployed infrastructure
- Hotel filtering is 100% accurate
- Documentation is complete and accurate
- System is ready for production use

---

## Simplified Success Metrics

### Functional Success

- [ ] All 28 hotel documents successfully ingested into single Knowledge Base
- [ ] Hotel-specific filtering works with 100% accuracy
- [ ] Multi-hotel queries work when no hotel filter is specified
- [ ] AgentCore integration functions properly
- [ ] Query responses are relevant and accurate

### Technical Success

- [ ] Single Knowledge Base and Aurora vector table architecture
- [ ] GIN index on JSONB metadata column performs well
- [ ] Aurora Serverless scales appropriately
- [ ] System integrates seamlessly with existing HotelPmsApiStack
- [ ] Deployment works with existing nx commands

### Quality Success

- [ ] Unit and integration tests pass
- [ ] No data leakage between hotels when filtering is applied
- [ ] Error handling prevents system crashes
- [ ] Documentation is complete and usable

---

## Deliverables

### Code Deliverables

- [ ] Extended Aurora construct with Bedrock integration
- [ ] Hotel Knowledge Base construct using L3 constructs
- [ ] Simplified Knowledge Base query handler
- [ ] Local metadata generation script
- [ ] Document upload and ingestion scripts
- [ ] AgentCore integration for Knowledge Base queries
- [ ] Unit and integration tests

### Infrastructure Deliverables

- [ ] Single Knowledge Base with Aurora PostgreSQL backend
- [ ] S3 bucket with organized hotel documents and metadata
- [ ] IAM roles and policies with appropriate permissions
- [ ] Integration with existing HotelPmsApiStack

### Documentation Deliverables

- [ ] Architecture and design documentation
- [ ] Deployment guide using nx commands
- [ ] API usage examples and troubleshooting guide
- [ ] Operations and maintenance documentation

---

## Key Simplifications Made

### Architecture Simplifications

- **Single Knowledge Base**: One Knowledge Base resource instead of multiple
- **Single Vector Table**: One Aurora table with metadata filtering
- **Single Data Source**: One S3 data source covering all hotels
- **No Custom Metrics**: Rely on built-in AWS service metrics
- **No Caching**: Eliminated Lambda function caching complexity

### Implementation Simplifications

- **Local Scripts**: Metadata generation runs locally, not in cloud
- **Default Parsing**: Use default parsing strategy for Markdown documents
- **Retrieve Only**: Query handler only retrieves, doesn't generate responses
- **Built-in Logging**: Use Python logging and Lambda Powertools
- **Existing Stack**: Integrate with existing HotelPmsApiStack

### Operational Simplifications

- **Existing Deployment**: Use existing nx deployment commands
- **No Load Testing**: Focus on unit and integration testing
- **No Resilience Patterns**: Client handles retries and error recovery
- **No Health Checks**: Rely on AWS service health monitoring

This simplified approach maintains all core functionality while reducing
complexity and development time significantly.
