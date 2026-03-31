# Design Document

## Overview

This design document specifies the architecture and implementation approach for
integrating the Virtual Assistant Chat and Voice agents with the Model Context
Protocol (MCP) infrastructure. The design enables dynamic system prompt loading,
multi-MCP server tool access, and secure credential management through a
standardized JSON configuration format stored in AWS Systems Manager Parameter
Store.

The design extends the standard MCP configuration format (used by Claude Desktop
and other MCP clients) to support HTTP-based MCP servers with Cognito
authentication, while maintaining compatibility with the core MCP specification.

## Current State Analysis

### Existing Implementation

**Virtual Assistant Chat
(`packages/virtual-assistant/virtual-assistant-chat/`):**

- Uses single `hotel_pms_mcp_client()` for MCP connection
- Loads system prompts from local file: `assets/system-prompt-es-mx.md`
- Uses `generate_dynamic_hotel_instructions()` to add dynamic context (date,
  hotel list)
- Initializes MCP client at module level with `MCPClient(hotel_pms_mcp_client)`
- Tools loaded synchronously: `mcp_client.list_tools_sync()`

**Virtual Assistant Voice
(`packages/virtual-assistant/virtual-assistant-livekit/`):**

- Uses `hotel_pms_mcp_client()` in prewarm function to fetch hotel data
- Loads system prompts from local file: `assets/voice_prompt.txt`
- Uses `generate_dynamic_hotel_instructions()` for prompt generation
- Creates per-session MCP connections in prewarm
- Uses `HotelPmsMCPServer` wrapper for LiveKit integration

**Common MCP Client (`packages/virtual-assistant/virtual-assistant-common/`):**

- `hotel_pms_mcp_client()`: Factory function for single MCP server
- Supports Secrets Manager and environment variable configuration
- Uses `cognito_mcp_client()` for Cognito authentication
- Configuration precedence: explicit params > env vars > Secrets Manager

### What Needs to Change

1. **Multi-MCP Server Support**: Replace single `hotel_pms_mcp_client()` with
   multi-server configuration
2. **Dynamic Prompt Loading**: Load prompts from MCP server instead of local
   files
3. **Standard Configuration Format**: Use MCP standard `mcpServers` format with
   HTTP extensions
4. **SSM Parameter Store**: Store configuration in SSM instead of individual env
   vars/secrets
5. **Fallback Prompts**: Update hardcoded fallbacks to indicate service
   unavailability

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  AWS Systems Manager Parameter Store            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Parameter: /hotel-assistant/mcp-config                   │  │
│  │  {                                                         │  │
│  │    "mcpServers": {                                        │  │
│  │      "hotel-assistant-mcp": {                            │  │
│  │        "type": "streamable-http",                        │  │
│  │        "url": "https://...",                             │  │
│  │        "authentication": {...},                          │  │
│  │        "systemPrompts": {                                │  │
│  │          "chat": "chat_system_prompt",                   │  │
│  │          "voice": "voice_system_prompt"                  │  │
│  │        }                                                  │  │
│  │      },                                                   │  │
│  │      "hotel-pms-mcp": {...}                             │  │
│  │    }                                                      │  │
│  │  }                                                         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Read at startup
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Virtual Assistant Chat / Voice                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  MCP Configuration Manager                                │  │
│  │  - Load from SSM Parameter Store                          │  │
│  │  - Parse standard mcpServers format                       │  │
│  │  - Retrieve credentials from Secrets Manager              │  │
│  │  - Initialize multiple MCP clients                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Multi-MCP Client Manager                                  │  │
│  │  - Manage connections to all configured servers           │  │
│  │  - Discover tools from each server                        │  │
│  │  - Route tool calls to appropriate server                 │  │
│  │  - Handle server failures gracefully                      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Prompt Loader                                             │  │
│  │  - Request prompts from MCP server with systemPrompts     │  │
│  │  - Fallback chain: configured → default → hardcoded       │  │
│  │  - Cache prompts per session                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP + Cognito Auth
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Servers (AgentCore Runtime)              │
│  ┌──────────────────────┐      ┌──────────────────────┐        │
│  │ Hotel Assistant MCP  │      │   Hotel PMS MCP      │        │
│  │                      │      │                      │        │
│  │ Tools:               │      │ Tools:               │        │
│  │ - query_hotel_       │      │ - get_availability   │        │
│  │   knowledge          │      │ - create_reservation │        │
│  │                      │      │ - get_reservation    │        │
│  │ Prompts:             │      │ - update_reservation │        │
│  │ - chat_system_prompt │      │ - cancel_reservation │        │
│  │ - voice_system_      │      │ - create_housekeeping│        │
│  │   prompt             │      │   _request           │        │
│  │ - default_system_    │      │                      │        │
│  │   prompt             │      │                      │        │
│  └──────────────────────┘      └──────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

