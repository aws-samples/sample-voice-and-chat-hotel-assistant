# Hotel Knowledge Base Design Document

## Architecture Overview

The Hotel Knowledge Base system provides AI-powered search and retrieval
capabilities for hotel information across the Paraíso Luxury Group chain. The
system uses a single Amazon Bedrock Knowledge Base with Aurora PostgreSQL as the
vector store, enabling semantic search with metadata-based hotel filtering for
scalability.

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Hotel Data    │    │   S3 Document    │    │   Bedrock Knowledge │
│   (Markdown)    │───▶│     Bucket       │───▶│       Base          │
│                 │    │                  │    │                     │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   AgentCore     │    │   Lambda Query   │    │   Aurora PostgreSQL │
│   Gateway       │◀───│    Handler       │◀───│   + pgvector        │
│                 │    │                  │    │                     │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

## Component Design

### 1. Aurora PostgreSQL Vector Store

#### Database Schema Extension

```sql
-- Bedrock integration schema
CREATE SCHEMA bedrock_integration;

-- Knowledge base table
CREATE TABLE bedrock_integration.bedrock_kb (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    embedding VECTOR(1024),  -- Titan v2 embeddings
    chunks TEXT NOT NULL,
    metadata JSON NOT NULL,
    custom_metadata JSONB    -- Hotel-specific filtering
);

-- Indexes for performance
CREATE INDEX bedrock_kb_vector_idx
ON bedrock_integration.bedrock_kb
USING hnsw (embedding vector_cosine_ops)
WITH (ef_construction=256);

CREATE INDEX bedrock_kb_metadata_idx
ON bedrock_integration.bedrock_kb
USING gin (custom_metadata);  -- GIN index supports JSONB filtering
```

#### Aurora Construct Extension

```python
class AuroraConstruct(Construct):
    def setup_bedrock_integration(self):
        """Configure Aurora for Bedrock Knowledge Base"""
        # Enable RDS Data API
        # Create Bedrock service user
        # Set up schema and permissions
        # Configure pgvector extension
```

### 2. Bedrock Knowledge Base

#### Knowledge Base Configuration

```python
from cdklabs.generative_ai_cdk_constructs import bedrock
from cdklabs.generative_ai_cdk_constructs.amazonaurora import AmazonAuroraVectorStore

class HotelKnowledgeBaseConstruct(Construct):
    def __init__(self, scope, construct_id, aurora_cluster):
        # Aurora vector store
        self.vector_store = AmazonAuroraVectorStore(
            self, "HotelAuroraVectorStore",
            embeddings_model_vector_dimension=1024,
            cluster_identifier=aurora_cluster.cluster_identifier,
            database_name="hotel_pms",
            table_name="bedrock_integration.bedrock_kb",
            primary_key_field="id",
            vector_field="embedding",
            text_field="chunks",
            metadata_field="metadata",
            custom_metadata_field="custom_metadata"
        )

        # Single Knowledge Base for all hotels - scalable architecture
        # Hotel filtering is handled via metadata, not separate Knowledge Bases
        self.knowledge_base = bedrock.VectorKnowledgeBase(
            self, "HotelKnowledgeBase",
            name="hotel-assistant-kb",
            embeddings_model=bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V2_1024,
            vector_store=self.vector_store,
            instruction="Answer hotel questions with hotel-specific context using metadata filtering"
        )
```

### 3. Data Sources and Organization

#### S3 Document Structure

```
hotel-documents-bucket/
├── hotel-knowledge-base/
│   ├── paraiso-vallarta/
│   │   ├── informacion-general.md
│   │   ├── informacion-general.md.metadata.json
│   │   ├── habitaciones-suites.md
│   │   ├── habitaciones-suites.md.metadata.json
│   │   └── ...
│   ├── paraiso-tulum/
│   ├── paraiso-los-cabos/
│   └── grand-paraiso-resort-spa/
```

#### Data Source Configuration

```python
def add_hotel_data_source(self):
    """Create single data source for all hotels"""
    # Single data source includes all hotels - metadata filtering handles hotel-specific queries
    bedrock.S3DataSource(
        self, "HotelDataSource",
        bucket=self.documents_bucket,
        knowledge_base=self.knowledge_base,
        data_source_name="hotel-documents",
        inclusion_prefixes=["hotel-knowledge-base/"],  # Include all hotel directories
        chunking_strategy=bedrock.ChunkingStrategy.SEMANTIC
        # Using default parsing strategy - documents are already in Markdown
    )
```

### 4. Metadata Schema Design

#### Document Metadata Structure

