# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel Assistant Common Package

This package contains shared utilities, models, and configurations
that can be used across virtual-assistant-livekit and virtual-assistant-chat packages.
"""

__version__ = "1.0.0"

# Import cognito_mcp module components
# Import messaging client
from .clients.messaging_client import MessagingClient
from .cognito_mcp import (
    CognitoAuth,
    CognitoAuthError,
    CognitoConfigError,
    CognitoMCPClientError,
    CognitoMcpError,
    McpConnectionError,
    TokenRefreshError,
    cognito_mcp_client,
)

# Import base exceptions
from .exceptions import (
    ConfigurationError,
    ConnectionError,
    HotelAssistantError,
)

# Import hotel PMS MCP client
from .hotel_pms_mcp_client import hotel_pms_mcp_client

# Import hotel PMS operations
from .hotel_pms_operations import (
    check_availability,
    create_reservation,
    get_hotel_by_id,
    get_hotels,
    get_reservations,
    get_room_types,
)

# Import messaging models and clients
from .models.messaging import (
    AgentInvocationPayload,
    MessageEvent,
    MessageResponse,
    MessageStatus,
    PlatformMessage,
    SendMessageRequest,
    StatusUpdateRequest,
)

# Import platform interfaces
from .platforms import (
    AWSEndUserMessaging,
    MessagingPlatform,
    TwilioMessaging,
    WebMessaging,
)

__all__ = [
    # Cognito MCP components
    "CognitoAuth",
    "cognito_mcp_client",
    "CognitoMcpError",
    "CognitoAuthError",
    "CognitoConfigError",
    "CognitoMCPClientError",
    "McpConnectionError",
    "TokenRefreshError",
    # Hotel PMS MCP client
    "hotel_pms_mcp_client",
    # Hotel PMS operations
    "get_hotels",
    "get_hotel_by_id",
    "check_availability",
    "get_room_types",
    "get_reservations",
    "create_reservation",
    # Base exceptions
    "HotelAssistantError",
    "ConfigurationError",
    "ConnectionError",
    # Messaging models
    "MessageStatus",
    "MessageEvent",
    "AgentInvocationPayload",
    "PlatformMessage",
    "MessageResponse",
    "StatusUpdateRequest",
    "SendMessageRequest",
    # Messaging client
    "MessagingClient",
    # Platform interfaces
    "MessagingPlatform",
    "WebMessaging",
    "TwilioMessaging",
    "AWSEndUserMessaging",
]
