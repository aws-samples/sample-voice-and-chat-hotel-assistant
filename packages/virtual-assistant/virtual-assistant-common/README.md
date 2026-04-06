# Virtual Assistant Common

Shared utilities and components for virtual assistant packages, providing OAuth2
authenticated MCP client functionality and hotel PMS operations.

## Overview

This package contains common code that can be shared between:

- `virtual-assistant-livekit`: LiveKit voice agent implementation
- `virtual-assistant-chat`: Text-based chat interface

### Key Features

- **Multi-MCP Server Support**: Connect to multiple MCP servers simultaneously
  with automatic tool discovery
- **Dynamic Prompt Loading**: Load system prompts from MCP servers with fallback
  chain
- **Amazon Cognito MCP Client**: OAuth2 authenticated streaming HTTP MCP client for
  Amazon Bedrock AgentCore Gateway
- **Hotel PMS Operations**: High-level operations for hotel management system
  integration
- **Configuration Management**: Centralized MCP configuration from AWS Systems
  Manager Parameter Store
- **Structured Error Handling**: Comprehensive exception hierarchy with detailed
  error context

## MCP Configuration

### Configuration Format

The virtual assistant uses a standard MCP configuration format stored in AWS
Systems Manager Parameter Store. This format is compatible with the MCP
specification used by Claude Desktop and other MCP clients, with extensions for
HTTP-based servers.

#### Standard MCP Format with HTTP Extensions

```json
{
  "mcpServers": {
    "hotel-assistant-mcp": {
      "type": "streamable-http",
      "url": "https://hotel-assistant-mcp.execute-api.us-east-1.amazonaws.com",
      "headers": {
        "X-Custom-Header": "value"
      },
      "authentication": {
        "type": "cognito",
        "secretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:hotel-assistant-mcp-creds"
      },
      "systemPrompts": {
        "chat": "chat_system_prompt",
        "voice": "voice_system_prompt"
      }
    },
    "hotel-pms-mcp": {
      "type": "streamable-http",
      "url": "https://hotel-pms-mcp.execute-api.us-east-1.amazonaws.com",
      "authentication": {
        "type": "cognito",
        "secretArn": "arn:aws:secretsmanager:us-east-1:123456789012:secret:hotel-pms-mcp-creds"
      }
    }
  }
}
```

#### Configuration Fields

**Standard MCP Fields:**

- `mcpServers`: Top-level object containing server configurations (required)
- Server name keys: Unique identifiers for each server (e.g.,
  "hotel-assistant-mcp")
- `type`: Transport type - must be "streamable-http" for HTTP-based servers
  (required)
- `headers`: Optional HTTP headers to include in requests (key-value pairs)

**Extension Fields:**

- `url`: HTTP endpoint for the MCP server (required for streamable-http type)
- `authentication`: Authentication configuration (required)
  - `type`: Authentication method - currently only "cognito" is supported
  - `secretArn`: ARN of AWS Secrets Manager secret containing credentials
- `systemPrompts`: Optional configuration for system prompt loading
  - `chat`: Prompt name for chat assistant (defaults to "chat_system_prompt")
  - `voice`: Prompt name for voice assistant (defaults to "voice_system_prompt")

### Adding New MCP Servers

To add a new MCP server to your configuration:

1. **Update the MCP configuration JSON** in your CDK stack:

```python
mcp_config = {
    "mcpServers": {
        # Existing servers...
        "hotel-assistant-mcp": { ... },
        "hotel-pms-mcp": { ... },

        # Add new server
        "my-custom-mcp": {
            "type": "streamable-http",
            "url": "https://my-custom-mcp.execute-api.us-east-1.amazonaws.com",
            "headers": {
                "X-API-Version": "v1"
            },
            "authentication": {
                "type": "cognito",
                "secretArn": self.my_custom_secret.secret_arn
            }
        }
    }
}
```

2. **Create a Secrets Manager secret** for the new server's credentials:

```python
my_custom_secret = secretsmanager.Secret(
    self, "MyCustomMCPSecret",
    secret_object_value={
        "userPoolId": SecretValue.unsafe_plain_text(user_pool_id),
        "clientId": SecretValue.unsafe_plain_text(client_id),
        "clientSecret": SecretValue.unsafe_plain_text(client_secret),
        "region": SecretValue.unsafe_plain_text(self.region)
    }
)
```

