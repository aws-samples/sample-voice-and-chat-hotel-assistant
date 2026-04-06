# Implementation Plan

- [x] 1. Install cdk-s3-vectors package
  - Run `uv add cdk-s3-vectors` in infra package
  - Verify package installation and imports
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 2. Create KnowledgeBaseConstruct with S3 Vectors
  - Implement `KnowledgeBaseConstruct` using cdk-s3-vectors Bucket, Index, and
    KnowledgeBase
  - Configure vector index with Titan Embeddings v2 (1024 dimensions, cosine
    similarity)
  - Add metadata configuration for entity filtering (entity_id, document_type,
    language, category)
  - Set up proper dependency chain (Bucket → Index → KnowledgeBase)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2,
    5.3, 5.4, 5.5_

- [x] 3. Add data source configuration
  - Create CfnDataSource pointing to `knowledge-base/` prefix in S3
  - Configure semantic chunking (500 tokens, buffer size 1, 95% breakpoint
    threshold)
  - Configure foundation model parsing (Claude 3 Sonnet)
  - Add data source ID property to construct
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Integrate with Application Stack
  - Add KnowledgeBaseConstruct to application stack
  - Create CloudFormation outputs: DocumentsBucketName, KnowledgeBaseId,
    DataSourceId, KnowledgeBaseArn
  - Ensure output names match existing script expectations
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 5. Validate with CDK synthesis
  - Run `pnpm exec nx run infra:synth` to generate CloudFormation template
  - Verify Bucket, Index, KnowledgeBase, and DataSource resources
  - Verify CloudFormation outputs are present
  - Check IAM roles and permissions
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 6. Deploy and test with existing scripts
  - Run `pnpm exec nx deploy infra` to deploy stack
  - Generate metadata with `python data/scripts/generate_metadata.py`
  - Upload documents with `python data/scripts/upload_and_ingest_documents.py`
  - Verify ingestion completes successfully
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 7. Test query functionality
  - Test entity-specific query with metadata filtering
  - Test cross-entity query
  - Test category-specific query
  - Verify query performance (sub-second latency)
  - Verify relevance scores meet 90%+ threshold
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 8. Security and compliance validation
  - Verify S3 bucket encryption (SSE-S3)
  - Verify IAM roles use least-privilege permissions
  - Verify S3 bucket logging is enabled
  - Test access control for knowledge base queries
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
