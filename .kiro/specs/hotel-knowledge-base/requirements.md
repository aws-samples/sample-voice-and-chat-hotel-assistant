# Hotel Knowledge Base Requirements

## Overview

Create a Bedrock Knowledge Base backed by Aurora PostgreSQL with pgvector to
provide AI-powered search and retrieval capabilities for hotel information
across multiple properties in the Paraíso Luxury Group chain.

## Business Requirements

### Core Functionality

- **Multi-Hotel Support**: Support 4 hotels using a single Knowledge Base
  resource and vector table with metadata-based filtering for scalability
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

- **Vector Store**: Aurora PostgreSQL Serverless v2 with pgvector extension
- **Knowledge Base**: Amazon Bedrock Knowledge Base with Titan embeddings
- **Data Source**: S3 bucket with organized hotel documents
- **CDK Implementation**: Use L3 constructs from
  `cdklabs-generative-ai-cdk-constructs` (already installed)
- **Existing Integration**: Extend current Aurora construct in the project

### Data Organization

- **Source Format**: Markdown files with accompanying metadata JSON files
- **Metadata Structure**: Hotel ID, document type, language, category, last
  updated
- **S3 Structure**: Organized by hotel with proper prefixes for data source
  filtering
- **Chunking Strategy**: Semantic chunking for better context preservation

### Performance Requirements

- **Scalability**: Support concurrent queries across multiple hotels
- **Availability**: 99.9% uptime leveraging Aurora Serverless auto-scaling
- **Cost Optimization**: Serverless scaling to minimize costs during low usage

### Security Requirements

- **Access Control**: IAM-based permissions for Bedrock service access
- **Data Encryption**: Encryption at rest and in transit
- **Network Security**: VPC isolation for Aurora cluster
- **Secrets Management**: Database credentials stored in AWS Secrets Manager

## Functional Requirements

### Knowledge Base Operations

- **Document Ingestion**: Automated ingestion of hotel documents with metadata
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

- **AgentCore Gateway**: Primary integration point for accessing knowledge base
  functionality
- **Chat Interface**: Conversational AI interactions through AgentCore Gateway

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
- **Indexing**: HNSW indexing for efficient vector similarity search

## Quality Requirements

### Accuracy

- **Relevance**: 90%+ relevance for hotel-specific queries
- **Attribution**: Proper source attribution for all responses
- **Consistency**: Consistent responses across similar queries
- **Completeness**: Comprehensive coverage of hotel information

### Performance

- **Scalability**: Auto-scale with demand using Aurora Serverless
- **Reliability**: 99.9% availability with automatic failover

### Maintainability

- **Documentation**: Comprehensive documentation for operations
- **Monitoring**: CloudWatch metrics and logging
- **Updates**: Easy process for updating hotel content
- **Versioning**: Track changes to knowledge base content

## Constraints

### Technical Constraints

- **AWS Region**: Must deploy in us-east-1 for Bedrock model availability
- **Existing Infrastructure**: Must integrate with existing Aurora cluster
- **CDK Version**: Compatible with current CDK version in project
- **Python Version**: Python 3.13+ for Lambda functions

### Business Constraints

- **Budget**: Optimize for cost using Serverless technologies

- **Resources**: Single developer implementation
- **Compliance**: Follow existing security and compliance standards

### Data Constraints

- **Language**: Primary content in Spanish
- **Format**: Markdown source files only
- **Size**: Approximately 28 documents, estimated 100KB total
- **Updates**: Manual update process initially

## Success Criteria

### Functional Success

- [ ] Knowledge base successfully ingests all 28 hotel documents
- [ ] Hotel-specific filtering works correctly for all 4 properties
- [ ] Semantic search returns relevant results with proper ranking
- [ ] Metadata filtering functions properly across all categories
- [ ] Integration with existing Aurora infrastructure is seamless

### Performance Success

- [ ] Aurora Serverless scales appropriately with load
- [ ] Cost remains within projected budget parameters

### Quality Success

- [ ] 90%+ user satisfaction with search relevance
- [ ] Proper source attribution for all responses
- [ ] No data leakage between hotel properties
- [ ] Comprehensive test coverage for all functionality

## Acceptance Criteria

### Infrastructure Deployment

- [ ] Aurora cluster extended with Bedrock integration schema
- [ ] Knowledge base created with proper IAM permissions
- [ ] S3 bucket configured with hotel document organization
- [ ] CDK deployment completes successfully without errors

### Data Ingestion

- [ ] All hotel documents uploaded to S3 with proper structure
- [ ] Metadata files created and associated with each document
- [ ] Knowledge base ingestion completes successfully
- [ ] Vector embeddings generated for all content chunks

### Query Testing

- [ ] Hotel-specific queries return only relevant hotel content
- [ ] Cross-hotel queries work when appropriate
- [ ] Metadata filtering functions correctly
- [ ] Response quality meets accuracy requirements

### Integration Testing

- [ ] Knowledge base integrates with existing AgentCore infrastructure
- [ ] API endpoints function properly
- [ ] Error handling works as expected
- [ ] Monitoring and logging capture all operations

## Risk Assessment

### Technical Risks

- **Aurora Integration Complexity**: Medium risk - existing construct needs
  extension
- **L3 Construct Compatibility**: Low risk - well-documented constructs
- **Performance at Scale**: Low risk - Aurora Serverless handles scaling
  automatically
- **Data Quality**: Low risk - controlled source data

### Mitigation Strategies

- **Incremental Development**: Build and test components incrementally
- **Comprehensive Testing**: Unit and integration testing
- **Monitoring**: Extensive monitoring and alerting
- **Documentation**: Detailed documentation for maintenance

## Dependencies

### External Dependencies

- **AWS Bedrock**: Titan embedding model availability
- **Aurora PostgreSQL**: pgvector extension support
- **CDK Constructs**: L3 constructs package availability
- **S3 Storage**: Reliable S3 service for document storage

### Internal Dependencies

- **Existing Aurora**: Current Aurora construct and cluster
- **AgentCore**: Integration with existing AgentCore infrastructure
- **Hotel Data**: Availability and quality of source hotel documents
- **Development Environment**: Proper CDK and Python setup

## Deliverables

### Code Deliverables

- [ ] Extended Aurora construct with Bedrock integration
- [ ] Hotel Knowledge Base CDK construct
- [ ] Data preparation and upload scripts
- [ ] Custom resource for database schema setup
- [ ] Integration tests and validation scripts

### Documentation Deliverables

- [ ] Architecture documentation
- [ ] Deployment guide
- [ ] API documentation
- [ ] Operations runbook
- [ ] Troubleshooting guide

### Infrastructure Deliverables

- [ ] Deployed Knowledge Base with Aurora backend
- [ ] S3 bucket with organized hotel documents
- [ ] IAM roles and policies
- [ ] CloudWatch monitoring and alerting
- [ ] Backup and recovery procedures
