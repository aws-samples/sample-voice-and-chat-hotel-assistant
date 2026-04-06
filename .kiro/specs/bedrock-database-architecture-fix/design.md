# Design Document

## Overview

This design addresses the architectural issues in the Hotel Knowledge Base
system by properly separating Hotel PMS and Bedrock Knowledge Base database
concerns. The solution involves restructuring the Aurora construct, creating a
dedicated Bedrock custom resource, and properly implementing the L3 construct
pattern for vector store configuration.

## Architecture

### Current Architecture Issues

The current implementation has several architectural problems:

1. **Mixed Concerns**: Aurora construct contains both Hotel PMS and Bedrock
   resources
2. **Credential Conflicts**: Single custom resource manages both systems with
   conflicting database names
3. **L3 Construct Conflicts**: Generative AI CDK constructs try to manage their
   own database setup, conflicting with our custom database architecture
4. **Database Confusion**: Both systems try to use the same PostgreSQL database
   within the Aurora cluster

### Target Architecture

The new architecture will have clear separation:

```
Aurora Cluster (Serverless V2 PostgreSQL)
├── hotel_pms (PostgreSQL database)
│   ├── Hotel PMS tables and data
│   └── Managed by Hotel PMS custom resource
└── bedrock_vector_db (PostgreSQL database)
    ├── bedrock_integration schema
    ├── bedrock_kb table with vector embeddings
    └── Managed by Bedrock custom resource
```

## Components and Interfaces

### 1. Aurora Construct (Simplified)

**Location**: `packages/infra/stack/stack_constructs/aurora_construct.py`

**Responsibilities**:

- Create Aurora Serverless V2 PostgreSQL cluster
- Manage Hotel PMS database credentials and security groups
- Provide cluster access for both Hotel PMS and Bedrock systems
- Enable RDS Data API for Bedrock integration

**Key Changes**:

- Remove all Bedrock-specific resources (credentials, IAM roles, security
  groups)
- Keep only Hotel PMS database resources
- Maintain cluster-level configuration for shared access

### 2. Bedrock Knowledge Base Construct (Enhanced)

**Location**:
`packages/infra/stack/stack_constructs/bedrock_knowledge_base_construct.py`

**Responsibilities**:

- Create Bedrock-specific database credentials for "bedrock_vector_db"
- Create Bedrock service IAM role with proper permissions
- Create Knowledge Base using L1 constructs (`aws_bedrock.CfnKnowledgeBase`)
- Create data source using L1 constructs (`aws_bedrock.CfnDataSource`)
- Manage S3 bucket for hotel documents
- Configure custom metadata field for hotel filtering

**Key Changes**:

- Add Bedrock database credential creation with `rds.DatabaseSecret`
- Add Bedrock service IAM role creation
- Replace L3 constructs with L1 constructs to avoid database setup conflicts
- Configure RDS storage directly in CfnKnowledgeBase
- Set custom_metadata_field to "hotel_id" for hotel filtering without escape
  hatches

### 3. Bedrock Database Custom Resource (New)

**Location**:
`packages/hotel-pms-lambda/hotel_pms_lambda/handlers/bedrock_db_custom_resource.py`

**Responsibilities**:

- Set up "bedrock_vector_db" PostgreSQL database
- Create bedrock_integration schema and bedrock_kb table
- Create bedrock_service user with proper permissions
- Enable pgvector extension
- Create vector indexes for performance

**Key Features**:

- Separate Lambda function from Hotel PMS custom resource
- Uses Bedrock-specific database credentials
- Idempotent operations for safe re-runs
- Proper error handling and CloudFormation responses

### 4. Hotel PMS Custom Resource (Cleaned)

**Location**:
`packages/hotel-pms-lambda/hotel_pms_lambda/handlers/db_custom_resource.py`

**Responsibilities**:

- Set up "hotel_pms" PostgreSQL database only
- Create Hotel PMS schema and tables
- Load Hotel PMS seed data
- No Bedrock-related operations

**Key Changes**:

- Remove all Bedrock integration code
- Focus only on Hotel PMS database setup
- Use Hotel PMS credentials exclusively

## Data Models

### Database Separation Model

```sql
-- Aurora Cluster contains two separate PostgreSQL databases:

-- 1. hotel_pms database (existing)
CREATE DATABASE hotel_pms;
-- Contains: hotels, rooms, reservations, guests, etc.

-- 2. bedrock_vector_db database (new)
CREATE DATABASE bedrock_vector_db;
-- Contains: bedrock_integration.bedrock_kb table
```

