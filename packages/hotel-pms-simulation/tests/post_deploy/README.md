# Post-Deployment Integration Tests

This directory contains integration tests that run against deployed AWS
infrastructure.

## Test Files

### `test_mcp_runtime_integration.py`

Tests the deployed MCP Server on Amazon Bedrock AgentCore Runtime, including:

- Authentication with Amazon Cognito
- Listing available MCP tools
- Retrieving chat prompts with hotel context
- Querying knowledge base for restaurants (all hotels and specific hotel)
- Verifying authentication requirements

### `test_mcp_server_integration.py`

Tests the MCP server's knowledge base query functionality:

- General hotel information queries
- Hotel-specific filtering
- Topic-specific queries (dining, activities)
- Relevance scoring and result ordering
- Prompt generation with Amazon DynamoDB data

## Prerequisites

1. **Deployed Infrastructure**

   ```bash
   pnpm exec nx run infra:deploy:hotel-pms
   ```

2. **AWS Credentials**

   ```bash
   aws configure --profile your-profile
   export AWS_PROFILE=your-profile
   ```

3. **Cognito Client Credentials** (for MCP Runtime tests)
   - The MCP server uses OAuth2 client credentials flow
   - Set the client secret as an environment variable:
     ```bash
     export COGNITO_CLIENT_SECRET="your-client-secret"
     ```
   - The client secret can be retrieved from AWS Secrets Manager or Cognito
     console

4. **Knowledge Base Synced**
   - Upload hotel documentation to the S3 bucket
   - Sync the knowledge base data source

## Running Tests

### Run All Integration Tests

```bash
cd packages/hotel-pms-simulation
uv run pytest tests/post_deploy/ -v -s -m integration
```

### Run Specific Test File

```bash
# MCP Runtime tests
uv run pytest tests/post_deploy/test_mcp_runtime_integration.py -v -s -m integration

# MCP Server tests
uv run pytest tests/post_deploy/test_mcp_server_integration.py -v -s -m integration
```

### Run Specific Test

```bash
uv run pytest tests/post_deploy/test_mcp_runtime_integration.py::TestMCPRuntimeDeployment::test_get_chat_prompt -v -s
```

## Environment Variables

Tests automatically retrieve configuration from AWS CloudFormation stack outputs:

- `STACK_NAME` - CloudFormation stack name (default: `HotelPmsStack`)
- `KNOWLEDGE_BASE_ID` - Auto-configured from stack outputs
- `HOTELS_TABLE_NAME` - Auto-configured from stack outputs
- Other DynamoDB table names - Auto-configured from stack outputs

## Test Output

Tests provide detailed output including:

- ✅ Success indicators with details
- ⚠️ Warning messages for missing resources
- 📊 Result counts and scores
- 📝 Content previews

Example output:

```
✅ Found MCP Server Runtime: hotel_assistant_mcp
   Runtime URL: https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/...
✅ Obtained Cognito token
✅ Found 1 tools
   - query_hotel_knowledge: Query hotel documentation and information
✅ Chat prompt retrieved successfully
   Prompt length: 2543 characters
   Hotels found: 4
   Hotel IDs: ['H-PVR-002', 'H-TUL-001', 'H-CAB-003', 'H-CUN-004']
```

## Troubleshooting

### Authentication Errors

**Cognito Client Secret Required**: The tests use OAuth2 client credentials flow
to authenticate with the MCP server. You must set the `COGNITO_CLIENT_SECRET`
environment variable:

```bash
export COGNITO_CLIENT_SECRET="your-client-secret"
```

To retrieve the client secret:

1. From AWS Secrets Manager (if stored there)
2. From Cognito User Pool App Client settings in AWS Console
3. From the infrastructure deployment outputs

**Common Issues**:

- Missing `COGNITO_CLIENT_SECRET`: Tests will skip if not set
- Invalid client secret: Will result in 401 Unauthorized errors
- Expired tokens: The tests automatically request new tokens for each session
- Missing Cognito domain: Ensure the User Pool has a domain configured

### MCP Server Not Found

- Verify HotelPmsStack is deployed
- Check CloudFormation outputs contain `MCPServerRuntimeArn`
- Ensure deployment completed successfully

### Knowledge Base Errors

- Verify knowledge base is synced
- Check that documents are uploaded to S3
- Ensure knowledge base data source is active

### DynamoDB Errors

- Verify DynamoDB tables are created
- Check that seed data is loaded
- Ensure AWS Lambda has permissions to access tables

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  env:
    AWS_REGION: us-east-1
    STACK_NAME: HotelPmsStack
  run: |
    cd packages/hotel-pms-simulation
    uv run pytest tests/post_deploy/ -v -m integration
```

## Test Coverage

Current test coverage includes:

- ✅ MCP Server deployment verification
- ✅ Cognito authentication
- ✅ Tool listing and discovery
- ✅ Prompt retrieval with hotel context
- ✅ Knowledge base queries (all hotels)
- ✅ Knowledge base queries (specific hotel)
- ✅ Authentication enforcement
- ✅ Hotel context generation
- ✅ Prompt template rendering
- ✅ Result relevance scoring
- ✅ Metadata validation
