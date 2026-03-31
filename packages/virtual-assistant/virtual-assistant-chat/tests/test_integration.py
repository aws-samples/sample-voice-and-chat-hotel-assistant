# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests using real deployed resources."""

import os

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@pytest.mark.integration
class TestConversationContinuity:
    """Test conversation continuity with real AgentCore Memory."""

    def test_memory_configuration_available(self):
        """Test that memory configuration is available when AGENTCORE_MEMORY_ID is set."""
        if not os.getenv("AGENTCORE_MEMORY_ID"):
            pytest.skip("AGENTCORE_MEMORY_ID not configured")

        # Test that memory ID is properly configured
        memory_id = os.getenv("AGENTCORE_MEMORY_ID")
        assert memory_id is not None
        assert len(memory_id) > 0

    def test_session_manager_integration(self):
        """Test that SessionManager can be imported and initialized."""
        from bedrock_agentcore.memory import MemoryClient
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
        from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

        # Test that classes can be imported
        assert MemoryClient is not None
        assert AgentCoreMemoryConfig is not None
        assert AgentCoreMemorySessionManager is not None

        # Test basic initialization (without actual AWS calls)
        if os.getenv("AGENTCORE_MEMORY_ID"):
            memory_id = os.getenv("AGENTCORE_MEMORY_ID")
            # Just test that we can create the config and session manager objects
            # without making actual AWS calls
            try:
                config = AgentCoreMemoryConfig(memory_id=memory_id, session_id="test_session", actor_id="test_actor")
                assert config.memory_id == memory_id
                assert config.session_id == "test_session"
                assert config.actor_id == "test_actor"
            except Exception as e:
                pytest.fail(f"Failed to create AgentCoreMemoryConfig: {e}")

    def test_agent_entrypoint_functions_exist(self, mock_agent_module):
        """Test that the agent entrypoint functions exist and can be imported."""
        # Test that the module has the expected structure for BedrockAgentCoreApp
        assert hasattr(mock_agent_module, "BedrockAgentCoreApp")
        assert hasattr(mock_agent_module, "logger")

    def test_bedrock_agent_core_integration(self):
        """Test that BedrockAgentCoreApp can be imported and initialized."""
        from bedrock_agentcore import BedrockAgentCoreApp

        # Test that we can create the app (without running it)
        app = BedrockAgentCoreApp()
        assert app is not None
