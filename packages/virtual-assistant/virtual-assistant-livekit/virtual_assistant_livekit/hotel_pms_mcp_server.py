# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel PMS MCP Server for LiveKit integration.

This module provides MCP server implementations that integrate with LiveKit's
agent framework using the standard MCPServer interface with Cognito authentication.
"""

import logging
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from livekit.agents import mcp
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class CognitoMCPServer(mcp.MCPServer):
    """
    MCP Server with Cognito authentication for LiveKit agents.

    This class extends LiveKit's MCPServer to support Cognito-authenticated
    MCP servers. It handles token acquisition and refresh automatically.
    """

    def __init__(
        self,
        url: str,
        user_pool_id: str,
        client_id: str,
        client_secret: str,
        region: str,
        server_name: str,
        headers: dict[str, Any] | None = None,
        timeout: float = 30,
        client_session_timeout_seconds: float = 30,
    ):
        """
        Initialize Cognito-authenticated MCP server.

        Args:
            url: MCP server URL
            user_pool_id: Cognito User Pool ID
            client_id: Cognito Client ID
            client_secret: Cognito Client Secret
            region: AWS region
            server_name: Name of the server (for logging)
            headers: Additional HTTP headers
            timeout: Connection timeout in seconds (default: 30)
            client_session_timeout_seconds: MCP tool call timeout in seconds (default: 30)
        """
        super().__init__(client_session_timeout_seconds=client_session_timeout_seconds)
        self.url = url
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.server_name = server_name
        self.headers = headers or {}
        self._timeout = timeout
        self._access_token: str | None = None
        logger.info(f"Created CognitoMCPServer for {server_name}")

    async def _get_access_token(self) -> str:
        """
        Get Cognito access token using client credentials flow.

        Returns:
            Access token string
        """
        if self._access_token:
            return self._access_token

        # Import here to avoid circular dependency
        from virtual_assistant_common.cognito_mcp.cognito_auth import CognitoAuth

        auth = CognitoAuth(
            user_pool_id=self.user_pool_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
            region=self.region,
        )

        # CognitoAuth is an httpx.Auth - we need to get the token directly
        token_info = auth._get_valid_token()
        self._access_token = token_info.access_token
        logger.debug(f"Acquired access token for {self.server_name}")
        return self._access_token

    def client_streams(
        self,
    ):
        """
        Create client streams for MCP communication.

        This method is called by LiveKit's MCPServer.initialize() to establish
        the connection to the MCP server.

        Returns:
            Context manager providing read/write streams and session ID callback
        """

        @asynccontextmanager
        async def _context():
            # Get access token
            token = await self._get_access_token()

            # Prepare headers with authentication
            headers = self.headers.copy()
            headers["Authorization"] = f"Bearer {token}"
            headers["Content-Type"] = "application/json"

            # Create streamable HTTP client
            async with streamablehttp_client(
                url=self.url,
                headers=headers,
                timeout=timedelta(seconds=self._timeout),
                terminate_on_close=False,
            ) as streams:
                yield streams

        return _context()

    def __repr__(self) -> str:
        return f"CognitoMCPServer(server_name={self.server_name}, url={self.url})"
