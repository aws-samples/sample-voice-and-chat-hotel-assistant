# Hotel PMS Seed Data

This directory contains CSV files with seed data for the Hotel PMS Amazon DynamoDB
tables.

## Architecture

The Hotel PMS uses **DynamoDB native CSV import** for automated data loading
during infrastructure deployment. This eliminates the need for custom AWS Lambda
functions or AWS CloudFormation custom resources.

## Files

### Static Data (Imported via DynamoDB)

These CSV files are automatically imported into DynamoDB tables during CDK
deployment:

- **`hotels.csv`** - Hotel property information (4 hotels)
- **`room_types.csv`** - Room type definitions with pricing
- **`rate_modifiers.csv`** - Seasonal and special rate adjustments

### Dynamic Data (Runtime Only)

The following tables exist but are populated at runtime, not from CSV files:

- **reservations** - Guest reservations (created via API)
- **requests** - Housekeeping and service requests (created via API)
- **quotes** - Temporary price quotes with TTL (created via API)

## How It Works

1. **CDK Synthesis**: CSV files are uploaded to S3 as CDK assets
2. **DynamoDB Import**: Tables are created with `import_source` pointing to S3
3. **Automatic Loading**: DynamoDB natively imports data during stack deployment
4. **No Custom Code**: Pure infrastructure-as-code, no Lambda functions needed

## Deployment

Data is automatically loaded when you deploy the infrastructure:

```bash
pnpm exec nx deploy infra
```

The import happens during CloudFormation stack creation. No manual steps
required.

## Updating Data

To update the seed data:

1. Edit the CSV files in this directory
2. Redeploy the infrastructure stack
3. DynamoDB will reimport the updated data

## Data Format

All CSV files use standard comma-separated format with headers:

- Date fields: ISO format (YYYY-MM-DD)
- Timestamps: ISO format with time (YYYY-MM-DD HH:MM:SS)
- Prices: Decimal format (e.g., 150.00)

## References

- CDK Construct:
  `packages/infra/stack/stack_constructs/hotel_pms_dynamodb_construct.py`
- Documentation: `documentation/cloudformation-custom-resources.md`
