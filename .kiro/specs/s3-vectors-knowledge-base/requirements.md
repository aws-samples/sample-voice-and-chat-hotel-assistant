# Hotel Knowledge Base Requirements (S3 Vectors)

## Overview

Create a Bedrock Knowledge Base using S3 vectors preview feature to provide
AI-powered search and retrieval capabilities for hotel information across
multiple properties in the Paraíso Luxury Group chain.

The S3 vectors approach simplifies deployment by eliminating the need for vector
databases like Aurora PostgreSQL with pgvector or OpenSearch, making it more
cost-effective and easier to manage for demonstration purposes.

**Architectural Context:**

- This knowledge base is part of the **Hotel PMS Stack** (customer-replaceable
  reference implementation)
- Demonstrates how customers can create knowledge bases for their own
  documentation
- The Hotel Assistant MCP Server (spec #5) will query this knowledge base
- Customers can replace with their own knowledge bases while keeping the core
  Virtual Assistant infrastructure

## Business Requirements

### Core Functionality

- **Multi-Hotel Support**: Support 4 hotels using a single Knowledge Base
  resource with metadata-based filtering for scalability
- **Hotel-Specific Filtering**: Enable queries to be filtered by specific hotel
  ID to provide contextually relevant responses
- **Comprehensive Content**: Include all hotel information (general info, rooms,
  amenities, policies, etc.)
- **Metadata-Rich Search**: Support filtering by document type, language,
  category, and hotel-specific attributes

### Hotels to Support

1. **Paraíso Vallarta Resort & Spa** (H-PVR-002)
2. **Paraíso Tulum Eco-Luxury Resort** (H-PTL-003)
3. **Paraíso Los Cabos Desert & Ocean Resort** (H-PLC-004)
4. **Grand Paraíso Resort & Spa** (H-GPR-001)

### Content Categories

- General hotel information and identity
- Location and contact details
- Room types and suites
- Dining and gastronomy
- Facilities and amenities
- Policies and services
- Operations and performance metrics

## Technical Requirements

### Infrastructure

- **Vector Store**: S3 vectors preview feature (no separate vector database
  needed)
- **Knowledge Base**: Amazon Bedrock Knowledge Base with Titan embeddings v2
- **Data Source**: S3 bucket with organized hotel documents
- **CDK Implementation**: Custom resource for S3 vectors preview feature
- **Simplified Architecture**: No VPC, no Aurora, no OpenSearch required

### Data Organization

- **Source Format**: Markdown files with accompanying metadata JSON files
- **Metadata Structure**: Hotel ID, document type, language, category, last
  updated
- **S3 Structure**: Organized by hotel with proper prefixes for data source
  filtering
- **Chunking Strategy**: Semantic chunking for better context preservation
  (300-500 tokens)

### Performance Requirements

- **Scalability**: Support concurrent queries across multiple hotels
- **Availability**: 99.9% uptime leveraging S3 and Bedrock managed services
- **Cost Optimization**: No vector database costs, only S3 storage and Bedrock
  API calls

### Security Requirements

- **Access Control**: IAM-based permissions for Bedrock service access to S3
- **Data Encryption**: S3 encryption at rest using AWS managed keys
- **Network Security**: No VPC required (fully managed services)
- **Secrets Management**: No database credentials needed

## Functional Requirements

### Knowledge Base Operations

- **Document Ingestion**: Automated ingestion of hotel documents with metadata
  from S3
- **Vector Search**: Semantic search across hotel content with relevance scoring
- **Metadata Filtering**: Filter results by hotel ID, document type, language
- **Content Retrieval**: Return relevant chunks with source attribution
- **Multi-Hotel Queries**: Support queries across all hotels or specific subsets

### Query Capabilities

- **Hotel-Specific**: "What room types are available at Paraíso Vallarta?"
- **Cross-Hotel**: "Compare spa services across all Paraíso properties"
- **Category-Specific**: "Show me dining options" (with hotel context)
- **Policy Queries**: "What is the cancellation policy for Tulum?"
- **Amenity Search**: "Which hotels have infinity pools?"

### Integration Points

- **Hotel Assistant MCP Server**: Primary integration point for accessing
  knowledge base functionality
- **AgentCore Runtime**: MCP server deployed on AgentCore Runtime
- **Virtual Assistant**: Chat and voice agents query through MCP server

## Data Requirements

### Source Data Location

- **Path**: `hotel_data/hotel-knowledge-base/`
- **Structure**: 4 hotel directories with 7 markdown files each
- **Total Files**: 28 markdown documents + metadata files
- **Languages**: Spanish (primary content language)

### Metadata Schema

```json
{
  "metadataAttributes": {
    "hotel_id": "H-PVR-002",
    "hotel_name": "Paraíso Vallarta Resort & Spa",
    "document_type": "informacion-general",
    "language": "es",
    "category": "general-info",
    "last_updated": "2024-01-15"
  }
}
```

### Content Processing

- **Chunking**: Semantic chunking with 300-500 token chunks
- **Embeddings**: Amazon Titan Text Embeddings v2 (1024 dimensions)
- **Parsing**: Foundation model parsing for enhanced document understanding
- **Indexing**: S3 vectors storage with metadata for filtering

## Glossary

- **Bedrock_Knowledge_Base**: AWS service for semantic search over documents
  using foundation models
- **S3_Vectors**: Preview feature allowing vector storage directly in S3 without
  separate vector database
- **Vector_Embeddings**: Numerical representations of text for semantic
  similarity search (1024 dimensions for Titan v2)
- **Embedding_Model**: Amazon Titan Text Embeddings v2 for converting text to
  vectors
- **Data_Source**: S3 bucket containing hotel documentation files (markdown
  format)
- **Chunking_Strategy**: Semantic chunking with 300-500 token segments
- **Custom_Resource**: CloudFormation custom resource for S3 vectors preview
  feature configuration
- **Metadata_Filtering**: Filtering by hotel_id, document_type, language, and
  category

## Requirements

### Requirement 1: S3 Data Source Configuration

**User Story:** As a system administrator, I want to store hotel documentation
in S3, so that the knowledge base can ingest and index the content for semantic
search.

#### Acceptance Criteria

1. THE System SHALL create an S3 bucket for hotel documentation storage
2. THE S3_Bucket SHALL store documentation in markdown format with metadata JSON
   files
3. THE S3_Bucket SHALL organize documentation by hotel with logical prefixes
   (H-PVR-002, H-PTL-003, etc.)
4. THE S3_Bucket SHALL enable versioning for document change tracking
5. THE System SHALL grant Bedrock Knowledge Base read access to the S3 bucket

### Requirement 2: Bedrock Knowledge Base with S3 Vectors

**User Story:** As a developer, I want to create a Bedrock Knowledge Base with
S3 vectors, so that AI agents can perform semantic search over hotel
documentation without managing a vector database.

#### Acceptance Criteria

1. THE System SHALL create a Bedrock Knowledge Base using S3 vectors preview
   feature
2. THE Knowledge_Base SHALL use Titan Text Embeddings v2 model for vector
   generation
3. THE Knowledge_Base SHALL configure S3 as the data source with proper IAM
   permissions
4. THE Knowledge_Base SHALL use custom resource for S3 vectors preview feature
   configuration
5. THE System SHALL return the knowledge base ID and ARN for MCP server
   integration

### Requirement 3: Multi-Hotel Support with Metadata Filtering

**User Story:** As an AI agent, I want to query hotel information with
hotel-specific filtering, so that I can provide contextually relevant responses
for each property.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL support metadata filtering by hotel_id for
   hotel-specific queries
2. THE Knowledge_Base SHALL support filtering by document_type (general,
   amenities, policies, etc.)
3. THE Knowledge_Base SHALL support filtering by language (es for Spanish)
4. THE Knowledge_Base SHALL support filtering by category for content
   organization
5. THE Knowledge_Base SHALL support cross-hotel queries WHEN no hotel filter is
   specified

### Requirement 4: Document Chunking and Ingestion

**User Story:** As a content manager, I want documents automatically chunked
into searchable segments, so that AI agents can retrieve relevant information
efficiently.

#### Acceptance Criteria

1. THE System SHALL configure semantic chunking with 300-500 token segments
2. THE Chunking_Strategy SHALL preserve document metadata (hotel_id,
   document_type, etc.) in chunks
3. THE System SHALL handle documents up to 50,000 tokens in length
4. THE Ingestion_Process SHALL generate vector embeddings for all document
   chunks
5. THE Ingestion_Process SHALL store vectors in S3 using the preview feature

### Requirement 5: CDK S3 Vectors Package Integration

**User Story:** As a DevOps engineer, I want to use the existing
`cdk-s3-vectors` package for S3 vectors configuration, so that the preview
feature can be deployed through CDK without custom resources.

#### Acceptance Criteria

1. THE System SHALL use the `cdk-s3-vectors` package for S3 vectors and
   knowledge base configuration
2. THE CDK_Construct SHALL leverage existing L3 constructs from the package
3. THE System SHALL handle CREATE, UPDATE, and DELETE operations through the
   package
4. THE System SHALL include proper IAM permissions for Bedrock and S3 access
5. THE System SHALL return knowledge base ID, ARN, and data source ID as outputs

### Requirement 6: CDK Construct Integration

**User Story:** As a developer, I want a reusable CDK construct for S3 vectors
knowledge base, so that I can easily deploy hotel documentation search
capabilities.

#### Acceptance Criteria

1. THE CDK_Construct SHALL use `cdk-s3-vectors` package for S3 bucket, vector
   index, and knowledge base
2. THE CDK_Construct SHALL configure data source pointing to
   `hotel-knowledge-base/` prefix in S3
3. THE CDK_Construct SHALL expose knowledge base ID, ARN, and data source ID as
   stack outputs
4. THE CDK_Construct SHALL manage IAM roles for Bedrock and S3 access
5. THE CDK_Construct SHALL support stack updates without data loss

### Requirement 7: Query Performance and Accuracy

**User Story:** As an AI agent, I want fast and accurate semantic search over
hotel documentation, so that I can provide relevant information to users.

#### Acceptance Criteria

1. THE Knowledge_Base SHALL return query results within 2 seconds for 95% of
   queries
2. THE Knowledge_Base SHALL return top 5 most relevant document chunks per query
3. THE Knowledge_Base SHALL include relevance scores for each result
4. THE Knowledge_Base SHALL support natural language queries in Spanish and
   English
5. THE Knowledge_Base SHALL achieve 90%+ relevance for hotel-specific queries

### Requirement 8: Deployment and Validation

**User Story:** As a QA engineer, I want automated validation of the knowledge
base deployment, so that I can verify semantic search functionality after
deployment.

#### Acceptance Criteria

1. THE System SHALL validate knowledge base creation using `cdk synth`
2. THE System SHALL verify S3 vectors storage configuration after `cdk deploy`
3. THE System SHALL use existing `upload_and_ingest_documents.py` script to
   upload all 28 hotel documents
4. THE System SHALL validate query functionality with test queries for each
   hotel
5. THE System SHALL provide clear error messages for deployment failures

### Requirement 9: Security and Compliance

**User Story:** As a security engineer, I want the knowledge base to follow AWS
security best practices, so that hotel documentation is protected.

#### Acceptance Criteria

1. THE System SHALL encrypt S3 bucket at rest using AWS managed keys
2. THE System SHALL use least-privilege IAM roles for Bedrock and S3 access
3. THE System SHALL enable S3 bucket logging for audit trails
4. THE System SHALL not expose sensitive information in knowledge base responses
5. THE System SHALL implement proper error handling without exposing internal
   details

### Requirement 10: Existing Scripts Compatibility

**User Story:** As a developer, I want to reuse existing hotel documentation
scripts, so that I don't need to rewrite document management tooling.

#### Acceptance Criteria

1. THE System SHALL work with existing `generate_metadata.py` script without
   modifications
2. THE System SHALL work with existing `upload_and_ingest_documents.py` script
   without modifications
3. THE System SHALL expose CloudFormation outputs matching script expectations
   (HotelDocumentsBucketName, HotelKnowledgeBaseId, HotelDataSourceId)
4. THE System SHALL support the same S3 prefix structure
   (`hotel-knowledge-base/{hotel-name}/`)
5. THE System SHALL maintain compatibility with existing metadata JSON format

### Requirement 11: Cost Optimization

**User Story:** As a system administrator, I want cost-effective knowledge base
deployment, so that demonstration costs remain minimal.

#### Acceptance Criteria

1. THE System SHALL eliminate vector database costs by using S3 vectors
2. THE System SHALL use S3 Standard storage class for hotel documentation
3. THE System SHALL minimize Bedrock API calls through efficient query design
4. THE System SHALL provide cost estimates for S3 storage and Bedrock usage
5. THE System SHALL support easy cleanup through stack deletion

## Success Criteria

### Functional Success

- [ ] Knowledge base successfully ingests all 28 hotel documents
- [ ] Hotel-specific filtering works correctly for all 4 properties
- [ ] Semantic search returns relevant results with proper ranking
- [ ] Metadata filtering functions properly across all categories
- [ ] S3 vectors storage configured successfully

### Performance Success

- [ ] Query response time under 2 seconds for 95% of queries
- [ ] Cost remains within projected budget parameters (no vector database costs)

### Quality Success

- [ ] 90%+ relevance for hotel-specific queries
- [ ] Proper source attribution for all responses
- [ ] No data leakage between hotel properties
- [ ] Comprehensive validation through cdk synth and deploy

## Acceptance Criteria

### Infrastructure Deployment

- [ ] S3 bucket created with hotel document organization
- [ ] Knowledge base created with S3 vectors configuration
- [ ] Custom resource deployed for preview feature
- [ ] CDK deployment completes successfully without errors

### Data Ingestion

- [ ] All hotel documents uploaded to S3 with proper structure
- [ ] Metadata files created and associated with each document
- [ ] Knowledge base ingestion completes successfully
- [ ] Vector embeddings generated and stored in S3

### Query Testing

- [ ] Hotel-specific queries return only relevant hotel content
- [ ] Cross-hotel queries work when appropriate
- [ ] Metadata filtering functions correctly
- [ ] Response quality meets accuracy requirements

### Integration Testing

- [ ] Knowledge base integrates with Hotel Assistant MCP Server (spec #5)
- [ ] Query API functions properly
- [ ] Error handling works as expected
- [ ] Monitoring and logging capture all operations

## Constraints

### Technical Constraints

- **AWS Region**: Must deploy in us-east-1 for Bedrock model availability
- **S3 Vectors**: Preview feature requires custom resource implementation
- **CDK Version**: Compatible with current CDK version in project
- **Python Version**: Python 3.13+ for Lambda functions

### Business Constraints

- **Budget**: Optimize for cost using S3 vectors (no vector database costs)
- **Timeline**: Single developer implementation
- **Compliance**: Follow existing security and compliance standards

### Data Constraints

- **Language**: Primary content in Spanish
- **Format**: Markdown source files with metadata JSON
- **Size**: Approximately 28 documents, estimated 100KB total
- **Updates**: Manual update process initially

## Dependencies

### External Dependencies

- **AWS Bedrock**: Titan embedding model and S3 vectors preview feature
  availability
- **S3 Storage**: Reliable S3 service for document and vector storage
- **CDK Constructs**: AwsCustomResource for preview feature configuration

### Internal Dependencies

- **Hotel Documentation**: Availability and quality of source hotel documents in
  `hotel_data/hotel-knowledge-base/`
- **Hotel Assistant MCP Server**: Integration point for knowledge base queries
  (spec #5)
- **Development Environment**: Proper CDK and Python setup

## Deliverables

### Code Deliverables

- [ ] S3 vectors knowledge base CDK construct
- [ ] Custom resource for S3 vectors preview feature
- [ ] Data upload scripts for hotel documentation
- [ ] Validation scripts using cdk synth and deploy

### Documentation Deliverables

- [ ] Architecture documentation
- [ ] Deployment guide
- [ ] Query API documentation
- [ ] Operations runbook

### Infrastructure Deliverables

- [ ] Deployed Knowledge Base with S3 vectors backend
- [ ] S3 bucket with organized hotel documents
- [ ] IAM roles and policies
- [ ] CloudWatch monitoring and logging
