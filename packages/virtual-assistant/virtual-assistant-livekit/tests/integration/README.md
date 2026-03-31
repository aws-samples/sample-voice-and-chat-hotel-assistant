# LiveKit Agent Integration Tests

This directory contains integration tests for the refactored LiveKit Hotel
Assistant agent. These tests validate the complete agent functionality with real
external services.

## Test Coverage

The integration tests cover the following requirements:

### Agent Prewarm Function (Requirements 3.1, 3.2, 3.3)

- **3.1**: Fresh MCP connections per session in prewarm function
- **3.2**: Hotel data fetching for dynamic prompt generation
- **3.3**: Hotel-specific instructions generation

### MCP Server Integration (Requirements 1.1, 1.2)

- **1.1**: Custom MCPServer subclass integration with hotel_pms_mcp_client
- **1.2**: LiveKit automatic tool loading from MCP server

### Tool Execution (Requirements 2.1, 2.2, 2.3)

- **2.1**: Voice request handling for room availability
- **2.2**: Voice request handling for hotel amenities
- **2.3**: Voice request handling for housekeeping

## Prerequisites

### Required Environment Variables

Create a `.env` file in the package root with the following configuration:

```bash
# Hotel PMS MCP Server Configuration
HOTEL_PMS_MCP_URL=https://your-agentcore-gateway-url.com
HOTEL_PMS_MCP_USER_POOL_ID=us-east-1_xxxxxxxxx
HOTEL_PMS_MCP_CLIENT_ID=your-cognito-client-id
HOTEL_PMS_MCP_CLIENT_SECRET=your-cognito-client-secret

# AWS Configuration
AWS_REGION=us-east-1

# LiveKit Configuration (optional - for full agent testing)
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret
LIVEKIT_URL=wss://your-livekit-server.com

# Agent Configuration
MODEL_TEMPERATURE=0.0
```

### External Services Required

1. **AWS Amazon Cognito User Pool**: For MCP authentication
2. **Amazon Bedrock AgentCore Gateway**: Deployed MCP server with Hotel PMS tools
3. **Hotel PMS AWS Lambda**: Backend service with hotel data
4. **LiveKit Server** (optional): For full agent session testing

## Running Integration Tests

### Run All Integration Tests

```bash
# From the package root
uv run pytest tests/integration/ -v -m integration
```

### Run Specific Test Categories

```bash
# Test prewarm function only
uv run pytest tests/integration/test_agent_integration.py::TestAgentIntegration::test_prewarm_function_with_real_mcp_server -v

# Test MCP server creation only
uv run pytest tests/integration/test_agent_integration.py::TestAgentIntegration::test_hotel_pms_mcp_server_creation -v

# Test tool execution only
uv run pytest tests/integration/test_agent_integration.py::TestAgentIntegration::test_tool_execution_through_mcp_integration -v
```

### Run with Detailed Output

```bash
# Show detailed test output and logging
uv run pytest tests/integration/ -v -s -m integration --log-cli-level=INFO
```

## Test Behavior

### Success Scenarios

When all external services are available and properly configured:

- ✅ All tests should pass
- ✅ Hotel data should be fetched successfully
- ✅ Dynamic instructions should be generated
- ✅ MCP tools should be available and executable

### Failure Scenarios (Expected)

The integration tests are designed to **fail** when external resources are
unavailable:

#### Missing Configuration

```bash
# Tests will be skipped with clear message
SKIPPED [1] tests/integration/conftest.py:45: Integration test skipped: Missing required environment variables: ['url', 'user_pool_id', 'client_id', 'client_secret']
```

#### Invalid Configuration

- Tests will fail with authentication errors
- Tests will fail with connection errors
- This is the expected behavior to ensure tests detect real issues

#### Service Unavailable

- MCP server unreachable → Connection failures
- Cognito authentication fails → Auth errors
- Hotel PMS service down → Tool execution failures

## Test Structure

### `test_agent_integration.py`

Main integration test file containing:

1. **`test_prewarm_function_with_real_mcp_server`**
   - Tests the agent prewarm function with real MCP connectivity
   - Verifies hotel data fetching and instruction generation

2. **`test_hotel_data_fetching_and_dynamic_prompt_generation`**
   - Tests direct hotel data fetching via MCP
   - Verifies dynamic prompt generation with and without hotel data

3. **`test_hotel_pms_mcp_server_creation`**
   - Tests HotelPmsMCPServer creation and stream generation
   - Verifies MCP tool discovery and availability

4. **`test_tool_execution_through_mcp_integration`**
   - Tests actual MCP tool execution
   - Covers hotel info, availability, and reservation tools

5. **`test_agent_session_creation_with_mcp_server`**
   - Tests agent session setup with MCP server integration
   - Verifies LiveKit agent can use MCP servers

6. **`test_error_handling_and_graceful_degradation`**
   - Tests graceful handling of MCP failures
   - Verifies fallback behavior when services are unavailable

7. **`test_integration_must_fail_if_external_resources_unavailable`**
   - Verifies that tests properly detect missing/invalid configuration
   - Ensures integration tests fail when they should

### `conftest.py`

Test configuration providing:

- Environment variable loading from `.env` file
- Configuration fixtures for MCP and LiveKit settings
- Automatic test skipping when required config is missing

## Debugging Integration Tests

### Common Issues

1. **Tests Skipped**: Missing environment variables
   - Solution: Create `.env` file with required configuration

2. **Authentication Failures**: Invalid Cognito credentials
   - Solution: Verify user pool ID, client ID, and client secret

3. **Connection Failures**: MCP server unreachable
   - Solution: Verify AgentCore Gateway URL and network connectivity

4. **Tool Execution Failures**: Backend service issues
   - Solution: Verify Hotel PMS Lambda deployment and database setup

### Debug Commands

```bash
# Run with maximum verbosity and logging
uv run pytest tests/integration/ -vvv -s -m integration --log-cli-level=DEBUG

# Run single test with full output
uv run pytest tests/integration/test_agent_integration.py::TestAgentIntegration::test_prewarm_function_with_real_mcp_server -vvv -s --log-cli-level=DEBUG

# Check environment variable loading
python -c "
import os
from dotenv import load_dotenv
load_dotenv('.env')
print('MCP URL:', os.getenv('HOTEL_PMS_MCP_URL'))
print('User Pool:', os.getenv('HOTEL_PMS_MCP_USER_POOL_ID'))
"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync
        working-directory: packages/virtual-assistant/virtual-assistant-livekit

      - name: Run integration tests
        env:
          HOTEL_PMS_MCP_URL: ${{ secrets.HOTEL_PMS_MCP_URL }}
          HOTEL_PMS_MCP_USER_POOL_ID: ${{ secrets.HOTEL_PMS_MCP_USER_POOL_ID }}
          HOTEL_PMS_MCP_CLIENT_ID: ${{ secrets.HOTEL_PMS_MCP_CLIENT_ID }}
          HOTEL_PMS_MCP_CLIENT_SECRET:
            ${{ secrets.HOTEL_PMS_MCP_CLIENT_SECRET }}
          AWS_REGION: us-east-1
        run: uv run pytest tests/integration/ -v -m integration
        working-directory: packages/virtual-assistant/virtual-assistant-livekit
```

## Best Practices

1. **Environment Isolation**: Use separate test environments
2. **Test Data**: Use dedicated test hotel data that won't affect production
3. **Timeouts**: Set appropriate timeouts for network operations
4. **Error Handling**: Verify both success and failure scenarios
5. **Resource Cleanup**: Ensure tests don't leave resources in inconsistent
   state
6. **Documentation**: Keep test documentation updated with infrastructure
   changes