3. **Grant permissions** to the virtual assistant roles:

```python
# Grant read access to the new secret
my_custom_secret.grant_read(chat_agent_role)
my_custom_secret.grant_read(voice_agent_role)
```

4. **Deploy the updated stack**:

```bash
pnpm exec nx deploy infra
```

The virtual assistant will automatically discover and connect to the new MCP
server on next initialization.

### Custom HTTP Headers

You can include custom HTTP headers in MCP server requests:

```json
{
  "mcpServers": {
    "my-server": {
      "type": "streamable-http",
      "url": "https://api.example.com",
      "headers": {
        "X-API-Version": "v2",
        "X-Client-ID": "virtual-assistant",
        "Accept": "application/json"
      },
      "authentication": { ... }
    }
  }
}
```

Headers are merged with authentication headers when making requests to the MCP
server.

### System Prompts Configuration

Only one MCP server should provide system prompts. Configure the `systemPrompts`
field to specify which prompts to use:

```json
{
  "mcpServers": {
    "prompt-server": {
      "type": "streamable-http",
      "url": "https://prompts.example.com",
      "authentication": { ... },
      "systemPrompts": {
        "chat": "custom_chat_prompt",
        "voice": "custom_voice_prompt"
      }
    }
  }
}
```

**Prompt Name Fallback Chain:**

1. Configured prompt name (e.g., "custom_chat_prompt")
2. Default prompt name ("chat_system_prompt" or "voice_system_prompt")
3. Generic default ("default_system_prompt")
4. Emergency fallback (hardcoded in code)

## Deploying with Custom MCP Configuration

### Using VirtualAssistantStack

When deploying the virtual assistant infrastructure, pass MCP configuration from
your HotelPmsStack:

```python
from aws_cdk import Stack
from constructs import Construct

class MyAppStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create HotelPmsStack with MCP servers
        hotel_pms_stack = HotelPmsStack(self, "HotelPMS")

        # Create VirtualAssistantStack with MCP configuration
        virtual_assistant_stack = VirtualAssistantStack(
            self, "VirtualAssistant",
            mcp_config_parameter=hotel_pms_stack.mcp_config_parameter,
            mcp_secrets=[
                hotel_pms_stack.hotel_assistant_secret,
                hotel_pms_stack.hotel_pms_secret
            ]
        )
```

### Cross-Stack References

The MCP configuration uses AWS CloudFormation cross-stack references:

1. **HotelPmsStack exports:**
   - MCP configuration parameter name
   - Secret ARNs for each MCP server

2. **VirtualAssistantStack imports:**
   - Reads MCP configuration from Parameter Store
   - Grants access to secrets for authentication

This pattern allows you to:

- Update MCP configuration independently
- Share MCP servers across multiple stacks
- Maintain separation of concerns

### Environment Variables

The virtual assistant requires the following environment variable:

- `MCP_CONFIG_PARAMETER`: Parameter Store path (e.g.,
  "/hotel-assistant/mcp-config")

This is automatically configured by the CDK stack:

```python
chat_agent_function.add_environment(
    "MCP_CONFIG_PARAMETER",
    mcp_config_parameter.parameter_name
)
```

## Configuration and Deployment

### Parameter Store Location

The MCP configuration is stored in AWS Systems Manager Parameter Store at:

```
/hotel-assistant/mcp-config
```

This location is configurable via the `MCP_CONFIG_PARAMETER` environment
variable. The parameter contains the complete MCP configuration JSON as a string
value.

**Parameter Properties:**

- **Type**: String
- **Tier**: Standard
- **Encryption**: Not required (contains only non-sensitive configuration)
- **Access**: Read-only for virtual assistant AWS Lambda functions and ECS tasks

### Authentication Credential Flow

MCP server authentication uses a secure credential flow through AWS Secrets
Manager:

1. **Configuration Reference**: MCP configuration contains `secretArn` pointing
   to Secrets Manager
2. **Runtime Retrieval**: Virtual assistant retrieves credentials at
   initialization
3. **OAuth2 Authentication**: Credentials used for Cognito OAuth2 client
   credentials flow
