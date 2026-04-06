# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Test MCP connection lifecycle management.

This test validates that MCP connections can be kept alive
across multiple operations, which is required for the LiveKit
agent prewarm pattern.
"""

import os

import pytest

from virtual_assistant_common.mcp import MCPConfigManager, MultiMCPClientManager


@pytest.mark.integration
class TestMCPConnectionLifecycle:
    """Integration tests for MCP connection lifecycle."""

    @pytest.fixture
    def setup_environment(self):
        """Set up environment variables for integration tests."""
        import boto3

        # Get HotelPmsStack outputs
        cfn_client = boto3.client("cloudformation")
        try:
            response = cfn_client.describe_stacks(StackName="HotelPmsStack")
            if not response["Stacks"]:
                pytest.skip("HotelPmsStack not found")

            outputs = {}
            for output in response["Stacks"][0].get("Outputs", []):
                outputs[output["OutputKey"]] = output["OutputValue"]

            # Store original environment
            original_env = os.environ.copy()

            # Set required environment variables
            os.environ["MCP_CONFIG_PARAMETER"] = outputs["MCPConfigParameterName"]
            os.environ["AWS_REGION"] = outputs.get("RegionName", "us-east-1")

            yield outputs

            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

        except Exception as e:
            pytest.skip(f"Failed to load CloudFormation outputs: {e}")

    @pytest.mark.asyncio
    async def test_multi_client_manager_keeps_connections_alive(self, setup_environment):
        """
        Test that MultiMCPClientManager keeps connections alive after initialization.

        This simulates the LiveKit agent prewarm pattern where:
        1. MCP connections are initialized once
        2. Connections stay alive for multiple operations
        3. Connections can be used across multiple sessions
        """
        print("\n🔄 Testing MCP connection lifecycle management...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()
        print("✅ Initialized MCPConfigManager")

        # Initialize multi-client manager
        client_manager = MultiMCPClientManager(config_manager)
        await client_manager.initialize()
        print(f"✅ Initialized MultiMCPClientManager with {len(client_manager.clients)} servers")

        # Verify connections are established
        assert len(client_manager.clients) > 0, "Should have at least one connected server"
        print(f"   Connected servers: {list(client_manager.clients.keys())}")

        # Verify context managers are stored
        assert len(client_manager._context_managers) > 0, "Should have stored context managers"
        print(f"   Stored {len(client_manager._context_managers)} context managers")

        # Simulate multiple operations using the same connections
        for i in range(3):
            print(f"\n   Operation {i + 1}:")

            # Get MCP clients (simulating what LiveKit agent does)
            mcp_clients = client_manager.get_mcp_clients()
            assert len(mcp_clients) > 0, f"Should have clients available for operation {i + 1}"
            print(f"   ✅ Retrieved {len(mcp_clients)} MCP clients")

            # Verify we can still list tools (connection is alive)
            for server_name, session in mcp_clients.items():
                try:
                    tools = await session.list_tools()
                    print(f"   ✅ {server_name}: Listed {len(tools.tools)} tools")
                except Exception as e:
                    pytest.fail(f"Failed to list tools from {server_name} on operation {i + 1}: {e}")

        print("\n✅ Successfully performed multiple operations with persistent connections")

        # Cleanup
        await client_manager.close()
        print("✅ Cleaned up connections")

    @pytest.mark.asyncio
    async def test_connection_timeout_handling(self, setup_environment):
        """
        Test that connection timeouts are handled gracefully.

        This verifies that if a server times out during initialization,
        it's marked as unavailable and other servers can still be used.
        """
        print("\n⏱️  Testing connection timeout handling...")

        # Initialize configuration manager
        config_manager = MCPConfigManager()

        # Initialize multi-client manager
        client_manager = MultiMCPClientManager(config_manager)

        # This should complete even if some servers timeout
        await client_manager.initialize()

        # Verify we got at least some connections
        total_servers = len(config_manager.load_config())
        connected_servers = len(client_manager.clients)
        unavailable_servers = len(client_manager.unavailable_servers)

        print(f"   Total servers configured: {total_servers}")
        print(f"   Connected servers: {connected_servers}")
        print(f"   Unavailable servers: {unavailable_servers}")

        # Should have attempted all servers
        assert connected_servers + unavailable_servers == total_servers

        # Should have at least one working connection
        assert connected_servers > 0, "Should have at least one connected server"

        print("✅ Timeout handling works correctly")

        # Cleanup
        await client_manager.close()
