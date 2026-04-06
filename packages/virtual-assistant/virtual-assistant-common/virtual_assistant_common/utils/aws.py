# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""AWS utility functions."""

import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

# Cache for boto3 sessions by region
_bedrock_sessions: dict[str, boto3.Session] = {}


def get_bedrock_boto_session(region: str, max_attempts: int = 100, retry_mode: str = "adaptive") -> boto3.Session:
    """
    Get or create a singleton boto3 Session configured with retry settings for Bedrock.

    Args:
        region: AWS region
        max_attempts: Maximum number of retry attempts (default: 100)
        retry_mode: Retry mode ('legacy', 'standard', or 'adaptive')

    Returns:
        Configured boto3 Session (singleton per region)
    """
    # Allow override from environment variables
    env_max_attempts = os.environ.get("BEDROCK_MAX_RETRY_ATTEMPTS")
    if env_max_attempts and env_max_attempts.isdigit():
        max_attempts = int(env_max_attempts)

    env_retry_mode = os.environ.get("BEDROCK_RETRY_MODE")
    if env_retry_mode in ["legacy", "standard", "adaptive"]:
        retry_mode = env_retry_mode

    xacct_role = os.getenv("BEDROCK_XACCT_ROLE")
    xacct_region = os.getenv(
        "BEDROCK_XACCT_REGION", "us-west-2"
    )  # we assume cross-account role happens in PDX by default

    client_kwargs = {"region_name": os.getenv("AWS_REGION", "us-east-1")}

    if xacct_role:
        sts = boto3.client("sts", config=Config(retries={"max_attempts": 3, "mode": "adaptive"}))

        response = sts.assume_role(RoleArn=xacct_role, RoleSessionName="x-acct-role-for-qa-express")

        client_kwargs["aws_access_key_id"] = response["Credentials"]["AccessKeyId"]
        client_kwargs["aws_secret_access_key"] = response["Credentials"]["SecretAccessKey"]
        client_kwargs["aws_session_token"] = response["Credentials"]["SessionToken"]

        # x-acct region
        client_kwargs["region_name"] = xacct_region

    # Return cached session if it exists
    if region not in _bedrock_sessions:
        # Create new session with retry config
        session = boto3.Session(**client_kwargs)
        # Apply the retry config to the session
        session._session.set_config_variable("max_attempts", max_attempts)
        session._session.set_config_variable("retry_mode", retry_mode)

        _bedrock_sessions[region] = session

    return _bedrock_sessions[region]
