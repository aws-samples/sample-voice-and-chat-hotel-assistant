# Knowledge Base Native CloudFormation Migration - Tasks

## Task List

- [x] 1. Update package dependencies
  - [x] 1.1 Remove cdk-s3-vectors from pyproject.toml
  - [x] 1.2 Run uv sync to update lock file
  - [x] 1.3 Verify CDK version is 2.233.0+

- [x] 2. Migrate to native CloudFormation L1 constructs
  - [x] 2.1 Update VectorBucket class
    - [x] 2.1.1 Replace custom Bucket with CfnVectorBucket
    - [x] 2.1.2 Remove vector_bucket_name parameter (use auto-generation)
    - [x] 2.1.3 Update bucket_arn property to use attr_vector_bucket_arn
    - [x] 2.1.4 Configure AES256 encryption using
          EncryptionConfigurationProperty
    - [x] 2.1.5 Remove bucket_name property (no longer available)
  - [x] 2.2 Update VectorIndex class
    - [x] 2.2.1 Replace custom Index with CfnIndex
    - [x] 2.2.2 Change parameter from vector_bucket_name to vector_bucket_arn
    - [x] 2.2.3 Remove index_name parameter (use auto-generation)
    - [x] 2.2.4 Update index_arn property to use attr_index_arn
    - [x] 2.2.5 Configure metadata using MetadataConfigurationProperty
  - [x] 2.3 Update BedrockKnowledgeBase class
    - [x] 2.3.1 Replace custom KnowledgeBase with CfnKnowledgeBase
    - [x] 2.3.2 Create explicit IAM role for Knowledge Base
    - [x] 2.3.3 Add S3 Vectors permissions to role (GetIndex, QueryIndex,
          PutVectors, DeleteVectors, GetVectorBucket)
    - [x] 2.3.4 Configure S3VectorsConfiguration with vector_bucket_arn and
          index_arn
    - [x] 2.3.5 Remove knowledge_base_name parameter (use auto-generation)
    - [x] 2.3.6 Update properties to use attr_knowledge_base_id and
          attr_knowledge_base_arn
    - [x] 2.3.7 Expose role property for document bucket access grants
  - [x] 2.4 Update DataSource class
    - [x] 2.4.1 Remove data_source_name parameter (use auto-generation)
    - [x] 2.4.2 Verify CfnDataSource configuration unchanged
    - [x] 2.4.3 Update property classes to use nested Property types
  - [x] 2.5 Update main KnowledgeBase class
    - [x] 2.5.1 Update VectorBucket instantiation (remove name parameter)
    - [x] 2.5.2 Update VectorIndex to pass vector_bucket_arn instead of name
    - [x] 2.5.3 Update BedrockKnowledgeBase to pass ARNs
    - [x] 2.5.4 Update document bucket grant to use role property
    - [x] 2.5.5 Remove vector_bucket_name property
    - [x] 2.5.6 Verify all other properties still work
  - [x] 2.6 Update CDK Nag suppressions
    - [x] 2.6.1 Remove all custom resource Lambda suppressions (IAM4, IAM5, L1)
    - [x] 2.6.2 Remove S3VectorsBucketHandler suppressions
    - [x] 2.6.3 Remove S3VectorsHandler suppressions
    - [x] 2.6.4 Remove BedrockKBHandler suppressions
    - [x] 2.6.5 Remove framework-onEvent provider suppressions
    - [x] 2.6.6 Add IAM5 suppression for Knowledge Base role S3 Vectors
          permissions
    - [x] 2.6.7 Add IAM5 suppression for Knowledge Base role document bucket
          access
    - [x] 2.6.8 Verify all suppressions reference correct resource paths

- [x] 3. Test with CDK synth
  - [x] 3.1 Run pnpm exec nx run infra:synth
  - [x] 3.2 Verify CloudFormation template generates without errors
  - [x] 3.3 Verify no custom resource Lambda functions in template
  - [x] 3.4 Verify all native resources present in template

- [ ] 4. Run CDK diff and verify changes
  - [ ] 4.1 Run cdk diff to see resource changes
  - [ ] 4.2 Verify all custom resources will be removed
  - [ ] 4.3 Verify all native resources will be created
  - [ ] 4.4 Verify no unexpected changes
  - [ ] 4.5 Document breaking changes for deployment

- [ ] 5. Deploy and validate
  - [ ] 5.1 Deploy to dev environment
  - [ ] 5.2 Verify vector bucket created with auto-generated name
  - [ ] 5.3 Verify vector index created with auto-generated name
  - [ ] 5.4 Verify knowledge base created with auto-generated name
  - [ ] 5.5 Verify data source created with auto-generated name
  - [ ] 5.6 Verify no Lambda functions in CloudFormation stack
  - [ ] 5.7 Upload test document to document bucket
  - [ ] 5.8 Start ingestion job
  - [ ] 5.9 Verify ingestion completes successfully
  - [ ] 5.10 Test knowledge base query
  - [ ] 5.11 Verify query returns expected results
  - [ ] 5.12 Run CDK Nag and verify all checks pass

## Task Dependencies

```
1 (Dependencies)
  ↓
2 (Migrate to Native L1 Constructs)
  ↓
3 (CDK Synth)
  ↓
4 (CDK Diff)
  ↓
5 (Deploy & Validate)
```

## Estimated Effort

- Task 1: 15 minutes
- Task 2: 3 hours (all construct updates + Nag suppressions)
- Task 3: 15 minutes
- Task 4: 30 minutes
- Task 5: 1 hour

**Total Estimated Time**: ~4.5 hours

## Notes

- This is a breaking change - existing Knowledge Bases will need to be recreated
- All resource names will change to CloudFormation auto-generated names
- No data migration path - documents must be re-ingested
- Deployment will be significantly faster without custom resources
- CDK Nag suppressions will be much simpler
