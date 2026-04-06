# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Cognito MCP client module for OAuth2 authenticated MCP connections.

This module provides OAuth2 authenticated streaming HTTP MCP client functionality
for connecting to MCP servers deployed with AgentCore Gateway that use Cognito authentication.
"""

from .cognito_auth import CognitoAuth
from .cognito_mcp_client import cognito_mcp_client
from .exceptions import (
    CognitoAuthError,
    CognitoConfigError,
    CognitoMCPClientError,
    CognitoMcpError,
    McpConnectionError,
    TokenRefreshError,
)

__all__ = [
    "CognitoAuth",
    "cognito_mcp_client",
    "CognitoMcpError",
    "CognitoAuthError",
    "CognitoConfigError",
    "CognitoMCPClientError",
    "McpConnectionError",
    "TokenRefreshError",
]