4. **Token Management**: Access tokens cached and refreshed automatically

**Secrets Manager Secret Format:**

```json
{
  "userPoolId": "us-east-1_XXXXXXXXX",
  "clientId": "abcdefghijklmnopqrstuvwxyz123456",
  "clientSecret": "secret-value-here",
  "region": "us-east-1"
}
```

**Security Benefits:**

- Credentials never stored in code or configuration files
- Automatic credential rotation support
- Fine-grained IAM access control
- Audit logging via CloudTrail

### Environment Variable Requirements

The virtual assistant requires the following environment variables:

#### Required Variables

- `MCP_CONFIG_PARAMETER`: Parameter Store path for MCP configuration
  - Example: `/hotel-assistant/mcp-config`
  - Set automatically by CDK deployment

#### Optional Variables

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
  - Default: `INFO`
  - Set to `DEBUG` for detailed MCP communication logs

- `AWS_REGION`: AWS region for service calls
  - Usually set automatically by Lambda/ECS runtime
  - Override if needed for cross-region deployments

### IAM Permissions Required

The virtual assistant IAM roles need the following permissions:

#### Parameter Store Access

```json
{
  "Effect": "Allow",
  "Action": ["ssm:GetParameter"],
  "Resource": [
    "arn:aws:ssm:us-east-1:123456789012:parameter/hotel-assistant/mcp-config"
  ]
}
```

#### Secrets Manager Access

```json
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": [
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:hotel-assistant-mcp-creds-*",
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:hotel-pms-mcp-creds-*"
  ]
}
```

#### Network Access (for ECS tasks)

- VPC access to MCP server endpoints
- Security group rules allowing HTTPS outbound traffic
- NAT Gateway or VPC endpoints for AWS service access

**CDK automatically configures these permissions** when you use the provided
stack constructs.

### Prompt Name Fallback Behavior

The system uses a multi-level fallback chain for loading system prompts:

1. **Configured Prompt Name** (from `systemPrompts` configuration)
   - Example: `"chat": "custom_chat_prompt"`
   - Used if specified in MCP configuration

2. **Default Prompt Name** (based on assistant type)
   - Chat: `"chat_system_prompt"`
   - Voice: `"voice_system_prompt"`
   - Used if configured name not found

3. **Generic Default Prompt**
   - Name: `"default_system_prompt"`
   - Used if assistant-specific prompt not found

4. **Emergency Fallback** (hardcoded in code)
   - Used only if all MCP attempts fail
   - Indicates technical difficulties to user
   - Prevents application crash

**Example Fallback Flow:**

```
Request: chat_system_prompt
  ↓ (not found)
Try: chat_system_prompt
  ↓ (not found)
Try: default_system_prompt
  ↓ (not found)
Use: Emergency fallback message
```

This ensures the virtual assistant always has a valid system prompt, even during
MCP server outages.

### Troubleshooting Common Issues

#### Issue: "MCP configuration parameter not found"

**Symptoms:**

- Virtual assistant fails to start
- Error message:
  `MCP configuration parameter '/hotel-assistant/mcp-config' not found`

**Solutions:**

1. Verify CDK stack deployed successfully:

   ```bash
   aws cloudformation describe-stacks --stack-name HotelPmsStack
   ```

2. Check SSM parameter exists:

   ```bash
   aws ssm get-parameter --name /hotel-assistant/mcp-config
   ```

3. Verify `MCP_CONFIG_PARAMETER` environment variable is set correctly

4. Ensure IAM role has `ssm:GetParameter` permission

#### Issue: "Access denied to secret"

**Symptoms:**

- Virtual assistant starts but fails to connect to MCP servers
- Error message: `Cannot access secret 'arn:aws:secretsmanager:...'`

**Solutions:**

1. Verify secret exists:

   ```bash
   aws secretsmanager describe-secret --secret-id <secret-arn>
   ```

2. Check IAM permissions for `secretsmanager:GetSecretValue`

3. Verify secret ARN in MCP configuration matches actual secret

4. Check secret is in same region as virtual assistant

#### Issue: "Failed to connect to MCP server"

**Symptoms:**

