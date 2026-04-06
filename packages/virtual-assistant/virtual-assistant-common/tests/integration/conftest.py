# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Configuration for integration tests.

This module provides fixtures and configuration for integration tests
that require real AWS services and environment variables.
"""

import logging
from pathlib import Path

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
        import os

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
