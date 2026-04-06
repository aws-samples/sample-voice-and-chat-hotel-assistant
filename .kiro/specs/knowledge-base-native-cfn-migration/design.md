# Knowledge Base Native CloudFormation Migration - Design

## Overview

This design document outlines the migration from the third-party
`cdk_s3_vectors` package to native AWS CloudFormation L1 constructs for the
Knowledge Base S3 Vectors implementation. The migration eliminates custom
Lambda-backed resources in favor of native CloudFormation resources introduced
before CDK 2.233.0.

## Architecture

### Current Architecture (cdk_s3_vectors)

```
┌─────────────────────────────────────────────────────────────┐
│ KnowledgeBase                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ VectorBucket     │  │ VectorIndex      │               │
│  │ (Custom Resource)│  │ (Custom Resource)│               │
│  │                  │  │                  │               │
│  │ - Lambda Handler │  │ - Lambda Handler │               │
│  │ - Provider       │  │ - Provider       │               │
│  └──────────────────┘  └──────────────────┘               │
│           │                     │                          │
│           └─────────┬───────────┘                          │
│                     │                                      │
│           ┌─────────▼──────────┐                          │
│           │ BedrockKnowledgeBase│                          │
│           │ (Custom Resource)   │                          │
│           │                     │                          │
│           │ - Lambda Handler    │                          │
│           │ - Provider          │                          │
│           └─────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### New Architecture (Native CloudFormation)

```
┌─────────────────────────────────────────────────────────────┐
│ KnowledgeBase                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │ CfnVectorBucket  │  │ CfnIndex         │               │
│  │ (Native L1)      │  │ (Native L1)      │               │
│  │                  │  │                  │               │
│  │ - No Lambda      │  │ - No Lambda      │               │
│  │ - Direct CFN     │  │ - Direct CFN     │               │
│  └──────────────────┘  └──────────────────┘               │
│           │                     │                          │
│           └─────────┬───────────┘                          │
│                     │                                      │
│           ┌─────────▼──────────┐                          │
│           │ CfnKnowledgeBase   │                          │
│           │ (Native L1)        │                          │
│           │                     │                          │
│           │ - No Lambda         │                          │
│           │ - Direct CFN        │                          │
│           └─────────────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Vector Bucket Construct

**Purpose**: Create an S3 vector bucket for storing vector embeddings.

**Implementation**:

```python
from aws_cdk import aws_s3vectors as s3vectors

class VectorBucket(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create vector bucket with auto-generated name
        self.bucket = s3vectors.CfnVectorBucket(
            self,
            "Bucket",
            # VectorBucketName omitted for auto-generation
            encryption_configuration=s3vectors.CfnVectorBucket.EncryptionConfigurationProperty(
                sse_type="AES256"
            )
        )

    @property
    def bucket_arn(self) -> str:
        """Get the vector bucket ARN."""
        return self.bucket.attr_vector_bucket_arn
```

**Key Changes**:

- Use `CfnVectorBucket` instead of custom `Bucket` class
- Omit `vector_bucket_name` parameter for auto-generation
- Access ARN via `attr_vector_bucket_arn` attribute
- Use `EncryptionConfigurationProperty` for type safety

### 2. Vector Index Construct

**Purpose**: Create a vector index within the vector bucket for similarity
search.

**Implementation**:

```python
from aws_cdk import aws_s3vectors as s3vectors

class VectorIndex(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vector_bucket_arn: str,
        non_filterable_metadata_keys: list[str] | None = None,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Configure metadata if needed
        metadata_config = None
        if non_filterable_metadata_keys:
            metadata_config = s3vectors.CfnIndex.MetadataConfigurationProperty(
                non_filterable_metadata_keys=non_filterable_metadata_keys
            )

        # Create vector index with auto-generated name
        self.index = s3vectors.CfnIndex(
            self,
            "Index",
            vector_bucket_arn=vector_bucket_arn,
            # IndexName omitted for auto-generation
            data_type="float32",
            dimension=1024,  # Titan Embeddings v2
            distance_metric="cosine",
            metadata_configuration=metadata_config,
        )

    @property
    def index_arn(self) -> str:
        """Get the index ARN."""
        return self.index.attr_index_arn
```