```json
{
  "metadataAttributes": {
    "hotel_id": "H-PVR-002",
    "hotel_name": "Paraíso Vallarta Resort & Spa",
    "document_type": "informacion-general",
    "language": "es",
    "category": "general-info",
    "last_updated": "2024-01-15",
    "content_sections": ["identity", "mission", "staff"],
    "target_audience": "guests"
  }
}
```

#### Metadata Field Mapping

| Field           | Purpose                   | Query Use Case             |
| --------------- | ------------------------- | -------------------------- |
| `hotel_id`      | Hotel identification      | Filter by specific hotel   |
| `hotel_name`    | Human-readable hotel name | Display and context        |
| `document_type` | Content category          | Filter by information type |
| `language`      | Content language          | Language-specific queries  |
| `category`      | Broad content grouping    | Categorical filtering      |
| `last_updated`  | Content freshness         | Prioritize recent content  |

### 5. Query Processing Design

#### Query Flow

```
User Query → AgentCore Gateway → Lambda Handler → Bedrock Knowledge Base → Aurora Vector Search → Ranked Results
```

#### Query Handler Implementation

```python
class KnowledgeBaseQueryHandler:
    def __init__(self, knowledge_base_id: str):
        self.bedrock_agent = boto3.client('bedrock-agent-runtime')
        self.knowledge_base_id = knowledge_base_id

    def query_hotel_specific(self, query: str, hotel_id: str) -> dict:
        """Query with hotel-specific filtering - returns all results for client to handle"""
        return self.bedrock_agent.retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'filter': {
                        'equals': {
                            'key': 'hotel_id',
                            'value': hotel_id
                        }
                    }
                }
            }
        )

    def query_multi_hotel(self, query: str, hotel_ids: List[str] = None) -> dict:
        """Query across multiple hotels - if hotel_ids is None or empty, queries all hotels"""
        filter_config = None
        if hotel_ids:  # Only filter if hotel_ids is provided and not empty
            filter_config = {
                'vectorSearchConfiguration': {
                    'filter': {
                        'in': {
                            'key': 'hotel_id',
                            'value': hotel_ids
                        }
                    }
                }
            }

        return self.bedrock_agent.retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={'text': query},
            retrievalConfiguration=filter_config or {}
        )
                    }
                }
            }
        )
```

## Data Processing Pipeline

### 1. Local Metadata Generation Script

```python
# scripts/generate_metadata.py - Run locally once to generate metadata files
import os
import json
from datetime import datetime

def generate_metadata_files(source_path: str):
    """Generate metadata files for all hotel documents - run once locally"""
    hotel_mapping = {
        "paraiso-vallarta": "H-PVR-002",
        "paraiso-tulum": "H-PTL-003",
        "paraiso-los-cabos": "H-PLC-004",
        "grand-paraiso-resort-spa": "H-GPR-001"
    }

    for hotel_dir in os.listdir(source_path):
        if hotel_dir not in hotel_mapping:
            continue

        hotel_path = os.path.join(source_path, hotel_dir)
        hotel_id = hotel_mapping[hotel_dir]

        for file in os.listdir(hotel_path):
            if file.endswith('.md'):
                metadata = {
                    "metadataAttributes": {
                        "hotel_id": hotel_id,
                        "hotel_name": format_hotel_name(hotel_dir),
                        "document_type": file.replace('.md', ''),
                        "language": "es",
                        "category": categorize_document(file),
                        "last_updated": datetime.now().isoformat()
                    }
                }

                # Write metadata file
                metadata_file = os.path.join(hotel_path, f"{file}.metadata.json")
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    generate_metadata_files("hotel_data/hotel-knowledge-base")
```

### 2. Chunking Strategy

```python
# Semantic chunking configuration
chunking_strategy = bedrock.ChunkingStrategy.semantic(
    buffer_size=1,  # Sentences to include around breakpoints
    breakpoint_percentile_threshold=95,  # Sensitivity to semantic breaks
    max_tokens=400  # Maximum chunk size
)
```

### 3. Embedding Configuration

```python
# Titan Text Embeddings v2 configuration
embeddings_model = bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V2_1024
# - 1024 dimensions
# - Supports Spanish language
# - Optimized for semantic search
```

## Security Design

### 1. IAM Permissions

```python
# Bedrock service role permissions
bedrock_role_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "rds-data:BatchExecuteStatement",
                "rds-data:BeginTransaction",
                "rds-data:CommitTransaction",
                "rds-data:ExecuteStatement",
                "rds-data:RollbackTransaction"
            ],
            "Resource": aurora_cluster.cluster_arn
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": aurora_cluster.secret.secret_arn
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                documents_bucket.bucket_arn,
                f"{documents_bucket.bucket_arn}/*"
            ]
        }
    ]
}
```

