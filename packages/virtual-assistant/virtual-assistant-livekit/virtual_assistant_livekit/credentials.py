# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Simple credential management for LiveKit agent.

This module provides straightforward credential retrieval from environment
variables or AWS Secrets Manager without unnecessary complexity.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)


class LiveKitCredentials:
    """Container for LiveKit credentials."""

    def __init__(self, url: str, api_key: str, api_secret: str):
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret


def get_livekit_credentials() -> LiveKitCredentials:
    """Get LiveKit credentials from environment variables or AWS Secrets Manager."""
    logger.info("Getting LiveKit credentials")

    # 1. Check environment variables first
    url = os.environ.get("LIVEKIT_URL")
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")

    if url and api_key and api_secret:
        logger.info("Using LiveKit credentials from environment variables")
        return LiveKitCredentials(url, api_key, api_secret)

    # 2. Check for secret name and get secret value
    secret_name = os.environ.get("LIVEKIT_SECRET_NAME")
    if secret_name:
        logger.info(f"Getting LiveKit credentials from secret: {secret_name}")
        try:
            secrets_client = boto3.client("secretsmanager")
            response = secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])

            url = secret_data.get("LIVEKIT_URL")
            api_key = secret_data.get("LIVEKIT_API_KEY")
            api_secret = secret_data.get("LIVEKIT_API_SECRET")

            if url and api_key and api_secret:
                logger.info("Successfully retrieved LiveKit credentials from AWS Secrets Manager")
                return LiveKitCredentials(url, api_key, api_secret)
            else:
                logger.error("Secret is missing required fields: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")

        except Exception as e:
            logger.error(f"Failed to retrieve secret {secret_name}: {e}")

    # 3. No credentials found
    logger.error("No LiveKit credentials found")
    logger.error("Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET environment variables")
    logger.error("Or set LIVEKIT_SECRET_NAME to point to an AWS Secrets Manager secret")
    raise SystemExit(1)