- Virtual assistant starts but tools unavailable
- Error message: `Failed to connect to <server-name>`
- Server listed in `unavailable_servers`

**Solutions:**

1. Verify MCP server is deployed and healthy:

   ```bash
   curl -I https://your-mcp-server.execute-api.us-east-1.amazonaws.com/health
   ```

2. Check network connectivity from virtual assistant VPC

3. Verify Cognito credentials are valid:

   ```bash
   aws cognito-idp describe-user-pool --user-pool-id <pool-id>
   ```

4. Check MCP server logs for authentication errors

5. Verify security groups allow HTTPS traffic

#### Issue: "Using emergency fallback prompt"

**Symptoms:**

- Virtual assistant responds with "technical difficulties" message
- Log message: `All MCP prompt attempts failed, using emergency fallback`

**Solutions:**

1. Verify MCP server with `systemPrompts` is accessible

2. Check prompt names exist on MCP server:

   ```python
   # Test prompt retrieval
   session.get_prompt("chat_system_prompt")
   ```

3. Verify `systemPrompts` configuration in MCP config JSON

4. Check MCP server logs for prompt retrieval errors

#### Issue: "Tool name conflicts"

**Symptoms:**

- Tools have unexpected names like `server-name__tool-name`
- Warning in logs: `Tool name conflict detected`

**Solutions:**

1. This is expected behavior when multiple servers provide same tool name

2. Use prefixed tool names in agent configuration

3. Consider renaming tools on one of the MCP servers

4. Review tool discovery logs to understand conflicts

#### Issue: "Invalid MCP configuration JSON"

**Symptoms:**

- Virtual assistant fails to start
- Error message: `MCP configuration is not valid JSON`

**Solutions:**

1. Validate JSON syntax:

   ```bash
   aws ssm get-parameter --name /hotel-assistant/mcp-config --query 'Parameter.Value' --output text | jq .
   ```

2. Check for common JSON errors:
   - Missing commas
   - Trailing commas
   - Unescaped quotes
   - Invalid escape sequences

3. Verify configuration follows standard MCP format

4. Redeploy CDK stack to regenerate configuration

### Monitoring and Debugging

#### CloudWatch Logs

Monitor MCP operations through CloudWatch Logs:

**Chat Agent:**

```bash
aws logs tail /aws/lambda/virtual-assistant-chat --follow
```

**Voice Agent:**

```bash
aws logs tail /ecs/virtual-assistant-livekit --follow
```

**Key Log Messages:**

- `Loading MCP configuration from SSM: /hotel-assistant/mcp-config`
- `Loaded N MCP server configurations`
- `Connecting to MCP server: <server-name>`
- `Successfully connected to <server-name>`
- `Discovered N tools from <server-name>`
- `Loaded prompt: <prompt-name> from <server-name>`

#### Structured Logging

All MCP operations use structured logging with context:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Successfully connected to hotel-pms-mcp",
  "server_name": "hotel-pms-mcp",
  "tools_discovered": 6,
  "correlation_id": "abc-123-def"
}
```

#### Metrics to Monitor

- **MCP Connection Success Rate**: Percentage of successful connections
- **Tool Discovery Count**: Number of tools discovered per server
- **Prompt Load Time**: Time to load system prompts
- **Authentication Failures**: Count of Cognito auth failures
- **Server Unavailability**: Count of unavailable servers

### Best Practices

1. **Configuration Management**
   - Store MCP configuration in version control (as CDK code)
   - Use separate configurations for dev/staging/production
   - Document any custom MCP servers added

2. **Security**
   - Rotate Cognito client secrets regularly
   - Use least-privilege IAM permissions
   - Monitor secret access via CloudTrail
   - Enable encryption for sensitive parameters

3. **Reliability**
   - Test MCP server connectivity before deployment
   - Implement health checks for MCP servers
   - Monitor unavailable server metrics
   - Have fallback prompts ready

4. **Performance**
   - Cache MCP configuration after first load
   - Reuse MCP client connections
   - Monitor prompt load times
   - Optimize tool discovery

5. **Debugging**
   - Enable DEBUG logging for troubleshooting
   - Use correlation IDs for request tracing
   - Monitor CloudWatch logs during deployment
   - Test configuration changes in dev environment first
