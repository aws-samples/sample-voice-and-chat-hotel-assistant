# Knowledge Base Native CloudFormation Migration - Requirements

## Overview

Migrate the Knowledge Base S3 Vectors construct from using the third-party
`cdk_s3_vectors` package to native AWS CloudFormation L1 constructs.
CloudFormation now natively supports Bedrock Knowledge Bases with S3 Vectors,
eliminating the need for custom resources.

## Background

The current implementation in
`packages/infra/stack/stack_constructs/knowledge_base_s3_vectors_construct.py`
uses the `cdk_s3_vectors` package which provides custom CloudFormation resources
via Lambda-backed custom resources. AWS CloudFormation now provides native L1
constructs for:

- `AWS::S3Vectors::VectorBucket` - Vector storage bucket
- `AWS::S3Vectors::Index` - Vector index for similarity search
- `AWS::Bedrock::KnowledgeBase` with `S3VectorsConfiguration` - Knowledge base
  integration

This is a breaking change that will require redeployment. The migration
simplifies the infrastructure by using CloudFormation's auto-generated resource
names and eliminating custom resource handlers. CDK 2.233.0 provides full
support for these native constructs.

## User Stories

### 1. As a DevOps Engineer

**I want** the infrastructure to use native CloudFormation resources instead of
custom resources  
**So that** deployments are more reliable, faster, and easier to troubleshoot

**Acceptance Criteria:**

- 1.1 All custom resources from `cdk_s3_vectors` package are replaced with
  native L1 constructs
- 1.2 No Lambda-backed custom resource handlers are deployed
- 1.3 CloudFormation stack uses only native AWS resource types
- 1.4 Deployment time is reduced by eliminating custom resource Lambda cold
  starts

### 2. As a Developer

**I want** simplified construct implementation using native CloudFormation
resources  
**So that** the code is easier to maintain and understand

**Acceptance Criteria:**

- 2.1 All resource names use CloudFormation auto-generated names (no manual
  naming)
- 2.2 Constructor parameters remain compatible: `non_filterable_metadata_keys`,
  `s3_prefix`, `description`
- 2.3 Public properties provide access to resource ARNs and IDs
- 2.4 CDK Nag suppressions are updated for native constructs only

### 3. As a Security Engineer

**I want** proper IAM permissions and encryption configurations  
**So that** the knowledge base follows security best practices

**Acceptance Criteria:**

- 3.1 Vector bucket uses AES256 encryption by default
- 3.2 Knowledge base role has least-privilege permissions
- 3.3 Document bucket access is properly scoped
- 3.4 All CDK Nag security checks pass

### 4. As a Platform Engineer

**I want** clean infrastructure deployment with auto-generated names  
**So that** resource management is simplified and follows AWS best practices

**Acceptance Criteria:**

- 4.1 All resources use CloudFormation auto-generated names
- 4.2 Resource dependencies are properly configured
- 4.3 Stack can be deployed and destroyed cleanly
- 4.4 No manual resource naming or CDK Names utility usage

## Technical Requirements

### Native CloudFormation Resources

#### Vector Bucket (AWS::S3Vectors::VectorBucket)

- **Properties:**
  - `VectorBucketName`: Omit to use CloudFormation auto-generated name
  - `EncryptionConfiguration`: AES256 encryption
- **Outputs:**
  - `VectorBucketArn`: ARN of the vector bucket (via `attr_vector_bucket_arn`)
  - `CreationTime`: Timestamp of creation (via `attr_creation_time`)

#### Vector Index (AWS::S3Vectors::Index)

- **Properties:**
  - `VectorBucketArn`: Reference to vector bucket ARN
  - `IndexName`: Omit to use CloudFormation auto-generated name
  - `DataType`: "float32" (only supported type)
  - `Dimension`: 1024 (Titan Embeddings v2)
  - `DistanceMetric`: "cosine" for semantic search
  - `MetadataConfiguration`: Optional, for non-filterable metadata keys
- **Outputs:**
  - `IndexArn`: ARN of the vector index (via `attr_index_arn`)
  - `CreationTime`: Timestamp of creation (via `attr_creation_time`)

#### Knowledge Base (AWS::Bedrock::KnowledgeBase)

- **Storage Configuration:**
  - `Type`: "S3_VECTORS"
  - `S3VectorsConfiguration`:
    - `VectorBucketArn`: Reference to vector bucket ARN
    - `IndexArn`: Reference to vector index ARN
- **Embedding Model:**
  - `amazon.titan-embed-text-v2:0` (1024 dimensions)
- **Name:** Omit to use CloudFormation auto-generated name

#### Data Source (AWS::Bedrock::DataSource)

- **Configuration:**
  - `Type`: "S3"
  - `S3Configuration`: Document bucket and prefix
  - `ChunkingStrategy`: "SEMANTIC" with semantic chunking configuration
- **Name:** Omit to use CloudFormation auto-generated name

### Dependencies

- Remove `cdk-s3-vectors>=0.3.0` from `packages/infra/pyproject.toml`
- Use only native CDK constructs from:
  - `aws_cdk.aws_s3vectors` (CfnVectorBucket, CfnIndex)
  - `aws_cdk.aws_bedrock` (CfnKnowledgeBase, CfnDataSource)
  - `aws_cdk.aws_s3` (for document bucket)
  - `aws_cdk.aws_iam` (for IAM roles and policies)

### Naming Strategy

- Use CloudFormation auto-generated names for all resources (omit name
  properties)
- CloudFormation ensures uniqueness and proper naming conventions
- No manual naming or CDK Names utility required

### Error Handling

- Proper dependency ordering with `node.add_dependency()`
- Validation of required parameters
- Clear error messages for configuration issues

## Non-Functional Requirements

### Performance

- Deployment time should be faster than custom resource approach
- No Lambda cold start delays during stack operations

### Maintainability

- Code should be simpler without custom resource handlers
- CDK Nag suppressions should be minimal and well-documented
- Clear comments explaining CloudFormation resource mappings

### Compatibility

- Must work with CDK version 2.233.0
- Must support Python 3.13
- Breaking change: requires redeployment of knowledge base resources

## Out of Scope

- Changes to knowledge base functionality or behavior
- Backward compatibility with existing deployments (breaking change)
- In-place migration of existing knowledge bases
- Changes to document ingestion or retrieval logic
- Performance tuning of vector search parameters

## Success Metrics

1. **Deployment Speed**: Stack deployment completes 30%+ faster
2. **Code Simplicity**: 50%+ reduction in lines of code (no custom resources)
3. **Security**: All CDK Nag checks pass
4. **Simplicity**: Zero custom resource handlers, all CloudFormation
   auto-generated names

## References

- [AWS::S3Vectors::VectorBucket CloudFormation Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3vectors-vectorbucket.html)
- [AWS::S3Vectors::Index CloudFormation Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3vectors-index.html)
- [AWS::Bedrock::KnowledgeBase S3VectorsConfiguration](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-bedrock-knowledgebase-s3vectorsconfiguration.html)
- [AWS CDK Python aws_s3vectors Module](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_s3vectors.html)
- [AWS CDK Python aws_bedrock Module](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock.html)