### Bedrock Vector Store Schema

```sql
-- In bedrock_vector_db database
CREATE SCHEMA bedrock_integration;

CREATE TABLE bedrock_integration.bedrock_kb (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    embedding VECTOR(1024),  -- Titan v2 embeddings
    chunks TEXT NOT NULL,
    metadata JSON NOT NULL,
    custom_metadata JSONB    -- Hotel filtering with GIN index
);

-- Performance indexes
CREATE INDEX bedrock_kb_vector_idx
ON bedrock_integration.bedrock_kb
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX bedrock_kb_metadata_idx
ON bedrock_integration.bedrock_kb
USING gin (custom_metadata);
```

### Credential Model

```python
# Hotel PMS credentials
hotel_pms_secret = rds.DatabaseSecret(
    username="postgres",
    dbname="hotel_pms",  # Points to hotel_pms database
    master_secret=cluster.secret
)

# Bedrock credentials (separate)
bedrock_secret = rds.DatabaseSecret(
    username="bedrock_service",
    dbname="bedrock_vector_db",  # Points to bedrock_vector_db database
    master_secret=cluster.secret
)
```

## Error Handling

### Custom Resource Error Handling

1. **Database Connection Failures**: Retry with exponential backoff
2. **Schema Creation Errors**: Rollback transaction and report to CloudFormation
3. **Permission Errors**: Clear error messages for troubleshooting
4. **Credential Issues**: Validate secret access before database operations

### Vector Store Configuration Errors

1. **L3 Construct Failures**: Validate all required parameters before creation
2. **Database Name Mismatches**: Fail fast with clear error messages
3. **Credential Access Issues**: Verify IAM permissions and secret access

## Testing Strategy

### CDK Construct Tests

1. **Aurora Construct Tests**: Verify only Hotel PMS resources using
   `uv run cdk synth HotelPmsApiStack`
2. **Bedrock Construct Tests**: Verify proper L1 construct usage using CDK synth
3. **Stack Integration**: Verify both constructs work together in the stack
   without conflicts

### Integration Tests

1. **End-to-End Database Setup**: Test complete deployment with both databases
   (requires deployed resources)
2. **Vector Store Integration**: Verify Knowledge Base can connect and query (no
   mocking)
3. **Functional Testing**: Focus on core functionality rather than edge cases

### Deployment Strategy

1. **Fast Deployment**: Use
   `pnpm exec nx run infra:deploy:hotel-pms --no-rollback` for quick turnaround
2. **CDK Synth Validation**: Validate constructs before deployment
3. **Functional Verification**: Test core operations after deployment

## Implementation Details

### L1 Construct Configuration

The Knowledge Base will use L1 constructs directly to avoid conflicts with the
generative AI CDK constructs that try to manage their own database setup:

```python
# Use L1 constructs for full control over Knowledge Base configuration
knowledge_base = aws_bedrock.CfnKnowledgeBase(
    self,
    "HotelKnowledgeBase",
    name="hotel-knowledge-base",
    description="Knowledge base for hotel information with vector search",
    role_arn=bedrock_service_role.role_arn,
    knowledge_base_configuration=aws_bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
        type="VECTOR",
        vector_knowledge_base_configuration=aws_bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
            embedding_model_arn="arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
        )
    ),
    storage_configuration=aws_bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
        type="RDS",
        rds_configuration=aws_bedrock.CfnKnowledgeBase.RdsConfigurationProperty(
            resource_arn=aurora_cluster.cluster_arn,
            credentials_secret_arn=bedrock_credentials_secret.secret_arn,
            database_name="bedrock_vector_db",
            table_name="bedrock_kb",
            field_mapping=aws_bedrock.CfnKnowledgeBase.RdsFieldMappingProperty(
                primary_key_field="id",
                vector_field="embedding",
                text_field="chunks",
                metadata_field="metadata",
                custom_metadata_field="custom_metadata"
            )
        )
    )
)

# Create data source using L1 construct
data_source = aws_bedrock.CfnDataSource(
    self,
    "HotelDataSource",
    knowledge_base_id=knowledge_base.attr_knowledge_base_id,
    name="hotel-documents",
    description="Hotel documents and information",
    data_source_configuration=aws_bedrock.CfnDataSource.DataSourceConfigurationProperty(
        type="S3",
        s3_configuration=aws_bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
            bucket_arn=documents_bucket.bucket_arn,
            inclusion_prefixes=["hotel-data/"]
        )
    ),
    vector_ingestion_configuration=aws_bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
        chunking_configuration=aws_bedrock.CfnDataSource.ChunkingConfigurationProperty(
            chunking_strategy="SEMANTIC",
            semantic_chunking_configuration=aws_bedrock.CfnDataSource.SemanticChunkingConfigurationProperty(
                max_tokens=300,
                buffer_size=1,
                breakpoint_percentile_threshold=95
            )
        )
    )
)
```

