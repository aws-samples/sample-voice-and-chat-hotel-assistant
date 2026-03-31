# Hotel Knowledge Base Scripts

This directory contains scripts for managing the Hotel Knowledge Base system.

## Scripts

### `generate_metadata.py`

Generates `.metadata.json` files for all hotel documents in the knowledge base.

**Usage:**

```bash
python hotel_data/scripts/generate_metadata.py
```

**What it does:**

- Processes all markdown files in `hotel-knowledge-base/`
- Creates corresponding `.metadata.json` files with hotel-specific metadata
- Includes hotel ID, document type, language, and category information
- Required for Bedrock Knowledge Base hotel-specific filtering

### `upload_and_ingest_documents.py`

Uploads all hotel documents and metadata files to S3 and triggers Knowledge Base
ingestion.

**Usage:**

```bash
# Upload and ingest documents
python hotel_data/scripts/upload_and_ingest_documents.py

# Dry run (show what would be done without doing it)
python hotel_data/scripts/upload_and_ingest_documents.py --dry-run

# Use different stack name
python hotel_data/scripts/upload_and_ingest_documents.py --stack-name MyHotelStack

# Force upload all files (skip incremental check)
python hotel_data/scripts/upload_and_ingest_documents.py --force-upload

# Set custom timeout for ingestion monitoring
python hotel_data/scripts/upload_and_ingest_documents.py --timeout 45
```

**What it does:**

1. Gets S3 bucket name and Knowledge Base ID from AWS CloudFormation outputs
2. Uploads only new or changed documents and metadata files to S3 (incremental
   upload)
3. Triggers Knowledge Base data source sync
4. Monitors ingestion progress and validates completion

**Incremental Upload:**

- By default, only uploads files that have changed (compares file timestamps)
- Skips unchanged files to save time and bandwidth
- Use `--force-upload` to upload all files regardless of changes

**Requirements:**

- AWS CLI configured with appropriate permissions
- Hotel PMS API Stack deployed successfully
- Hotel documents and metadata files generated (run `generate_metadata.py`
  first)

**Expected CloudFormation Outputs:**

- `KnowledgeBaseId` or `HotelKnowledgeBaseId`
- `DataSourceId` or `HotelDataSourceId`
- `DocumentsBucketName` or `HotelDocumentsBucketName`

### `test_upload_script.py`

Tests the upload script logic without requiring AWS infrastructure.

**Usage:**

```bash
python hotel_data/scripts/test_upload_script.py
```

**What it does:**

- Validates file discovery logic
- Checks that all expected hotels and documents are found
- Verifies metadata files exist for all markdown files
- Useful for testing before actual deployment

## Workflow

1. **Generate metadata files:**

   ```bash
   python hotel_data/scripts/generate_metadata.py
   ```

2. **Deploy infrastructure:**

   ```bash
   pnpm exec nx run infra:deploy:hotel-pms --no-rollback
   ```

3. **Upload and ingest documents:**

   ```bash
   python hotel_data/scripts/upload_and_ingest_documents.py
   ```

4. **Test the Knowledge Base:**
   - Use Amazon Bedrock AgentCore Gateway to query the Knowledge Base
   - Test hotel-specific filtering
   - Verify search results are relevant and accurate

## File Structure

The scripts expect the following file structure:

```
hotel_data/hotel-knowledge-base/
├── paraiso-vallarta/
│   ├── informacion-general.md
│   ├── informacion-general.md.metadata.json
│   ├── habitaciones-suites.md
│   ├── habitaciones-suites.md.metadata.json
│   └── ... (7 documents + metadata each)
├── paraiso-tulum/
├── paraiso-los-cabos/
└── grand-paraiso-resort-spa/
```

Each hotel should have:

- 7 markdown documents
- 7 corresponding metadata files
- Total: 28 documents + 28 metadata files = 56 files

## Troubleshooting

### Common Issues

1. **Stack not deployed:**

   ```
   Error: Stack HotelPmsApiStack is not in a complete state
   ```

   **Solution:** Deploy the infrastructure first using
   `pnpm exec nx run infra:deploy:hotel-pms`

2. **Missing CloudFormation outputs:**

   ```
   Error: Could not find KnowledgeBaseId output in stack
   ```

   **Solution:** Ensure the Knowledge Base construct is properly deployed and
   exports the required outputs

3. **AWS credentials not configured:**

   ```
   Error: AWS credentials not configured
   ```

   **Solution:** Run `aws configure` or set AWS environment variables

4. **Ingestion timeout:**
   ```
   Error: Ingestion timed out after 30 minutes
   ```
   **Solution:** Use `--timeout 60` to increase timeout, or check CloudWatch
   logs for ingestion issues

### Debugging

- Use `--dry-run` to see what would be uploaded without actually doing it
- Check CloudWatch logs for the Knowledge Base ingestion job
- Verify S3 bucket contents after upload
- Test file discovery with `python hotel_data/scripts/test_upload_script.py`

## Security

- All files are uploaded with server-side encryption (AES256)
- S3 bucket access is restricted to Amazon Bedrock service role
- AWS credentials should follow least-privilege principle
- Metadata files may contain hotel-specific information - ensure proper access
  controls