**Key Changes**:

- Use `CfnIndex` instead of custom `Index` class
- Pass `vector_bucket_arn` instead of `vector_bucket_name`
- Omit `index_name` parameter for auto-generation
- Access ARN via `attr_index_arn` attribute
- Use `MetadataConfigurationProperty` for type safety

### 3. Bedrock Knowledge Base Construct

**Purpose**: Create a Bedrock Knowledge Base using S3 Vectors storage.

**Implementation**:

```python
from aws_cdk import Stack, aws_bedrock as bedrock, aws_iam as iam

class BedrockKnowledgeBase(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vector_bucket_arn: str,
        index_arn: str,
        description: str,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        stack = Stack.of(self)

        # Create IAM role for Knowledge Base
        self.role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Role for Bedrock Knowledge Base to access S3 Vectors",
        )

        # Grant permissions for S3 Vectors operations
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:GetIndex",
                    "s3vectors:QueryIndex",
                    "s3vectors:PutVectors",
                    "s3vectors:DeleteVectors",
                ],
                resources=[index_arn],
            )
        )

        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:GetVectorBucket",
                ],
                resources=[vector_bucket_arn],
            )
        )

        # Embedding model ARN
        embedding_model_arn = (
            f"arn:aws:bedrock:{stack.region}::foundation-model/"
            "amazon.titan-embed-text-v2:0"
        )

        # Create Knowledge Base with auto-generated name
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            # Name omitted for auto-generation
            role_arn=self.role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="S3_VECTORS",
                s3_vectors_configuration=bedrock.CfnKnowledgeBase.S3VectorsConfigurationProperty(
                    vector_bucket_arn=vector_bucket_arn,
                    index_arn=index_arn,
                ),
            ),
            description=description,
        )

    @property
    def knowledge_base_id(self) -> str:
        """Get the Knowledge Base ID."""
        return self.knowledge_base.attr_knowledge_base_id

    @property
    def knowledge_base_arn(self) -> str:
        """Get the Knowledge Base ARN."""
        return self.knowledge_base.attr_knowledge_base_arn
```

**Key Changes**:

- Use `CfnKnowledgeBase` directly (no custom wrapper)
- Create IAM role explicitly with proper S3 Vectors permissions
- Omit `name` parameter for auto-generation
- Use nested property classes for type safety
- Access ID/ARN via `attr_knowledge_base_id` and `attr_knowledge_base_arn`

### 4. Data Source Construct

**Purpose**: Create a data source pointing to the S3 document bucket.

**Implementation**:

```python
from aws_cdk import aws_bedrock as bedrock

class DataSource(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        knowledge_base_id: str,
        document_bucket_arn: str,
        s3_prefix: str,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Create data source with auto-generated name
        self.data_source = bedrock.CfnDataSource(
            self,
            "DataSource",
            knowledge_base_id=knowledge_base_id,
            # Name omitted for auto-generation
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=document_bucket_arn,
                    inclusion_prefixes=[s3_prefix],
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="SEMANTIC",
                    semantic_chunking_configuration=bedrock.CfnDataSource.SemanticChunkingConfigurationProperty(
                        max_tokens=500,
                        buffer_size=1,
                        breakpoint_percentile_threshold=95,
                    ),
                ),
            ),
        )

    @property
    def data_source_id(self) -> str:
        """Get the Data Source ID."""
        return self.data_source.attr_data_source_id
```

**Key Changes**:

- Already using `CfnDataSource` (no change needed)
- Omit `name` parameter for auto-generation
- Use nested property classes for type safety

### 5. Main Knowledge Base Construct