### Custom Resource Separation

Two separate Lambda functions will handle database setup:

1. **Hotel PMS Custom Resource**:
   - Uses hotel_pms database credentials
   - Sets up hotel_pms database schema
   - Loads Hotel PMS seed data
   - **Note**: Can be restored using `git checkout` for the following files:
     - `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/db_custom_resource.py`
     - `packages/hotel-pms-lambda/hotel_pms_lambda/handlers/db_setup.py`
     - `packages/hotel-pms-lambda/tests/test_db_custom_resource_integration.py`
     - `packages/hotel-pms-lambda/tests/test_db_setup.py`

2. **Bedrock Custom Resource** (New):
   - Uses bedrock_vector_db database credentials
   - Sets up bedrock_vector_db database and schema
   - Creates bedrock_service user
   - Enables pgvector extension

### Security Group Configuration

```python
# Aurora construct - simplified security groups
lambda_security_group = ec2.SecurityGroup(
    vpc=vpc,
    description="Lambda functions accessing Aurora",
    allow_all_outbound=True
)

# Bedrock construct - Bedrock-specific security group
bedrock_security_group = ec2.SecurityGroup(
    vpc=vpc,
    description="Bedrock Knowledge Base access to Aurora",
    allow_all_outbound=False
)

# Allow both to access Aurora
db_security_group.add_ingress_rule(
    peer=lambda_security_group,
    connection=ec2.Port.tcp(5432)
)
db_security_group.add_ingress_rule(
    peer=bedrock_security_group,
    connection=ec2.Port.tcp(5432)
)
```

## Migration Strategy

### Phase 1: Clean Slate Deployment

Since the stack has been deleted, we can implement the correct architecture from
the start:

1. Deploy Aurora construct with only Hotel PMS resources
2. Deploy Bedrock Knowledge Base construct with its own resources
3. Deploy both custom resources to set up respective databases
4. Verify both systems work independently

### Phase 2: Validation

1. Test Hotel PMS API functionality with hotel_pms database
2. Test Bedrock Knowledge Base with bedrock_vector_db database
3. Verify credential separation and rotation
4. Validate vector store operations

## Monitoring and Observability

### Logging Strategy

1. **Structured Logging**: Use Lambda Powertools for consistent log format
2. **Error Context**: Include database name and operation type in error logs
3. **Custom Resource Logging**: Track success/failure of both custom resources
4. **Functional Logging**: Log key operations without performance timing

## Security Considerations

### Credential Isolation

1. **Separate Secrets**: Hotel PMS and Bedrock use different secrets
2. **Independent Rotation**: Each system rotates credentials independently
3. **Least Privilege**: Each service role has minimal required permissions
4. **Database Isolation**: PostgreSQL database-level separation

### Network Security

1. **VPC Isolation**: Both systems use same VPC but different security groups
2. **Database Access**: Aurora cluster allows both systems but with different
   credentials
3. **S3 Access**: Bedrock service role has access only to documents bucket
4. **IAM Boundaries**: Clear separation of IAM permissions between systems

## Performance Considerations

### Database Performance

1. **Connection Pooling**: Each system manages its own connection pools
2. **Index Optimization**: Vector indexes optimized for Bedrock queries
3. **Query Isolation**: Hotel PMS queries don't affect vector operations
4. **Scaling**: Aurora Serverless scales based on combined load

### Vector Store Performance

1. **HNSW Index**: Optimized for vector similarity search
2. **GIN Index**: Fast JSONB metadata filtering for hotel-specific queries
3. **Chunking Strategy**: Semantic chunking for better retrieval quality
4. **Embedding Dimensions**: 1024 dimensions for Titan v2 model

This design provides a clean separation of concerns while maintaining the
functionality of both the Hotel PMS and Bedrock Knowledge Base systems.