## MCP Configuration Format

### Standard MCP Format with HTTP Extensions

The configuration follows the standard MCP `mcpServers` format used by Claude
Desktop and other MCP clients, extended with HTTP-specific fields:

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

**Standard Fields (MCP Specification):**

- `mcpServers`: Top-level object containing server configurations (standard)
- Server name keys: Unique identifiers for each server (standard)
- `type`: Transport type - "streamable-http" for HTTP-based servers (standard)
- `headers`: Optional HTTP headers to include in requests (standard, key-value
  pairs)

**Extension Fields:**

- `url`: HTTP endpoint for the MCP server (extension for streamable-http type)
- `authentication`: Authentication configuration (extension)
  - `type`: Authentication method ("cognito")
  - `secretArn`: ARN of Secrets Manager secret with credentials
- `systemPrompts`: Optional configuration for system prompt loading (extension)
  - `chat`: Prompt name for chat assistant
  - `voice`: Prompt name for voice assistant
  - If not specified, defaults to "chat_system_prompt" and "voice_system_prompt"

**Why This Format:**

1. Compatible with standard MCP configuration structure
2. Uses standard `type` field instead of custom `transport`
3. Supports standard `headers` for custom HTTP headers
4. Extensible via `additionalProperties` in MCP spec
5. Familiar to developers using other MCP clients
6. Easy to add new servers without code changes

**Tool Discovery:**

- All MCP servers are assumed to provide tools
- Tools are discovered via `list_tools()` call during initialization
- No explicit configuration needed for tool support

**System Prompts:**

- Only one MCP server should have `systemPrompts` configuration
- If multiple servers have `systemPrompts`, the first one found is used
- If no server has `systemPrompts`, fallback to default prompt names

### Secrets Manager Secret Format

Each MCP server references a Secrets Manager secret containing Cognito
credentials:

```json
{
  "userPoolId": "us-east-1_XXXXXXXXX",
  "clientId": "abcdefghijklmnopqrstuvwxyz123456",
  "clientSecret": "secret-value-here",
  "region": "us-east-1"
}
```

**Note:** The `clientSecret` field is included in the secret (not in the MCP
config) for machine-to-machine OAuth2 authentication.

## Components and Interfaces

### 1. MCP Configuration Manager

**Module:** `virtual_assistant_common/mcp/config_manager.py`

Loads and parses MCP configuration from SSM Parameter Store, replacing the
current single-server approach.

