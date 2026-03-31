# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Simple tests for messaging client."""

import os
from unittest.mock import patch

import pytest

from virtual_assistant_common.clients.messaging_client import MessagingClient


class TestMessagingClientBasic:
    """Test basic MessagingClient functionality."""

    def test_init_with_endpoint(self):
        """Test client initialization with explicit endpoint."""
        client = MessagingClient(api_endpoint="https://api.example.com")
        assert client.api_endpoint == "https://api.example.com"

    def test_init_with_env_var(self):
        """Test client initialization with environment variable."""
        with patch.dict(os.environ, {"MESSAGING_API_ENDPOINT": "https://env.example.com"}):
            client = MessagingClient()
            assert client.api_endpoint == "https://env.example.com"

    def test_init_without_endpoint_raises_error(self):
        """Test that missing endpoint raises ValueError."""
        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="MESSAGING_API_ENDPOINT"):
            MessagingClient()

    def test_endpoint_trailing_slash_removed(self):
        """Test that trailing slash is removed from endpoint."""
        client = MessagingClient(api_endpoint="https://api.example.com/")
        assert client.api_endpoint == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using client as async context manager."""
        async with MessagingClient(api_endpoint="https://api.example.com") as client:
            assert isinstance(client, MessagingClient)

        # Client should be closed after context exit
        assert client._client is None
