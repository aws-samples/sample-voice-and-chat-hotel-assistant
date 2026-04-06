# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Factory for creating evaluatable Strands agents.

Creates Strands Agent instances without AgentCore dependencies (no session_manager,
no Step Functions, no platform router). Connects to the deployed MCP server for
real tool execution using the same system prompt and authentication as production.

Key differences from production agent:
- No AgentCore Memory (uses in-memory conversation history via agent.messages)
- No Step Functions integration (synchronous execution)
- No platform router (direct response capture)
- Same system prompt, MCP tools, and authentication as production
"""

import logging

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from virtual_assistant_common.cognito_mcp import cognito_mcp_client
from virtual_assistant_common.mcp import AssistantType, PromptLoader
from virtual_assistant_common.mcp.config_manager import MCPConfigManager
from virtual_assistant_common.utils.aws import get_bedrock_boto_session

logger = logging.getLogger(__name__)


class AgentFactoryError(Exception):
    """Base exception for AgentFactory errors."""

    pass


class MCPConfigurationError(AgentFactoryError):
    """Raised when MCP configuration fails."""

    pass


class SystemPromptError(AgentFactoryError):
    """Raised when system prompt cannot be retrieved."""

    pass


class AgentFactory:
    """Factory for creating evaluatable Strands agents.

    Example:
        >>> factory = AgentFactory(config_manager)
        >>> await factory.initialize()
        >>> agent = factory.create_agent("us.amazon.nova-lite-v1:0")
        >>> result = agent("Hello")
    """

    def __init__(self, config_manager: MCPConfigManager):
        self.config_manager = config_manager
        self.system_prompt: str | None = None
        self._mcp_clients: list[MCPClient] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize MCP connections and load system prompt.

        Must be called before create_agent().

        Raises:
            MCPConfigurationError: If MCP configuration cannot be loaded
            SystemPromptError: If system prompt is invalid
        """
        try:
            prompt_loader = PromptLoader(self.config_manager)
            self.system_prompt = await prompt_loader.load_prompt(AssistantType.CHAT)

            if not self.system_prompt or len(self.system_prompt) < 100:
                raise SystemPromptError(
                    f"System prompt appears invalid (length: {len(self.system_prompt) if self.system_prompt else 0})"
                )

            servers = self.config_manager.load_config()
            if not servers:
                raise MCPConfigurationError("No MCP servers found in configuration")

            for server_name, server_config in servers.items():
                if not server_config.authentication:
                    continue

                try:
                    credentials = self.config_manager.get_credentials(server_config.authentication.secret_arn)
                    url = server_config.url
                    headers = server_config.headers or {}

                    mcp_client = MCPClient(
                        lambda url=url, creds=credentials, headers=headers: cognito_mcp_client(
                            url=url,
                            user_pool_id=creds["userPoolId"],
                            client_id=creds["clientId"],
                            client_secret=creds["clientSecret"],
                            region=creds.get("region", "us-east-1"),
                            headers=headers,
                        ),
                        prefix=server_name.replace("-", "_"),
                    )
                    self._mcp_clients.append(mcp_client)
                except Exception as e:
                    logger.warning(f"Failed to create MCP client for server '{server_name}': {e}")

            if not self._mcp_clients:
                raise MCPConfigurationError("No MCP clients could be created")

            self._initialized = True

        except (MCPConfigurationError, SystemPromptError):
            raise
        except Exception as e:
            raise MCPConfigurationError(f"Failed to initialize AgentFactory: {e}") from e

    def create_agent(self, model_id: str, region: str = "us-east-1", **agent_kwargs) -> Agent:
        """Create a Strands agent with initialized MCP tools and system prompt.

        Any additional keyword arguments are forwarded to the Agent constructor,
        allowing callers to pass session_manager, callback_handler, trace_attributes, etc.

        Args:
            model_id: Bedrock model identifier (e.g., "us.amazon.nova-lite-v1:0")
            region: AWS region for Bedrock
            **agent_kwargs: Additional arguments forwarded to Agent(). Common options:
                - session_manager: AgentCore Memory session manager
                - temperature: Model temperature (applied to BedrockModel)
                - callback_handler: Custom callback handler
                - trace_attributes: OpenTelemetry trace attributes

        Returns:
            Configured Strands Agent

        Raises:
            RuntimeError: If initialize() has not been called
            AgentFactoryError: If agent creation fails
        """
        if not self._initialized:
            raise RuntimeError("Must call initialize() before creating agents")

        try:
            # Extract BedrockModel-specific kwargs before forwarding the rest to Agent
            bedrock_kwargs = {}
            for key in ("temperature", "max_tokens", "top_p", "stop_sequences"):
                if key in agent_kwargs:
                    bedrock_kwargs[key] = agent_kwargs.pop(key)

            boto_session = get_bedrock_boto_session(region=region)
            model = BedrockModel(model_id=model_id, boto_session=boto_session, **bedrock_kwargs)

            return Agent(
                model=model,
                system_prompt=self.system_prompt,
                tools=self._mcp_clients,
                **agent_kwargs,
            )
        except Exception as e:
            raise AgentFactoryError(f"Failed to create agent: {e}") from e

    @property
    def is_initialized(self) -> bool:
        return self._initialized
