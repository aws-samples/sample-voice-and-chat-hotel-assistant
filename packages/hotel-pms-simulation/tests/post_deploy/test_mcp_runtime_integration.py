# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for deployed MCP Server on AgentCore Runtime.

This test suite validates the MCP server deployment on AgentCore Runtime using
proper MCP client with Cognito OAuth2 client credentials authentication.

Note: With the response interceptor enabled, all HTTP responses return status code 200.
Success is indicated by the presence of expected data fields in the response body.

Prerequisites:
- HotelPmsStack deployed with MCP Server on AgentCore Runtime and response interceptor
- AWS credentials configured

Usage:
    pytest tests/post_deploy/test_mcp_runtime_integration.py -v -s -m integration
"""

import base64
from urllib.parse import quote

import boto3
import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@pytest.fixture(scope="session")
def mcp_server_info(stack_name):
    """Get MCP Server information from deployed CloudFormation stack."""
    cf_client = boto3.client("cloudformation")

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0]["Outputs"]

        mcp_info = {}
        for output in outputs:
            key = output["OutputKey"]
            value = output["OutputValue"]

            if "MCPServer" in key:
                if "RuntimeArn" in key:
                    mcp_info["runtime_arn"] = value
                elif "RuntimeId" in key:
                    mcp_info["runtime_id"] = value
                elif "RuntimeName" in key:
                    mcp_info["runtime_name"] = value
            elif "CognitoUserPoolId" in key:
                mcp_info["user_pool_id"] = value
            elif "CognitoClientId" in key:
                mcp_info["client_id"] = value

        if "runtime_arn" not in mcp_info:
            print("⚠️ MCP Server Runtime ARN not found in stack outputs")
            return None

        # Construct runtime URL from runtime ARN
        # AgentCore Runtime MCP servers use /invocations endpoint with URL-encoded ARN
        runtime_arn = mcp_info["runtime_arn"]
        # Extract region from ARN
        region = runtime_arn.split(":")[3]
        # URL-encode the ARN
        encoded_arn = quote(runtime_arn, safe="")
        mcp_info["runtime_url"] = (
            f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
        )

        print(f"✅ Found MCP Server Runtime: {mcp_info['runtime_id']}")
        print(f"   Runtime URL: {mcp_info['runtime_url']}")
        return mcp_info

    except Exception as e:
        print(f"⚠️ Could not get MCP Server info from stack {stack_name}: {e}")
        return None


@pytest.fixture(scope="session")
def cognito_access_token(mcp_server_info):
    """Get Cognito access token using client credentials flow."""
    if not mcp_server_info or "user_pool_id" not in mcp_server_info:
        return None

    try:
        # Get Cognito domain from user pool
        cognito_client = boto3.client("cognito-idp")
        user_pool_response = cognito_client.describe_user_pool(
            UserPoolId=mcp_server_info["user_pool_id"]
        )
        domain = user_pool_response["UserPool"].get("Domain")

        if not domain:
            print("⚠️ Cognito User Pool does not have a domain configured")
            return None

        # Get client secret from Cognito User Pool Client
        try:
            client_response = cognito_client.describe_user_pool_client(
                UserPoolId=mcp_server_info["user_pool_id"],
                ClientId=mcp_server_info["client_id"],
            )
            client_secret = client_response["UserPoolClient"].get("ClientSecret")

            if not client_secret:
                print("⚠️ Cognito User Pool Client does not have a secret")
                return None

            print("✅ Retrieved client secret from Cognito User Pool Client")

        except Exception as e:
            print(f"⚠️ Could not retrieve client secret from Cognito: {e}")
            return None

        # Construct token endpoint
        region = user_pool_response["UserPool"]["Arn"].split(":")[3]
        token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

        # Prepare client credentials
        client_id = mcp_server_info["client_id"]
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        # Request access token using client credentials flow
        response = httpx.post(
            token_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {encoded_credentials}",
            },
            data={
                "grant_type": "client_credentials",
                # Don't specify scope - let Cognito use the default scopes
            },
            timeout=30.0,
        )

        if response.status_code != 200:
            print(
                f"⚠️ Failed to get access token: {response.status_code} - {response.text}"
            )
            return None

        token_data = response.json()
        access_token = token_data.get("access_token")

        if access_token:
            print("✅ Obtained Cognito access token")
        else:
            print("⚠️ No access token in response")

        return access_token

    except Exception as e:
        print(f"⚠️ Could not obtain Cognito token: {e}")
        return None


@pytest.mark.integration
class TestMCPRuntimeDeployment:
    """Integration tests for MCP Server deployment on AgentCore Runtime."""

    def test_mcp_server_deployed(self, mcp_server_info):
        """Test that MCP server is deployed and accessible.

        With response interceptor: All responses return 200 status code.
        Validates: Requirements 6.1, 6.3
        """
        if not mcp_server_info:
            pytest.skip("MCP Server not deployed")

        assert "runtime_arn" in mcp_server_info
        assert "runtime_id" in mcp_server_info
        assert "runtime_url" in mcp_server_info

        print("\n✅ MCP Server deployed successfully")
        print(f"   Runtime ARN: {mcp_server_info['runtime_arn']}")
        print(f"   Runtime ID: {mcp_server_info['runtime_id']}")

    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_server_info, cognito_access_token):
        """Test listing available MCP tools using MCP client.

        With response interceptor: All responses return 200 status code.
        Success is indicated by the presence of expected tools in response.
        Validates: Requirements 6.1, 6.3, 6.5
        """
        if not mcp_server_info or not cognito_access_token:
            pytest.skip("MCP Server or authentication not available")

        try:
            # Set up headers with Bearer token
            headers = {
                "Authorization": f"Bearer {cognito_access_token}",
                "Content-Type": "application/json",
            }

            # Connect to MCP server using streamablehttp_client
            print("   Connecting to MCP server...")
            async with streamablehttp_client(
                mcp_server_info["runtime_url"],
                headers=headers,
                timeout=30,  # Reduced timeout
                terminate_on_close=False,
            ) as (read_stream, write_stream, _):
                print("   Connected, creating session...")
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the session
                    print("   Initializing session...")
                    await session.initialize()
                    print("   Session initialized, listing tools...")

                    # List tools
                    tool_result = await session.list_tools()
                    print("   Tools listed successfully!")

                    # Verify expected tools are present
                    tools = tool_result.tools
                    tool_names = [tool.name for tool in tools]
                    expected_tools = ["query_hotel_knowledge"]

                    for expected_tool in expected_tools:
                        assert expected_tool in tool_names, (
                            f"Expected tool '{expected_tool}' not found in {tool_names}"
                        )

                    print(f"\n✅ Found {len(tool_names)} tools")
                    for tool in tools:
                        print(
                            f"   - {tool.name}: {tool.description or 'No description'}"
                        )

                    return tools

        except Exception as e:
            pytest.fail(f"Failed to list tools: {e}")

    @pytest.mark.asyncio
    async def test_get_chat_prompt(self, mcp_server_info, cognito_access_token):
        """Test retrieving chat prompt and verify it contains 4 hotels.

        With response interceptor: All responses return 200 status code.
        Success is indicated by the presence of prompt data in response.
        Validates: Requirements 6.1, 6.3, 6.5
        """
        if not mcp_server_info or not cognito_access_token:
            pytest.skip("MCP Server or authentication not available")

        try:
            headers = {
                "Authorization": f"Bearer {cognito_access_token}",
                "Content-Type": "application/json",
            }

            async with streamablehttp_client(
                mcp_server_info["runtime_url"],
                headers=headers,
                timeout=120,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()

                    # Get chat prompt (using correct prompt name)
                    prompt_result = await session.get_prompt("chat_system_prompt")

                    # Extract prompt messages
                    messages = prompt_result.messages
                    assert len(messages) > 0, "Should have at least one message"

                    # Combine all message content
                    prompt = "\n".join(
                        [
                            msg.content.text
                            for msg in messages
                            if hasattr(msg.content, "text")
                        ]
                    )
                    assert len(prompt) > 0, "Prompt should not be empty"

                    # Verify prompt contains hotel information
                    assert "Available hotels:" in prompt, (
                        "Prompt should contain hotel list section"
                    )

                    # Count hotels in the prompt (each hotel line contains "(ID: H-")
                    hotel_lines = [
                        line for line in prompt.split("\n") if "(ID: H-" in line
                    ]
                    hotel_count = len(hotel_lines)

                    assert hotel_count == 4, (
                        f"Expected 4 hotels in prompt, found {hotel_count}"
                    )

                    # Extract hotel IDs
                    hotel_ids = []
                    for line in hotel_lines:
                        id_part = line.split("(ID:")[1].strip().rstrip(")")
                        hotel_ids.append(id_part)

                    print("\n✅ Chat prompt retrieved successfully")
                    print(f"   Prompt length: {len(prompt)} characters")
                    print(f"   Hotels found: {hotel_count}")
                    print(f"   Hotel IDs: {hotel_ids}")

                    return prompt, hotel_ids

        except Exception as e:
            pytest.fail(f"Failed to get chat prompt: {e}")

    @pytest.mark.asyncio
    async def test_query_restaurants_all_hotels(
        self, mcp_server_info, cognito_access_token
    ):
        """Test querying restaurants at all hotels.

        With response interceptor: All responses return 200 status code.
        Success is indicated by the presence of restaurant data in response.
        Validates: Requirements 6.1, 6.3, 6.5
        """
        if not mcp_server_info or not cognito_access_token:
            pytest.skip("MCP Server or authentication not available")

        headers = {
            "Authorization": f"Bearer {cognito_access_token}",
            "Content-Type": "application/json",
        }

        async with streamablehttp_client(
            mcp_server_info["runtime_url"],
            headers=headers,
            timeout=120,
            terminate_on_close=False,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call query_hotel_knowledge tool
                tool_result = await session.call_tool(
                    "query_hotel_knowledge",
                    arguments={
                        "query": "What restaurants are available at the hotels?",
                        "max_results": 10,
                    },
                )

                # Parse the result - tool now returns a formatted string
                result_text = tool_result.content[0].text

                # Verify result is a string
                assert isinstance(result_text, str), "Should return a formatted string"
                assert len(result_text) > 0, "Result should not be empty"

                # Check for restaurant-related keywords
                result_lower = result_text.lower()
                assert any(
                    keyword in result_lower
                    for keyword in ["restaurant", "dining", "food", "cuisine"]
                ), "Results should contain restaurant-related keywords"

                # Verify formatting includes result numbers and relevance scores
                assert "result" in result_lower, "Should contain result numbering"
                assert "relevance:" in result_lower, "Should contain relevance scores"

        # Print results outside the session context
        print("\n✅ Retrieved formatted results for all hotels")
        print(f"   Result length: {len(result_text)} characters")
        print(f"   Preview: {result_text[:200]}...")

    @pytest.mark.asyncio
    async def test_query_restaurants_single_hotel(
        self, mcp_server_info, cognito_access_token
    ):
        """Test querying restaurants at a specific hotel.

        With response interceptor: All responses return 200 status code.
        Success is indicated by the presence of restaurant data in response.
        Validates: Requirements 6.1, 6.3, 6.5
        """
        if not mcp_server_info or not cognito_access_token:
            pytest.skip("MCP Server or authentication not available")

        # Query for a specific hotel (Paraiso Vallarta)
        hotel_id = "H-PVR-002"

        headers = {
            "Authorization": f"Bearer {cognito_access_token}",
            "Content-Type": "application/json",
        }

        async with streamablehttp_client(
            mcp_server_info["runtime_url"],
            headers=headers,
            timeout=120,
            terminate_on_close=False,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call query_hotel_knowledge tool with hotel filter
                tool_result = await session.call_tool(
                    "query_hotel_knowledge",
                    arguments={
                        "query": "What restaurants and dining options are available?",
                        "hotel_ids": [hotel_id],
                        "max_results": 5,
                    },
                )

                # Parse the result - tool now returns a formatted string
                result_text = tool_result.content[0].text

                # Verify result is a string
                assert isinstance(result_text, str), "Should return a formatted string"
                assert len(result_text) > 0, "Result should not be empty"

                # Verify result contains content (not the "No relevant information" message)
                assert "No relevant information found" not in result_text, (
                    "Should have found relevant results for specific hotel"
                )

                # Verify formatting includes result numbers and relevance scores
                assert "result" in result_text.lower(), (
                    "Should contain result numbering"
                )
                assert "relevance:" in result_text.lower(), (
                    "Should contain relevance scores"
                )

        # Print results outside the session context
        print(f"\n✅ Retrieved formatted results for hotel {hotel_id}")
        print(f"   Result length: {len(result_text)} characters")
        print(f"   Preview: {result_text[:200]}...")

        return result_text
