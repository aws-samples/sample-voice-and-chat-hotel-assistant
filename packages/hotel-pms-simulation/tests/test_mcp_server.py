# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for MCP server knowledge query tool."""

import os
from unittest.mock import patch

import pytest

from hotel_pms_simulation.mcp.server import (
    generate_hotel_context,
    load_prompt_with_context,
    query_hotel_knowledge,
)


class TestQueryHotelKnowledge:
    """Test cases for query_hotel_knowledge tool."""

    @pytest.fixture
    def mock_bedrock_client(self):
        """Mock Bedrock agent runtime client."""
        with patch("hotel_pms_simulation.mcp.server.bedrock_agent") as mock_client:
            yield mock_client

    @pytest.fixture
    def sample_bedrock_response(self):
        """Sample Bedrock knowledge base response."""
        return {
            "retrievalResults": [
                {
                    "content": {
                        "text": "Check-in time is 3:00 PM and check-out is 11:00 AM."
                    },
                    "score": 0.95,
                    "metadata": {
                        "hotel_id": "H-PVR-002",
                        "hotel_name": "Paraiso Vallarta Resort",
                        "category": "policies",
                    },
                    "location": {
                        "s3Location": {"uri": "s3://bucket/hotel-001/policies.md"}
                    },
                },
                {
                    "content": {
                        "text": "Our resort features 5 restaurants and 3 bars."
                    },
                    "score": 0.87,
                    "metadata": {
                        "hotel_id": "H-PVR-002",
                        "hotel_name": "Paraiso Vallarta Resort",
                        "category": "amenities",
                    },
                    "location": {
                        "s3Location": {"uri": "s3://bucket/hotel-001/amenities.md"}
                    },
                },
            ]
        }

    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """Set up environment variables for tests."""
        original_kb_id = os.environ.get("KNOWLEDGE_BASE_ID")
        os.environ["KNOWLEDGE_BASE_ID"] = "test-kb-id"

        # Reload the module to pick up the new environment variable
        import importlib

        import hotel_pms_simulation.mcp.server as server_module

        importlib.reload(server_module)

        yield

        if original_kb_id:
            os.environ["KNOWLEDGE_BASE_ID"] = original_kb_id
        else:
            os.environ.pop("KNOWLEDGE_BASE_ID", None)

        # Reload again to restore original state
        importlib.reload(server_module)

    @pytest.mark.asyncio
    async def test_query_without_hotel_filter(
        self, mock_bedrock_client, sample_bedrock_response
    ):
        """Test querying knowledge base without hotel_ids filter."""
        mock_bedrock_client.retrieve.return_value = sample_bedrock_response

        result = await query_hotel_knowledge(query="check-in time", max_results=5)

        # Verify bedrock client was called correctly
        mock_bedrock_client.retrieve.assert_called_once()
        call_kwargs = mock_bedrock_client.retrieve.call_args.kwargs

        assert call_kwargs["knowledgeBaseId"] == "test-kb-id"
        assert call_kwargs["retrievalQuery"]["text"] == "check-in time"
        assert (
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"][
                "numberOfResults"
            ]
            == 5
        )
        assert (
            "filter"
            not in call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]
        )

        # Verify result is a formatted string
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify result contains expected content
        assert "Check-in time is 3:00 PM and check-out is 11:00 AM." in result
        assert "Result 1" in result
        assert "Result 2" in result
        assert "relevance:" in result.lower()

        # Verify hotel names are included
        assert "Paraiso Vallarta Resort" in result or "H-PVR-002" in result

    @pytest.mark.asyncio
    async def test_query_with_hotel_filter(
        self, mock_bedrock_client, sample_bedrock_response
    ):
        """Test querying knowledge base with hotel_ids filter."""
        mock_bedrock_client.retrieve.return_value = sample_bedrock_response

        hotel_ids = ["H-PVR-002", "H-TUL-001"]
        result = await query_hotel_knowledge(
            query="amenities", hotel_ids=hotel_ids, max_results=3
        )

        # Verify bedrock client was called with filter
        mock_bedrock_client.retrieve.assert_called_once()
        call_kwargs = mock_bedrock_client.retrieve.call_args.kwargs

        assert call_kwargs["knowledgeBaseId"] == "test-kb-id"
        assert call_kwargs["retrievalQuery"]["text"] == "amenities"
        assert (
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"][
                "numberOfResults"
            ]
            == 3
        )

        # Verify filter was applied
        filter_config = call_kwargs["retrievalConfiguration"][
            "vectorSearchConfiguration"
        ]["filter"]
        assert filter_config["in"]["key"] == "hotel_id"
        assert filter_config["in"]["value"] == hotel_ids

        # Verify result is a formatted string
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_query_with_max_results(
        self, mock_bedrock_client, sample_bedrock_response
    ):
        """Test querying with max_results parameter."""
        mock_bedrock_client.retrieve.return_value = sample_bedrock_response

        result = await query_hotel_knowledge(query="restaurants", max_results=10)

        # Verify max_results was passed correctly
        call_kwargs = mock_bedrock_client.retrieve.call_args.kwargs
        assert (
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"][
                "numberOfResults"
            ]
            == 10
        )

        # Verify result is a formatted string
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_query_response_formatting(
        self, mock_bedrock_client, sample_bedrock_response
    ):
        """Test that query response is formatted correctly as a string."""
        mock_bedrock_client.retrieve.return_value = sample_bedrock_response

        result = await query_hotel_knowledge(query="test query")

        # Verify result is a string
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify formatting includes result numbers
        assert "Result 1" in result
        assert "Result 2" in result

        # Verify formatting includes relevance scores
        assert "relevance:" in result.lower()

        # Verify formatting includes content from both results
        assert "Check-in time is 3:00 PM and check-out is 11:00 AM." in result
        assert "Our resort features 5 restaurants and 3 bars." in result

        # Verify results are separated
        assert "---" in result

    @pytest.mark.asyncio
    async def test_query_error_handling(self, mock_bedrock_client):
        """Test error handling when Bedrock query fails."""
        mock_bedrock_client.retrieve.side_effect = Exception("Bedrock service error")

        with pytest.raises(Exception) as exc_info:
            await query_hotel_knowledge(query="test query")

        assert "Bedrock service error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_empty_results(self, mock_bedrock_client):
        """Test handling of empty results from knowledge base."""
        mock_bedrock_client.retrieve.return_value = {"retrievalResults": []}

        result = await query_hotel_knowledge(query="test query")

        # Verify result is a string with appropriate message
        assert isinstance(result, str)
        assert "No relevant information found" in result


