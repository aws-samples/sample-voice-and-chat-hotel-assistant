# Hotel PMS AWS Lambda Tests

This directory contains unit and integration tests for the Hotel PMS Lambda API.

## Test Types

### Unit Tests

- Test business logic without external dependencies
- Use mocked database connections
- Run by default with `uv run pytest`

### Integration Tests

- Test against deployed AWS infrastructure
- Require Amazon API Gateway, Lambda, and Aurora database to be deployed
- Marked with `@pytest.mark.integration` and `@pytest.mark.aws`

## Running Tests

### Unit Tests Only

```bash
uv run pytest
# or
uv run pytest -m "not integration"
```

### Integration Tests Only

```bash
uv run pytest -m integration
# or
nx run hotel-pms-simulation:test:api-integration
```

### All Tests

```bash
uv run pytest -m ""
```

### Specific Test File

```bash
uv run pytest tests/test_api_integration.py -v
```

## Prerequisites for Integration Tests

1. **Deployed Infrastructure**: The HotelPmsStack must be deployed
2. **AWS Credentials**: Configure AWS credentials with appropriate permissions
3. **Environment Variables** (optional):
   - `STACK_NAME`: AWS CloudFormation stack name (default: "HotelPmsStack")
   - `AWS_REGION`: AWS region (default: "us-east-1")

## Integration Test Coverage

The integration tests cover:

- **API Health**: Basic connectivity and health checks
- **Authentication**: IAM authentication requirements
- **Availability**: Room availability checking and pricing
- **Reservations**: Full reservation lifecycle (create, read, update)
- **Guest Services**: Checkout and housekeeping requests
- **Error Handling**: Invalid inputs and edge cases
- **Data Consistency**: Business logic validation

## Test Data

Integration tests use:

- Dynamic test data with timestamps to avoid conflicts
- Real hotel data from the seeded database
- Future dates to avoid booking conflicts
- Cleanup mechanisms where possible

## Troubleshooting

### Common Issues

1. **Stack Not Found**: Ensure the CloudFormation stack is deployed
2. **Permission Denied**: Check AWS credentials and IAM permissions
3. **API Gateway 403**: Verify IAM authentication is working
4. **Test Timeouts**: Some tests may take time due to database operations

### Debug Mode

```bash
uv run pytest tests/test_api_integration.py -v -s --log-cli-level=DEBUG
```
