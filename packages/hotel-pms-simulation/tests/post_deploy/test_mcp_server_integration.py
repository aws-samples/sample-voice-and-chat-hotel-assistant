# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for MCP server with deployed knowledge base.

This test suite validates the MCP server's knowledge base query functionality
against the deployed AWS infrastructure.

Prerequisites:
- HotelPmsStack deployed with Knowledge Base
- AWS credentials configured
- Knowledge Base synced with hotel documentation

Usage:
    pytest tests/post_deploy/test_mcp_server_integration.py -v -s -m integration
"""

import pytest

from hotel_pms_simulation.mcp.server import (
    PROMPT_DIR,
    generate_hotel_context,
    load_prompt_with_context,
    query_hotel_knowledge,
)


@pytest.mark.integration
@pytest.mark.asyncio
class TestKnowledgeBaseIntegration:
    """Integration tests for knowledge base query functionality."""

    async def test_query_general_hotel_information(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test querying general hotel information from knowledge base."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query for general hotel information
        result = await query_hotel_knowledge(
            query="What are the check-in and check-out times?", max_results=3
        )

        # Verify we got a string result
        assert isinstance(result, str), "Should return a formatted string"
        assert len(result) > 0, "Result should not be empty"

        # Verify result contains expected formatting
        assert "Result" in result, "Should contain result numbering"
        assert "relevance:" in result.lower(), "Should contain relevance scores"

        # Verify result contains content (not the "No relevant information" message)
        assert "No relevant information found" not in result, (
            "Should have found relevant results"
        )

        print("\n✅ Retrieved formatted results for general query")
        print(f"Result preview: {result[:200]}...")
        print(f"Total length: {len(result)} characters")

    async def test_query_with_hotel_filter(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test querying with hotel_ids filter."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query with specific hotel filter
        hotel_ids = ["H-PVR-002"]  # Paraiso Vallarta
        result = await query_hotel_knowledge(
            query="What amenities are available?",
            hotel_ids=hotel_ids,
            max_results=5,
        )

        # Verify we got a string result
        assert isinstance(result, str), "Should return a formatted string"
        assert len(result) > 0, "Result should not be empty"

        # Verify result contains content (not the "No relevant information" message)
        assert "No relevant information found" not in result, (
            "Should have found relevant results"
        )

        print("\n✅ Retrieved formatted results with hotel filter")
        print(f"Filter applied: {hotel_ids}")
        print(f"Result preview: {result[:200]}...")

    async def test_query_specific_topic(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test querying for specific topics like dining or activities."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query for dining information
        result = await query_hotel_knowledge(
            query="Tell me about the restaurants and dining options", max_results=5
        )

        # Verify we got a string result
        assert isinstance(result, str), "Should return a formatted string"
        assert len(result) > 0, "Result should not be empty"

        # Verify result contains relevant information
        result_lower = result.lower()
        assert any(
            keyword in result_lower
            for keyword in ["restaurant", "dining", "food", "cuisine", "bar"]
        ), "Results should contain dining-related keywords"

        print("\n✅ Retrieved formatted results for dining query")
        print(f"Result length: {len(result)} characters")
        print(f"Result preview: {result[:200]}...")

    async def test_query_max_results_parameter(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test that max_results parameter affects the output."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query with different max_results values
        for max_results in [1, 3, 5]:
            result = await query_hotel_knowledge(
                query="hotel information", max_results=max_results
            )

            # Verify we got a string result
            assert isinstance(result, str), "Should return a formatted string"

            # Count number of results in the formatted string
            # Each result starts with "Result N"
            result_count = result.count("Result ")

            # Should not exceed max_results
            assert result_count <= max_results, (
                f"Should return at most {max_results} results, got {result_count}"
            )

            print(
                f"✅ max_results={max_results}: got {result_count} results in formatted string"
            )

    async def test_query_relevance_scoring(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test that results include relevance scores in the formatted output."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query for specific information
        result = await query_hotel_knowledge(
            query="What is the cancellation policy?", max_results=5
        )

        # Verify we got a string result
        assert isinstance(result, str), "Should return a formatted string"
        assert len(result) > 0, "Result should not be empty"

        # Verify result contains relevance scores
        assert "relevance:" in result.lower(), "Should include relevance scores"

        # Extract scores from the formatted string (format: "relevance: 0.XX")
        import re

        scores = re.findall(r"relevance:\s*(\d+\.\d+)", result, re.IGNORECASE)
        scores = [float(s) for s in scores]

        if len(scores) > 1:
            # Verify scores are in descending order (highest relevance first)
            assert scores == sorted(scores, reverse=True), (
                "Results should be ordered by relevance (highest first)"
            )
            print(
                f"\n✅ Results properly ordered by relevance: {[f'{s:.2f}' for s in scores]}"
            )
        else:
            print(
                f"\n✅ Result includes relevance score: {scores[0]:.2f}"
                if scores
                else "✅ Result formatted correctly"
            )

    async def test_query_metadata_presence(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test that results include hotel names in the formatted output."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query for information
        result = await query_hotel_knowledge(
            query="hotel policies and procedures", max_results=3
        )

        # Verify we got a string result
        assert isinstance(result, str), "Should return a formatted string"
        assert len(result) > 0, "Result should not be empty"

        # Verify result includes hotel names (from metadata)
        # The formatted output should include hotel names like "Paraiso", "Grand", etc.
        result_lower = result.lower()
        has_hotel_info = any(
            keyword in result_lower
            for keyword in ["paraiso", "grand", "hotel", "resort"]
        )

        assert has_hotel_info, "Results should include hotel names from metadata"

        print("\n✅ Results include hotel information from metadata")
        print(f"Result preview: {result[:300]}...")

    async def test_query_multiple_hotels(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test querying across multiple hotels."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query with multiple hotel filters
        hotel_ids = ["H-PVR-002", "H-TUL-001", "H-CAB-003"]
        result = await query_hotel_knowledge(
            query="What activities are available?",
            hotel_ids=hotel_ids,
            max_results=10,
        )

        # Verify we got a string result
        assert isinstance(result, str), "Should return a formatted string"
        assert len(result) > 0, "Result should not be empty"

        # Verify result contains content (not the "No relevant information" message)
        assert "No relevant information found" not in result, (
            "Should have found relevant results"
        )

        print(f"\n✅ Retrieved formatted results across {len(hotel_ids)} hotels")
        print(f"Hotels queried: {hotel_ids}")
        print(f"Result length: {len(result)} characters")

    async def test_query_empty_results_handling(
        self, setup_knowledge_base_env, knowledge_base_info
    ):
        """Test handling of queries that might return no results."""
        if not knowledge_base_info:
            pytest.skip("Knowledge Base not deployed")

        # Query for something very specific that might not exist
        result = await query_hotel_knowledge(
            query="quantum physics research laboratory facilities", max_results=5
        )

        # Should return a string (even if no results found)
        assert isinstance(result, str), "Should return a string"
        assert len(result) > 0, "Should return a non-empty string"

        # Check if we got results or the "no results" message
        if "No relevant information found" in result:
            print("\n✅ Query handled gracefully with no results message")
        else:
            print(f"\n✅ Query returned results (length: {len(result)} characters)")

        print(f"Result: {result[:200]}...")


@pytest.mark.integration
class TestPromptFunctionsIntegration:
    """Integration tests for prompt functions with deployed DynamoDB."""

    def test_generate_hotel_context_with_real_data(
        self, setup_dynamodb_env, dynamodb_table_names
    ):
        """Test hotel context generation with real DynamoDB data."""
        if not dynamodb_table_names:
            pytest.skip("DynamoDB tables not deployed")

        # Generate context from real DynamoDB
        context = generate_hotel_context()

        # Verify structure
        assert "current_date" in context
        assert "hotel_list" in context

        # Verify current_date is formatted correctly
        assert len(context["current_date"]) > 0
        # Should be in format like "November 17, 2025"
        assert "," in context["current_date"]

        # Verify hotel_list contains real data
        assert "Available hotels:" in context["hotel_list"]
        assert len(context["hotel_list"]) > len("Available hotels:")

        # Should contain hotel names and IDs
        assert "(ID:" in context["hotel_list"]

        print("\n✅ Generated hotel context with real data")
        print(f"Current date: {context['current_date']}")
        print(f"Hotel list preview:\n{context['hotel_list'][:200]}...")

    def test_generate_hotel_context_hotel_count(
        self, setup_dynamodb_env, dynamodb_table_names
    ):
        """Test that hotel context includes all deployed hotels."""
        if not dynamodb_table_names:
            pytest.skip("DynamoDB tables not deployed")

        context = generate_hotel_context()

        # Count number of hotels in the list
        # Each hotel line starts with "- " and contains "(ID:"
        hotel_lines = [
            line
            for line in context["hotel_list"].split("\n")
            if line.strip().startswith("-") and "(ID:" in line
        ]

        # Should have at least one hotel
        assert len(hotel_lines) > 0, "Should have at least one hotel in the list"

        print(f"\n✅ Found {len(hotel_lines)} hotels in context")
        for line in hotel_lines:
            print(f"  {line.strip()}")

    def test_generate_hotel_context_format(
        self, setup_dynamodb_env, dynamodb_table_names
    ):
        """Test that hotel context follows expected format."""
        if not dynamodb_table_names:
            pytest.skip("DynamoDB tables not deployed")

        context = generate_hotel_context()

        # Verify format: "- {name} (ID: {id})"
        hotel_lines = [
            line
            for line in context["hotel_list"].split("\n")
            if line.strip().startswith("-") and "(ID:" in line
        ]

        for line in hotel_lines:
            # Should start with "- "
            assert line.strip().startswith("-")

            # Should contain "(ID: " and end with ")"
            assert "(ID:" in line
            assert line.strip().endswith(")")

            # Extract hotel ID (should start with H-)
            id_part = line.split("(ID:")[1].strip().rstrip(")")
            assert id_part.startswith("H-"), (
                f"Hotel ID should start with H-, got {id_part}"
            )

        print(f"\n✅ All {len(hotel_lines)} hotels follow correct format")

    def test_load_prompt_with_context_chat_integration(
        self, setup_dynamodb_env, dynamodb_table_names
    ):
        """Test loading chat prompt with real DynamoDB context."""
        if not dynamodb_table_names:
            pytest.skip("DynamoDB tables not deployed")

        # Load chat prompt with real context
        prompt = load_prompt_with_context("chat", prompt_dir=PROMPT_DIR)

        # Verify template was loaded
        assert len(prompt) > 0

        # Verify placeholders were replaced
        assert "{current_date}" not in prompt, (
            "current_date placeholder should be replaced"
        )
        assert "{hotel_list}" not in prompt, "hotel_list placeholder should be replaced"

        # Verify real data was injected
        assert "Available hotels:" in prompt
        assert "(ID:" in prompt  # Should contain hotel IDs

        # Verify date was injected (should contain month name)
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        assert any(month in prompt for month in months), "Should contain a month name"

        print("\n✅ Chat prompt loaded with real context")
        print(f"Prompt length: {len(prompt)} characters")
        print(f"Preview:\n{prompt[:300]}...")

    def test_load_prompt_with_context_voice_integration(
        self, setup_dynamodb_env, dynamodb_table_names
    ):
        """Test loading voice prompt with real DynamoDB context."""
        if not dynamodb_table_names:
            pytest.skip("DynamoDB tables not deployed")

        # Load voice prompt with real context
        prompt = load_prompt_with_context("voice", prompt_dir=PROMPT_DIR)

        # Verify template was loaded
        assert len(prompt) > 0

        # Verify placeholders were replaced
        assert "{current_date}" not in prompt, (
            "current_date placeholder should be replaced"
        )
        assert "{hotel_list}" not in prompt, "hotel_list placeholder should be replaced"

        # Verify real data was injected
        assert "Available hotels:" in prompt
        assert "(ID:" in prompt  # Should contain hotel IDs

        print("\n✅ Voice prompt loaded with real context")
        print(f"Prompt length: {len(prompt)} characters")

    def test_prompt_context_consistency(self, setup_dynamodb_env, dynamodb_table_names):
        """Test that both prompts use the same hotel context."""
        if not dynamodb_table_names:
            pytest.skip("DynamoDB tables not deployed")

        # Load both prompts
        chat_prompt = load_prompt_with_context("chat", prompt_dir=PROMPT_DIR)
        voice_prompt = load_prompt_with_context("voice", prompt_dir=PROMPT_DIR)

        # Extract hotel list sections from both prompts
        # Both should contain the same hotel data
        chat_hotels = [line for line in chat_prompt.split("\n") if "(ID:" in line]
        voice_hotels = [line for line in voice_prompt.split("\n") if "(ID:" in line]

        # Should have the same number of hotels
        assert len(chat_hotels) == len(voice_hotels), (
            "Both prompts should contain the same number of hotels"
        )

        # Should have the same hotel IDs
        chat_ids = set()
        voice_ids = set()

        for line in chat_hotels:
            if "(ID:" in line:
                id_part = line.split("(ID:")[1].strip().rstrip(")")
                chat_ids.add(id_part)

        for line in voice_hotels:
            if "(ID:" in line:
                id_part = line.split("(ID:")[1].strip().rstrip(")")
                voice_ids.add(id_part)

        assert chat_ids == voice_ids, "Both prompts should contain the same hotel IDs"

        print("\n✅ Both prompts use consistent hotel context")
        print(f"Hotels in both prompts: {sorted(chat_ids)}")