**Purpose**: Orchestrate all components into a complete Knowledge Base solution.

**Implementation**:

```python
from constructs import Construct
from .s3_constructs import PACEBucket

class KnowledgeBase(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        non_filterable_metadata_keys: list[str] | None = None,
        s3_prefix: str = "knowledge-base/",
        description: str = "Knowledge base using S3 Vectors",
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Create document bucket (unchanged)
        self.document_bucket = PACEBucket(
            self,
            "DocumentBucket",
            lifecycle_rules=[],
        )

        # Create vector bucket
        self.vector_bucket_construct = VectorBucket(
            self, "VectorBucket"
        )

        # Create vector index
        self.vector_index_construct = VectorIndex(
            self,
            "VectorIndex",
            vector_bucket_arn=self.vector_bucket_construct.bucket_arn,
            non_filterable_metadata_keys=non_filterable_metadata_keys,
        )

        # Add dependency
        self.vector_index_construct.node.add_dependency(
            self.vector_bucket_construct
        )

        # Create Knowledge Base
        self.bedrock_kb_construct = BedrockKnowledgeBase(
            self,
            "BedrockKnowledgeBase",
            vector_bucket_arn=self.vector_bucket_construct.bucket_arn,
            index_arn=self.vector_index_construct.index_arn,
            description=description,
        )

        # Add dependency
        self.bedrock_kb_construct.node.add_dependency(
            self.vector_index_construct
        )

        # Create data source
        self.data_source_construct = DataSource(
            self,
            "DataSource",
            knowledge_base_id=self.bedrock_kb_construct.knowledge_base_id,
            document_bucket_arn=self.document_bucket.bucket_arn,
            s3_prefix=s3_prefix,
        )

        # Grant document bucket access to KB role
        self.document_bucket.grant_read(self.bedrock_kb_construct.role)

        # Apply CDK Nag suppressions
        self._apply_nag_suppressions()

    @property
    def bucket_name(self) -> str:
        """Get the document bucket name."""
        return self.document_bucket.bucket_name

    @property
    def bucket_arn(self) -> str:
        """Get the document bucket ARN."""
        return self.document_bucket.bucket_arn

    @property
    def vector_bucket_arn(self) -> str:
        """Get the vector bucket ARN."""
        return self.vector_bucket_construct.bucket_arn

    @property
    def knowledge_base_id(self) -> str:
        """Get the Knowledge Base ID."""
        return self.bedrock_kb_construct.knowledge_base_id

    @property
    def knowledge_base_arn(self) -> str:
        """Get the Knowledge Base ARN."""
        return self.bedrock_kb_construct.knowledge_base_arn

    @property
    def data_source_id(self) -> str:
        """Get the Data Source ID."""
        return self.data_source_construct.data_source_id

    @property
    def index_arn(self) -> str:
        """Get the Vector Index ARN."""
        return self.vector_index_construct.index_arn
```

**Key Changes**:

- Removed `vector_bucket_name` property (no longer needed)
- Pass ARNs instead of names between constructs
- Simplified property accessors

## CDK Nag Suppressions

### Suppressions to Remove

All suppressions related to custom resource Lambda functions:

- `AwsSolutions-IAM4` for Lambda execution roles
- `AwsSolutions-IAM5` for Lambda wildcard permissions
- `AwsSolutions-L1` for Lambda runtime versions
- Custom resource provider framework suppressions

### Suppressions to Keep/Add

Only IAM suppressions for the Knowledge Base role:

