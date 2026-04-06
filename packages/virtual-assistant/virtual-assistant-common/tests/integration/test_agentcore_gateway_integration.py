# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration test for AgentCore Gateway deployment.

This test verifies that the AgentCore Gateway is properly deployed and can be
accessed using authenticated MCP connections to list Hotel PMS tools.
"""

import boto3
import pytest
from mcp.client.session import ClientSession

from virtual_assistant_common.cognito_mcp.cognito_mcp_client import cognito_mcp_client


@pytest.mark.integration
async def test_agentcore_gateway_tool_listing():
    """Test listing tools from deployed AgentCore Gateway using authenticated MCP connection."""

    # Get stack outputs from HotelPmsStack
    cfn = boto3.client("cloudformation", region_name="us-east-1")

    try:
        response = cfn.describe_stacks(StackName="HotelPmsStack")
        outputs = {o["OutputKey"]: o["OutputValue"] for o in response["Stacks"][0]["Outputs"]}
    except Exception as e:
        pytest.skip(f"HotelPmsStack not deployed or not accessible: {e}")

    # Verify required outputs exist
    required_outputs = ["GatewayId", "CognitoUserPoolId", "CognitoClientId"]
    missing_outputs = [key for key in required_outputs if key not in outputs]
    if missing_outputs:
        pytest.skip(f"Required stack outputs missing: {missing_outputs}")

    gateway_id = outputs["GatewayId"]
    gateway_url = f"https://{gateway_id}.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
    user_pool_id = outputs["CognitoUserPoolId"]
    client_id = outputs["CognitoClientId"]

    print("\n🔍 Testing AgentCore Gateway MCP Integration")
    print(f"Gateway URL: {gateway_url}")
    print(f"User Pool: {user_pool_id}")
    print(f"Client ID: {client_id}")

    # Get client secret from Cognito
    cognito_idp = boto3.client("cognito-idp", region_name="us-east-1")

    try:
        # Describe the user pool client to get the secret
        client_response = cognito_idp.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)

        client_secret = client_response["UserPoolClient"].get("ClientSecret")

        if not client_secret:
            pytest.skip("Client secret not available - client may not be configured for client credentials flow")

        print("✅ Retrieved client secret from Cognito")

        # Connect to AgentCore Gateway using cognito_mcp_client
        async with cognito_mcp_client(
            url=gateway_url,
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region="us-east-1",
            timeout=30.0,
        ) as (read_stream, write_stream, get_session_id):
            print("✅ Established authenticated MCP streams to AgentCore Gateway")

            # Create ClientSession from streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("✅ MCP session initialized")

                # List tools from AgentCore Gateway
                tools_response = await session.list_tools()
                tools = tools_response.tools

                print(f"\n✅ Successfully listed {len(tools)} tools from AgentCore Gateway:")

                # Display tool information
                for tool in tools:
                    print(f"  - {tool.name}")
                    if hasattr(tool, "description") and tool.description:
                        desc = tool.description[:80] + "..." if len(tool.description) > 80 else tool.description
                        print(f"    {desc}")

                # Verify expected Hotel PMS tools are present
                # Tool names from AgentCore Gateway include the target name as a prefix
                tool_names = [tool.name for tool in tools]
                expected_tool_suffixes = [
                    "check_availability",
                    "get_hotels",
                    "create_reservation",
                    "get_reservation",
                    "update_reservation",
                ]

                # Check if tool names end with expected suffixes
                found_tools = []
                missing_tools = []
                for suffix in expected_tool_suffixes:
                    matching = [t for t in tool_names if t.endswith(f"___{suffix}")]
                    if matching:
                        found_tools.append(suffix)
                    else:
                        missing_tools.append(suffix)

                if found_tools:
                    print(f"\n✅ Found expected Hotel PMS tools ({len(found_tools)}/{len(expected_tool_suffixes)}):")
                    for tool in found_tools:
                        print(f"  ✓ {tool}")

                if missing_tools:
                    print(f"\n⚠️  Missing expected tools ({len(missing_tools)}/{len(expected_tool_suffixes)}):")
                    for tool in missing_tools:
                        print(f"  ✗ {tool}")

                # Verify we got some tools
                assert len(tools) > 0, "Should have at least one tool available from AgentCore Gateway"

                # Verify at least some expected tools are present
                assert len(found_tools) > 0, (
                    f"Should find at least some expected Hotel PMS tools. Available: {tool_names}"
                )

                print("\n✅ AgentCore Gateway integration test PASSED!")
                print("   - Gateway accessible: ✓")
                print("   - Authentication working: ✓")
                print("   - MCP protocol working: ✓")
                print(f"   - Tools available: {len(tools)} ✓")
                print(f"   - Expected tools found: {len(found_tools)}/{len(expected_tool_suffixes)} ✓")

    except Exception as e:
        print(f"\n❌ Error during AgentCore Gateway integration test: {e}")
        raise
