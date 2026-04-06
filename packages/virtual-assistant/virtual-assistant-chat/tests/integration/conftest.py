# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Pytest configuration for chat agent integration tests.

Provides shared fixtures for CloudFormation outputs and environment setup.
"""

import os

import boto3
import pytest


@pytest.fixture(scope="session")
def cloudformation_outputs():
    """
    Load CloudFormation stack outputs for integration tests.

    Returns:
        dict: Dictionary with outputs from both stacks

    Raises:
        pytest.fail: If stacks are not deployed or outputs cannot be loaded
    """
    cfn_client = boto3.client("cloudformation")

    # Get VirtualAssistantStack outputs (required for chat agent)
    try:
        response = cfn_client.describe_stacks(StackName="VirtualAssistantStack")
    except cfn_client.exceptions.ClientError as e:
        pytest.fail(
            f"VirtualAssistantStack not found. Please deploy infrastructure first: {e}\nRun: pnpm exec nx deploy infra"
        )

    if not response["Stacks"]:
        pytest.fail("VirtualAssistantStack exists but has no stack data")

    va_outputs = response["Stacks"][0].get("Outputs", [])

    # Get HotelPmsStack outputs (for MCP configuration)
    try:
        pms_response = cfn_client.describe_stacks(StackName="HotelPmsStack")
        pms_outputs = pms_response["Stacks"][0].get("Outputs", []) if pms_response["Stacks"] else []
    except Exception:
        pms_outputs = []

    # Convert to dictionary for easier access
    outputs = {}
    for output in va_outputs + pms_outputs:
        outputs[output["OutputKey"]] = output["OutputValue"]

    # Verify required outputs are present
    required_outputs = ["AgentCoreRuntimeArn", "AgentCoreMemoryArn", "MCPConfigParameterName", "RegionName"]
    missing_outputs = [key for key in required_outputs if key not in outputs]
    if missing_outputs:
        pytest.fail(
            f"Required CloudFormation outputs missing: {missing_outputs}\nAvailable outputs: {list(outputs.keys())}"
        )

    return outputs


@pytest.fixture
def setup_environment(cloudformation_outputs):
    """Set up environment variables for integration tests."""
    # Store original environment
    original_env = os.environ.copy()

    # Set required environment variables from CloudFormation outputs
    os.environ["MCP_CONFIG_PARAMETER"] = cloudformation_outputs["MCPConfigParameterName"]
    os.environ["AWS_REGION"] = cloudformation_outputs.get("RegionName", "us-east-1")
    os.environ["AGENTCORE_MEMORY_ID"] = cloudformation_outputs["AgentCoreMemoryArn"].split("/")[-1]

    yield cloudformation_outputs

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