```python
def _apply_nag_suppressions(self):
    """Apply CDK Nag suppressions for native constructs."""
    stack = Stack.of(self)
    base_path = self.node.path

    # Suppress IAM5 for Knowledge Base role S3 Vectors permissions
    NagSuppressions.add_resource_suppressions_by_path(
        stack,
        f"{base_path}/BedrockKnowledgeBase/Role/DefaultPolicy/Resource",
        [
            NagPackSuppression(
                id="AwsSolutions-IAM5",
                reason="Knowledge Base requires S3 Vectors permissions for "
                "vector operations. Scoped to specific vector bucket and index.",
                applies_to=[
                    "Action::s3vectors:*",
                ],
            )
        ],
    )

    # Suppress IAM5 for document bucket read access
    NagSuppressions.add_resource_suppressions_by_path(
        stack,
        f"{base_path}/BedrockKnowledgeBase/Role/DefaultPolicy/Resource",
        [
            NagPackSuppression(
                id="AwsSolutions-IAM5",
                reason="Knowledge Base requires read access to all documents "
                "in the document bucket for ingestion.",
                applies_to=[
                    "Action::s3:GetObject*",
                    "Action::s3:GetBucket*",
                    "Action::s3:List*",
                    "Resource::<KnowledgeBaseDocumentBucket*.Arn>/*",
                ],
            )
        ],
    )
```

## IAM Permissions

### Knowledge Base Role Permissions

**S3 Vectors Permissions**:

```python
{
    "Effect": "Allow",
    "Action": [
        "s3vectors:GetIndex",
        "s3vectors:QueryIndex",
        "s3vectors:PutVectors",
        "s3vectors:DeleteVectors",
        "s3vectors:GetVectorBucket"
    ],
    "Resource": [
        "<vector-bucket-arn>",
        "<index-arn>"
    ]
}
```

**Document Bucket Permissions**:

```python
{
    "Effect": "Allow",
    "Action": [
        "s3:GetObject",
        "s3:ListBucket"
    ],
    "Resource": [
        "<document-bucket-arn>",
        "<document-bucket-arn>/*"
    ]
}
```

**Bedrock Model Permissions**:

```python
{
    "Effect": "Allow",
    "Action": [
        "bedrock:InvokeModel"
    ],
    "Resource": [
        "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"
    ]
}
```

## Resource Dependencies

```
DocumentBucket (independent)
     │
     ├─────────────────────┐
     │                     │
VectorBucket          (grant read)
     │                     │
     ▼                     │
VectorIndex                │
     │                     │
     ▼                     │
KnowledgeBase ◄────────────┘
     │
     ▼
DataSource
```

**Dependency Rules**:

1. VectorIndex depends on VectorBucket
2. KnowledgeBase depends on VectorIndex
3. DataSource depends on KnowledgeBase
4. KnowledgeBase role needs read access to DocumentBucket

## Migration Strategy

### Breaking Changes

This is a **breaking change** that requires:

1. Destroying existing Knowledge Base resources
2. Redeploying with new native constructs
3. Re-ingesting documents into new Knowledge Base

### Migration Steps

1. **Backup Data** (if needed):
   - Export any critical metadata
   - Document current configuration

2. **Update Dependencies**:

   ```bash
   cd packages/infra
   uv remove cdk-s3-vectors
   uv sync
   ```

3. **Deploy New Stack**:

   ```bash
   pnpm exec nx deploy infra
   ```

4. **Re-ingest Documents**:
   - Upload documents to new document bucket
   - Trigger ingestion job via Bedrock console or API

### Rollback Plan

If issues occur:

1. Revert code changes
2. Re-add `cdk-s3-vectors` dependency
3. Redeploy previous version
4. Re-ingest documents

## Testing Strategy

CDK constructs are tested through synth and deploy:

1. **Synth Test**:

   ```bash
   pnpm exec nx run infra:synth
   ```

   Verifies CloudFormation template generation without errors.

2. **Deploy Test**:

   ```bash
   pnpm exec nx deploy infra
   ```

   Deploys to AWS and validates actual resource creation.

3. **Verify Resources**:

   ```bash
   # Check vector bucket
   aws s3vectors list-vector-buckets

   # Check index
   aws s3vectors list-indexes --vector-bucket-name <bucket-name>

   # Check knowledge base
   aws bedrock-agent list-knowledge-bases
   ```

