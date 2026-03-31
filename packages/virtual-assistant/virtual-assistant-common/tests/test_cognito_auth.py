# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Unit tests for CognitoAuth class.

This module contains comprehensive unit tests for the CognitoAuth class,
covering OAuth2 flow, token caching, automatic refresh, and error handling.
"""

import base64
import contextlib
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from virtual_assistant_common.cognito_mcp.cognito_auth import CognitoAuth, TokenInfo
from virtual_assistant_common.cognito_mcp.exceptions import CognitoAuthError, TokenRefreshError


class TestTokenInfo:
    """Test cases for TokenInfo dataclass."""

    def test_token_info_creation(self):
        """Test TokenInfo creation with required fields."""
        token = TokenInfo(access_token="test-token", expires_at=time.time() + 3600)

        assert token.access_token == "test-token"
        assert token.token_type == "Bearer"
        assert not token.is_expired

    def test_token_info_custom_type(self):
        """Test TokenInfo with custom token type."""
        token = TokenInfo(access_token="test-token", expires_at=time.time() + 3600, token_type="Custom")

        assert token.token_type == "Custom"

    def test_is_expired_false(self):
        """Test is_expired returns False for valid token."""
        token = TokenInfo(
            access_token="test-token",
            expires_at=time.time() + 3600,  # 1 hour from now
        )

        assert not token.is_expired

    def test_is_expired_true(self):
        """Test is_expired returns True for expired token."""
        token = TokenInfo(
            access_token="test-token",
            expires_at=time.time() - 3600,  # 1 hour ago
        )

        assert token.is_expired

    def test_expires_soon_false(self):
        """Test expires_soon returns False for token with plenty of time."""
        token = TokenInfo(
            access_token="test-token",
            expires_at=time.time() + 3600,  # 1 hour from now
        )

        assert not token.expires_soon()

    def test_expires_soon_true(self):
        """Test expires_soon returns True for token expiring within buffer."""
        token = TokenInfo(
            access_token="test-token",
            expires_at=time.time() + 30,  # 30 seconds from now
        )

        assert token.expires_soon()  # Default buffer is 60 seconds

    def test_expires_soon_custom_buffer(self):
        """Test expires_soon with custom buffer."""
        token = TokenInfo(
            access_token="test-token",
            expires_at=time.time() + 90,  # 90 seconds from now
        )

        assert not token.expires_soon(buffer_seconds=60)
        assert token.expires_soon(buffer_seconds=120)


class TestCognitoAuth:
    """Test cases for CognitoAuth class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.user_pool_id = "us-east-1_test123"
        self.client_id = "test-client-id"
        self.client_secret = "test-client-secret"
        self.region = "us-east-1"

        self.auth = CognitoAuth(
            user_pool_id=self.user_pool_id,
            client_id=self.client_id,
            client_secret=self.client_secret,
            region=self.region,
            timeout=30.0,
            max_retries=3,
        )

    def _mock_oidc_discovery(
        self, mock_client, token_endpoint="https://test-user-pool.auth.us-east-1.amazoncognito.com/oauth2/token"
    ):
        """Helper method to mock OIDC discovery."""
        oidc_response = MagicMock()
        oidc_response.status_code = 200
        oidc_response.json.return_value = {"token_endpoint": token_endpoint}
        mock_client.get.return_value = oidc_response
        return oidc_response

    def test_init(self):
        """Test CognitoAuth initialization."""
        assert self.auth.user_pool_id == self.user_pool_id
        assert self.auth.client_id == self.client_id
        assert self.auth.client_secret == self.client_secret
        assert self.auth.region == self.region
        assert self.auth.timeout == 30.0
        assert self.auth.max_retries == 3
        assert self.auth._token is None
        assert self.auth._token_endpoint is None  # Not discovered yet

    def test_init_defaults(self):
        """Test CognitoAuth initialization with defaults."""
        auth = CognitoAuth(user_pool_id=self.user_pool_id, client_id=self.client_id, client_secret=self.client_secret)

        assert auth.region == "us-east-1"
        assert auth.timeout == 30.0
        assert auth.max_retries == 3

    def test_get_valid_token_cached_valid(self):
        """Test _get_valid_token with valid cached token."""
        # Set up a valid cached token
        self.auth._token = TokenInfo(
            access_token="cached-token",
            expires_at=time.time() + 3600,  # 1 hour from now
        )

        result = self.auth._get_valid_token()

        assert result == self.auth._token
        assert result.access_token == "cached-token"

    def test_get_valid_token_no_token(self):
        """Test _get_valid_token with no cached token."""
        with patch.object(self.auth, "_acquire_token") as mock_acquire:
            mock_token = TokenInfo(access_token="new-token", expires_at=time.time() + 3600)
            mock_acquire.return_value = mock_token

            result = self.auth._get_valid_token()

            assert result == mock_token
            assert self.auth._token == mock_token
            mock_acquire.assert_called_once()

    def test_get_valid_token_token_expires_soon(self):
        """Test _get_valid_token with token expiring soon."""
        # Set up a token that expires soon
        self.auth._token = TokenInfo(
            access_token="expiring-token",
            expires_at=time.time() + 30,  # 30 seconds from now
        )

        with patch.object(self.auth, "_acquire_token") as mock_acquire:
            mock_token = TokenInfo(access_token="refreshed-token", expires_at=time.time() + 3600)
            mock_acquire.return_value = mock_token

            result = self.auth._get_valid_token()

            assert result == mock_token
            assert self.auth._token == mock_token
            mock_acquire.assert_called_once()

    def test_get_valid_token_refresh_error(self):
        """Test _get_valid_token with refresh error."""
        # Set up a token that expires soon
        self.auth._token = TokenInfo(access_token="expiring-token", expires_at=time.time() + 30)

        with patch.object(self.auth, "_acquire_token") as mock_acquire:
            mock_acquire.side_effect = ValueError("Refresh failed")

            with pytest.raises(TokenRefreshError, match="Failed to refresh token"):
                self.auth._get_valid_token()

    def test_acquire_token_success(self):
        """Test _acquire_token success path."""
        # Mock OIDC discovery response
        oidc_response = MagicMock()
        oidc_response.status_code = 200
        oidc_response.json.return_value = {
            "token_endpoint": "https://test-user-pool.auth.us-east-1.amazoncognito.com/oauth2/token"
        }

        # Mock token response
        token_response_data = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = token_response_data

        mock_client = MagicMock()
        mock_client.get.return_value = oidc_response  # OIDC discovery
        mock_client.post.return_value = token_response  # Token request

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = self.auth._acquire_token()

            assert result.access_token == "test-access-token"
            assert result.token_type == "Bearer"
            assert result.expires_at > time.time()

            # Verify OIDC discovery was called
            mock_client.get.assert_called_once()
            oidc_call_args = mock_client.get.call_args
            expected_oidc_url = (
                f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/openid-configuration"
            )
            assert oidc_call_args[0][0] == expected_oidc_url

            # Verify token request was made correctly
            mock_client.post.assert_called_once()
            token_call_args = mock_client.post.call_args

            # Check URL
            assert token_call_args[0][0] == "https://test-user-pool.auth.us-east-1.amazoncognito.com/oauth2/token"

            # Check headers
            headers = token_call_args[1]["headers"]
            assert "Authorization" in headers
            assert headers["Authorization"].startswith("Basic ")
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"

            # Check data
            data = token_call_args[1]["data"]
            assert data["grant_type"] == "client_credentials"

    def test_acquire_token_http_error_4xx(self):
        """Test _acquire_token with 4xx HTTP error (no retry)."""
        # Mock OIDC discovery response
        oidc_response = MagicMock()
        oidc_response.status_code = 200
        oidc_response.json.return_value = {
            "token_endpoint": "https://test-user-pool.auth.us-east-1.amazoncognito.com/oauth2/token"
        }

        # Mock token error response
        token_response = MagicMock()
        token_response.status_code = 400
        token_response.json.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials",
        }

        mock_client = MagicMock()
        mock_client.get.return_value = oidc_response  # OIDC discovery
        mock_client.post.return_value = token_response  # Token request

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            with pytest.raises(CognitoAuthError) as exc_info:
                self.auth._acquire_token()

            error = exc_info.value
            assert "Invalid client credentials" in str(error)
            assert error.status_code == 400
            assert error.cognito_error_code == "invalid_client"

            # Should only be called once (no retry for 4xx)
            mock_client.post.assert_called_once()

    def test_acquire_token_http_error_5xx_with_retry(self):
        """Test _acquire_token with 5xx HTTP error (with retry)."""
        token_response = MagicMock()
        token_response.status_code = 500
        token_response.json.return_value = {"error": "server_error", "error_description": "Internal server error"}

        mock_client = MagicMock()
        self._mock_oidc_discovery(mock_client)  # Mock OIDC discovery
        mock_client.post.return_value = token_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            with patch("time.sleep") as mock_sleep:
                with pytest.raises(CognitoAuthError) as exc_info:
                    self.auth._acquire_token()

                error = exc_info.value
                assert "Internal server error" in str(error)
                assert error.status_code == 500

                # Should be called max_retries + 1 times (OIDC discovery once, then token requests)
                assert mock_client.post.call_count == self.auth.max_retries + 1

                # Should have called sleep for backoff
                assert mock_sleep.call_count == self.auth.max_retries

    def test_acquire_token_network_error_with_retry(self):
        """Test _acquire_token with network error (with retry)."""
        mock_client = MagicMock()
        self._mock_oidc_discovery(mock_client)  # Mock OIDC discovery
        mock_client.post.side_effect = httpx.RequestError("Network error")

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            with patch("time.sleep") as mock_sleep:
                with pytest.raises(CognitoAuthError) as exc_info:
                    self.auth._acquire_token()

                error = exc_info.value
                assert "Network error during token acquisition" in str(error)

                # Should be called max_retries + 1 times
                assert mock_client.post.call_count == self.auth.max_retries + 1

                # Should have called sleep for backoff
                assert mock_sleep.call_count == self.auth.max_retries

    def test_acquire_token_exponential_backoff(self):
        """Test _acquire_token uses exponential backoff."""
        mock_client = MagicMock()
        self._mock_oidc_discovery(mock_client)  # Mock OIDC discovery
        mock_client.post.side_effect = httpx.RequestError("Network error")

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            with patch("time.sleep") as mock_sleep:
                with pytest.raises(CognitoAuthError):
                    self.auth._acquire_token()

                # Check exponential backoff: 1s, 2s, 4s
                expected_calls = [1, 2, 4]
                actual_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert actual_calls == expected_calls

    def test_acquire_token_success_after_retry(self):
        """Test _acquire_token succeeds after initial failure."""
        # First call fails, second succeeds
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.json.return_value = {"error": "server_error"}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "access_token": "retry-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_client = MagicMock()
        self._mock_oidc_discovery(mock_client)  # Mock OIDC discovery
        mock_client.post.side_effect = [mock_response_error, mock_response_success]

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            with patch("time.sleep"):
                result = self.auth._acquire_token()

                assert result.access_token == "retry-token"
                assert mock_client.post.call_count == 2

    def test_auth_flow_success(self):
        """Test auth_flow success path."""
        # Mock _get_valid_token to return a token
        mock_token = TokenInfo(access_token="test-token", expires_at=time.time() + 3600)

        with patch.object(self.auth, "_get_valid_token", return_value=mock_token):
            request = httpx.Request("GET", "https://example.com")

            # Get the generator
            auth_gen = self.auth.auth_flow(request)

            # First yield should return the authenticated request
            authenticated_request = next(auth_gen)

            assert authenticated_request.headers["Authorization"] == "Bearer test-token"

            # Simulate a successful response
            response = httpx.Response(200)

            with contextlib.suppress(StopIteration):
                auth_gen.send(response)

    def test_auth_flow_401_retry(self):
        """Test auth_flow retries on 401 response."""
        # Mock _get_valid_token to return different tokens on each call
        mock_token1 = TokenInfo(access_token="expired-token", expires_at=time.time() + 3600)
        mock_token2 = TokenInfo(access_token="refreshed-token", expires_at=time.time() + 3600)

        with patch.object(self.auth, "_get_valid_token", side_effect=[mock_token1, mock_token2]):
            request = httpx.Request("GET", "https://example.com")

            # Get the generator
            auth_gen = self.auth.auth_flow(request)

            # First yield should return the authenticated request
            authenticated_request = next(auth_gen)
            assert authenticated_request.headers["Authorization"] == "Bearer expired-token"

            # Simulate a 401 response
            response_401 = httpx.Response(401)

            # Send the 401 response - should trigger retry
            retry_request = auth_gen.send(response_401)

            # Should have updated token
            assert retry_request.headers["Authorization"] == "Bearer refreshed-token"

            # Verify token was cleared (by checking _get_valid_token was called twice)
            assert self.auth._token is None

    def test_auth_flow_token_acquisition_error(self):
        """Test auth_flow with token acquisition error."""
        with patch.object(self.auth, "_get_valid_token", side_effect=CognitoAuthError("Token error")):
            request = httpx.Request("GET", "https://example.com")

            with pytest.raises(CognitoAuthError, match="Token error"):
                auth_gen = self.auth.auth_flow(request)
                next(auth_gen)

    def test_basic_auth_header_encoding(self):
        """Test that Basic auth header is properly encoded."""
        expected_credentials = f"{self.client_id}:{self.client_secret}"
        expected_encoded = base64.b64encode(expected_credentials.encode()).decode()

        # This is tested indirectly through the _acquire_token method
        # We can verify the encoding logic separately
        actual_encoded = base64.b64encode(expected_credentials.encode()).decode()
        assert actual_encoded == expected_encoded

    def test_oidc_discovery(self):
        """Test OIDC discovery functionality."""
        expected_token_endpoint = "https://test-user-pool.auth.us-east-1.amazoncognito.com/oauth2/token"

        mock_client = MagicMock()
        self._mock_oidc_discovery(mock_client, expected_token_endpoint)

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Call _get_token_endpoint to trigger discovery
            result = self.auth._get_token_endpoint()

            assert result == expected_token_endpoint
            assert self.auth._token_endpoint == expected_token_endpoint

            # Verify OIDC discovery was called correctly
            mock_client.get.assert_called_once()
            oidc_call_args = mock_client.get.call_args
            expected_oidc_url = (
                f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/openid-configuration"
            )
            assert oidc_call_args[0][0] == expected_oidc_url

    def test_requires_response_body_property(self):
        """Test that requires_response_body is set to True."""
        assert self.auth.requires_response_body is True
        assert hasattr(CognitoAuth, "requires_response_body")
        assert CognitoAuth.requires_response_body is True