class TestPromptFunctions:
    """Test cases for prompt loading and context generation."""

    @pytest.fixture
    def mock_hotel_service(self):
        """Mock HotelService for testing."""
        with patch("hotel_pms_simulation.mcp.server.hotel_service") as mock_service:
            mock_service.get_hotels.return_value = {
                "hotels": [
                    {"hotel_id": "H-PVR-002", "name": "Paraiso Vallarta"},
                    {"hotel_id": "H-TUL-001", "name": "Paraiso Tulum"},
                    {"hotel_id": "H-CAB-003", "name": "Paraiso Los Cabos"},
                ],
                "total_count": 3,
            }
            yield mock_service

    @pytest.fixture
    def temp_prompt_dir(self, tmp_path):
        """Create temporary prompt directory with test templates."""
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()

        # Create chat prompt template
        chat_prompt = prompt_dir / "chat_prompt.txt"
        chat_prompt.write_text(
            "You are a hotel assistant.\n\nCurrent date: {current_date}\n\n{hotel_list}\n\nHow can I help?"
        )

        # Create voice prompt template
        voice_prompt = prompt_dir / "voice_prompt.txt"
        voice_prompt.write_text(
            "Voice assistant.\n\nDate: {current_date}\n\n{hotel_list}\n\nSpeak naturally."
        )

        return prompt_dir

    def test_generate_hotel_context(self, mock_hotel_service):
        """Test hotel context generation from DynamoDB."""
        context = generate_hotel_context()

        # Verify current_date is present and formatted correctly
        assert "current_date" in context
        assert len(context["current_date"]) > 0

        # Verify hotel_list is present and formatted correctly
        assert "hotel_list" in context
        assert "Available hotels:" in context["hotel_list"]
        assert "Paraiso Vallarta (ID: H-PVR-002)" in context["hotel_list"]
        assert "Paraiso Tulum (ID: H-TUL-001)" in context["hotel_list"]
        assert "Paraiso Los Cabos (ID: H-CAB-003)" in context["hotel_list"]

        # Verify hotel service was called
        mock_hotel_service.get_hotels.assert_called_once()

    def test_generate_hotel_context_error_handling(self):
        """Test hotel context generation when DynamoDB fails."""
        with patch("hotel_pms_simulation.mcp.server.hotel_service") as mock_service:
            mock_service.get_hotels.side_effect = Exception("DynamoDB error")

            context = generate_hotel_context()

            # Should still return current_date
            assert "current_date" in context

            # Should return fallback message for hotel_list
            assert "hotel_list" in context
            assert "Hotel list temporarily unavailable" in context["hotel_list"]

    def test_load_prompt_with_context_chat(self, temp_prompt_dir, mock_hotel_service):
        """Test loading chat prompt with context injection."""
        prompt = load_prompt_with_context("chat", prompt_dir=temp_prompt_dir)

        # Verify template was loaded
        assert "You are a hotel assistant" in prompt
        assert "How can I help?" in prompt

        # Verify context was injected
        assert "{current_date}" not in prompt  # Should be replaced
        assert "{hotel_list}" not in prompt  # Should be replaced
        assert "Available hotels:" in prompt
        assert "Paraiso Vallarta (ID: H-PVR-002)" in prompt

    def test_load_prompt_with_context_voice(self, temp_prompt_dir, mock_hotel_service):
        """Test loading voice prompt with context injection."""
        prompt = load_prompt_with_context("voice", prompt_dir=temp_prompt_dir)

        # Verify template was loaded
        assert "Voice assistant" in prompt
        assert "Speak naturally" in prompt

        # Verify context was injected
        assert "{current_date}" not in prompt
        assert "{hotel_list}" not in prompt
        assert "Available hotels:" in prompt

    def test_load_prompt_template_not_found(self, temp_prompt_dir):
        """Test error handling when prompt template doesn't exist."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_prompt_with_context("nonexistent", prompt_dir=temp_prompt_dir)

        assert "Prompt template not found" in str(exc_info.value)
