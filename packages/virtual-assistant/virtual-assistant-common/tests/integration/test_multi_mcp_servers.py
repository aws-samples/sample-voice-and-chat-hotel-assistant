# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Multi-MCP server integration tests.

These tests validate that the virtual assistant configuration supports
multiple MCP servers simultaneously, including both Hotel Assistant MCP
and Hotel PMS MCP servers.

Requirements tested:
- 11.7: Multi-MCP server integration with real AWS resources
"""

import base64
import os

import boto3
import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from virtual_assistant_common.mcp.config_manager import MCPConfigManager


@pytest.mark.integration
class TestMultiMCPServerIntegration:
    """Integration tests for multi-MCP server functionality."""

    @pytest.fixture
    def cloudformation_outputs(self):
        """
        Load CloudFormation stack outputs for integration tests.

        Returns:
            dict: Dictionary with outputs from both stacks
        """
        try:
            import boto3

            # Get HotelPmsStack outputs
            cfn_client = boto3.client("cloudformation")
            response = cfn_client.describe_stacks(StackName="HotelPmsStack")

            if not response["Stacks"]:
                pytest.skip("HotelPmsStack not found")

            hotel_pms_outputs = response["Stacks"][0].get("Outputs", [])

            # Convert to dictionary for easier access
            outputs = {}
            for output in hotel_pms_outputs:
                outputs[output["OutputKey"]] = output["OutputValue"]

            return outputs

        except cfn_client.exceptions.ClientError as e:
            pytest.skip(f"Failed to load CloudFormation outputs: {e}")
        except Exception as e:
            pytest.skip(f"Failed to load CloudFormation outputs: {str(e)}")

    @pytest.fixture
    def setup_environment(self, cloudformation_outputs):
        """Set up environment variables for integration tests."""
        # Store original environment
        original_env = os.environ.copy()

        # Set required environment variables from CloudFormation outputs
        os.environ["MCP_CONFIG_PARAMETER"] = cloudformation_outputs["MCPConfigParameterName"]
        os.environ["AWS_REGION"] = cloudformation_outputs.get("RegionName", "us-east-1")

        yield cloudformation_outputs

        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)

    def test_mcp_configuration_loaded_from_ssm(self, setup_environment):
        """
        Test that MCP configuration is loaded from SSM Parameter Store.

        Requirement 11.7: Multi-MCP server integration
        """
        print("\n🌐 Testing MCP configuration loading from SSM...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        print(f"✅ Loaded configuration for {len(servers)} MCP servers")

        # Verify both expected servers are configured
        assert "hotel-assistant-mcp" in servers, "hotel-assistant-mcp should be configured"
        assert "hotel-pms-mcp" in servers, "hotel-pms-mcp should be configured"

        print("✅ Both hotel-assistant-mcp and hotel-pms-mcp are configured")

        # Verify server configurations
        hotel_assistant_config = servers["hotel-assistant-mcp"]
        assert hotel_assistant_config.type == "streamable-http", "Should be streamable-http type"
        assert hotel_assistant_config.url, "Should have URL configured"
        assert hotel_assistant_config.authentication, "Should have authentication configured"

        hotel_pms_config = servers["hotel-pms-mcp"]
        assert hotel_pms_config.type == "streamable-http", "Should be streamable-http type"
        assert hotel_pms_config.url, "Should have URL configured"
        assert hotel_pms_config.authentication, "Should have authentication configured"

        print("✅ Server configurations are valid")

    def test_prompts_configured_for_hotel_assistant_mcp_only(self, setup_environment):
        """
        Test that prompts are configured for Hotel Assistant MCP only.

        Requirement 11.7: Multi-MCP server integration
        """
        print("\n📝 Testing prompt configuration...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Verify that hotel-assistant-mcp is configured with systemPrompts
        hotel_assistant_config = servers["hotel-assistant-mcp"]

        assert hotel_assistant_config.system_prompts is not None, (
            "hotel-assistant-mcp should have systemPrompts configuration"
        )

        print("✅ hotel-assistant-mcp has systemPrompts configuration")
        print(f"   Configured prompts: {hotel_assistant_config.system_prompts}")

        # Verify that hotel-pms-mcp does NOT have systemPrompts
        hotel_pms_config = servers["hotel-pms-mcp"]
        assert hotel_pms_config.system_prompts is None, "hotel-pms-mcp should NOT have systemPrompts configuration"

        print("✅ hotel-pms-mcp does NOT have systemPrompts (as expected)")

    def test_authentication_secrets_configured(self, setup_environment):
        """
        Test that authentication secrets are properly configured.

        Requirement 11.7: Multi-MCP server integration
        """
        print("\n🔐 Testing authentication configuration...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Verify both servers have authentication configured
        for server_name, server_config in servers.items():
            assert server_config.authentication is not None, f"{server_name} should have authentication"
            assert server_config.authentication.type == "cognito", f"{server_name} should use Cognito auth"
            assert server_config.authentication.secret_arn, f"{server_name} should have secret ARN"

            print(f"✅ {server_name} has Cognito authentication configured")

            # Verify we can retrieve credentials
            try:
                creds = config_manager.get_credentials(server_config.authentication.secret_arn)
                assert "userPoolId" in creds, "Credentials should have userPoolId"
                assert "clientId" in creds, "Credentials should have clientId"
                assert "clientSecret" in creds, "Credentials should have clientSecret"
                assert "region" in creds, "Credentials should have region"

                print(f"✅ {server_name} credentials retrieved successfully")
            except Exception as e:
                pytest.fail(f"Failed to retrieve credentials for {server_name}: {e}")

    def test_configuration_format_is_standard_mcp(self, setup_environment):
        """
        Test that configuration follows standard MCP format.

        Requirement 11.7: Multi-MCP server integration
        """
        print("\n📋 Testing standard MCP configuration format...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Verify standard MCP fields
        for server_name, server_config in servers.items():
            # Standard fields
            assert server_config.type, f"{server_name} should have type field"
            assert server_config.url, f"{server_name} should have url field"

            # Extension fields
            assert server_config.authentication, f"{server_name} should have authentication field"

            print(f"✅ {server_name} follows standard MCP format")

        print("✅ All servers follow standard MCP configuration format")

    def test_find_prompt_server_returns_hotel_assistant(self, setup_environment):
        """
        Test that find_prompt_server returns hotel-assistant-mcp.

        Requirement 11.7: Multi-MCP server integration
        """
        print("\n🔍 Testing prompt server discovery...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()

        # Find the server with systemPrompts
        prompt_server = config_manager.find_prompt_server()

        assert prompt_server is not None, "Should find a server with systemPrompts"
        assert prompt_server == "hotel-assistant-mcp", "hotel-assistant-mcp should be the prompt server"

        print(f"✅ Found prompt server: {prompt_server}")

    @pytest.mark.asyncio
    async def test_connect_and_list_tools_from_both_servers(self, setup_environment):
        """
        Test connecting to both MCP servers and listing their tools.

        Requirement 11.7: Multi-MCP server integration - verify tools from both servers
        """
        print("\n🔧 Testing tool discovery from both MCP servers...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        all_tools = {}

        # Connect to each server and list tools
        for server_name, server_config in servers.items():
            print(f"\n   Connecting to {server_name}...")

            try:
                # Get credentials
                creds = config_manager.get_credentials(server_config.authentication.secret_arn)

                # Get Cognito access token
                access_token = await self._get_cognito_token(creds)

                # Set up headers
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }

                # Connect to MCP server
                async with streamablehttp_client(
                    server_config.url,
                    headers=headers,
                    timeout=30,
                    terminate_on_close=False,
                ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                    # Initialize session
                    await session.initialize()

                    # List tools
                    tool_result = await session.list_tools()
                    tools = tool_result.tools
                    tool_names = [tool.name for tool in tools]

                    all_tools[server_name] = tool_names

                    print(f"   ✅ {server_name}: Found {len(tool_names)} tools")
                    for tool in tools:
                        print(f"      - {tool.name}: {tool.description or 'No description'}")

            except Exception as e:
                pytest.fail(f"Failed to connect to {server_name}: {e}")

        # Verify we got tools from both servers
        assert len(all_tools) == 2, f"Should have tools from 2 servers, got {len(all_tools)}"
        assert "hotel-assistant-mcp" in all_tools, "Should have tools from hotel-assistant-mcp"
        assert "hotel-pms-mcp" in all_tools, "Should have tools from hotel-pms-mcp"

        # Verify each server has at least one tool
        for server_name, tools in all_tools.items():
            assert len(tools) > 0, f"{server_name} should have at least one tool"

        print(f"\n✅ Successfully discovered tools from {len(all_tools)} MCP servers")

    @pytest.mark.asyncio
    async def test_list_prompts_from_hotel_assistant_mcp(self, setup_environment):
        """
        Test listing prompts from hotel-assistant-mcp server.

        Requirement 11.7: Multi-MCP server integration - verify prompts from hotel-assistant-mcp
        """
        print("\n📝 Testing prompt discovery from hotel-assistant-mcp...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Get hotel-assistant-mcp server
        server_config = servers["hotel-assistant-mcp"]

        try:
            # Get credentials
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            # Get Cognito access token
            access_token = await self._get_cognito_token(creds)

            # Set up headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Connect to MCP server
            async with streamablehttp_client(
                server_config.url,
                headers=headers,
                timeout=30,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # List prompts
                prompt_result = await session.list_prompts()
                prompts = prompt_result.prompts
                prompt_names = [prompt.name for prompt in prompts]

                print(f"   ✅ Found {len(prompt_names)} prompts")
                for prompt in prompts:
                    print(f"      - {prompt.name}: {prompt.description or 'No description'}")

                # Verify expected prompts are present
                expected_prompts = ["chat_system_prompt", "voice_system_prompt"]
                for expected_prompt in expected_prompts:
                    assert expected_prompt in prompt_names, (
                        f"Expected prompt '{expected_prompt}' not found in {prompt_names}"
                    )

                print("\n✅ Successfully discovered prompts from hotel-assistant-mcp")

        except Exception as e:
            pytest.fail(f"Failed to list prompts from hotel-assistant-mcp: {e}")

    @pytest.mark.asyncio
    async def test_retrieve_chat_prompt_content(self, setup_environment):
        """
        Test retrieving actual chat prompt content from hotel-assistant-mcp.

        Requirement 11.7: Multi-MCP server integration - verify prompt content
        """
        print("\n📄 Testing chat prompt content retrieval...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Get hotel-assistant-mcp server
        server_config = servers["hotel-assistant-mcp"]

        try:
            # Get credentials
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            # Get Cognito access token
            access_token = await self._get_cognito_token(creds)

            # Set up headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Connect to MCP server
            async with streamablehttp_client(
                server_config.url,
                headers=headers,
                timeout=120,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # Get chat prompt
                prompt_result = await session.get_prompt("chat_system_prompt")

                # Extract prompt messages
                messages = prompt_result.messages
                assert len(messages) > 0, "Should have at least one message"

                # Combine all message content
                prompt = "\n".join([msg.content.text for msg in messages if hasattr(msg.content, "text")])
                assert len(prompt) > 0, "Prompt should not be empty"

                print(f"   ✅ Retrieved chat prompt ({len(prompt)} characters)")
                print(f"   Preview: {prompt[:200]}...")

                # Verify prompt contains expected content
                assert len(prompt) > 100, "Prompt should be substantial"

                print("\n✅ Successfully retrieved chat prompt content")

        except Exception as e:
            pytest.fail(f"Failed to retrieve chat prompt: {e}")

    @pytest.mark.asyncio
    async def test_call_hotel_pms_get_hotels_tool(self, setup_environment):
        """
        Test calling the HotelPMS___get_hotels tool from hotel-pms-mcp server.

        Requirement 11.7: Multi-MCP server integration - verify tool execution
        """
        print("\n🔧 Testing HotelPMS___get_hotels tool execution...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Get hotel-pms-mcp server
        server_config = servers["hotel-pms-mcp"]

        try:
            # Get credentials
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            # Get Cognito access token
            access_token = await self._get_cognito_token(creds)

            # Set up headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Connect to MCP server
            async with streamablehttp_client(
                server_config.url,
                headers=headers,
                timeout=30,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # Call the get_hotels tool
                print("   Calling HotelPMS___get_hotels tool...")
                call_result = await session.call_tool(
                    name="HotelPMS___get_hotels",
                    arguments={},
                )

                # Verify response structure
                assert call_result.content is not None, "Tool response should contain content"
                print(f"   ✅ Tool returned content: {len(call_result.content)} items")

                # Parse the response
                import json

                if isinstance(call_result.content, list) and len(call_result.content) > 0:
                    text_content = (
                        call_result.content[0].text
                        if hasattr(call_result.content[0], "text")
                        else str(call_result.content[0])
                    )

                    if text_content:
                        try:
                            # Parse as JSON
                            response_data = json.loads(text_content)
                            print("   ✅ Tool response parsed successfully")

                            # Check for error in response
                            if isinstance(response_data, dict) and response_data.get("error"):
                                pytest.fail(
                                    f"Tool returned error: {response_data.get('error_code')} - "
                                    f"{response_data.get('message')}"
                                )

                            # Verify hotels data structure
                            if isinstance(response_data, dict) and "hotels" in response_data:
                                hotels = response_data["hotels"]
                                print(f"   ✅ Found {len(hotels)} hotels in response")

                                if len(hotels) > 0:
                                    first_hotel = hotels[0]
                                    print(
                                        f"      First hotel: {first_hotel.get('name', 'Unknown')} "
                                        f"(ID: {first_hotel.get('hotel_id', 'Unknown')})"
                                    )
                            elif isinstance(response_data, list):
                                print(f"   ✅ Found {len(response_data)} hotels in response")
                            else:
                                print(f"   ⚠️  Unexpected response structure: {type(response_data)}")

                        except json.JSONDecodeError as e:
                            pytest.fail(
                                f"Failed to parse tool response as JSON: {e}\nContent: {text_content[:200]}"
                            )
                    else:
                        pytest.fail("Tool response content is empty")
                else:
                    pytest.fail(f"Unexpected tool response structure: {call_result.content}")

                print("\n✅ Successfully executed HotelPMS___get_hotels tool")

        except Exception as e:
            pytest.fail(f"Failed to execute HotelPMS___get_hotels tool: {e}")

    @pytest.mark.asyncio
    async def test_call_query_hotel_knowledge_tool(self, setup_environment):
        """
        Test calling the query_hotel_knowledge tool from hotel-assistant-mcp server.

        Requirement 11.7: Multi-MCP server integration - verify tool execution
        """
        print("\n🔍 Testing query_hotel_knowledge tool execution...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        # Get hotel-assistant-mcp server
        server_config = servers["hotel-assistant-mcp"]

        try:
            # Get credentials
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            # Get Cognito access token
            access_token = await self._get_cognito_token(creds)

            # Set up headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Connect to MCP server
            async with streamablehttp_client(
                server_config.url,
                headers=headers,
                timeout=30,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
                # Initialize session
                await session.initialize()

                # Call the query_hotel_knowledge tool
                print("   Calling query_hotel_knowledge tool...")
                call_result = await session.call_tool(
                    name="query_hotel_knowledge",
                    arguments={
                        "query": "What amenities are available?",
                        "max_results": 3,
                    },
                )

                # Verify response structure
                assert call_result.content is not None, "Tool response should contain content"
                print(f"   ✅ Tool returned content: {len(call_result.content)} items")

                # Parse the response - tool now returns a formatted string
                if isinstance(call_result.content, list) and len(call_result.content) > 0:
                    text_content = (
                        call_result.content[0].text
                        if hasattr(call_result.content[0], "text")
                        else str(call_result.content[0])
                    )

                    if text_content:
                        # Verify it's a string (not JSON)
                        assert isinstance(text_content, str), "Tool should return a formatted string"
                        print(f"   ✅ Tool response is a formatted string ({len(text_content)} characters)")

                        # Verify formatting includes expected elements
                        text_lower = text_content.lower()

                        # Check for either results or "no relevant information" message
                        has_results = "result" in text_lower and "relevance:" in text_lower
                        has_no_results = "no relevant information found" in text_lower

                        assert has_results or has_no_results, (
                            "Response should contain either formatted results or 'no relevant information' message"
                        )

                        if has_results:
                            print("   ✅ Found formatted knowledge base results")
                            print(f"      Content preview: {text_content[:150]}...")
                        else:
                            print("   ⚠️  No relevant information found for query")
                    else:
                        pytest.fail("Tool response content is empty")
                else:
                    pytest.fail(f"Unexpected tool response structure: {call_result.content}")

                print("\n✅ Successfully executed query_hotel_knowledge tool")

        except Exception as e:
            # Knowledge base might not be configured, which is acceptable
            if "KNOWLEDGE_BASE_ID" in str(e) or "knowledge base" in str(e).lower():
                print(f"   ⚠️  Knowledge base not configured, skipping test: {e}")
                pytest.skip(f"Knowledge base not configured: {e}")
            else:
                pytest.fail(f"Failed to execute query_hotel_knowledge tool: {e}")


@pytest.mark.asyncio
async def test_call_get_hotels_tool_via_agentcore_gateway(self, setup_environment):
    """
    Test calling HotelPMS___get_hotels tool via AgentCore Gateway.

    This test validates the complete flow:
    - OAuth2 client credentials authentication
    - MCP connection to AgentCore Gateway
    - Tool discovery
    - Tool execution (get_hotels)
    - Response parsing

    Requirement 11.7: Multi-MCP server integration - verify AgentCore Gateway integration
    """
    print("\n🔧 Testing HotelPMS___get_hotels tool via AgentCore Gateway...")

    # Get configuration from CloudFormation outputs
    gateway_url = setup_environment.get("HotelPMSMCPGatewayUrl")
    if not gateway_url:
        pytest.skip("HotelPMSMCPGatewayUrl not found in stack outputs")

    # Get Cognito credentials from Secrets Manager
    secrets_client = boto3.client("secretsmanager")
    secret_arn = setup_environment.get("HotelPMSMCPSecretArn")
    if not secret_arn:
        pytest.skip("HotelPMSMCPSecretArn not found in stack outputs")

    try:
        secret_response = secrets_client.get_secret_value(SecretId=secret_arn)
        credentials = json.loads(secret_response["SecretString"])

        client_id = credentials["clientId"]
        client_secret = credentials["clientSecret"]
        user_pool_id = credentials["userPoolId"]
        region = credentials.get("region", "us-east-1")

        print(f"   Gateway URL: {gateway_url}")
        print(f"   User Pool ID: {user_pool_id}")

    except Exception as e:
        pytest.skip(f"Failed to get credentials: {e}")

    # Get Cognito domain for token endpoint
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        user_pool_response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
        domain = user_pool_response["UserPool"].get("Domain")
        if not domain:
            pytest.skip("Cognito User Pool does not have a domain configured")

        token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
        print(f"   Token URL: {token_url}")

    except Exception as e:
        pytest.skip(f"Failed to get Cognito domain: {e}")

    # Step 1: Get OAuth2 access token
    print("\n   Step 1: Acquiring OAuth2 access token...")
    try:
        token_response = httpx.post(
            token_url,
            data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30.0,
        )

        if token_response.status_code != 200:
            pytest.fail(f"Failed to get access token: {token_response.status_code} - {token_response.text}")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            pytest.fail("No access token in response")

        print("   ✅ Access token acquired")

    except Exception as e:
        pytest.fail(f"Failed to acquire access token: {e}")

    # Step 2: Connect to AgentCore Gateway MCP server
    print("\n   Step 2: Connecting to AgentCore Gateway...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with streamablehttp_client(
            url=gateway_url,
            headers=headers,
            timeout=30,
            terminate_on_close=False,
        ) as (read_stream, write_stream, _), ClientSession(read_stream, write_stream) as session:
            # Step 3: Initialize MCP session
            print("   Step 3: Initializing MCP session...")
            init_response = await session.initialize()
            print(f"   ✅ MCP session initialized: {init_response.server_info.name}")

            # Step 4: List available tools
            print("\n   Step 4: Listing available tools...")
            cursor = True
            tools = []
            while cursor:
                next_cursor = cursor if type(cursor) != bool else None
                list_tools_response = await session.list_tools(next_cursor)
                tools.extend(list_tools_response.tools)
                cursor = list_tools_response.nextCursor

            tool_names = [tool.name for tool in tools]
            print(f"   ✅ Found {len(tools)} tools")

            # Verify get_hotels tool exists
            if "HotelPMS___get_hotels" not in tool_names:
                pytest.fail(f"HotelPMS___get_hotels tool not found. Available tools: {tool_names}")

            print("   ✅ HotelPMS___get_hotels tool found")

            # Step 5: Call get_hotels tool
            print("\n   Step 5: Calling HotelPMS___get_hotels tool...")
            call_result = await session.call_tool(
                name="HotelPMS___get_hotels",
                arguments={},
            )

            # Step 6: Parse and validate response
            print("   Step 6: Parsing response...")
            assert call_result.content is not None, "Tool response should contain content"
            print(f"   ✅ Tool returned content: {len(call_result.content)} items")

            # Parse the response
            if isinstance(call_result.content, list) and len(call_result.content) > 0:
                text_content = (
                    call_result.content[0].text
                    if hasattr(call_result.content[0], "text")
                    else str(call_result.content[0])
                )

                if text_content:
                    try:
                        # Parse as JSON
                        response_data = json.loads(text_content)
                        print("   ✅ Tool response parsed successfully")

                        # Check for error in response
                        if isinstance(response_data, dict) and response_data.get("error"):
                            pytest.fail(
                                f"Tool returned error: {response_data.get('error_code')} - "
                                f"{response_data.get('message')}"
                            )

                        # Verify hotels data structure
                        if isinstance(response_data, dict) and "hotels" in response_data:
                            hotels = response_data["hotels"]
                            print(f"   ✅ Found {len(hotels)} hotels in response")

                            if len(hotels) > 0:
                                first_hotel = hotels[0]
                                print(
                                    f"      First hotel: {first_hotel.get('name', 'Unknown')} "
                                    f"(ID: {first_hotel.get('hotel_id', 'Unknown')})"
                                )

                                # Verify hotel structure
                                assert "hotel_id" in first_hotel, "Hotel should have hotel_id"
                                assert "name" in first_hotel, "Hotel should have name"
                                assert "location" in first_hotel, "Hotel should have location"

                                print("\n✅ Successfully called HotelPMS___get_hotels via AgentCore Gateway!")
                                print("   - OAuth2 authentication: ✅")
                                print("   - MCP connection: ✅")
                                print("   - Tool discovery: ✅")
                                print("   - Tool execution: ✅")
                                print("   - Response parsing: ✅")
                            else:
                                print("   ⚠️  No hotels returned (empty result)")
                        elif isinstance(response_data, list):
                            print(f"   ✅ Found {len(response_data)} hotels in response")
                        else:
                            pytest.fail(f"Unexpected response structure: {type(response_data)}")

                    except json.JSONDecodeError as e:
                        pytest.fail(f"Failed to parse tool response as JSON: {e}\nContent: {text_content[:200]}")
                else:
                    pytest.fail("Tool response content is empty")
            else:
                pytest.fail(f"Unexpected tool response structure: {call_result.content}")

    except Exception as e:
        pytest.fail(f"Failed to execute get_hotels tool via AgentCore Gateway: {e}")

    async def _get_cognito_token(self, credentials: dict) -> str:
        """
        Get Cognito access token using client credentials flow.

        Args:
            credentials: Dictionary with userPoolId, clientId, clientSecret, region

        Returns:
            Access token string
        """
        try:
            # Get Cognito domain from user pool
            cognito_client = boto3.client("cognito-idp", region_name=credentials["region"])
            user_pool_response = cognito_client.describe_user_pool(UserPoolId=credentials["userPoolId"])
            domain = user_pool_response["UserPool"].get("Domain")

            if not domain:
                raise ValueError("Cognito User Pool does not have a domain configured")

            # Construct token endpoint
            token_url = f"https://{domain}.auth.{credentials['region']}.amazoncognito.com/oauth2/token"

            # Prepare client credentials
            client_id = credentials["clientId"]
            client_secret = credentials["clientSecret"]
            credentials_str = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials_str.encode()).decode()

            # Request access token using client credentials flow
            response = httpx.post(
                token_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {encoded_credentials}",
                },
                data={
                    "grant_type": "client_credentials",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise ValueError(f"Failed to get access token: {response.status_code} - {response.text}")

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise ValueError("No access token in response")

            return access_token

        except Exception as e:
            raise ValueError(f"Could not obtain Cognito token: {e}")