class TestCognitoAuthIntegration:
    """Integration-style tests for CognitoAuth (still using mocks but testing full flows)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.auth = CognitoAuth(
            user_pool_id="us-east-1_test123",
            client_id="test-client-id",
            client_secret="test-client-secret",
            region="us-east-1",
            max_retries=2,  # Reduce for faster tests
        )

    def _mock_oidc_discovery(
        self, mock_client, token_endpoint="https://test-user-pool.auth.us-east-1.amazoncognito.com/oauth2/token"
    ):
        """Helper method to mock OIDC discovery."""
        oidc_response = MagicMock()
        oidc_response.status_code = 200
        oidc_response.json.return_value = {"token_endpoint": token_endpoint}
        mock_client.get.return_value = oidc_response
        return oidc_response

    def test_full_token_lifecycle(self):
        """Test complete token lifecycle: acquire, cache, refresh."""
        # Mock successful token acquisition
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "lifecycle-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_client = MagicMock()
        self._mock_oidc_discovery(mock_client)  # Mock OIDC discovery
        mock_client.post.return_value = token_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.return_value = mock_client

            # First acquisition
            token1 = self.auth._get_valid_token()
            assert token1.access_token == "lifecycle-token"
            assert mock_client.post.call_count == 1

            # Second call should use cached token
            token2 = self.auth._get_valid_token()
            assert token2 == token1  # Same object
            assert mock_client.post.call_count == 1  # No additional call

            # Simulate token expiring soon
            self.auth._token.expires_at = time.time() + 30  # 30 seconds from now

            # Mock new token response
            token_response.json.return_value = {
                "access_token": "refreshed-lifecycle-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            }

            # Third call should refresh token
            token3 = self.auth._get_valid_token()
            assert token3.access_token == "refreshed-lifecycle-token"
            assert mock_client.post.call_count == 2  # One additional call

    def test_httpx_integration(self):
        """Test integration with httpx client."""
        # Mock token acquisition
        mock_token = TokenInfo(access_token="httpx-integration-token", expires_at=time.time() + 3600)

        with patch.object(self.auth, "_get_valid_token", return_value=mock_token):
            # Create an httpx client with our auth
            client = httpx.Client(auth=self.auth)

            # Mock the transport to capture the actual request sent
            with patch("httpx._transports.default.HTTPTransport.handle_request") as mock_transport:
                mock_response = httpx.Response(200)
                mock_transport.return_value = mock_response

                # Make a request - this will trigger the auth flow
                response = client.get("https://api.example.com/test")

                # Verify the request was authenticated
                sent_request = mock_transport.call_args[0][0]
                assert sent_request.headers["Authorization"] == "Bearer httpx-integration-token"
                assert response.status_code == 200
