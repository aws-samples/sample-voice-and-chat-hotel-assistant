# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared messaging API client for Lambda and AgentCore Runtime."""

import base64
import json
import logging
import os
from typing import Any

import boto3
import httpx

from ..models.messaging import SendMessageRequest

logger = logging.getLogger(__name__)


class MessagingClient:
    """Shared messaging API client for Lambda and AgentCore Runtime.

    This client provides a unified interface for interacting with the
    chatbot-messaging-backend API from both Lambda functions and
    AgentCore Runtime environments.
    """

    def __init__(self, api_endpoint: str | None = None, auth_token: str | None = None):
        """Initialize messaging client.

        Args:
            api_endpoint: Messaging API endpoint URL (defaults to env var)
            auth_token: Authentication token (defaults to env-based method)
        """
        self.api_endpoint = api_endpoint or os.environ.get("MESSAGING_API_ENDPOINT")
        if not self.api_endpoint:
            raise ValueError("MESSAGING_API_ENDPOINT environment variable or api_endpoint parameter required")

        # Remove trailing slash for consistent URL building
        self.api_endpoint = self.api_endpoint.rstrip("/")

        self._auth_token = auth_token
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),  # 30 second timeout
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Dictionary with authorization headers
        """
        headers = {}

        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        else:
            # TODO: Implement context-specific authentication
            # For Lambda: Use IAM role or service-to-service auth
            # For AgentCore: Use context-provided authentication
            auth_token = self._get_auth_token()
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"

        return headers

    def _get_auth_token(self) -> str | None:
        """Get authentication token based on execution context.

        In Lambda: Use OAuth2 client credentials from Secrets Manager
        In AgentCore: Use request context authentication

        Returns:
            Authentication token or None
        """
        # Check if we're in Lambda with messaging client secret
        secret_arn = os.environ.get("MESSAGING_CLIENT_SECRET_ARN")
        if secret_arn:
            try:
                return self._get_oauth2_token(secret_arn)
            except Exception as e:
                logger.error(f"Failed to get OAuth2 token from secret {secret_arn}: {e}")
                return None

        # Fallback to environment variable
        return os.environ.get("MESSAGING_API_TOKEN")

    def _get_oauth2_token(self, secret_arn: str) -> str:
        """Get OAuth2 access token using client credentials flow.

        Args:
            secret_arn: ARN of the secret containing OAuth2 credentials

        Returns:
            OAuth2 access token

        Raises:
            Exception: If token retrieval fails
        """
        # Get credentials from Secrets Manager
        secrets_client = boto3.client("secretsmanager")
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        credentials = json.loads(response["SecretString"])

        # Extract OAuth2 configuration
        client_id = credentials["client_id"]
        client_secret = credentials["client_secret"]
        token_url = credentials["oauth_token_url"]
        scope = credentials["scope"]

        # Create Basic Auth header
        auth_string = f"{client_id}:{client_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()

        # Make OAuth2 client credentials request using httpx in sync mode
        with httpx.Client(timeout=30.0) as client:
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "client_credentials",
                "scope": scope,
            }

            response = client.post(token_url, headers=headers, data=data)
            response.raise_for_status()

            token_data = response.json()
            return token_data["access_token"]

    async def send_message(self, recipient_id: str, content: str, conversation_id: str | None = None) -> dict[str, Any]:
        """Send message via messaging API.

        Args:
            recipient_id: Message recipient identifier
            content: Message content
            conversation_id: Optional conversation identifier (UUID format)

        Returns:
            API response with message details including conversationId

        Raises:
            httpx.HTTPError: If API request fails
        """
        client = await self._get_client()
        headers = await self._get_auth_headers()

        request_data = SendMessageRequest(recipient_id=recipient_id, content=content, conversation_id=conversation_id)

        logger.debug(f"Sending message to {recipient_id}")
        if conversation_id:
            logger.debug(f"Using conversation ID: {conversation_id}")

        try:
            response = await client.post(
                f"{self.api_endpoint}/messages", json=request_data.model_dump(), headers=headers
            )
            response.raise_for_status()
            result = response.json()

            logger.debug(f"Message sent successfully: {result.get('messageId')}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def update_message_status(self, message_id: str, status: str) -> dict[str, Any]:
        """Update message status via messaging API.

        Args:
            message_id: ID of message to update
            status: New status value

        Returns:
            API response with update confirmation

        Raises:
            httpx.HTTPError: If API request fails
        """
        client = await self._get_client()
        headers = await self._get_auth_headers()

        logger.debug(f"Updating message {message_id} status to {status}")

        try:
            response = await client.put(
                f"{self.api_endpoint}/messages/{message_id}/status", json={"status": status}, headers=headers
            )
            response.raise_for_status()
            result = response.json()

            logger.debug(f"Message status updated successfully: {message_id}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to update message status: {e}")
            raise

    async def get_message(self, message_id: str) -> dict[str, Any]:
        """Get message details by ID.

        Args:
            message_id: ID of message to retrieve

        Returns:
            Message details from API

        Raises:
            httpx.HTTPError: If API request fails
        """
        client = await self._get_client()
        headers = await self._get_auth_headers()

        logger.debug(f"Retrieving message {message_id}")

        try:
            response = await client.get(f"{self.api_endpoint}/messages/{message_id}", headers=headers)
            response.raise_for_status()
            result = response.json()

            logger.debug(f"Message retrieved successfully: {message_id}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to retrieve message: {e}")
            raise

    async def get_conversation_messages(
        self, conversation_id: str, limit: int = 50, before_timestamp: str | None = None
    ) -> dict[str, Any]:
        """Get messages for a conversation.

        Args:
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            before_timestamp: Get messages before this timestamp

        Returns:
            List of messages and pagination info

        Raises:
            httpx.HTTPError: If API request fails
        """
        client = await self._get_client()
        headers = await self._get_auth_headers()

        params = {"limit": limit}
        if before_timestamp:
            params["before"] = before_timestamp

        logger.debug(f"Retrieving messages for conversation {conversation_id}")

        try:
            response = await client.get(
                f"{self.api_endpoint}/conversations/{conversation_id}/messages", params=params, headers=headers
            )
            response.raise_for_status()
            result = response.json()

            logger.debug(f"Retrieved {len(result.get('messages', []))} messages for conversation {conversation_id}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to retrieve conversation messages: {e}")
            raise

    async def close(self):
        """Close the HTTP client and clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
