# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
CognitoAuth implementation for httpx.Auth interface.

This module provides OAuth2 client credentials flow authentication
for Cognito user pools with automatic token refresh and caching.
"""

import base64
import json
import logging
import time
from collections.abc import Generator
from dataclasses import dataclass

import httpx

from .exceptions import CognitoAuthError, TokenRefreshError

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """OAuth2 token information."""

    access_token: str
    expires_at: float
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return time.time() >= self.expires_at

    def expires_soon(self, buffer_seconds: int = 60) -> bool:
        """Check if token expires within buffer_seconds."""
        return time.time() >= (self.expires_at - buffer_seconds)


class CognitoAuth(httpx.Auth):
    """
    httpx.Auth implementation for Cognito OAuth2 client credentials flow.

    This class handles automatic token acquisition, caching, and refresh
    for Cognito user pools using the OAuth2 client credentials flow.
    It implements exponential backoff retry logic for authentication failures.
    """

    requires_response_body = True

    def __init__(
        self,
        user_pool_id: str,
        client_id: str,
        client_secret: str,
        region: str = "us-east-1",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize CognitoAuth.

        Args:
            user_pool_id: Cognito user pool ID
            client_id: Cognito client ID
            client_secret: Cognito client secret
            region: AWS region
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.timeout = timeout
        self.max_retries = max_retries

        # Token caching
        self._token: TokenInfo | None = None
        self._token_endpoint: str | None = None

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        """
        httpx.Auth flow implementation.

        This method is called by httpx for each request that needs authentication.
        It ensures a valid token is available and adds the Authorization header.

        Args:
            request: The HTTP request to authenticate

        Yields:
            The authenticated request
        """
        # Ensure we have a valid token
        token = self._get_valid_token()

        # Add Authorization header
        request.headers["Authorization"] = f"{token.token_type} {token.access_token}"

        # Yield the authenticated request
        response = yield request

        # If we get a 401, try to refresh the token and retry once
        if response.status_code == 401:
            logger.warning("Received 401 response, attempting token refresh")

            # Clear cached token and get a new one
            self._token = None
            token = self._get_valid_token()

            # Update the request with new token
            request.headers["Authorization"] = f"{token.token_type} {token.access_token}"

            # Retry the request
            yield request

    def _get_valid_token(self) -> TokenInfo:
        """
        Get a valid access token, refreshing if necessary.

        This method handles token caching and automatic refresh.

        Returns:
            Valid TokenInfo object

        Raises:
            CognitoAuthError: If token acquisition fails
            TokenRefreshError: If token refresh fails
        """
        # Check if we have a cached token that's still valid
        if self._token and not self._token.expires_soon():
            return self._token

        # Need to acquire or refresh token
        is_refresh = self._token and self._token.expires_soon()
        logger.info("Token expires soon, refreshing" if is_refresh else "Acquiring new token")

        try:
            self._token = self._acquire_token()
            return self._token
        except Exception as e:
            if is_refresh:
                raise TokenRefreshError(
                    f"Failed to refresh token: {e}",
                    token_expires_at=self._token.expires_at,
                    refresh_attempt=1,
                    user_pool_id=self.user_pool_id,
                    client_id=self.client_id,
                ) from e
            else:
                # Let the original exception bubble up for new token acquisition
                raise

    def _get_token_endpoint(self) -> str:
        """
        Get the OAuth2 token endpoint using OpenID Connect discovery.

        Returns:
            Token endpoint URL

        Raises:
            CognitoAuthError: If endpoint discovery fails
        """
        if self._token_endpoint:
            return self._token_endpoint

        try:
            # Construct the OpenID Connect configuration URL
            oidc_config_url = (
                f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/openid-configuration"
            )

            logger.debug(f"Discovering token endpoint from: {oidc_config_url}")

            # Fetch the OpenID Connect configuration
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(oidc_config_url)

                if response.status_code != 200:
                    raise CognitoAuthError(
                        f"Failed to fetch OIDC configuration: HTTP {response.status_code}",
                        user_pool_id=self.user_pool_id,
                        client_id=self.client_id,
                        region=self.region,
                        auth_flow="oidc_discovery",
                        status_code=response.status_code,
                    )

                oidc_config = response.json()
                token_endpoint = oidc_config.get("token_endpoint")

                if not token_endpoint:
                    raise CognitoAuthError(
                        "No token_endpoint found in OIDC configuration",
                        user_pool_id=self.user_pool_id,
                        client_id=self.client_id,
                        region=self.region,
                        auth_flow="oidc_discovery",
                    )

                self._token_endpoint = token_endpoint
                logger.info(f"Discovered token endpoint: {token_endpoint}")
                return token_endpoint

        except httpx.RequestError as e:
            raise CognitoAuthError(
                f"Network error during OIDC discovery: {e}",
                user_pool_id=self.user_pool_id,
                client_id=self.client_id,
                region=self.region,
                auth_flow="oidc_discovery",
            ) from e
        except json.JSONDecodeError as e:
            raise CognitoAuthError(
                f"Invalid JSON in OIDC configuration: {e}",
                user_pool_id=self.user_pool_id,
                client_id=self.client_id,
                region=self.region,
                auth_flow="oidc_discovery",
            ) from e
        except Exception as e:
            raise CognitoAuthError(
                f"Unexpected error during OIDC discovery: {e}",
                user_pool_id=self.user_pool_id,
                client_id=self.client_id,
                region=self.region,
                auth_flow="oidc_discovery",
            ) from e

    def _acquire_token(self) -> TokenInfo:
        """
        Acquire a new access token using OAuth2 client credentials flow.

        Implements exponential backoff retry logic for transient failures.

        Returns:
            TokenInfo object with new access token

        Raises:
            CognitoAuthError: If token acquisition fails after all retries
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                # Get the token endpoint using OIDC discovery
                token_endpoint = self._get_token_endpoint()

                # Prepare OAuth2 client credentials request
                auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

                headers = {
                    "Authorization": f"Basic {auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded",
                }

                data = {"grant_type": "client_credentials"}

                # Make the token request using synchronous client
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(token_endpoint, headers=headers, data=data)

                # Handle response
                if response.status_code == 200:
                    token_data = response.json()

                    # Calculate expiration time
                    expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                    expires_at = time.time() + expires_in

                    token_info = TokenInfo(
                        access_token=token_data["access_token"],
                        expires_at=expires_at,
                        token_type=token_data.get("token_type", "Bearer"),
                    )

                    logger.info(
                        "Successfully acquired token",
                        extra={"expires_at": expires_at, "expires_in": expires_in, "attempt": attempt + 1},
                    )

                    return token_info

                else:
                    # Parse error response
                    try:
                        error_data = response.json()
                        error_code = error_data.get("error", "unknown_error")
                        error_description = error_data.get("error_description", "No description provided")
                        logger.debug(f"OAuth2 error response: {error_data}")
                    except (json.JSONDecodeError, KeyError):
                        error_code = "http_error"
                        error_description = f"HTTP {response.status_code}: {response.text}"
                        logger.debug(f"OAuth2 raw error response: {response.text}")

                    # Create exception for this attempt
                    auth_error = CognitoAuthError(
                        f"OAuth2 token request failed: {error_description}",
                        user_pool_id=self.user_pool_id,
                        client_id=self.client_id,
                        region=self.region,
                        auth_flow="client_credentials",
                        status_code=response.status_code,
                        cognito_error_code=error_code,
                    )

                    # For 4xx errors (client errors), don't retry
                    if 400 <= response.status_code < 500:
                        logger.error(f"Client error during token acquisition: {auth_error}")
                        raise auth_error

                    # For 5xx errors, retry with backoff
                    last_exception = auth_error

            except CognitoAuthError:
                # Re-raise CognitoAuthError (from 4xx responses) without modification
                raise

            except httpx.RequestError as e:
                # Network/connection errors - retry with backoff
                last_exception = CognitoAuthError(
                    f"Network error during token acquisition: {e}",
                    user_pool_id=self.user_pool_id,
                    client_id=self.client_id,
                    region=self.region,
                    auth_flow="client_credentials",
                )

            except Exception as e:
                # Unexpected errors
                last_exception = CognitoAuthError(
                    f"Unexpected error during token acquisition: {e}",
                    user_pool_id=self.user_pool_id,
                    client_id=self.client_id,
                    region=self.region,
                    auth_flow="client_credentials",
                )

            # If this wasn't the last attempt, wait before retrying
            if attempt < self.max_retries:
                # Exponential backoff: 1s, 2s, 4s, 8s, etc.
                backoff_time = 2**attempt
                logger.warning(
                    f"Token acquisition attempt {attempt + 1} failed, retrying in {backoff_time}s",
                    extra={"error": str(last_exception), "backoff_time": backoff_time},
                )
                time.sleep(backoff_time)

        # All retries exhausted
        logger.error(f"Token acquisition failed after {self.max_retries + 1} attempts")
        if last_exception:
            raise last_exception
        else:
            raise CognitoAuthError(
                "Token acquisition failed after all retries",
                user_pool_id=self.user_pool_id,
                client_id=self.client_id,
                region=self.region,
                auth_flow="client_credentials",
            )