### 2. Network Security

```python
# Aurora security group for Bedrock access
bedrock_security_group = ec2.SecurityGroup(
    self, "BedrockSecurityGroup",
    vpc=vpc,
    description="Security group for Bedrock Knowledge Base access to Aurora",
    allow_all_outbound=False
)

# Allow Bedrock service access to Aurora
aurora_security_group.add_ingress_rule(
    peer=bedrock_security_group,
    connection=ec2.Port.tcp(5432),
    description="Allow Bedrock Knowledge Base access to Aurora"
)
```

### 3. Data Encryption

- **Aurora**: Encryption at rest using AWS managed keys
- **S3**: Server-side encryption with S3 managed keys
- **Secrets Manager**: Automatic encryption of database credentials
- **Transit**: TLS encryption for all data in transit

## Performance Optimization

### 1. Vector Index Optimization

```sql
-- HNSW index with optimized parameters
CREATE INDEX bedrock_kb_vector_idx
ON bedrock_integration.bedrock_kb
USING hnsw (embedding vector_cosine_ops)
WITH (
    ef_construction=256,  -- Build-time parameter for accuracy
    m=16                  -- Number of connections per node
);
```

### 2. Aurora Serverless Configuration

```python
# Aurora Serverless v2 scaling configuration
aurora_cluster = rds.DatabaseCluster(
    self, "AuroraCluster",
    engine=rds.DatabaseClusterEngine.aurora_postgres(
        version=rds.AuroraPostgresEngineVersion.VER_15_4
    ),
    serverless_v2_min_capacity=0.5,  # Minimum ACUs
    serverless_v2_max_capacity=16,   # Maximum ACUs
    # Auto-scaling based on CPU and connections
)
```

## Monitoring and Observability

### 1. Structured Logging

```python
import logging
from aws_lambda_powertools import Logger

# For Lambda functions - use Lambda Powertools
logger = Logger()

# For scripts - use Python builtin logging with structured data
def log_query_event(query: str, hotel_id: str, results_count: int, duration: float):
    logging.info(
        "Knowledge base query completed",
        extra={
            "query": query,
            "hotel_id": hotel_id,
            "results_count": results_count,
            "duration_ms": duration * 1000,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

## Testing Strategy

### 1. Unit Tests

```python
class TestKnowledgeBaseQuery:
    def test_hotel_specific_query(self):
        """Test hotel-specific filtering"""
        handler = KnowledgeBaseQueryHandler(kb_id)
        result = handler.query_hotel_specific(
            "What room types are available?",
            "H-PVR-002"
        )

        assert result['hotel_id'] == "H-PVR-002"
        assert 'room types' in result['response'].lower()

    def test_metadata_filtering(self):
        """Test metadata-based filtering"""
        # Test implementation
```

### 2. Integration Tests

```python
class TestKnowledgeBaseIntegration:
    def test_end_to_end_query(self):
        """Test complete query flow"""
        # Upload test document
        # Trigger ingestion
        # Query knowledge base
        # Verify results

    def test_aurora_integration(self):
        """Test Aurora vector store integration"""
        # Test vector storage and retrieval
```

## Deployment Strategy

### 1. Integration with Existing HotelPMSAPI Stack

```python
# Knowledge Base will be added to the existing HotelPmsApiStack
# in packages/infra/stack/hotel_pms_api_stack.py

class HotelPmsApiStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Existing Aurora cluster and other resources...

        # Add Knowledge Base construct
        self.knowledge_base = HotelKnowledgeBaseConstruct(
            self, "HotelKnowledgeBase",
            aurora_cluster=self.aurora_cluster
        )
```

### 2. Deployment Commands

```bash
# Development deployment with no rollback for faster debugging
pnpm exec nx run infra:deploy:hotel-pms --no-rollback

# Production deployment
pnpm exec nx run infra:deploy:hotel-pms

# Generate metadata files (run once locally)
python scripts/generate_metadata.py

# Upload documents to S3
python scripts/upload_hotel_documents.py

# Trigger Knowledge Base ingestion
python scripts/trigger_ingestion.py
```

This design provides a comprehensive, scalable, and maintainable solution for
the Hotel Knowledge Base system, leveraging AWS best practices and the existing
infrastructure. The single Knowledge Base architecture with metadata-based
filtering ensures optimal scalability when adding new hotels to the Paraíso
Luxury Group chain.
