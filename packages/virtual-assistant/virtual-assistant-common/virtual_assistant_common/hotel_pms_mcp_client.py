# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel PMS MCP client factory function.

This module provides the hotel_pms_mcp_client async context manager function
specifically for Hotel PMS MCP server with configuration loading from
Secrets Manager and environment variables.
"""

import json
import logging
import os
from datetime import timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .cognito_mcp.cognito_mcp_client import cognito_mcp_client
from .cognito_mcp.exceptions import CognitoConfigError
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class HotelPmsMcpConfig(BaseModel):
    """Configuration model for Hotel PMS MCP client."""

    url: str = Field(..., description="MCP server URL")
    user_pool_id: str = Field(..., description="Cognito user pool ID")
    client_id: str = Field(..., description="Cognito client ID")
    client_secret: str = Field(..., description="Cognito client secret")
    region: str = Field(default="us-east-1", description="AWS region")

    model_config = ConfigDict(extra="forbid")  # Don't allow extra fields


def _load_config_from_secrets_manager(
    secret_arn: str | None = None, region: str = "us-east-1"
) -> dict[str, Any] | None:
    """
    Load configuration from AWS Secrets Manager using ARN.

    Args:
        secret_arn: ARN of the secret in Secrets Manager (if None, uses HOTEL_PMS_MCP_SECRET_ARN env var)
        region: AWS region where the secret is stored

    Returns:
        Configuration dictionary or None if loading fails

    Raises:
        ConfigurationError: If secret exists but contains invalid JSON
    """
    # Get secret ARN from parameter or environment variable
    if secret_arn is None:
        secret_arn = os.getenv("HOTEL_PMS_MCP_SECRET_ARN")

    if not secret_arn:
        logger.debug("No secret ARN provided and HOTEL_PMS_MCP_SECRET_ARN not set, skipping Secrets Manager")
        return None

    try:
        logger.debug(f"Loading configuration from Secrets Manager: {secret_arn}")

        # Create Secrets Manager client
        session = boto3.Session()
        client = session.client("secretsmanager", region_name=region)

        # Get secret value using ARN
        response = client.get_secret_value(SecretId=secret_arn)
        secret_string = response["SecretString"]

        # Parse JSON
        config = json.loads(secret_string)
        logger.info(f"Successfully loaded configuration from Secrets Manager: {secret_arn}")
        return config

    except (ClientError, BotoCoreError) as e:
        # AWS service errors - log and return None to fall back to environment variables
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown")
        logger.warning(
            f"Failed to load configuration from Secrets Manager: {error_code} - {e}",
            extra={"secret_arn": secret_arn, "region": region, "error_code": error_code},
        )
        return None

    except json.JSONDecodeError as e:
        # Invalid JSON in secret - this is a configuration error
        logger.error(f"Invalid JSON in Secrets Manager secret {secret_arn}: {e}")
        raise ConfigurationError(
            f"Invalid JSON in Secrets Manager secret '{secret_arn}': {e}",
            details={"secret_arn": secret_arn, "region": region},
            error_code="INVALID_SECRET_JSON",
        ) from e

    except Exception as e:
        # Unexpected errors - log and return None to fall back
        logger.warning(
            f"Unexpected error loading from Secrets Manager: {e}",
            extra={"secret_arn": secret_arn, "region": region},
        )
        return None


def _load_config_from_environment() -> dict[str, Any]:
    """
    Load configuration from environment variables.

    Returns:
        Configuration dictionary with values from environment variables

    Environment Variables:
        HOTEL_PMS_MCP_URL: MCP server URL
        HOTEL_PMS_MCP_USER_POOL_ID: Cognito user pool ID
        HOTEL_PMS_MCP_CLIENT_ID: Cognito client ID
        HOTEL_PMS_MCP_CLIENT_SECRET: Cognito client secret
        HOTEL_PMS_MCP_REGION: AWS region (optional, defaults to us-east-1)
    """
    logger.debug("Loading configuration from environment variables")

    config = {}

    # Load required configuration
    env_mappings = {
        "url": "HOTEL_PMS_MCP_URL",
        "user_pool_id": "HOTEL_PMS_MCP_USER_POOL_ID",
        "client_id": "HOTEL_PMS_MCP_CLIENT_ID",
        "client_secret": "HOTEL_PMS_MCP_CLIENT_SECRET",
    }

    for config_key, env_key in env_mappings.items():
        value = os.getenv(env_key)
        if value:
            config[config_key] = value

    # Load optional configuration with defaults
    region = os.getenv("HOTEL_PMS_MCP_REGION", "us-east-1")
    config["region"] = region

    logger.debug(f"Loaded configuration from environment: {list(config.keys())}")
    return config


def _merge_config(
    secrets_config: dict[str, Any] | None,
    env_config: dict[str, Any],
    explicit_params: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge configuration from different sources with precedence.

    Precedence order (highest to lowest):
    1. Explicit parameters passed to function
    2. Environment variables
    3. Secrets Manager

    Args:
        secrets_config: Configuration from Secrets Manager (may be None)
        env_config: Configuration from environment variables
        explicit_params: Explicit parameters passed to function

    Returns:
        Merged configuration dictionary
    """
    # Start with Secrets Manager config (lowest precedence)
    merged = secrets_config.copy() if secrets_config else {}

    # Override with environment variables
    for key, value in env_config.items():
        if value is not None:
            merged[key] = value

    # Override with explicit parameters (highest precedence)
    for key, value in explicit_params.items():
        if value is not None:
            merged[key] = value

    return merged


