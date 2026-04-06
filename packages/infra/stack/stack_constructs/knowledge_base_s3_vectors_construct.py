# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Knowledge Base Construct using S3 Vectors.

This construct creates a Bedrock Knowledge Base using native CloudFormation L1 constructs
for cost-effective vector storage without requiring a separate vector database.
"""

from aws_cdk import Names, Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3vectors as s3vectors
from cdk_nag import NagSuppressions
from constructs import Construct

from .s3_constructs import PACEBucket


class VectorBucket(Construct):
    """Construct for S3 Vector Bucket - stores vectors only."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create vector bucket with auto-generated name
        self.bucket = s3vectors.CfnVectorBucket(
            self,
            "Bucket",
            # VectorBucketName omitted for auto-generation
            encryption_configuration=s3vectors.CfnVectorBucket.EncryptionConfigurationProperty(sse_type="AES256"),
        )

    @property
    def bucket_arn(self) -> str:
        """Get the vector bucket ARN."""
        return self.bucket.attr_vector_bucket_arn


class VectorIndex(Construct):
    """
    Construct for Vector Index.

    Creates a vector index for similarity search with configurable non-filterable metadata.
    All metadata keys defined in document metadata are filterable by default (e.g., hotel_id,
    document_type). Only specify non_filterable_metadata_keys for metadata that should be
    stored but not used for filtering.

    Args:
        scope: The scope in which to define this construct
        construct_id: The scoped construct ID
        vector_bucket_arn: ARN of the vector bucket
        non_filterable_metadata_keys: List of metadata key names that should NOT be filterable.
                                     These keys can be retrieved but cannot be used in query filters.
                                     Leave empty (default) to make all metadata keys filterable.
                                     Example: ["description", "raw_content"]
        **kwargs: Additional keyword arguments
    """

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


class BedrockKnowledgeBase(Construct):
    """Construct for Bedrock Knowledge Base."""

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
        # QueryVectors and GetVectors are both required for Bedrock Knowledge Base queries
        # GetVectors is needed when metadata filters are used or when returning metadata
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3vectors:GetIndex",
                    "s3vectors:QueryVectors",
                    "s3vectors:GetVectors",
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
        embedding_model_arn = f"arn:aws:bedrock:{stack.region}::foundation-model/amazon.titan-embed-text-v2:0"

        # Grant invoke model permission for the embedding model
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[embedding_model_arn],
            )
        )
        # Generate unique knowledge base name using CDK Names utility
        kb_name = Names.unique_resource_name(
            self,
            max_length=64,
            separator="-",
            allowed_special_characters="",
        )

        # Create Knowledge Base with unique name
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name=kb_name,
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

        # Ensure Knowledge Base waits for IAM role policies to be attached
        # This prevents "not authorized" errors during Knowledge Base creation
        self.knowledge_base.node.add_dependency(self.role)

    @property
    def knowledge_base_id(self) -> str:
        """Get the Knowledge Base ID."""
        return self.knowledge_base.attr_knowledge_base_id

    @property
    def knowledge_base_arn(self) -> str:
        """Get the Knowledge Base ARN."""
        return self.knowledge_base.attr_knowledge_base_arn