```python
from dataclasses import dataclass
from typing import Dict, Optional
import boto3
import json
import logging
import os

logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server"""
    name: str
    type: str
    url: str
    headers: Optional[Dict[str, str]]
    authentication: Dict[str, str]
    system_prompts: Optional[Dict[str, str]]

class MCPConfigManager:
    """Manages MCP configuration from SSM Parameter Store"""

    def __init__(self, parameter_name: str = None):
        """
        Initialize configuration manager.

        Args:
            parameter_name: SSM parameter name (defaults to env var MCP_CONFIG_PARAMETER)
        """
        self.parameter_name = parameter_name or os.environ.get('MCP_CONFIG_PARAMETER')
        if not self.parameter_name:
            raise ValueError("MCP_CONFIG_PARAMETER environment variable required")

        self.ssm_client = boto3.client('ssm')
        self.secrets_client = boto3.client('secretsmanager')
        self._config_cache = None

    def load_config(self) -> Dict[str, MCPServerConfig]:
        """
        Load MCP configuration from SSM Parameter Store.

        Returns:
            Dictionary mapping server names to configurations

        Raises:
            RuntimeError: If parameter not found or invalid JSON
        """
        if self._config_cache:
            return self._config_cache

        try:
            logger.info(f"Loading MCP configuration from SSM: {self.parameter_name}")
            response = self.ssm_client.get_parameter(
                Name=self.parameter_name,
                WithDecryption=True
            )
            config_json = json.loads(response['Parameter']['Value'])

            # Validate standard mcpServers format
            if 'mcpServers' not in config_json:
                raise ValueError("Configuration must contain 'mcpServers' key")

            # Parse server configurations
            servers = {}
            for name, server_config in config_json['mcpServers'].items():
                # Validate required fields
                self._validate_server_config(name, server_config)

                servers[name] = MCPServerConfig(
                    name=name,
                    type=server_config['type'],
                    url=server_config['url'],
                    headers=server_config.get('headers'),
                    authentication=server_config['authentication'],
                    system_prompts=server_config.get('systemPrompts')
                )

            self._config_cache = servers
            logger.info(f"Loaded {len(servers)} MCP server configurations")
            return servers

        except self.ssm_client.exceptions.ParameterNotFound:
            logger.error(f"MCP configuration not found: {self.parameter_name}")
            raise RuntimeError(
                f"MCP configuration parameter '{self.parameter_name}' not found. "
                "Ensure infrastructure is deployed correctly."
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid MCP configuration JSON: {e}")
            raise RuntimeError(f"MCP configuration is not valid JSON: {e}")

    def _validate_server_config(self, name: str, config: Dict):
        """Validate server configuration has required fields"""
        required_fields = ['type', 'url', 'authentication']
        missing = [f for f in required_fields if f not in config]
        if missing:
            raise ValueError(
                f"Server '{name}' missing required fields: {', '.join(missing)}"
            )

        # Validate type
        if config['type'] != 'streamable-http':
            raise ValueError(
                f"Server '{name}' has unsupported type: {config['type']}. "
                "Only 'streamable-http' is supported."
            )

    def get_credentials(self, secret_arn: str) -> Dict[str, str]:
        """
        Retrieve credentials from Secrets Manager.

        Args:
            secret_arn: ARN of the secret

        Returns:
            Dictionary with userPoolId, clientId, clientSecret, region
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            return json.loads(response['SecretString'])
        except self.secrets_client.exceptions.AccessDeniedException:
            logger.error(f"Access denied to secret: {secret_arn}")
            raise RuntimeError(
                f"Cannot access secret '{secret_arn}'. "
                "Check IAM permissions for secretsmanager:GetSecretValue"
            )

    def find_prompt_server(self) -> Optional[str]:
        """
        Find the MCP server that provides system prompts.

        Returns:
            Server name that has systemPrompts configuration, or None
        """
        servers = self.load_config()
        for name, config in servers.items():
            if config.system_prompts:
                return name
        return None
```

### 2. Multi-MCP Client Manager

**Module:** `virtual_assistant_common/mcp/multi_client_manager.py`

Manages connections to multiple MCP servers, replacing the single
`MCPClient(hotel_pms_mcp_client)` pattern.

