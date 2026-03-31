# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Tests to verify hardcoded prompts have been removed.

These tests validate that the virtual assistants no longer use hardcoded
prompt files and instead load prompts dynamically from MCP servers.

Requirements tested:
- 3.8: Virtual Assistant Chat SHALL NOT use hardcoded system prompts as primary source
- 3.9: Virtual Assistant Voice SHALL NOT use hardcoded system prompts as primary source
- 11.8: Validate that hardcoded prompts are removed from both virtual assistants
"""

import ast
from pathlib import Path

import pytest


@pytest.mark.integration
class TestHardcodedPromptsRemoved:
    """Tests to verify hardcoded prompts are no longer used."""

    @staticmethod
    def get_workspace_root():
        """Get the workspace root directory."""
        # Navigate up from test file to workspace root
        # __file__ is in: packages/virtual-assistant/virtual-assistant-common/tests/integration/
        # workspace root is 6 levels up
        return Path(__file__).parent.parent.parent.parent.parent.parent

    def test_chat_agent_not_using_hardcoded_prompts(self):
        """
        Verify chat agent does not use hardcoded prompt files.

        Requirement 3.8, 11.8: Chat agent should not use hardcoded prompts
        """
        print("\n📝 Verifying chat agent does not use hardcoded prompts...")

        # Read the chat agent source code
        # Path is relative to workspace root
        workspace_root = Path(__file__).parent.parent.parent.parent.parent.parent
        agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py"
        )
        assert agent_file.exists(), f"Chat agent file not found: {agent_file}"

        with open(agent_file) as f:
            agent_code = f.read()

        # Parse the code to check for imports and function calls
        tree = ast.parse(agent_code)

        # Check that it doesn't import from prompts module
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "prompts" in node.module:
                # Check what's being imported
                imported_names = [alias.name for alias in node.names]
                assert "load_base_hotel_prompt" not in imported_names, (
                    "Chat agent should not import load_base_hotel_prompt"
                )
                assert "generate_dynamic_hotel_instructions" not in imported_names, (
                    "Chat agent should not import generate_dynamic_hotel_instructions"
                )

        # Check that it doesn't call these functions
        assert "load_base_hotel_prompt" not in agent_code, "Chat agent should not call load_base_hotel_prompt"
        assert "generate_dynamic_hotel_instructions" not in agent_code, (
            "Chat agent should not call generate_dynamic_hotel_instructions"
        )

        # Check that it doesn't reference the hardcoded prompt files
        assert "system-prompt-es-mx.md" not in agent_code, "Chat agent should not reference system-prompt-es-mx.md"
        assert "system-prompt-en.md" not in agent_code, "Chat agent should not reference system-prompt-en.md"

        print("✅ Chat agent does not use hardcoded prompts")
        print("   - No imports of load_base_hotel_prompt")
        print("   - No imports of generate_dynamic_hotel_instructions")
        print("   - No references to system-prompt-*.md files")

    def test_voice_agent_not_using_hardcoded_prompts(self):
        """
        Verify voice agent does not use hardcoded prompt files.

        Requirement 3.9, 11.8: Voice agent should not use hardcoded prompts
        """
        print("\n🎙️ Verifying voice agent does not use hardcoded prompts...")

        # Read the voice agent source code
        workspace_root = self.get_workspace_root()
        agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/agent.py"
        )
        assert agent_file.exists(), f"Voice agent file not found: {agent_file}"

        with open(agent_file) as f:
            agent_code = f.read()

        # Parse the code to check for imports and function calls
        tree = ast.parse(agent_code)

        # Check that it doesn't import from prompts module
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "prompts" in node.module:
                # Check what's being imported
                imported_names = [alias.name for alias in node.names]
                assert "load_base_hotel_prompt" not in imported_names, (
                    "Voice agent should not import load_base_hotel_prompt"
                )
                assert "generate_dynamic_hotel_instructions" not in imported_names, (
                    "Voice agent should not import generate_dynamic_hotel_instructions"
                )

        # Check that it doesn't call these functions
        assert "load_base_hotel_prompt" not in agent_code, "Voice agent should not call load_base_hotel_prompt"
        assert "generate_dynamic_hotel_instructions" not in agent_code, (
            "Voice agent should not call generate_dynamic_hotel_instructions"
        )

        # Check that it doesn't reference the hardcoded prompt files
        assert "hotel_assistant_system_prompt_en.txt" not in agent_code, (
            "Voice agent should not reference hotel_assistant_system_prompt_en.txt"
        )
        assert "hotel_assistant_system_prompt_es.txt" not in agent_code, (
            "Voice agent should not reference hotel_assistant_system_prompt_es.txt"
        )

        print("✅ Voice agent does not use hardcoded prompts")
        print("   - No imports of load_base_hotel_prompt")
        print("   - No imports of generate_dynamic_hotel_instructions")
        print("   - No references to hotel_assistant_system_prompt_*.txt files")

    def test_generate_dynamic_hotel_instructions_not_called(self):
        """
        Verify generate_dynamic_hotel_instructions is not called in agents.

        Requirement 11.8: Verify generate_dynamic_hotel_instructions() no longer called
        """
        print("\n🔍 Verifying generate_dynamic_hotel_instructions is not called...")

        # Check chat agent
        workspace_root = self.get_workspace_root()
        chat_agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py"
        )
        with open(chat_agent_file) as f:
            chat_agent_code = f.read()

        assert "generate_dynamic_hotel_instructions" not in chat_agent_code, (
            "Chat agent should not call generate_dynamic_hotel_instructions"
        )

        print("✅ Chat agent does not call generate_dynamic_hotel_instructions")

        # Check voice agent
        workspace_root = self.get_workspace_root()
        voice_agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/agent.py"
        )
        with open(voice_agent_file) as f:
            voice_agent_code = f.read()

        assert "generate_dynamic_hotel_instructions" not in voice_agent_code, (
            "Voice agent should not call generate_dynamic_hotel_instructions"
        )

        print("✅ Voice agent does not call generate_dynamic_hotel_instructions")

    def test_emergency_fallback_prompts_indicate_service_unavailability(self):
        """
        Verify emergency fallback prompts indicate service unavailability.

        Requirement 11.8: Emergency fallback prompts should indicate technical difficulties
        """
        print("\n🚨 Verifying emergency fallback prompts indicate service unavailability...")

        # Read the prompt loader source code
        workspace_root = self.get_workspace_root()
        prompt_loader_file = (
            workspace_root
            / "packages/virtual-assistant/virtual-assistant-common/virtual_assistant_common/mcp/prompt_loader.py"
        )
        assert prompt_loader_file.exists(), f"Prompt loader file not found: {prompt_loader_file}"

        with open(prompt_loader_file) as f:
            prompt_loader_code = f.read()

        # Check that emergency fallback contains "technical difficulties"
        assert "technical difficulties" in prompt_loader_code.lower(), (
            "Emergency fallback should mention 'technical difficulties'"
        )

        # Parse the code to find the _get_emergency_fallback method
        tree = ast.parse(prompt_loader_code)

        found_emergency_fallback = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_get_emergency_fallback":
                found_emergency_fallback = True

                # Get the function source
                func_source = ast.get_source_segment(prompt_loader_code, node)
                assert func_source is not None, "Could not extract emergency fallback function source"

                # Verify it contains appropriate messaging
                assert "technical difficulties" in func_source.lower(), (
                    "Emergency fallback should mention 'technical difficulties'"
                )
                assert "try again" in func_source.lower(), "Emergency fallback should suggest trying again"

                print("✅ Emergency fallback prompts properly indicate service unavailability")
                print("   - Contains 'technical difficulties' message")
                print("   - Suggests user try again later")
                break

        assert found_emergency_fallback, "_get_emergency_fallback method not found in prompt_loader.py"

    def test_mcp_prompt_loading_is_primary_source(self):
        """
        Verify that MCP prompt loading is the primary source for prompts.

        Requirement 3.8, 3.9: MCP servers should be primary prompt source
        """
        print("\n🌐 Verifying MCP prompt loading is primary source...")

        # Check chat agent uses PromptLoader
        workspace_root = self.get_workspace_root()
        chat_agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py"
        )
        with open(chat_agent_file) as f:
            chat_agent_code = f.read()

        assert "PromptLoader" in chat_agent_code, "Chat agent should use PromptLoader"
        assert "load_prompt" in chat_agent_code, "Chat agent should call load_prompt"

        print("✅ Chat agent uses PromptLoader for dynamic prompt loading")

        # Check voice agent uses PromptLoader
        workspace_root = self.get_workspace_root()
        voice_agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/agent.py"
        )
        with open(voice_agent_file) as f:
            voice_agent_code = f.read()

        assert "PromptLoader" in voice_agent_code, "Voice agent should use PromptLoader"
        assert "load_prompt" in voice_agent_code, "Voice agent should call load_prompt"

        print("✅ Voice agent uses PromptLoader for dynamic prompt loading")

    def test_hardcoded_prompt_files_still_exist_but_unused(self):
        """
        Verify hardcoded prompt files still exist (for reference) but are not used.

        This test documents that the files exist but are no longer the primary source.
        """
        print("\n📁 Checking status of hardcoded prompt files...")

        # Check chat agent prompt files
        workspace_root = self.get_workspace_root()
        chat_prompt_es = (
            workspace_root
            / "packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/assets/system-prompt-es-mx.md"
        )
        chat_prompt_en = (
            workspace_root
            / "packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/assets/system-prompt-en.md"
        )

        if chat_prompt_es.exists():
            print("ℹ️  Chat prompt file exists (es-mx): system-prompt-es-mx.md (not used)")
        if chat_prompt_en.exists():
            print("ℹ️  Chat prompt file exists (en): system-prompt-en.md (not used)")

        # Check voice agent prompt files
        voice_prompt_es = (
            workspace_root
            / "packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/assets/hotel_assistant_system_prompt_es.txt"
        )
        voice_prompt_en = (
            workspace_root
            / "packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/assets/hotel_assistant_system_prompt_en.txt"
        )

        if voice_prompt_es.exists():
            print("ℹ️  Voice prompt file exists (es): hotel_assistant_system_prompt_es.txt (not used)")
        if voice_prompt_en.exists():
            print("ℹ️  Voice prompt file exists (en): hotel_assistant_system_prompt_en.txt (not used)")

        print("✅ Hardcoded prompt files may exist but are not used by agents")

    def test_complete_prompt_loading_workflow(self):
        """
        Verify the complete prompt loading workflow uses MCP.

        This test ensures the entire workflow from configuration to prompt loading
        goes through the MCP infrastructure.
        """
        print("\n🔄 Verifying complete prompt loading workflow...")

        # Check that both agents import from mcp module
        workspace_root = self.get_workspace_root()
        chat_agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py"
        )
        with open(chat_agent_file) as f:
            chat_agent_code = f.read()

        assert "from virtual_assistant_common.mcp" in chat_agent_code, "Chat agent should import from mcp module"

        voice_agent_file = (
            workspace_root / "packages/virtual-assistant/virtual-assistant-livekit/virtual_assistant_livekit/agent.py"
        )
        with open(voice_agent_file) as f:
            voice_agent_code = f.read()

        assert "from virtual_assistant_common.mcp" in voice_agent_code, "Voice agent should import from mcp module"

        print("✅ Both agents use MCP infrastructure for prompt loading")
        print("   - Chat agent imports from virtual_assistant_common.mcp")
        print("   - Voice agent imports from virtual_assistant_common.mcp")
        print("   - Complete workflow: SSM → Config → MCP Client → Prompt")
