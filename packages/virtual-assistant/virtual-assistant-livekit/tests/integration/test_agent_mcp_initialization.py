# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration tests for agent MCP initialization with real AWS resources.

These tests validate the complete MCP initialization flow including:
- Loading MCP configuration from SSM Parameter Store
- Connecting to multiple MCP servers (hotel-assistant-mcp, hotel-pms-mcp)
- Loading system prompts from MCP servers
- Creating HotelPmsMCPServer wrappers
- Tool discovery and availability

Based on the pattern from virtual-assistant-common/tests/integration/test_multi_mcp_servers.py

REQUIRED CREDENTIALS:
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- Deployed CloudFormation stacks: HotelPmsStack (required), VirtualAssistantStack (optional)
- MCP configuration in SSM Parameter Store (created by HotelPmsStack)
- Cognito credentials in Secrets Manager (created by HotelPmsStack)

NOT REQUIRED:
- LiveKit API key/secret (these tests don't create LiveKit sessions)
- .env file (configuration comes from CloudFormation/SSM)

These tests will FAIL (not skip) if:
- AWS credentials are not configured
- CloudFormation stacks are not deployed
- MCP configuration is missing or invalid
- Cognito authentication fails
- MCP servers are unreachable
"""

import base64
import os

import boto3
import httpx
import pytest
from livekit.agents import JobProcess
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from virtual_assistant_common.mcp import (
    AssistantType,
    MCPConfigManager,
    PromptLoader,
)

from virtual_assistant_livekit.agent import prewarm


@pytest.mark.integration
class TestAgentMCPInitialization:
    """Integration tests for agent MCP initialization with real resources."""

    @pytest.fixture
    def cloudformation_outputs(self):
        """
        Load CloudFormation stack outputs for integration tests.

        Returns:
            dict: Dictionary with outputs from both stacks

        Raises:
            AssertionError: If stacks are not deployed or outputs cannot be loaded
        """
        cfn_client = boto3.client("cloudformation")

        # Get HotelPmsStack outputs
        try:
            response = cfn_client.describe_stacks(StackName="HotelPmsStack")
        except cfn_client.exceptions.ClientError as e:
            pytest.fail(
                f"HotelPmsStack not found. Please deploy infrastructure first: {e}\nRun: pnpm exec nx deploy infra"
            )

        if not response["Stacks"]:
            pytest.fail("HotelPmsStack exists but has no stack data")

        hotel_pms_outputs = response["Stacks"][0].get("Outputs", [])

        # Get VirtualAssistantStack outputs (optional - not all tests need it)
        try:
            va_response = cfn_client.describe_stacks(StackName="VirtualAssistantStack")
            va_outputs = va_response["Stacks"][0].get("Outputs", []) if va_response["Stacks"] else []
        except Exception:
            va_outputs = []

        # Convert to dictionary for easier access
        outputs = {}
        for output in hotel_pms_outputs + va_outputs:
            outputs[output["OutputKey"]] = output["OutputValue"]

        # Verify required outputs are present
        required_outputs = ["MCPConfigParameterName", "RegionName"]
        missing_outputs = [key for key in required_outputs if key not in outputs]
        if missing_outputs:
            pytest.fail(
                f"Required CloudFormation outputs missing: {missing_outputs}\nAvailable outputs: {list(outputs.keys())}"
            )

        return outputs

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

    def test_mcp_config_manager_loads_configuration(self, setup_environment):
        """
        Test that MCPConfigManager loads configuration from SSM.

        This validates the first step of agent initialization.
        """
        print("\n🔧 Testing MCPConfigManager initialization...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers = config_manager.load_config()

        print(f"✅ Loaded configuration for {len(servers)} MCP servers")

        # Verify both expected servers are configured
        assert "hotel-assistant-mcp" in servers, "hotel-assistant-mcp should be configured"
        assert "hotel-pms-mcp" in servers, "hotel-pms-mcp should be configured"

        print("✅ Both hotel-assistant-mcp and hotel-pms-mcp are configured")

    @pytest.mark.asyncio
    async def test_cognito_mcp_server_creation(self, setup_environment):
        """
        Test creating CognitoMCPServer instances for LiveKit integration.

        This validates the new approach where LiveKit manages connection lifecycle.
        """
        print("\n🌐 Testing CognitoMCPServer creation...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        # Import CognitoMCPServer
        from virtual_assistant_livekit.hotel_pms_mcp_server import CognitoMCPServer

        mcp_servers = []
        for server_name, server_config in servers_config.items():
            # Get credentials
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            # Create CognitoMCPServer
            mcp_server = CognitoMCPServer(
                url=server_config.url,
                user_pool_id=creds["userPoolId"],
                client_id=creds["clientId"],
                client_secret=creds["clientSecret"],
                region=creds["region"],
                server_name=server_name,
                headers=server_config.headers,
            )
            mcp_servers.append(mcp_server)
            print(f"   ✅ Created CognitoMCPServer for {server_name}")

        # Verify we created servers for both MCP servers
        assert len(mcp_servers) == 2, "Should have 2 CognitoMCPServer instances"

        print(f"✅ Successfully created {len(mcp_servers)} CognitoMCPServer instances")

        # Note: We don't initialize here - LiveKit will do that
        # This test just validates we can create the server objects

    @pytest.mark.asyncio
    async def test_prompt_loader_loads_voice_instructions(self, setup_environment):
        """
        Test that PromptLoader loads voice system prompt from MCP.

        This validates prompt loading with the new direct connection approach.
        """
        print("\n📝 Testing PromptLoader for voice instructions...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()

        # Initialize prompt loader (no client manager needed)
        prompt_loader = PromptLoader(config_manager)

        # Load voice system prompt
        instructions = await prompt_loader.load_prompt(AssistantType.VOICE)

        print(f"✅ Loaded voice system prompt ({len(instructions)} characters)")
        print(f"   Preview: {instructions[:200]}...")

        # Verify prompt is not empty and not emergency fallback
        assert len(instructions) > 0, "Voice prompt should not be empty"
        assert "technical difficulties" not in instructions.lower(), "Should not be emergency fallback"
        assert "dificultades técnicas" not in instructions.lower(), "Should not be emergency fallback"

        print("✅ Voice system prompt loaded successfully")

    def test_prewarm_function_complete_flow(self, setup_environment):
        """
        Test the complete prewarm function flow with real MCP resources.

        This validates the entire prewarm process that happens before agent sessions.
        """
        print("\n🚀 Testing complete prewarm function flow...")

        # Create a JobProcess with required parameters
        from livekit.agents import JobExecutorType

        proc = JobProcess(executor_type=JobExecutorType.PROCESS, user_arguments=None, http_proxy=None)
        # Note: proc.userdata is already a dict, no need to set it

        # Call prewarm function
        try:
            prewarm(proc)
            print("✅ Prewarm function completed successfully")
        except Exception as e:
            pytest.fail(f"Prewarm function failed: {e}")

        # Verify instructions were stored
        assert "instructions" in proc.userdata, "Instructions should be stored in userdata"
        instructions = proc.userdata["instructions"]

        print(f"✅ Instructions stored in userdata ({len(instructions)} characters)")

        # Verify instructions are valid
        assert len(instructions) > 0, "Instructions should not be empty"
        assert "technical difficulties" not in instructions.lower(), "Should not be emergency fallback"

        print("✅ Prewarm function validation complete")

    @pytest.mark.asyncio
    async def test_cognito_mcp_server_initialization_and_tools(self, setup_environment):
        """
        Test initializing CognitoMCPServer and discovering tools.

        This validates that the new server implementation works correctly.
        """
        print("\n🔧 Testing CognitoMCPServer initialization and tool discovery...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        # Import CognitoMCPServer
        from virtual_assistant_livekit.hotel_pms_mcp_server import CognitoMCPServer

        # Test with one server (hotel-pms-mcp)
        server_name = "hotel-pms-mcp"
        server_config = servers_config[server_name]
        creds = config_manager.get_credentials(server_config.authentication.secret_arn)

        # Create CognitoMCPServer
        mcp_server = CognitoMCPServer(
            url=server_config.url,
            user_pool_id=creds["userPoolId"],
            client_id=creds["clientId"],
            client_secret=creds["clientSecret"],
            region=creds["region"],
            server_name=server_name,
            headers=server_config.headers,
        )
        print(f"   ✅ Created CognitoMCPServer for {server_name}")

        # Initialize the server (this is what LiveKit does)
        await mcp_server.initialize()
        print(f"   ✅ Initialized {server_name}")

        # List tools (this is what LiveKit does)
        tools = await mcp_server.list_tools()
        print(f"   ✅ Discovered {len(tools)} tools from {server_name}")

        # Verify tools were discovered
        assert len(tools) > 0, f"{server_name} should have at least one tool"

        # Print tool info (tools are LiveKit MCPTool functions)
        for i, _tool in enumerate(tools, 1):
            print(f"      - Tool {i}")

        # Clean up
        await mcp_server.aclose()
        print(f"   ✅ Closed {server_name}")

        print("✅ CognitoMCPServer initialization and tool discovery successful")

    @pytest.mark.asyncio
    async def test_tool_discovery_from_mcp_servers(self, setup_environment):
        """
        Test discovering tools from both MCP servers.

        This validates that tools are available for the agent to use.
        """
        print("\n🔧 Testing tool discovery from MCP servers...")

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
                async with (
                    streamablehttp_client(
                        server_config.url,
                        headers=headers,
                        timeout=30,
                        terminate_on_close=False,
                    ) as (read_stream, write_stream, _),
                    ClientSession(read_stream, write_stream) as session,
                ):
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
                raise AssertionError(f"Failed to connect to {server_name}: {e}") from e

        # Verify we got tools from both servers
        assert len(all_tools) == 2, f"Should have tools from 2 servers, got {len(all_tools)}"
        assert "hotel-assistant-mcp" in all_tools, "Should have tools from hotel-assistant-mcp"
        assert "hotel-pms-mcp" in all_tools, "Should have tools from hotel-pms-mcp"

        # Verify each server has at least one tool
        for server_name, tools in all_tools.items():
            assert len(tools) > 0, f"{server_name} should have at least one tool"

        print(f"\n✅ Successfully discovered tools from {len(all_tools)} MCP servers")

    @pytest.mark.asyncio
    async def test_complete_agent_initialization_flow(self, setup_environment):
        """
        Test the complete agent initialization flow from prewarm to entrypoint.

        This validates the entire initialization sequence:
        1. Prewarm: Load MCP config and system prompt
        2. Entrypoint: Create CognitoMCPServer instances
        3. Verify servers can be initialized
        """
        print("\n🎯 Testing complete agent initialization flow...")

        # Step 1: Prewarm (call async function directly since we're in async test)
        print("\n   Step 1: Running prewarm...")
        from livekit.agents import JobExecutorType

        proc = JobProcess(executor_type=JobExecutorType.PROCESS, user_arguments=None, http_proxy=None)
        # Note: proc.userdata is already a dict, no need to set it

        try:
            # Load prompt directly (prewarm() uses asyncio.run which can't be called from async context)
            config_manager = MCPConfigManager()
            prompt_loader = PromptLoader(config_manager)
            instructions = await prompt_loader.load_prompt(AssistantType.VOICE)
            proc.userdata["instructions"] = instructions
            print("   ✅ Prewarm completed")
        except Exception as e:
            pytest.fail(f"Prewarm failed: {e}")

        assert "instructions" in proc.userdata, "Instructions should be stored"
        instructions = proc.userdata["instructions"]
        print(f"   ✅ Instructions loaded ({len(instructions)} characters)")

        # Step 2: Create CognitoMCPServer instances (simulating entrypoint)
        print("\n   Step 2: Creating CognitoMCPServer instances...")
        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        from virtual_assistant_livekit.hotel_pms_mcp_server import CognitoMCPServer

        mcp_servers = []
        for server_name, server_config in servers_config.items():
            creds = config_manager.get_credentials(server_config.authentication.secret_arn)

            mcp_server = CognitoMCPServer(
                url=server_config.url,
                user_pool_id=creds["userPoolId"],
                client_id=creds["clientId"],
                client_secret=creds["clientSecret"],
                region=creds["region"],
                server_name=server_name,
                headers=server_config.headers,
            )
            mcp_servers.append(mcp_server)
            print(f"   ✅ Created CognitoMCPServer for {server_name}")

        assert len(mcp_servers) == 2, "Should have 2 MCP servers"

        # Step 3: Verify servers can be initialized (what LiveKit does)
        print("\n   Step 3: Verifying servers can be initialized...")
        for mcp_server in mcp_servers:
            try:
                await mcp_server.initialize()
                print(f"   ✅ Initialized {mcp_server.server_name}")

                # Verify tools are available
                tools = await mcp_server.list_tools()
                assert len(tools) > 0, f"{mcp_server.server_name} should have tools"
                print(f"   ✅ {mcp_server.server_name} has {len(tools)} tools")

                # Clean up
                await mcp_server.aclose()
            except Exception as e:
                pytest.fail(f"Failed to initialize {mcp_server.server_name}: {e}")

        print("\n✅ Complete agent initialization flow validated")

    @pytest.mark.asyncio
    async def test_mcp_connection_lifecycle(self, setup_environment):
        """
        Test the MCP connection lifecycle with CognitoMCPServer.

        This validates proper resource management with the new approach.
        """
        print("\n♻️  Testing MCP connection lifecycle with CognitoMCPServer...")

        # Initialize
        print("\n   Phase 1: Create CognitoMCPServer...")
        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        from virtual_assistant_livekit.hotel_pms_mcp_server import CognitoMCPServer

        server_name = "hotel-pms-mcp"
        server_config = servers_config[server_name]
        creds = config_manager.get_credentials(server_config.authentication.secret_arn)

        mcp_server = CognitoMCPServer(
            url=server_config.url,
            user_pool_id=creds["userPoolId"],
            client_id=creds["clientId"],
            client_secret=creds["clientSecret"],
            region=creds["region"],
            server_name=server_name,
        )
        print("   ✅ Created CognitoMCPServer")

        # Initialize (LiveKit does this)
        print("\n   Phase 2: Initialize connection...")
        await mcp_server.initialize()
        assert mcp_server.initialized, "Server should be initialized"
        print("   ✅ Server initialized")

        # Use (LiveKit does this)
        print("\n   Phase 3: Use connection...")
        tools = await mcp_server.list_tools()
        assert len(tools) > 0, "Should have tools"
        print(f"   ✅ Listed {len(tools)} tools")

        # Close (LiveKit does this)
        print("\n   Phase 4: Close connection...")
        await mcp_server.aclose()
        print("   ✅ Connection closed")

        print("\n✅ Connection lifecycle validated")

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
            raise ValueError(f"Could not obtain Cognito token: {e}") from e