```python
from typing import Dict, List
from mcp.client.session import ClientSession
from virtual_assistant_common.cognito_mcp import cognito_mcp_client
import logging

logger = logging.getLogger(__name__)

class MultiMCPClientManager:
    """Manages multiple MCP client connections"""

    def __init__(self, config_manager: MCPConfigManager):
        self.config_manager = config_manager
        self.clients: Dict[str, ClientSession] = {}
        self.tools: Dict[str, str] = {}  # tool_name -> server_name mapping
        self.unavailable_servers: set = set()

    async def initialize(self):
        """
        Initialize all MCP client connections.

        Connects to all configured servers, discovers tools, and handles failures gracefully.
        """
        servers = self.config_manager.load_config()

        for name, config in servers.items():
            try:
                logger.info(f"Connecting to MCP server: {name}")

                # Get authentication credentials
                creds = self.config_manager.get_credentials(
                    config.authentication['secretArn']
                )

                # Prepare headers (merge config headers with auth)
                headers = config.headers.copy() if config.headers else {}

                # Create authenticated MCP client
                async with cognito_mcp_client(
                    url=config.url,
                    user_pool_id=creds['userPoolId'],
                    client_id=creds['clientId'],
                    client_secret=creds['clientSecret'],
                    region=creds['region'],
                    headers=headers
                ) as (read_stream, write_stream, get_session_id):

                    # Create MCP session
                    session = ClientSession(read_stream, write_stream)
                    await session.initialize()

                    self.clients[name] = session

                    # Discover tools (all servers provide tools)
                    await self._discover_tools(name, session)

                    logger.info(f"Successfully connected to {name}")

            except Exception as e:
                logger.error(f"Failed to connect to {name}: {e}")
                self.unavailable_servers.add(name)
                # Continue with other servers (graceful degradation)

        if not self.clients:
            raise RuntimeError(
                "Failed to connect to any MCP servers. "
                "Check server availability and credentials."
            )

        logger.info(
            f"Initialized {len(self.clients)} MCP clients, "
            f"{len(self.unavailable_servers)} unavailable"
        )

    async def _discover_tools(self, server_name: str, session: ClientSession):
        """Discover available tools from MCP server"""
        try:
            tools_list = await session.list_tools()
            for tool in tools_list.tools:
                if tool.name in self.tools:
                    # Conflict detected - use server-prefixed name
                    prefixed_name = f"{server_name}__{tool.name}"
                    logger.warning(
                        f"Tool name conflict: {tool.name} exists in both "
                        f"{self.tools[tool.name]} and {server_name}. "
                        f"Registering as {prefixed_name}"
                    )
                    self.tools[prefixed_name] = server_name
                else:
                    # No conflict - use original name
                    self.tools[tool.name] = server_name

            logger.info(f"Discovered {len(tools_list.tools)} tools from {server_name}")
        except Exception as e:
            logger.error(f"Failed to discover tools from {server_name}: {e}")

    def get_mcp_clients(self) -> Dict[str, ClientSession]:
        """
        Get all MCP client sessions for LiveKit integration.

        LiveKit handles tool calls directly, so we pass it the MCP client sessions.

        Returns:
            Dictionary mapping server names to MCP client sessions
        """
        return {name: session for name, session in self.clients.items()
                if name not in self.unavailable_servers}

    def get_tools_for_strands(self) -> List:
        """
        Get all discovered tools as Strands tool objects.

        Strands handles tool calls directly, so we pass it tool objects.
        This method converts MCP tools to Strands-compatible format.

        Returns:
            List of tool objects for Strands Agent
        """
        # TODO: Implementation will convert MCP tool definitions to Strands format
        # This depends on how Strands expects tools to be formatted
        tools = []
        for tool_name, server_name in self.tools.items():
            if server_name not in self.unavailable_servers:
                # Create Strands-compatible tool object
                # The actual implementation will depend on Strands API
                tools.append({
                    'name': tool_name,
                    'server': server_name,
                    'session': self.clients[server_name]
                })
        return tools

    async def get_prompt(self, prompt_name: str, server_name: str = None) -> str:
        """
        Get prompt from MCP server.

        Args:
            prompt_name: Name of the prompt
            server_name: Specific server to query (if None, uses server with systemPrompts)

        Returns:
            Prompt text
        """
        if server_name is None:
            # Find server with systemPrompts configuration
            server_name = self.config_manager.find_prompt_server()
            if not server_name:
                raise ValueError("No MCP server configured with systemPrompts")

        if server_name not in self.clients:
            raise ValueError(f"Unknown MCP server: {server_name}")

        if server_name in self.unavailable_servers:
            raise RuntimeError(f"MCP server {server_name} is unavailable")

        session = self.clients[server_name]
        prompt = await session.get_prompt(prompt_name)
        return prompt.messages[0].content.text

    def get_all_tools(self) -> List:
        """Get all discovered tools for agent initialization"""
        return list(self.tools.keys())
```

### 3. Prompt Loader with Fallback Chain

**Module:** `virtual_assistant_common/mcp/prompt_loader.py`

Loads system prompts from MCP servers with fallback logic, replacing local file
loading.

