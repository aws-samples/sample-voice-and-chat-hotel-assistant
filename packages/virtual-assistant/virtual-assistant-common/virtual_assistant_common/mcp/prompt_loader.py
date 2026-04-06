# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Prompt Loader with Fallback Chain.

This module loads system prompts from MCP servers with a fallback chain
to ensure the virtual assistant always has a valid prompt.
"""

import logging
from enum import Enum

from mcp import ClientSession

from ..cognito_mcp import cognito_mcp_client
from .config_manager import MCPConfigManager

logger = logging.getLogger(__name__)


class AssistantType(Enum):
    """Type of virtual assistant."""

    CHAT = "chat"
    VOICE = "voice"


class PromptLoader:
    """Loads system prompts from MCP servers with fallback chain."""

    def __init__(self, config_manager: MCPConfigManager):
        """
        Initialize prompt loader.

        Args:
            config_manager: Configuration manager for MCP servers
        """
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
        if server_config.system_prompts:
            prompt_value = getattr(server_config.system_prompts, assistant_type.value, None)
            if prompt_value:
                prompt_names.append(prompt_value)

        # 2. Default prompt name
        prompt_names.append(f"{assistant_type.value}_system_prompt")

        # 3. Generic default
        prompt_names.append("default_system_prompt")

        # Get credentials
        creds = self.config_manager.get_credentials(server_config.authentication.secret_arn)

        # Try each prompt name in order
        for prompt_name in prompt_names:
            try:
                # Create temporary connection to load prompt
                async with cognito_mcp_client(
                    url=server_config.url,
                    user_pool_id=creds["userPoolId"],
                    client_id=creds["clientId"],
                    client_secret=creds["clientSecret"],
                    region=creds["region"],
                    headers=server_config.headers,
                ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # Get prompt
                    prompt_result = await session.get_prompt(prompt_name)
                    prompt_text = prompt_result.messages[0].content.text

                    logger.info(f"Loaded prompt: {prompt_name} from {prompt_server}")
                    return prompt_text

            except Exception as e:
                logger.warning(f"Failed to load {prompt_name}: {e}")

        # All MCP attempts failed, use hardcoded emergency fallback
        logger.error("All MCP prompt attempts failed, using emergency fallback")
        return self._get_emergency_fallback(assistant_type)

    def _get_emergency_fallback(self, assistant_type: AssistantType) -> str:
        """
        Emergency fallback prompt when all MCP attempts fail.

        This prompt indicates technical difficulties and asks user to try again later.

        Args:
            assistant_type: Type of assistant

        Returns:
            Emergency fallback prompt text
        """
        if assistant_type == AssistantType.CHAT:
            return (
                "I apologize, but I'm experiencing technical difficulties and cannot access my full capabilities "
                "at the moment. Please try again in a few minutes. If the problem persists, please contact support."
            )
        else:  # VOICE
            return "I'm sorry, but I'm having technical difficulties right now. Please try again in a few minutes."
