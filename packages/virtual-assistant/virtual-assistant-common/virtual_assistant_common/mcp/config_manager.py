# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
MCP Configuration Manager.

This module provides configuration management for multiple MCP servers,
loading configuration from AWS Systems Manager Parameter Store and
retrieving credentials from AWS Secrets Manager.
"""

import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class MCPAuthenticationConfig(BaseModel):
    """Authentication configuration for MCP server."""

    type: str = Field(..., description="Authentication type (e.g., 'cognito')")
    secret_arn: str = Field(..., alias="secretArn", description="ARN of the secret in AWS Secrets Manager")

    model_config = {"populate_by_name": True}


class MCPSystemPromptsConfig(BaseModel):
    """System prompts configuration for MCP server."""

    chat: str | None = Field(None, description="Prompt name for chat assistant")
    voice: str | None = Field(None, description="Prompt name for voice assistant")

    model_config = {"extra": "allow"}  # Allow additional prompt types


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    model_config = {"populate_by_name": True}

    name: str = Field(..., description="Unique identifier for the MCP server")
    type: str = Field(..., description="Server type (currently only 'streamable-http' is supported)")
    url: str = Field(..., description="Base URL for the MCP server")
    headers: dict[str, str] | None = Field(None, description="Optional HTTP headers to include in requests")
    authentication: MCPAuthenticationConfig | None = Field(
        None, description="Optional authentication configuration (Cognito credentials from Secrets Manager)"
    )
    system_prompts: MCPSystemPromptsConfig | None = Field(
        None, alias="systemPrompts", description="Optional system prompt names for different assistant types"
    )


class MCPConfigManager:
    """Manages MCP configuration from SSM Parameter Store."""

    def __init__(self, parameter_name: str | None = None):
        """
        Initialize configuration manager.

        Args:
            parameter_name: SSM parameter name (defaults to env var MCP_CONFIG_PARAMETER)

        Raises:
            ValueError: If parameter_name is not provided and MCP_CONFIG_PARAMETER env var is not set
        """
        self.parameter_name = parameter_name or os.environ.get("MCP_CONFIG_PARAMETER")
        if not self.parameter_name:
            raise ValueError("MCP_CONFIG_PARAMETER environment variable required")

        self.ssm_client = boto3.client("ssm")
        self.secrets_client = boto3.client("secretsmanager")
        self._config_cache: dict[str, MCPServerConfig] | None = None

    def load_config(self) -> dict[str, MCPServerConfig]:
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
            response = self.ssm_client.get_parameter(Name=self.parameter_name, WithDecryption=True)
            config_json = json.loads(response["Parameter"]["Value"])

            # Validate standard mcpServers format
            if "mcpServers" not in config_json:
                raise ValueError("Configuration must contain 'mcpServers' key")

            # Parse server configurations
            servers = {}
            for name, server_config in config_json["mcpServers"].items():
                try:
                    # Add name to config for validation
                    server_config_with_name = {"name": name, **server_config}
                    servers[name] = MCPServerConfig(**server_config_with_name)
                except ValidationError as e:
                    logger.error(f"Invalid configuration for server '{name}': {e}")
                    raise ValueError(f"Invalid configuration for server '{name}': {e}") from e

            self._config_cache = servers
            logger.info(f"Loaded {len(servers)} MCP server configurations")
            return servers

        except ClientError as e:
            if e.response["Error"]["Code"] == "ParameterNotFound":
                logger.error(f"MCP configuration not found: {self.parameter_name}")
                raise RuntimeError(
                    f"MCP configuration parameter '{self.parameter_name}' not found. "
                    "Ensure infrastructure is deployed correctly."
                ) from e
            else:
                logger.error(f"AWS error loading MCP configuration: {e}")
                raise RuntimeError(f"Failed to load MCP configuration from SSM: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid MCP configuration JSON: {e}")
            raise RuntimeError(f"MCP configuration is not valid JSON: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error loading MCP configuration: {e}")
            raise RuntimeError(f"Failed to load MCP configuration: {e}") from e

    def get_credentials(self, secret_arn: str) -> dict[str, str]:
        """
        Retrieve credentials from Secrets Manager.

        Args:
            secret_arn: ARN of the secret

        Returns:
            Dictionary with userPoolId, clientId, clientSecret, region

        Raises:
            RuntimeError: If secret cannot be accessed
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_arn)
            return json.loads(response["SecretString"])
        except ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                logger.error(f"Access denied to secret: {secret_arn}")
                raise RuntimeError(
                    f"Cannot access secret '{secret_arn}'. Check IAM permissions for secretsmanager:GetSecretValue"
                ) from e
            else:
                logger.error(f"Failed to retrieve secret {secret_arn}: {e}")
                raise RuntimeError(f"Failed to retrieve credentials from Secrets Manager: {e}") from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in secret {secret_arn}: {e}")
            raise RuntimeError(f"Secret '{secret_arn}' contains invalid JSON: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_arn}: {e}")
            raise RuntimeError(f"Failed to retrieve credentials: {e}") from e

    def find_prompt_server(self) -> str | None:
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