```python
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AssistantType(Enum):
    CHAT = "chat"
    VOICE = "voice"

class PromptLoader:
    """Loads system prompts from MCP servers with fallback chain"""

    def __init__(self, client_manager: MultiMCPClientManager, config_manager: MCPConfigManager):
        self.client_manager = client_manager
        self.config_manager = config_manager

    async def load_prompt(self, assistant_type: AssistantType) -> str:
        """
        Load system prompt with fallback chain.

        Fallback order:
        1. Configured prompt name from systemPrompts (e.g., "chat": "custom_chat_prompt")
        2. Default prompt name (e.g., "chat_system_prompt")
        3. "default_system_prompt"
        4. Hardcoded emergency fallback

        Args:
            assistant_type: Type of assistant (CHAT or VOICE)

        Returns:
            System prompt text
        """
        # Find server with systemPrompts configuration
        prompt_server = self.config_manager.find_prompt_server()

        if not prompt_server:
            logger.warning("No MCP server configured with systemPrompts, using emergency fallback")
            return self._get_emergency_fallback(assistant_type)

        # Get server configuration
        servers = self.config_manager.load_config()
        server_config = servers[prompt_server]

        # Build fallback chain
        prompt_names = []

        # 1. Configured prompt name (if specified)
        if server_config.system_prompts and assistant_type.value in server_config.system_prompts:
            prompt_names.append(server_config.system_prompts[assistant_type.value])

        # 2. Default prompt name
        prompt_names.append(f"{assistant_type.value}_system_prompt")

        # 3. Generic default
        prompt_names.append("default_system_prompt")

        # Try each prompt name in order
        for prompt_name in prompt_names:
            try:
                prompt = await self.client_manager.get_prompt(prompt_name, prompt_server)
                logger.info(f"Loaded prompt: {prompt_name} from {prompt_server}")
                return prompt
            except Exception as e:
                logger.warning(f"Failed to load {prompt_name}: {e}")

        # All MCP attempts failed, use hardcoded emergency fallback
        logger.error("All MCP prompt attempts failed, using emergency fallback")
        return self._get_emergency_fallback(assistant_type)

    def _get_emergency_fallback(self, assistant_type: AssistantType) -> str:
        """
        Emergency fallback prompt when all MCP attempts fail.

        This prompt indicates technical difficulties and asks user to try again later.
        """
        if assistant_type == AssistantType.CHAT:
            return """I apologize, but I'm experiencing technical difficulties and cannot access my full capabilities at the moment. Please try again in a few minutes. If the problem persists, please contact support."""
        else:  # VOICE
            return """I'm sorry, but I'm having technical difficulties right now. Please try again in a few minutes."""
```

### 4. CDK Infrastructure - Cross-Stack MCP Configuration

#### HotelPmsStack - Generate and Export MCP Configuration

**Module:** `packages/infra/stack/hotel_pms_stack.py`

Generate MCP configuration JSON, store in SSM Parameter Store, and export for
use by VirtualAssistantStack.

```python
from aws_cdk import (
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager,
    SecretValue,
    CfnOutput,
)
import json

class HotelPmsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Existing constructs create MCP servers and Cognito resources
        # ...

        # Create secrets for MCP server credentials
        self.hotel_assistant_secret = self._create_mcp_secret(
            "HotelAssistantMCPSecret",
            self.hotel_assistant_user_pool.user_pool_id,
            self.hotel_assistant_client.user_pool_client_id,
            self.hotel_assistant_client_secret
        )

        self.hotel_pms_secret = self._create_mcp_secret(
            "HotelPMSMCPSecret",
            self.hotel_pms_user_pool.user_pool_id,
            self.hotel_pms_client.user_pool_client_id,
            self.hotel_pms_client_secret
        )

        # Generate MCP configuration JSON (standard format with extensions)
        mcp_config = {
            "mcpServers": {
                "hotel-assistant-mcp": {
                    "type": "streamable-http",
                    "url": self.hotel_assistant_mcp_url,
                    "authentication": {
                        "type": "cognito",
                        "secretArn": self.hotel_assistant_secret.secret_arn
                    },
                    "systemPrompts": {
                        "chat": "chat_system_prompt",
                        "voice": "voice_system_prompt"
                    }
                },
                "hotel-pms-mcp": {
                    "type": "streamable-http",
                    "url": self.hotel_pms_mcp_url,
                    "authentication": {
                        "type": "cognito",
                        "secretArn": self.hotel_pms_secret.secret_arn
                    }
                }
            }
        }

        # Store in SSM Parameter Store
        self.mcp_config_parameter = ssm.StringParameter(
            self, "MCPConfigParameter",
            parameter_name="/hotel-assistant/mcp-config",
            string_value=json.dumps(mcp_config, indent=2),
            description="MCP server configuration for virtual assistants",
            tier=ssm.ParameterTier.STANDARD
        )

        # Export for cross-stack reference
        CfnOutput(
            self, "MCPConfigParameterName",
            value=self.mcp_config_parameter.parameter_name,
            export_name="HotelPMS-MCPConfigParameter"
        )

        CfnOutput(
            self, "HotelAssistantSecretArn",
            value=self.hotel_assistant_secret.secret_arn,
            export_name="HotelPMS-HotelAssistantSecretArn"
        )

        CfnOutput(
            self, "HotelPMSSecretArn",
            value=self.hotel_pms_secret.secret_arn,
            export_name="HotelPMS-HotelPMSSecretArn"
        )

    def _create_mcp_secret(
        self,
        id: str,
        user_pool_id: str,
        client_id: str,
        client_secret: str
    ) -> secretsmanager.Secret:
        """Create Secrets Manager secret for MCP credentials"""
        return secretsmanager.Secret(
            self, id,
            secret_object_value={
                "userPoolId": SecretValue.unsafe_plain_text(user_pool_id),
                "clientId": SecretValue.unsafe_plain_text(client_id),
                "clientSecret": SecretValue.unsafe_plain_text(client_secret),
                "region": SecretValue.unsafe_plain_text(self.region)
            },
            description=f"Cognito credentials for {id}"
        )
```