class DataSource(Construct):
    """Construct for Bedrock Data Source pointing to document bucket."""

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

        # Generate unique data source name using CDK Names utility
        data_source_name = Names.unique_resource_name(
            self,
            max_length=64,
            separator="-",
            allowed_special_characters="",
        )

        # Create data source with unique name
        self.data_source = bedrock.CfnDataSource(
            self,
            "DataSource",
            knowledge_base_id=knowledge_base_id,
            name=data_source_name,
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


class KnowledgeBase(Construct):
    """
    Construct for creating a Bedrock Knowledge Base with S3 Vectors.

    This construct creates:
    - S3 Vector Bucket for document and vector storage
    - Vector Index with Titan Embeddings v2 (1024 dimensions)
    - Bedrock Knowledge Base with metadata filtering support
    - S3 Data Source for documents

    The S3 vectors approach eliminates the need for Aurora PostgreSQL or OpenSearch,
    making it more cost-effective and easier to manage for demonstration purposes.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        non_filterable_metadata_keys: list[str] | None = None,
        s3_prefix: str = "knowledge-base/",
        description: str = "Knowledge base using S3 Vectors for cost-effective document storage and retrieval",
        **kwargs,
    ):
        """
        Initialize Knowledge Base construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            non_filterable_metadata_keys: List of metadata key names that should NOT be filterable.
                                         All metadata keys in document metadata are filterable by default
                                         (e.g., hotel_id, document_type, language, category).
                                         Only specify keys here that should be stored but not filtered.
                                         Example: ["description", "raw_content"]
            s3_prefix: S3 prefix for document storage (default: "knowledge-base/")
            description: Description for the knowledge base
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 Document Bucket for source documents (regular S3 bucket)
        self.document_bucket = PACEBucket(
            self,
            "DocumentBucket",
            lifecycle_rules=[],
        )

        # Create S3 Vector Bucket for vector storage (S3 Vectors bucket)
        self.vector_bucket = VectorBucket(self, "VectorBucket")

        # Create Vector Index
        # All metadata keys in documents are filterable by default
        # Only specify non_filterable_metadata_keys for keys that should not be filtered
        self.vector_index = VectorIndex(
            self,
            "VectorIndex",
            vector_bucket_arn=self.vector_bucket.bucket_arn,
            non_filterable_metadata_keys=non_filterable_metadata_keys,
        )

        # Add dependency to ensure proper creation order
        self.vector_index.node.add_dependency(self.vector_bucket)

        # Create Bedrock Knowledge Base
        self.bedrock_kb = BedrockKnowledgeBase(
            self,
            "KnowledgeBase",
            vector_bucket_arn=self.vector_bucket.bucket_arn,
            index_arn=self.vector_index.index_arn,
            description=description,
        )

        # Add dependency to ensure proper creation order
        self.bedrock_kb.node.add_dependency(self.vector_index)

        # Create S3 Data Source pointing to document bucket
        self.data_source = DataSource(
            self,
            "DataSource",
            knowledge_base_id=self.bedrock_kb.knowledge_base_id,
            document_bucket_arn=self.document_bucket.bucket_arn,
            s3_prefix=s3_prefix,
        )

        # Grant Knowledge Base role access to document bucket
        self.document_bucket.grant_read(self.bedrock_kb.role)

        # Add CDK Nag suppressions for IAM wildcard permissions on the document bucket access
        # This must be done after grant_read() creates the DefaultPolicy
        NagSuppressions.add_resource_suppressions(
            self.bedrock_kb.role.node.find_child("DefaultPolicy"),
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions required for S3 Vectors operations (QueryIndex, PutVectors, "
                    "DeleteVectors) and document bucket read access. These are scoped to specific vector index "
                    "and bucket ARNs.",
                }
            ],
        )

    @property
    def bucket_name(self) -> str:
        """Get the S3 document bucket name where source documents are stored."""
        return self.document_bucket.bucket_name

    @property
    def bucket_arn(self) -> str:
        """Get the S3 document bucket ARN."""
        return self.document_bucket.bucket_arn

    @property
    def vector_bucket_arn(self) -> str:
        """Get the S3 vector bucket ARN."""
        return self.vector_bucket.bucket_arn

    @property
    def knowledge_base_id(self) -> str:
        """Get the Knowledge Base ID."""
        return self.bedrock_kb.knowledge_base_id

    @property
    def knowledge_base_arn(self) -> str:
        """Get the Knowledge Base ARN."""
        return self.bedrock_kb.knowledge_base_arn

    @property
    def data_source_id(self) -> str:
        """Get the Data Source ID."""
        return self.data_source.data_source_id

    @property
    def index_arn(self) -> str:
        """Get the Vector Index ARN."""
        return self.vector_index.index_arn
