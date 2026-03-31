# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Test that the integration test fixture is working correctly.
"""

import os

import pytest


@pytest.mark.integration
def test_cloudformation_outputs_fixture(cloudformation_outputs):
    """Test that CloudFormation outputs are loaded correctly."""
    # Verify we have outputs from both stacks
    assert "MCPConfigParameterName" in cloudformation_outputs
    assert "AgentCoreMemoryId" in cloudformation_outputs
    assert "RegionName" in cloudformation_outputs or "AWS_REGION" in os.environ

    # Print outputs for debugging
    print("\nCloudFormation Outputs:")
    for key, value in sorted(cloudformation_outputs.items()):
        print(f"  {key}: {value}")


@pytest.mark.integration
def test_environment_variables_set(setup_environment):
    """Test that environment variables are set correctly."""
    # Verify required environment variables are set
    assert os.environ.get("MCP_CONFIG_PARAMETER") is not None
    assert os.environ.get("AWS_REGION") is not None
    assert os.environ.get("AGENTCORE_MEMORY_ID") is not None

    # Print environment variables for debugging
    print("\nEnvironment Variables:")
    print(f"  MCP_CONFIG_PARAMETER: {os.environ.get('MCP_CONFIG_PARAMETER')}")
    print(f"  AWS_REGION: {os.environ.get('AWS_REGION')}")
    print(f"  AGENTCORE_MEMORY_ID: {os.environ.get('AGENTCORE_MEMORY_ID')}")