#### VirtualAssistantStack - Accept and Use MCP Configuration

**Module:** `packages/infra/stack/virtual_assistant_stack.py`

Accept MCP configuration as input and grant appropriate permissions.

```python
from aws_cdk import (
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
)

class VirtualAssistantStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        mcp_config_parameter: ssm.IStringParameter,
        mcp_secrets: list[secretsmanager.ISecret],
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        # Create virtual assistant resources (chat agent, voice agent, etc.)
        # ...

        # Grant MCP configuration access to chat agent
        mcp_config_parameter.grant_read(self.chat_agent_role)
        for secret in mcp_secrets:
            secret.grant_read(self.chat_agent_role)

        # Grant MCP configuration access to voice agent
        mcp_config_parameter.grant_read(self.voice_agent_role)
        for secret in mcp_secrets:
            secret.grant_read(self.voice_agent_role)

        # Add environment variable to virtual assistants
        self.chat_agent_function.add_environment(
            "MCP_CONFIG_PARAMETER",
            mcp_config_parameter.parameter_name
        )

        self.voice_agent_container.add_environment(
            "MCP_CONFIG_PARAMETER",
            mcp_config_parameter.parameter_name
        )
```

#### Main CDK App - Wire Stacks Together

**Module:** `packages/infra/app.py`

Connect HotelPmsStack outputs to VirtualAssistantStack inputs.

```python
from aws_cdk import App
from hotel_pms_stack import HotelPmsStack
from virtual_assistant_stack import VirtualAssistantStack

app = App()

# Deploy Hotel PMS Stack with MCP servers
hotel_pms_stack = HotelPmsStack(app, "HotelPmsStack")

# Deploy Virtual Assistant Stack with MCP configuration
virtual_assistant_stack = VirtualAssistantStack(
    app, "VirtualAssistantStack",
    mcp_config_parameter=hotel_pms_stack.mcp_config_parameter,
    mcp_secrets=[
        hotel_pms_stack.hotel_assistant_secret,
        hotel_pms_stack.hotel_pms_secret
    ]
)

# Ensure proper deployment order
virtual_assistant_stack.add_dependency(hotel_pms_stack)

app.synth()
```

**Benefits of This Approach:**

1. **Decoupling**: VirtualAssistantStack can be deployed independently with
   different MCP servers
2. **Flexibility**: Customers can provide their own MCP configuration and
   secrets
3. **Reusability**: VirtualAssistantStack is not tied to Hotel PMS
   implementation
4. **Clear Dependencies**: Stack dependencies are explicit in the code

```

## Summary

This design provides a complete solution for integrating virtual assistants with
multiple MCP servers using a standard configuration format. The key benefits
are:

1. **Standard Compliance**: Uses MCP standard `mcpServers` format with minimal
   extensions
2. **Flexibility**: Easy to add new MCP servers without code changes
3. **Graceful Degradation**: Continues operating if some servers are unavailable
4. **Security**: Credentials stored in Secrets Manager, not in configuration
5. **Maintainability**: Clear separation of concerns between configuration,
   connection management, and prompt loading

The implementation preserves existing patterns in both chat and voice agents
while adding multi-MCP support and dynamic prompt loading.
```