def _validate_config(config: dict[str, Any]) -> HotelPmsMcpConfig:
    """
    Validate configuration using Pydantic model.

    Args:
        config: Configuration dictionary to validate

    Returns:
        Validated configuration model

    Raises:
        CognitoConfigError: If configuration is invalid or missing required fields
    """
    try:
        return HotelPmsMcpConfig(**config)
    except ValidationError as e:
        # Extract missing and invalid fields from Pydantic errors
        missing_fields = []
        invalid_fields = []

        for error in e.errors():
            field_name = ".".join(str(loc) for loc in error["loc"])
            error_type = error["type"]

            if error_type == "missing":
                missing_fields.append(field_name)
            else:
                invalid_fields.append(f"{field_name}: {error['msg']}")

        # Create detailed error message
        error_parts = []
        if missing_fields:
            error_parts.append(f"Missing required fields: {', '.join(missing_fields)}")
        if invalid_fields:
            error_parts.append(f"Invalid fields: {', '.join(invalid_fields)}")

        error_message = "Hotel PMS MCP configuration validation failed: " + "; ".join(error_parts)

        logger.error(error_message, extra={"missing_fields": missing_fields, "invalid_fields": invalid_fields})

        raise CognitoConfigError(
            error_message,
            missing_config=missing_fields,
            invalid_config=invalid_fields,
            config_source="merged",
        ) from e


def hotel_pms_mcp_client(
    url: str | None = None,
    user_pool_id: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    region: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | timedelta = 30,
    sse_read_timeout: float | timedelta = 60 * 5,
    terminate_on_close: bool = True,
    secret_arn: str | None = None,
):
    """
    Create an authenticated MCP client specifically for Hotel PMS server.

    This function loads configuration from AWS Secrets Manager with fallback to
    environment variables, then creates an authenticated MCP client using the
    cognito_mcp_client function.

    Configuration precedence (highest to lowest):
    1. Explicit parameters passed to this function
    2. Environment variables (HOTEL_PMS_MCP_*)
    3. AWS Secrets Manager

    Args:
        url: MCP server URL (overrides config)
        user_pool_id: Cognito user pool ID (overrides config)
        client_id: Cognito client ID (overrides config)
        client_secret: Cognito client secret (overrides config)
        region: AWS region (overrides config, defaults to us-east-1)
        headers: Additional HTTP headers to send with requests
        timeout: HTTP request timeout
        sse_read_timeout: Server-sent events read timeout
        terminate_on_close: Whether to terminate the connection on close
        secret_arn: ARN of the secret in Secrets Manager (if None, uses HOTEL_PMS_MCP_SECRET_ARN env var)

    Returns:
        Async context manager that yields:
            - read_stream: Stream for reading messages from the server
            - write_stream: Stream for sending messages to the server
            - get_session_id_callback: Function to retrieve the current session ID

    Raises:
        CognitoConfigError: If configuration is invalid or missing required fields
        ConfigurationError: If Secrets Manager contains invalid JSON
        CognitoAuthError: If authentication fails
        CognitoMCPClientError: If MCP client creation fails

    Environment Variables:
        HOTEL_PMS_MCP_URL: MCP server URL
        HOTEL_PMS_MCP_USER_POOL_ID: Cognito user pool ID
        HOTEL_PMS_MCP_CLIENT_ID: Cognito client ID
        HOTEL_PMS_MCP_CLIENT_SECRET: Cognito client secret
        HOTEL_PMS_MCP_REGION: AWS region (optional, defaults to us-east-1)
        HOTEL_PMS_MCP_SECRET_ARN: ARN of the secret in Secrets Manager

    Example:
        ```python
        # High-level usage with ClientSession
        async with hotel_pms_mcp_client() as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                # Use session...

        # Low-level usage with streams directly
        async with hotel_pms_mcp_client() as (read_stream, write_stream, get_session_id):
            # Use streams directly...
        ```
    """
    logger.info("Creating Hotel PMS MCP client")

    # Determine region for Secrets Manager lookup
    lookup_region = region or os.getenv("HOTEL_PMS_MCP_REGION", "us-east-1")

    # Load configuration from different sources
    secrets_config = _load_config_from_secrets_manager(secret_arn, lookup_region)
    env_config = _load_config_from_environment()

    # Merge explicit parameters
    explicit_params = {
        "url": url,
        "user_pool_id": user_pool_id,
        "client_id": client_id,
        "client_secret": client_secret,
        "region": region,
    }

    # Merge all configuration sources
    merged_config = _merge_config(secrets_config, env_config, explicit_params)

    # Validate configuration
    validated_config = _validate_config(merged_config)

    logger.info(
        "Successfully loaded and validated Hotel PMS MCP configuration",
        extra={
            "url": validated_config.url,
            "user_pool_id": validated_config.user_pool_id,
            "client_id": f"{validated_config.client_id[:4]}...{validated_config.client_id[-4:]}",
            "region": validated_config.region,
            "config_sources": {
                "secrets_manager": secrets_config is not None,
                "environment": bool(env_config),
                "explicit_params": any(v is not None for v in explicit_params.values()),
            },
        },
    )

    # Return the cognito_mcp_client context manager directly
    return cognito_mcp_client(
        url=validated_config.url,
        user_pool_id=validated_config.user_pool_id,
        client_id=validated_config.client_id,
        client_secret=validated_config.client_secret,
        region=validated_config.region,
        headers=headers,
        timeout=timeout,
        sse_read_timeout=sse_read_timeout,
        terminate_on_close=terminate_on_close,
    )
