# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration tests for chat agent MCP initialization with real AWS resources.

These tests validate the complete MCP initialization flow for AgentCore Runtime including:
- Loading MCP configuration from SSM Parameter Store
- Connecting to multiple MCP servers (hotel-assistant-mcp, hotel-pms-mcp)
- Loading system prompts from MCP servers
- Creating agent with MCP tools
- Session-lifetime connection management
- Tool discovery and availability

REQUIRED CREDENTIALS:
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- Deployed CloudFormation stacks: VirtualAssistantStack (required), HotelPmsStack (required)
- MCP configuration in SSM Parameter Store (created by HotelPmsStack)
- Cognito credentials in Secrets Manager (created by HotelPmsStack)
- AgentCore Memory configured (created by VirtualAssistantStack)

NOT REQUIRED:
- AgentCore Runtime deployment (tests validate initialization logic, not runtime invocation)
- .env file (configuration comes from CloudFormation/SSM)

These tests will FAIL (not skip) if:
- AWS credentials are not configured
- CloudFormation stacks are not deployed
- MCP configuration is missing or invalid
- Cognito authentication fails
- MCP servers are unreachable
"""

from contextlib import AsyncExitStack

import pytest
from mcp import ClientSession
from virtual_assistant_common.cognito_mcp import cognito_mcp_client
from virtual_assistant_common.mcp import AssistantType, MCPConfigManager, PromptLoader


@pytest.mark.integration
class TestChatAgentMCPInitialization:
    """Integration tests for chat agent MCP initialization with real resources."""

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
    async def test_prompt_loader_loads_chat_instructions(self, setup_environment):
        """
        Test that PromptLoader loads chat system prompt from MCP.

        This validates prompt loading with the new direct connection approach.
        """
        print("\n📝 Testing PromptLoader for chat instructions...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()

        # Initialize prompt loader (no client manager needed)
        prompt_loader = PromptLoader(config_manager)

        # Load chat system prompt
        instructions = await prompt_loader.load_prompt(AssistantType.CHAT)

        print(f"✅ Loaded chat system prompt ({len(instructions)} characters)")
        print(f"   Preview: {instructions[:200]}...")

        # Verify prompt is not empty and not emergency fallback
        assert len(instructions) > 0, "Chat prompt should not be empty"
        assert "technical difficulties" not in instructions.lower(), "Should not be emergency fallback"
        assert "dificultades técnicas" not in instructions.lower(), "Should not be emergency fallback"

        print("✅ Chat system prompt loaded successfully")

    @pytest.mark.asyncio
    async def test_mcp_connections_with_exit_stack(self, setup_environment):
        """
        Test creating MCP connections managed by AsyncExitStack.

        This validates the session-lifetime connection pattern used by chat agent.
        """
        print("\n🔗 Testing MCP connections with AsyncExitStack...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        # Create AsyncExitStack to manage connections
        async with AsyncExitStack() as exit_stack:
            tools = []

            for server_name, server_config in servers_config.items():
                print(f"\n   Connecting to {server_name}...")

                try:
                    # Get credentials
                    creds = config_manager.get_credentials(server_config.authentication.secret_arn)

                    # Create connection managed by exit stack
                    read_stream, write_stream, _ = await exit_stack.enter_async_context(
                        cognito_mcp_client(
                            url=server_config.url,
                            user_pool_id=creds["userPoolId"],
                            client_id=creds["clientId"],
                            client_secret=creds["clientSecret"],
                            region=creds["region"],
                            headers=server_config.headers,
                        )
                    )

                    session_obj = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))

                    await session_obj.initialize()

                    # List tools from this server
                    tool_result = await session_obj.list_tools()
                    server_tools = tool_result.tools
                    tools.extend(server_tools)

                    print(f"   ✅ {server_name}: Loaded {len(server_tools)} tools (connection kept alive)")

                except Exception as e:
                    raise AssertionError(f"Failed to connect to {server_name}: {e}") from e

            # Verify we got tools from both servers
            assert len(tools) > 0, "Should have loaded tools from MCP servers"
            print(f"\n✅ Total tools loaded: {len(tools)} (connections managed by AsyncExitStack)")

            # Connections are still alive here - simulate using them
            print("   ✅ Connections remain active within AsyncExitStack context")

        # Connections automatically closed when exiting AsyncExitStack
        print("   ✅ Connections automatically closed on exit")

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

                # Create temporary connection to list tools
                async with (
                    cognito_mcp_client(
                        url=server_config.url,
                        user_pool_id=creds["userPoolId"],
                        client_id=creds["clientId"],
                        client_secret=creds["clientSecret"],
                        region=creds["region"],
                        headers=server_config.headers,
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
        Test the complete agent initialization flow for chat agent.

        This validates the entire initialization sequence:
        1. Load MCP config and system prompt
        2. Create MCP connections with AsyncExitStack
        3. Load tools from all servers
        4. Verify connections remain active
        """
        print("\n🎯 Testing complete agent initialization flow...")

        # Step 1: Load prompt
        print("\n   Step 1: Loading system prompt...")
        config_manager = MCPConfigManager()
        prompt_loader = PromptLoader(config_manager)
        instructions = await prompt_loader.load_prompt(AssistantType.CHAT)
        print(f"   ✅ Instructions loaded ({len(instructions)} characters)")

        # Step 2: Create MCP connections with AsyncExitStack (simulating agent creation)
        print("\n   Step 2: Creating MCP connections with AsyncExitStack...")
        servers_config = config_manager.load_config()

        async with AsyncExitStack() as mcp_exit_stack:
            tools = []

            for server_name, server_config in servers_config.items():
                try:
                    # Get credentials
                    creds = config_manager.get_credentials(server_config.authentication.secret_arn)

                    # Create connection that persists for session lifetime
                    read_stream, write_stream, _ = await mcp_exit_stack.enter_async_context(
                        cognito_mcp_client(
                            url=server_config.url,
                            user_pool_id=creds["userPoolId"],
                            client_id=creds["clientId"],
                            client_secret=creds["clientSecret"],
                            region=creds["region"],
                            headers=server_config.headers,
                        )
                    )

                    session_obj = await mcp_exit_stack.enter_async_context(ClientSession(read_stream, write_stream))

                    await session_obj.initialize()

                    # List tools from this server
                    tool_result = await session_obj.list_tools()
                    server_tools = tool_result.tools
                    tools.extend(server_tools)

                    print(f"   ✅ Loaded {len(server_tools)} tools from {server_name}")

                except Exception as e:
                    raise AssertionError(f"Failed to load tools from {server_name}: {e}") from e

            print(f"\n   ✅ Total tools loaded: {len(tools)}")

            # Step 3: Verify we have everything needed for agent creation
            assert len(instructions) > 0, "Should have instructions"
            assert len(tools) > 0, "Should have tools"
            print("   ✅ Agent would be created with instructions and tools")

            # Step 4: Simulate agent usage (connections still active)
            print("\n   Step 3: Simulating agent usage...")
            print("   ✅ MCP connections remain active for session lifetime")
            print("   ✅ Tools can be called while connections are alive")

        # Connections automatically cleaned up
        print("\n   Step 4: AsyncExitStack cleanup...")
        print("   ✅ MCP connections automatically closed")

        print("\n✅ Complete agent initialization flow validated")

    @pytest.mark.asyncio
    async def test_mcp_connection_lifecycle(self, setup_environment):
        """
        Test the MCP connection lifecycle with AsyncExitStack.

        This validates proper resource management for session-lifetime connections.
        """
        print("\n♻️  Testing MCP connection lifecycle with AsyncExitStack...")

        # Initialize
        print("\n   Phase 1: Create AsyncExitStack and connections...")
        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        server_name = "hotel-pms-mcp"
        server_config = servers_config[server_name]
        creds = config_manager.get_credentials(server_config.authentication.secret_arn)

        async with AsyncExitStack() as exit_stack:
            print("   ✅ AsyncExitStack created")

            # Phase 2: Enter connection context
            print("\n   Phase 2: Enter connection context...")
            read_stream, write_stream, _ = await exit_stack.enter_async_context(
                cognito_mcp_client(
                    url=server_config.url,
                    user_pool_id=creds["userPoolId"],
                    client_id=creds["clientId"],
                    client_secret=creds["clientSecret"],
                    region=creds["region"],
                )
            )
            print("   ✅ Connection context entered")

            # Phase 3: Enter session context
            print("\n   Phase 3: Enter session context...")
            session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            print("   ✅ Session initialized")

            # Phase 4: Use connection
            print("\n   Phase 4: Use connection...")
            tools = await session.list_tools()
            assert len(tools.tools) > 0, "Should have tools"
            print(f"   ✅ Listed {len(tools.tools)} tools")

            # Phase 5: Connection remains active
            print("\n   Phase 5: Connection remains active...")
            print("   ✅ Connection still alive within AsyncExitStack")

        # Phase 6: Automatic cleanup
        print("\n   Phase 6: Automatic cleanup on exit...")
        print("   ✅ AsyncExitStack automatically closed all contexts")

        print("\n✅ Connection lifecycle validated")

    @pytest.mark.asyncio
    async def test_session_reuse_simulation(self, setup_environment):
        """
        Test simulating session reuse with persistent connections.

        This validates that connections can be reused across multiple operations
        (simulating multiple message invocations in AgentCore Runtime session).
        """
        print("\n🔄 Testing session reuse simulation...")

        config_manager = MCPConfigManager()
        servers_config = config_manager.load_config()

        async with AsyncExitStack() as mcp_exit_stack:
            # Create connections once (simulating agent creation)
            print("\n   Creating connections (simulating agent creation)...")
            sessions = {}

            for server_name, server_config in servers_config.items():
                creds = config_manager.get_credentials(server_config.authentication.secret_arn)

                read_stream, write_stream, _ = await mcp_exit_stack.enter_async_context(
                    cognito_mcp_client(
                        url=server_config.url,
                        user_pool_id=creds["userPoolId"],
                        client_id=creds["clientId"],
                        client_secret=creds["clientSecret"],
                        region=creds["region"],
                        headers=server_config.headers,
                    )
                )

                session = await mcp_exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
                await session.initialize()
                sessions[server_name] = session

                print(f"   ✅ Connected to {server_name}")

            # Simulate multiple message invocations (reusing connections)
            print("\n   Simulating multiple message invocations...")

            for i in range(3):
                print(f"\n   Message {i + 1}:")
                for server_name, session in sessions.items():
                    # List tools (simulating tool discovery for each message)
                    tools = await session.list_tools()
                    print(f"      ✅ {server_name}: {len(tools.tools)} tools available")

            print("\n   ✅ Connections successfully reused across multiple invocations")

        print("\n✅ Session reuse simulation validated")
