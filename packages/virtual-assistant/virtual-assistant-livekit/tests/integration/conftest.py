# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Configuration for LiveKit agent integration tests.

This module provides fixtures and configuration for integration tests
that require real AWS services and MCP server connectivity.
"""

import logging
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Configure logging for integration tests
logger = logging.getLogger(__name__)


def pytest_configure(config):
    """Configure pytest for integration tests."""
    # Load environment variables from .env file in the package root
    package_root = Path(__file__).parent.parent.parent
    env_file = package_root / ".env"

    if env_file.exists():
        logger.info(f"Loading environment variables from {env_file}")
        load_dotenv(env_file, override=True)  # Override existing env vars

        # Verify key variables were loaded
        url = os.getenv("HOTEL_PMS_MCP_URL")
        if url:
            logger.info(f"Successfully loaded MCP URL: {url}")
        else:
            logger.warning("HOTEL_PMS_MCP_URL not found after loading .env file")
    else:
        logger.warning(f"No .env file found at {env_file}")


# Also load .env at module import time to ensure it's available
package_root = Path(__file__).parent.parent.parent
env_file = package_root / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)


@pytest.fixture
def mcp_config():
    """Load MCP configuration from environment variables.

    Note: These tests use CloudFormation outputs, not environment variables.
    This fixture is kept for backward compatibility with existing tests.
    """
    config = {
        "url": os.getenv("HOTEL_PMS_MCP_URL"),
        "user_pool_id": os.getenv("HOTEL_PMS_MCP_USER_POOL_ID"),
        "client_id": os.getenv("HOTEL_PMS_MCP_CLIENT_ID"),
        "client_secret": os.getenv("HOTEL_PMS_MCP_CLIENT_SECRET"),
        "region": os.getenv("AWS_REGION", "us-east-1"),
    }

    # Check if all required configuration is available
    missing_config = [key for key, value in config.items() if not value and key != "region"]
    if missing_config:
        pytest.fail(
            f"Integration test failed: Missing required environment variables: {missing_config}. "
            "Please set HOTEL_PMS_MCP_URL, HOTEL_PMS_MCP_USER_POOL_ID, "
            "HOTEL_PMS_MCP_CLIENT_ID, and HOTEL_PMS_MCP_CLIENT_SECRET in .env file"
        )

    return config


@pytest.fixture
def livekit_config():
    """Load LiveKit configuration from environment variables.

    Note: Most MCP integration tests don't need LiveKit credentials.
    Only tests that create actual LiveKit sessions need this.
    """
    config = {
        "api_key": os.getenv("LIVEKIT_API_KEY"),
        "api_secret": os.getenv("LIVEKIT_API_SECRET"),
        "url": os.getenv("LIVEKIT_URL"),
    }

    # Check if all required configuration is available
    missing_config = [key for key, value in config.items() if not value]
    if missing_config:
        pytest.fail(
            f"Integration test failed: Missing required LiveKit environment variables: {missing_config}. "
            "Please set LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL in .env file. "
            "Note: Most MCP tests don't need LiveKit credentials - only tests that create LiveKit sessions."
        )

    return config