4. **Test Document Ingestion**:

   ```bash
   # Upload test document
   aws s3 cp test-doc.md s3://<document-bucket>/knowledge-base/

   # Start ingestion
   aws bedrock-agent start-ingestion-job \
     --knowledge-base-id <kb-id> \
     --data-source-id <ds-id>
   ```

5. **Test Retrieval**:
   ```bash
   # Query knowledge base
   aws bedrock-agent-runtime retrieve \
     --knowledge-base-id <kb-id> \
     --retrieval-query text="test query"
   ```

## Performance Considerations

### Deployment Time Improvements

**Before (Custom Resources)**:

- Vector Bucket: ~15s (Lambda cold start + execution)
- Vector Index: ~20s (Lambda cold start + execution)
- Knowledge Base: ~25s (Lambda cold start + execution)
- **Total**: ~60s

**After (Native CloudFormation)**:

- Vector Bucket: ~5s (direct CloudFormation)
- Vector Index: ~8s (direct CloudFormation)
- Knowledge Base: ~10s (direct CloudFormation)
- **Total**: ~23s

**Expected Improvement**: ~60% faster deployment

### Runtime Performance

No change to runtime performance:

- Vector search latency: Same
- Document ingestion: Same
- Query performance: Same

## Security Considerations

### Encryption

- **Vector Bucket**: AES256 server-side encryption
- **Document Bucket**: Existing PACEBucket encryption
- **Data in Transit**: TLS 1.2+ for all API calls

### IAM Least Privilege

Knowledge Base role has minimal permissions:

- Read-only access to document bucket
- Vector operations scoped to specific bucket/index
- Bedrock model invocation for embeddings only

### Network Security

- All resources deployed in same region
- No cross-region data transfer
- VPC endpoints can be added if needed

## Monitoring and Observability

### CloudWatch Metrics

Monitor via Bedrock CloudWatch metrics:

- `KnowledgeBaseQueries`: Query count
- `KnowledgeBaseQueryLatency`: Query performance
- `DataSourceSyncJobs`: Ingestion job status

### CloudWatch Logs

- Bedrock API calls logged to CloudTrail
- No custom resource Lambda logs (eliminated)

### Alarms

Recommended alarms:

- High query latency (> 2s)
- Failed ingestion jobs
- IAM permission errors

## Cost Analysis

### Cost Reduction

**Eliminated Costs**:

- Lambda invocations for custom resources: ~$0.20/month
- Lambda execution time: ~$0.10/month
- CloudWatch Logs for Lambda: ~$0.05/month

**Total Savings**: ~$0.35/month per stack

### Ongoing Costs

No change to ongoing costs:

- S3 Vectors storage: Same
- Bedrock embeddings: Same
- S3 document storage: Same

## Rollout Plan

### Phase 1: Development (Week 1)

- Implement new constructs
- Write unit tests
- Update CDK Nag suppressions

### Phase 2: Testing (Week 1)

- Deploy to dev environment
- Run integration tests
- Verify document ingestion

### Phase 3: Documentation (Week 1)

- Update README
- Document migration steps
- Create troubleshooting guide

### Phase 4: Production (Week 2)

- Deploy to production
- Monitor for issues
- Re-ingest documents

## Success Criteria

1. ✅ All custom resources removed
2. ✅ Deployment time reduced by 30%+
3. ✅ All CDK Nag checks pass
4. ✅ Zero Lambda functions for Knowledge Base
5. ✅ Document ingestion works correctly
6. ✅ Query performance unchanged

## References

- [AWS::S3Vectors::VectorBucket](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3vectors-vectorbucket.html)
- [AWS::S3Vectors::Index](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3vectors-index.html)
- [AWS::Bedrock::KnowledgeBase](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-bedrock-knowledgebase.html)
- [CDK Python API Reference](https://docs.aws.amazon.com/cdk/api/v2/python/)
